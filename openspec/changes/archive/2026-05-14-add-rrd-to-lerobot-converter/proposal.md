## Why

Per-episode `.rrd` files written by `RerunDataRecorder` are the source of truth for Piper teleop demonstrations, but they are not directly trainable: LeRobot policies expect a `LeRobotDataset` on disk (parquet frames + mp4 videos under a versioned directory). There is no in-tree converter today, the prior pickle path was retired, and LeRobot's gripper convention is binary (open/close) while DimOS records continuous gripper position in `[0.0, 0.85]`. We need a converter that bridges these formats, and a small *robot contract* abstraction so the rrd→frame translation lives in one place that a future `PolicyNode` can also use at inference time.

## What Changes

- Add a `RobotContract` Protocol in `dimos.manipulation.policy.contract` that owns the schema mapping between raw DimOS data and a LeRobot frame dict. The protocol declares cameras, state/action joint ordering, gripper binarization config, the LeRobot `features()` schema, and an `from_rerun_row()` translator. A future change wires the same contract into `PolicyNode` for inference (`from_messages()`/`to_command()`); the inference-side methods are part of the protocol from day one but are not exercised by this change.
- Add `PiperRobotContract` under `dimos.manipulation.policy.contracts.piper` implementing the protocol for the Piper teleop schema (six arm joints + gripper, single `usb` camera at `/observation/camera/usb`, gripper open=0.85 / closed=0.0).
- Add a small registry (`dimos.manipulation.policy.contracts.registry`) keyed by robot name (initially `"piper"`) so the CLI converter can resolve a contract by name.
- Add a CLI converter at `scripts/datasets/rrd_to_lerobot.py` that reads either a single `.rrd` or a session directory of `episode_*.rrd` files, translates each via the selected contract, and writes a `LeRobotDataset` v2 directory using the LeRobot SDK's `LeRobotDataset.create()` / `add_frame()` / `save_episode()` / `consolidate()` flow. One `.rrd` file = one LeRobot episode.
- Frame indexing: read `rerun.dataframe` views indexed by `log_time`, gated on camera-frame arrival (`filter_is_not_null("/observation/camera/usb")`) so the dataset rate equals the camera rate (~30 Hz). Joint state and action scalars are filled by Rerun's latest-at semantics on the same query.
- Gripper binarization (default ON, threshold 0.7): the converter normalizes the recorded `/action/gripper` scalar to fraction-open in `[0, 1]` (using contract-declared `gripper_open_pos`/`gripper_closed_pos`), thresholds to `1.0` when fraction > threshold else `0.0`, and writes that into the LeRobot action vector's gripper slot. State (`/observation/state/gripper`) is **not** binarized — the model still observes continuous gripper position. CLI flags `--no-binarize-gripper` and `--gripper-threshold <float>` override the contract defaults.
- Task description is supplied at conversion time via `--task <str>` (constant per session) or `--task-per-episode <path/to/jsonl>` (one entry per `episode_NNN`). Task strings live in the LeRobot dataset's `tasks.jsonl`; no `/meta/task` is read from the rrd in this change.
- LeRobot dataset output goes to `<output_dir>/<repo_id>/` (default `data/lerobot/<session_name>/`) at LeRobot dataset format version v2. Camera frames are encoded to mp4 by the SDK's default `save_episode()` path.
- Document the converter usage in `docs/usage/visualization.md` (or a new `docs/usage/datasets.md` if cleaner) with the canonical session-dir → dataset workflow and the post-`rerun rrd optimize` reminder.
- **Out of scope (deferred to follow-up changes):** policy-node integration that consumes the same contract at inference time; multi-robot contracts beyond Piper; in-stream `VideoStream`/`EncodedImage` reading; per-episode task labels generated automatically; reverse converter (LeRobot → rrd) for evaluation playback; in-tree LeRobot training script.

## Capabilities

### New Capabilities

- `robot-policy-contract`: Declares a `RobotContract` Protocol that maps a robot's raw observation/action streams to and from a LeRobot frame dict, plus a per-robot registry. Owns the canonical schema for cameras, state/action joint ordering, and gripper binarization. Used offline by the rrd→LeRobot converter and (in a later change) online by `PolicyNode`.
- `lerobot-dataset-conversion`: Provides a CLI tool that reads `.rrd` files written by `RerunDataRecorder` and produces a `LeRobotDataset` v2 directory by combining a `RobotContract`, the LeRobot SDK's dataset writer, and `rerun.dataframe` queries. Owns gripper binarization defaults, frame indexing strategy (camera-gated latest-at), and per-session/per-episode task labeling.

### Modified Capabilities

<!-- None: this change is additive. The recorder's on-disk format is unchanged; this consumes it. -->

## Impact

- **Code:**
  - `dimos/manipulation/policy/__init__.py` *(new)*: package marker; re-exports `RobotContract`.
  - `dimos/manipulation/policy/contract.py` *(new)*: `RobotContract` Protocol, `LeRobotFrame` TypedDict, `GripperBinarization` dataclass.
  - `dimos/manipulation/policy/contracts/__init__.py` *(new)*: registry exports.
  - `dimos/manipulation/policy/contracts/piper.py` *(new)*: `PiperRobotContract` concrete impl.
  - `dimos/manipulation/policy/contracts/registry.py` *(new)*: `get_contract(name) -> RobotContract` with `"piper"` registered.
  - `scripts/datasets/rrd_to_lerobot.py` *(new)*: CLI entrypoint (argparse), batch loop over rrd files, dataset writer.
  - Tests: `dimos/manipulation/policy/test_contract.py`, `dimos/manipulation/policy/test_piper_contract.py`, `dimos/manipulation/policy/test_rrd_to_lerobot.py` (uses recorder fixtures + tmp_path round-trip).
  - Docs: extend `docs/usage/visualization.md` with a "Convert recordings to LeRobot" section, or add `docs/usage/datasets.md` and cross-link.
- **Specs:** two new spec files (`robot-policy-contract`, `lerobot-dataset-conversion`).
- **Dependencies:**
  - Add `lerobot>=0.5.1` as an **optional** dependency in the existing `manipulation` extra in `pyproject.toml` (avoids creating a one-package extra; lerobot already conflicts with the `perception` extra so it slots into `manipulation` cleanly). Importing the converter without the extra installed should raise a clear error pointing to `pip install dimos[manipulation]`.
  - `rerun-sdk` already pinned ≥0.30; we use `rerun.dataframe.load_recording()` + `view().select()` which exists in 0.30+. No version bump.
  - No runtime dependency added to the recorder or to any non-converter code path.
- **Runtime:**
  - The converter is offline only — no live subscribers, no LCM traffic. It reads `.rrd` files from disk and writes a LeRobot dataset directory.
  - LeRobot mp4 encoding is CPU-bound; expect a session of ~5 minutes of 640×480@30Hz to take seconds-to-minutes to convert depending on `ffmpeg` availability.
- **Migration:** none. Existing `.rrd` files written under `data/piper_data_collection/<session>/` are consumed as-is; the recorder is unchanged.
- **Sequencing:** depends on `add-rerun-data-recorder` landing first (this change's tests use the recorder's fixtures and the `/observation/...`, `/action/...`, `/meta/...` entity-path schema that change introduces). The follow-up `policy-node-abstraction` change may later adopt `RobotContract` and shrink its own `PolicyNodeConfig` — that adoption is not a precondition for this change to land.
