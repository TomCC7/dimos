## Context

`RerunDataRecorder` (added in `add-rerun-data-recorder`) writes one `.rrd` file per teleop episode under `{data_dir}/piper_data_collection/<session_ts>/episode_<NNN>.rrd`, using a LeRobot-aligned entity-path schema (`/observation/camera/usb`, `/observation/state/<joint>`, `/action/<joint>`, `/meta/*`). Confirmed by `rerun_bindings.load_recording(...)` against a real session, the per-episode rrd exposes:

```
/observation/camera/usb              ← rr.Image (raw, RGB)
/observation/state/{joint1..6, gripper}  ← rr.Scalars (1-element)
/action/{joint1..6, gripper}             ← rr.Scalars (1-element)
/meta/{episode_id, episode_index, session_id}  ← static rr.TextDocument
+ incidental: /__properties, /camera_info, /coordinator/*, /world/tf/*
```

LeRobot v3.0 datasets (lerobot >= 0.5.x) are directory-shaped: `meta/info.json` (with `codebase_version: "v3.0"`), `meta/tasks.parquet`, `meta/stats.json`, `meta/episodes/chunk-000/file-000.parquet`, a single concatenated `data/chunk-000/file-000.parquet` for all frames across all episodes (with an `episode_index` column), and a single concatenated `videos/observation.images.<cam>/chunk-000/file-000.mp4` per camera. The LeRobot SDK exposes `LeRobotDataset.create(...)` / `add_frame(frame)` (with the task carried inside `frame["task"]`) / `save_episode()` as the supported writer. Doing this by hand is forward-incompatible.

Two consumers need the same per-robot schema knowledge: this offline converter, and (later) `PolicyNode` at inference time. The right abstraction is one `RobotContract` Protocol owned by the policy package, with a Piper concrete implementation. This change ships the contract + the offline consumer; the inference consumer comes later.

The recorded gripper scalar is a continuous position in robot units (Piper: `0.0` closed → `0.85` open, set in `dimos/control/blueprints/teleop.py`). Most LeRobot policies expect a binary gripper command. Binarization is configurable (default ON, threshold 0.7 fraction-open) so we can produce both forms from the same recordings.

## Goals / Non-Goals

**Goals:**

- One `RobotContract` Protocol, in `dimos.manipulation.policy.contract`, that fully describes the schema mapping for a robot: cameras, state/action joint ordering, gripper binarization, LeRobot `features()`, and an `from_rerun_row(row) -> LeRobot frame dict` translator. The same protocol declares inference-side methods (`from_messages`, `to_command`) that are unimplemented-but-defined on day one.
- A `PiperRobotContract` that codifies the Piper teleop schema verified against the real `episode_001.rrd` (six arm joints + gripper, single `usb` camera).
- A CLI converter `scripts/datasets/rrd_to_lerobot.py` that takes a session directory or a single `.rrd`, writes a LeRobot v2 dataset using the LeRobot SDK, and exposes gripper-binarization knobs as CLI flags overriding contract defaults.
- Frames are camera-rate gated; one `.rrd` becomes exactly one LeRobot episode; task description is supplied at conversion time.

**Non-Goals:**

- Wiring `RobotContract` into `PolicyNode` (deferred to the policy-node-abstraction change). The `from_messages` / `to_command` methods are part of the protocol but their tests live in the policy-node change, not here.
- A reverse converter (LeRobot → rrd) for evaluation playback.
- Multi-robot contracts beyond Piper. The registry is open for extension; no second concrete implementation lands here.
- Encoded video (`rr.VideoStream` / `rr.EncodedImage`) reading. Recorder writes raw `rr.Image` today and that's what we consume.
- Per-episode automatic task labeling. Task strings come from a CLI flag or a JSONL file the operator supplies.
- Modifying the recorder, the bridge, or any teleop blueprint.

## Decisions

### Decision 1 — `RobotContract` is a Protocol in the policy package, not the robot package

The contract lives at `dimos/manipulation/policy/contract.py` as a `typing.Protocol`. Concrete implementations live alongside at `dimos/manipulation/policy/contracts/<robot>.py` (e.g. `piper.py`).

Rationale:

