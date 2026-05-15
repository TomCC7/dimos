## 1. Policy package scaffold and core types

- [x] 1.1 Create `dimos/manipulation/policy/__init__.py` re-exporting `RobotContract`, `LeRobotFrame`, `GripperBinarization`. *(Deviation: not created. The dimos project uses namespace packages — only `dimos/__init__.py` exists. Users import directly from `dimos.manipulation.policy.contract`. Re-export adds no value here.)*
- [x] 1.2 Create `dimos/manipulation/policy/contract.py` with the `RobotContract` `typing.Protocol` (`@runtime_checkable`), the `LeRobotFrame` `TypedDict`, and the `GripperBinarization` dataclass (defaults: `enabled=True`, `threshold=0.7`; `open_pos` and `closed_pos` required).
- [x] 1.3 Verify the three modules import in an environment without `lerobot` installed (no top-level `import lerobot`). *(Verified live: `'lerobot' in sys.modules` is False after importing all three.)*

## 2. Piper contract

- [x] 2.1 Create `dimos/manipulation/policy/contracts/__init__.py` (empty package marker). *(Deviation: not created — namespace package convention.)*
- [x] 2.2 Create `dimos/manipulation/policy/contracts/piper.py` with `PiperRobotContract`, deriving `state_joint_names` / `action_joint_names` from `dimos.teleop.quest.data_collection_vis.piper_data_collection_joint_short_names()` (single source of truth — no duplicated literals).
- [x] 2.3 Implement `PiperRobotContract.features()` returning a plain `dict[str, dict]` describing `observation.images.usb` (uint8, `(480, 640, 3)`), `observation.state` (float32, `(7,)`), `action` (float32, `(7,)`), with shape/dtype/kind keys but NO `lerobot` imports.
- [x] 2.4 Implement `PiperRobotContract.rerun_entities()` returning the seven `/observation/state/<joint>`, seven `/action/<joint>`, plus `/observation/camera/usb` paths.
- [x] 2.5 Implement `PiperRobotContract.from_rerun_row(row)` reading the listed entity paths from an Arrow row, packing state/action vectors in `state_joint_names` order, applying gripper binarization to the action slot only when enabled (state slot is rescaled to fraction-open without thresholding), preserving raw units when binarization is disabled. *(Refinement: the contract receives a pre-extracted `Mapping[str, Any]` per row keyed by entity path; the CLI converter does the Arrow→dict extraction. This keeps the contract version-independent across rerun-sdk releases and trivially testable without rerun installed.)*
- [x] 2.6 Implement `PiperRobotContract.from_messages(images, state, *, action=None, task="")` returning a frame dict with the exact same keys, dtypes, and shapes as `from_rerun_row` (omitting `"action"` when `action is None`); raise `KeyError` naming missing cameras or joints.
- [x] 2.7 Implement `PiperRobotContract.to_command(action_vec)` returning a `JointState` with `name=["arm/joint1", ..., "arm/joint6", "arm/gripper"]` and the gripper slot mapped from `{0.0, 1.0}` back to `{closed_pos, open_pos}` when binarization is enabled; raise `ValueError` when shape is not `(7,)`.

## 3. Contract registry

- [x] 3.1 Create `dimos/manipulation/policy/contracts/registry.py` exposing `register_contract`, `get_contract`, `available_contracts`.
- [x] 3.2 Register `"piper" -> PiperRobotContract` at module import time.
- [x] 3.3 `get_contract` raises `KeyError` listing the available names when called with an unknown name.

## 4. CLI converter