- The contract is *policy-package property* — its job is to translate between robot-side data and a policy-framework-shaped dict. It is the shared boundary that both the converter and the future `PolicyNode` will speak through.
- Putting it in `dimos/robot/<robot>/policy_contract.py` would couple every robot model file to LeRobot framing decisions (binarization config, action-vector ordering, feature dict layout). That's reverse-direction coupling.
- Aligns with `dimos.manipulation.policy` chosen by the `policy-node-abstraction` change for `PolicyObservation` / `PolicyBackend` / `PolicyNode`. A single policy package = a single import root for policy concepts.

Alternatives considered:

- `dimos/robot/<robot>/policy_contract.py` (robot owns it): rejected for the coupling reason above.
- Generic `RobotContract` base class with subclasses: rejected in favor of `Protocol` because the contract is a structural interface, not an inheritance hierarchy — concrete classes do not share implementation, only shape. Protocol gives static checkers everything they need without forcing a base import.

### Decision 2 — Inference-side methods are on the protocol from day one, but unimplemented in concrete classes

The protocol declares `from_messages(images, state, action=None, task) -> LeRobotFrame` and `to_command(action_vec) -> JointState` from the start. `PiperRobotContract` either:

- (a) implements both methods now (small additional code, no runtime users this change), or
- (b) implements `from_messages` only; `to_command` raises `NotImplementedError("wired in policy-node-abstraction")`.

We pick **(a)**: implement both. Both are < 30 lines combined and share the joint-name ordering / gripper-rescaling logic with `from_rerun_row`. Implementing them now keeps the three translation paths in one place where they can share helpers; deferring would force a duplicate when the policy-node change lands.

Rationale:

- Single source of truth for joint-name ordering, gripper rescaling direction, and action-vector layout. If `from_rerun_row` and `from_messages` produce different shapes, the policy backend trained on offline data will silently misalign at inference.
- `to_command` is the inverse of binarization on the gripper slot — trivial to write and trivial to test in isolation.

Alternatives considered:

- Implement only `from_rerun_row` for this change: rejected because it forces the `policy-node-abstraction` change to re-derive joint ordering and gripper rescaling — guaranteed drift.
- Drop `from_messages` / `to_command` from the protocol entirely: rejected because the converter would not constrain the inference-time interface, defeating the "one contract, two consumers" goal.

### Decision 3 — Frame indexing: camera-gated latest-at on `log_time`

Use `rerun.dataframe.load_recording(path).view(index="log_time", contents=contract.rerun_entities()).filter_is_not_null("/observation/camera/usb")`. Each row in the resulting Arrow stream is one frame at the camera arrival time. Joint state and action scalars are filled by Rerun's built-in latest-at semantics on the same query (so a 100 Hz joint stream gets sampled to camera rate without an explicit resample).

Rationale:

- Camera is the slowest stream (~30 Hz vs joint ~100 Hz). Gating on it produces a natural target rate equal to the camera rate without inventing a fixed-frequency resampler.
- LeRobot frame indices and timestamps align cleanly with the camera frame index — the canonical thing to render in the dataset's mp4.
- Latest-at is what `rerun.dataframe` does by default for non-camera columns when joined to a different timeline; we don't fight it.

Alternatives considered:

- Fixed-rate resample (e.g. 30 Hz interpolated): rejected — interpolating joint commands across frames is unsafe (creates positions the operator never commanded) and the camera is already at the target rate.
- Index by joint state: rejected — would explode dataset size and force decimation of camera frames.
- Index by `frame_nr` (rerun's int sequence): rejected — `frame_nr` isn't logged by the recorder; `log_time` is the only timeline present.

### Decision 4 — Gripper binarization on action only, not state

The CLI defaults `--binarize-gripper` ON with `--gripper-threshold 0.7`. Binarization is applied to the gripper slot of the **action** vector only:

```
norm = (raw_action_gripper - closed_pos) / (open_pos - closed_pos)
binarized = 1.0 if norm > threshold else 0.0
```

The state vector's gripper slot keeps the raw position (rescaled to fraction-open in `[0, 1]` for unit consistency, but not thresholded).

Rationale:

- The model should *observe* the actual continuous gripper position so it can react to slip / mid-close states; thresholding the observation throws that signal away.
- The model should *emit* a discrete decision — most teleop demonstrators flick the trigger past the threshold and hold, so the underlying intent is binary even when the recorded value isn't.
- `to_command(action)` simply emits `open_pos` or `closed_pos` based on the binary slot — the inverse mapping is well-defined with no threshold needed.

Alternatives considered:

- Binarize state too: rejected for the observation-signal reason above.
- Hysteresis (separate open / close thresholds): deferred — adds two config knobs for marginal benefit until we see a real failure mode.
- Don't binarize at all: available via `--no-binarize-gripper`, but not the default — the LeRobot ecosystem and most policy backbones expect binary gripper.

### Decision 5 — One `.rrd` ↔ one LeRobot episode

The recorder already writes one episode per file. The converter mirrors that 1:1 — no segmentation, no merging. Episode order in the LeRobot dataset is `sorted(input_dir.glob("episode_*.rrd"))`.

Rationale:

- Episode boundaries are operator-driven and authoritative in the rrd — the file IS the episode. Re-segmenting risks losing or splitting an intentional demonstration.
- Trivially parallelizable later (per-rrd workers) without changing the format.

Alternatives considered:

- Read multi-episode rrds: rejected because the recorder doesn't produce them.
- Re-segment by activity / motion: rejected as out of scope and unsafe (would require labeling).

### Decision 6 — Use `LeRobotDataset.create()` / `add_frame()` / `save_episode()`

Write the dataset via the LeRobot SDK directly. The SDK is added as an **optional** dependency under the existing `manipulation` extra in `pyproject.toml`:

```toml
[project.optional-dependencies]
manipulation = [
    # ...existing manipulation deps...
    "lerobot>=0.5.1; python_version >= '3.12'",
]
```

LeRobot is grouped with `manipulation` rather than getting its own `datasets` extra because (a) it's logically a manipulation policy concern, and (b) lerobot already conflicts with the `perception` extra (lerobot needs `huggingface-hub>=1.0`, perception's transformers<4.54 needs `huggingface-hub<1.0`) — putting it in `manipulation` slots into the existing perception/manipulation conflict declared in `[tool.uv].conflicts` and avoids a parallel one-package extra.

Importing the converter without the extra raises a clear error pointing to `pip install dimos[manipulation]`. Core DimOS imports (`dimos.manipulation.policy.contract`, `dimos.manipulation.policy.contracts.piper`) must NOT import LeRobot — only the converter script does.

Rationale:

- Hand-rolling the v3.0 parquet/mp4 layout is forward-incompatible. Format details (chunk size, metadata schema, codec choice) change between LeRobot versions.
- The contract knows the *schema* (what features look like). The SDK knows the *encoding* (how to serialize them). Clean separation.
- LeRobot is a heavy dependency (torch, av, pillow); making it optional keeps the rest of DimOS lean.

Alternatives considered:

- Hand-write parquet via pyarrow + mp4 via ffmpeg: rejected — duplicates SDK work and bit-rots when LeRobot bumps its format version.
- Make LeRobot a hard dependency: rejected — only the converter script and the future LeRobot policy backend need it; the rest of DimOS does not.
- Write a generic intermediate format (HDF5/zarr) and convert separately: rejected as unnecessary indirection; LeRobot is the only consumer in scope.

### Decision 7 — Task description supplied at conversion time

Two CLI surfaces:

- `--task "<single string>"`: applies the same task to every episode in the session. This is the common case for teleop sessions where the operator was demonstrating one task.
- `--task-per-episode <path/to/jsonl>`: a JSONL file with `{"episode": "episode_001", "task": "..."}` lines, used when one session contains heterogeneous demonstrations.

Exactly one must be supplied (CLI validates). Task strings flow into LeRobot's `tasks.jsonl` via `save_episode(task=...)`.

Rationale:

- The recorder doesn't log a task description today, and adding `/meta/task` is a recorder change. Conversion-time labeling is the lowest-cost path that unblocks training.
- Per-episode JSONL handles the multi-task session case without forcing per-episode CLI invocations.
- A future change can add `/meta/task` to the recorder and have the converter prefer it over the CLI flag.

Alternatives considered:

- Read from `/meta/task`: not present today; would require recorder change + migration of existing data.
- Default to filename-derived task (`episode_001` → `"episode_001"`): rejected — meaningless training signal.
- Require per-episode JSONL always: rejected as friction for the common single-task case.