- [x] 4.1 Create `scripts/datasets/__init__.py` and `scripts/datasets/rrd_to_lerobot.py` with an `argparse`-based CLI (no `click` dependency added). *(Deviation: no `__init__.py` — `scripts/` is a script directory, not a package. The CLI is invoked as `python scripts/datasets/rrd_to_lerobot.py`.)*
- [x] 4.2 Define CLI flags: `--input` (required, file or dir), `--output` (default `data/lerobot/<input_dir_name>/`), `--repo-id` (default `<contract_name>/<input_dir_name>`), `--contract` (default `piper`), `--fps` (default `30`), `--binarize-gripper` / `--no-binarize-gripper` (default ON), `--gripper-threshold <float>` (default contract value, validated `[0.0, 1.0]`), `--task <str>` and `--task-per-episode <path>` (mutually exclusive, exactly one required).
- [x] 4.3 Validate inputs upfront (file/dir exists, contains `.rrd` files, gripper threshold range, exactly-one task flag, JSONL parse succeeds and covers every input rrd) before opening any output dataset; fail fast with clear errors naming the offending input.
- [x] 4.4 Lazy-import `lerobot` inside `main()`; on `ImportError` print `pip install dimos[manipulation]` and exit non-zero. *(Verified live: smoke run against real `episode_001.rrd` exits with code 2 and the install hint when lerobot is missing.)*
- [x] 4.5 Resolve the contract via `get_contract(args.contract)`; produce a per-invocation copy of `gripper_binarization` with CLI overrides applied; do NOT mutate the registered contract instance.
- [x] 4.6 For each rrd file in sorted order: open with `rerun.dataframe.load_recording(path)`, build the `view(index="log_time", contents=contract.rerun_entities()).filter_is_not_null("/observation/camera/usb")`, stream rows via `view().select()`, call `contract.from_rerun_row(row)` per row, call `dataset.add_frame(frame)` per row (do NOT materialize all rows in memory), then `dataset.save_episode(task=resolved_task)`. Resolved task comes from `--task` (constant) or `--task-per-episode` lookup keyed by the rrd file stem. *(Adjustment: `dataset.add_frame(frame, task=...)` per call rather than `save_episode(task=...)`, which matches the LeRobotDataset v2 SDK signature.)*
- [x] 4.7 Skip empty / unreadable / camera-frame-less rrd files with a `WARNING` log naming the file; continue with the rest of the session; exit non-zero only if zero episodes were written.
- [x] 4.8 Skip the first camera frame(s) when no joint state has yet arrived (avoid emitting partial frames with NaN state); log the skip at INFO level.
- [x] 4.9 Call `dataset.consolidate()` once after the loop completes. *(Guarded by `getattr` since some LeRobot releases have removed `consolidate()` in favor of implicit consolidation per `save_episode`.)*

## 5. Dependencies and packaging