### Decision 8 — Registry shape mirrors the policy-node backend registry

`dimos.manipulation.policy.contracts.registry.get_contract(name: str) -> RobotContract` plus `register_contract(name, factory)`. Initial registration: `{"piper": PiperRobotContract}`.

Rationale:

- Mirrors the backend registry pattern in `policy-node-abstraction` (Decision 4 / Task 2.2 in that change). Same `register_X` / `get_X` convention everywhere in the policy package.
- Keeps `--contract <name>` on the CLI as a one-flag selector with clear errors when the name is unknown.

Alternatives considered:

- Importlib entry points: deferred until external robot packages need it.
- Eager class import in CLI: rejected — registry isolates the CLI from concrete implementations and lets future contracts register themselves at import time.

## Risks / Trade-offs

- **LeRobot SDK API drift** → Pin a minimum LeRobot version that has stable `LeRobotDataset.create()` / `save_episode()` signatures. Document the tested version range in the change README. CI smoke test exercises a tmp-dir round trip.
- **Gripper threshold tuning per-robot** → Mitigated by per-contract defaults (`PiperRobotContract.gripper_binarization.threshold = 0.7`) and a CLI override. If a robot's recorded distribution is bimodal at a different point, the contract's default changes once and the CLI keeps working.
- **Contract drift between converter and future PolicyNode** → Implement `from_rerun_row` and `from_messages` in the same class so they share helpers; cover both with the same `test_piper_contract.py` parametrization to fail fast when shapes diverge.
- **Camera-gated indexing drops joint frames between camera ticks** → Intentional. If a downstream policy needs higher action rate it should be trained on a different frame rate, which is a contract/config decision, not a converter bug.
- **Reading raw `rr.Image` is memory-hungry on long sessions** → Stream rows from `view().select()` rather than materializing the whole RecordBatch into Python; `add_frame` per row, never a list-comprehension over all frames.
- **LeRobot dataset on-disk format may change between versions** → Pin tested LeRobot version range; CI re-runs the round trip against each pin bump. The contract layer is unaffected — only the converter script touches LeRobot APIs.
- **Operator forgets `--task`** → CLI fails fast with a clear error before opening any rrd file. No silent dataset with empty tasks.
- **Empty / corrupt rrd files** → Recorder already deletes empty rrd files; the converter additionally `try/except` around each rrd and logs+skips with a clear warning, completing the rest of the session rather than aborting.
- **Multiple cameras in future Piper recordings** → `PiperRobotContract.cameras` is a `Mapping[str, ...]`; second camera entry is a one-line addition. Frame-key naming (`observation.images.<cam>`) follows LeRobot convention.

## Migration Plan

1. Add the `dimos.manipulation.policy` package, the `RobotContract` Protocol, the `LeRobotFrame` TypedDict, and the `GripperBinarization` dataclass. No external behavior change.
2. Add `PiperRobotContract` and the registry. Unit tests exercise `from_rerun_row` against a synthetic Arrow row, `from_messages` against synthetic `Image` + `JointState`, `to_command` round trip, and `features()` shape assertions.
3. Add the CLI converter. Integration test uses the `RerunDataRecorder` test fixtures to write a 2-episode rrd session into `tmp_path`, runs the converter, and asserts the LeRobot dataset directory has the expected files and one row per camera-tick per episode.
4. Add `lerobot>=0.5.1` to the existing `manipulation` extra in `pyproject.toml`. Document the install step in the new `docs/usage/datasets.md`.
5. Rollback: remove the script + the optional extra. The contract Protocol is harmless — even if a downstream change references it, removing only the converter doesn't break anything else (PolicyNode hasn't shipped yet).

## Open Questions

- Should the converter shell out to `rerun rrd optimize` first when the rrd is large, or assume the operator has already run it? Lean: assume already-optimized; document it in the docs page; no auto-optimize from the script.
- LeRobot dataset `repo_id` convention — auto-derive from session name (`piper/<session_ts>`) or require the operator to supply `--repo-id`? Lean: default to `piper/<session_ts>`, allow override.
- Where to put the docs page: extend `docs/usage/visualization.md` or add a fresh `docs/usage/datasets.md`? Lean: new file, since dataset conversion isn't a visualization concern.