- [x] 5.1 Add `lerobot>=<min-version>` to `pyproject.toml` under `[project.optional-dependencies] datasets = [...]`. Pick the minimum version that exposes `LeRobotDataset.create()`/`add_frame()`/`save_episode()`/`consolidate()` and v2 features schema. *(Adjustment: pinned `lerobot>=0.5.1; python_version >= '3.12'` inside the existing `manipulation` extra — not a standalone `datasets` extra. lerobot 0.5.x conflicts with the `perception` extra (huggingface-hub<1 vs >=1), so it slots into the existing perception/manipulation conflict declared in `[tool.uv].conflicts`. Output dataset is now LeRobotDataset v3.0 (lerobot 0.5.1's format).)*
- [x] 5.2 Add a brief comment in `pyproject.toml` explaining the `datasets` extra is for the rrd → LeRobot converter only. *(Folded into the `manipulation` extra; comment lives in `pyproject.toml` next to the `manipulation` entries.)*
- [x] 5.3 Verify no other DimOS module gains a transitive dependency on `lerobot` (run `python -c "import dimos"` against an environment without the extra installed). *(Verified: importing `dimos`, `dimos.manipulation.policy.contract`, `dimos.manipulation.policy.contracts.piper`, and `dimos.manipulation.policy.contracts.registry` leaves `'lerobot' in sys.modules` False.)*

## 6. Tests

- [x] 6.1 Create `dimos/manipulation/policy/test_contract.py` covering: `RobotContract` is `runtime_checkable`; a structural class (no inheritance) with all members satisfies `isinstance`; `LeRobotFrame` keys; `GripperBinarization` defaults; threshold-on-the-open-side exclusivity at the boundary. *(5 tests passing.)*
- [x] 6.2 Create `dimos/manipulation/policy/test_piper_contract.py` covering: joint ordering matches `piper_data_collection_joint_short_names()`; `features()` shape; `from_rerun_row` packs state/action in order; binarization above / at / below threshold (default `0.7`); `--no-binarize-gripper` equivalent (`enabled=False`) preserves raw units in BOTH state and action; `from_messages` produces identical keys/shapes/dtypes to `from_rerun_row` for equivalent synthetic input; `from_messages(action=None)` omits the `"action"` key; `from_messages` raises `KeyError` for missing cameras and missing joints; `to_command` round trip for binarized and non-binarized inputs; `to_command` raises `ValueError` on wrong vector length. *(17 tests passing.)*
- [x] 6.3 Create `dimos/manipulation/policy/test_contracts_registry.py` covering: `"piper"` is registered by default; `get_contract("piper")` returns a `PiperRobotContract`; `available_contracts()` includes `"piper"`; unknown name raises `KeyError` listing available names. *(4 tests passing.)*
- [x] 6.4 Create `scripts/datasets/test_rrd_to_lerobot.py` (integration) using `dimos.teleop.quest.test_data_collection_integration._FakePubSub` / `_drive_session` patterns to write a real 2-episode rrd session into `tmp_path`, run the converter (subprocess or `main()` call), and assert the LeRobot dataset directory has the expected v2 layout (`info.json`, `meta/episodes.jsonl` with 2 entries, `tasks.jsonl`, `data/chunk-000/episode_000000.parquet` and `episode_000001.parquet`, `videos/.../episode_000000.mp4` and `episode_000001.mp4`). Skip the test when `lerobot` is not importable (pytest marker). *(Deviation: lives at `dimos/manipulation/policy/test_rrd_to_lerobot_integration.py` so pytest's `testpaths = ["dimos"]` discovers it. Skips cleanly when `lerobot` or `rerun.dataframe` is not importable.)*
- [x] 6.5 Add CLI input-validation tests (no rrd needed): missing `--task` flags fails fast; both task flags fails fast; `--gripper-threshold 1.5` fails fast; missing `--input` path fails fast; `--task-per-episode` JSONL missing an entry fails fast. *(15 tests in `test_rrd_to_lerobot_cli.py` passing.)*
- [x] 6.6 Add the empty-rrd integration test: a 3-episode session where episode 2 is force-emptied (truncated/no payload); assert dataset has 2 episodes, WARNING was logged, exit status 0. *(`test_empty_rrd_in_session_is_skipped_with_warning` in the integration file — runs when the `manipulation` extra is installed and rerun-sdk>=0.32 is available.)*

## 7. Documentation

- [x] 7.1 Add a `docs/usage/datasets.md` page documenting the converter: install `pip install dimos[manipulation]`; CLI usage examples (single rrd, session dir, per-episode tasks, gripper binarization toggle); recommended `rerun rrd optimize` step before conversion; LeRobot v3.0 dataset layout produced.
- [x] 7.2 Cross-link `docs/usage/visualization.md` (which already covers the recorder) to `docs/usage/datasets.md` from the "What's next after recording?" section. *(Linked from the existing "Reading recordings for training" section.)*
- [x] 7.3 Document the gripper binarization defaults (`threshold=0.7` fraction-open; applies to action only; state stays continuous) and how to override.

## 8. Verification

- [x] 8.1 Run `pytest dimos/manipulation/policy/ scripts/datasets/` and confirm all new tests pass. *(41 passed, 1 skipped — the one skip is the lerobot integration test which requires the `datasets` extra not installed in this environment.)*
- [x] 8.2 Run the converter manually against `data/piper_data_collection/20260514T210114Z/episode_001.rrd` and confirm the output dataset opens cleanly via `LeRobotDataset(repo_id, root=...)` and yields one episode with the expected feature shapes. *(Verified end-to-end against `data/piper_data_collection/20260514T223348Z/` — 4 episodes, 325 frames, codebase_version v3.0, gripper action correctly binarized to {0.0, 1.0} and gripper state continuous in fraction-open units.)*
- [x] 8.3 Run type diagnostics (`pyright` or project-standard) on changed files and confirm zero new errors. *(`mypy` on the four production files: success, no issues found.)*
- [x] 8.4 Run `openspec validate add-rrd-to-lerobot-converter` and confirm the change is well-formed. *(`Change 'add-rrd-to-lerobot-converter' is valid`.)*
