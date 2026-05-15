## ADDED Requirements

### Requirement: CLI converter accepts a session directory or single rrd

The system SHALL provide a CLI script at `scripts/datasets/rrd_to_lerobot.py` whose `--input` argument accepts either:

- A directory containing one or more `episode_*.rrd` files, processed in `sorted(glob)` order. The directory's name is used as the default LeRobot `repo_id` suffix (e.g. session timestamp).
- A single `.rrd` file, processed as one episode.

The CLI SHALL fail fast with a clear error message when `--input` does not exist, contains no `.rrd` files (when a directory), or is not a `.rrd` file (when a file).

#### Scenario: Session directory expands to all episode files in sorted order

- **WHEN** `--input data/piper_data_collection/<session>/` is passed and the directory contains `episode_001.rrd`, `episode_002.rrd`, `episode_003.rrd`
- **THEN** the converter processes the three files in numeric order
- **AND** writes three episodes into the LeRobot dataset

#### Scenario: Single rrd file produces a one-episode dataset

- **WHEN** `--input data/.../episode_001.rrd` is passed
- **THEN** the converter writes a one-episode LeRobot dataset

#### Scenario: Missing input fails fast with a clear error

- **WHEN** `--input does/not/exist` is passed
- **THEN** the script exits with non-zero status before opening any output dataset
- **AND** the error message names the missing path

### Requirement: CLI selects a robot contract by name

The CLI SHALL accept `--contract <name>` (default `piper`) which is resolved through `dimos.manipulation.policy.contracts.registry.get_contract(name)`.

When the name is unknown, the CLI SHALL print the available contract names and exit non-zero.

#### Scenario: Default contract is piper

- **WHEN** `--contract` is omitted
- **THEN** the converter uses `get_contract("piper")`

#### Scenario: Unknown contract name fails with the available list

- **WHEN** `--contract not-a-robot` is passed
- **THEN** the script exits non-zero
- **AND** stderr lists the available contract names registered in the registry

### Requirement: Gripper binarization defaults to ON with threshold 0.7 and is overridable per invocation

The CLI SHALL expose:

- `--binarize-gripper` / `--no-binarize-gripper` — toggles `GripperBinarization.enabled`. Default `--binarize-gripper`.
- `--gripper-threshold <float in [0, 1]>` — overrides `GripperBinarization.threshold`. Defaults to the contract's declared threshold.

These flags SHALL produce a copy of the contract's `gripper_binarization` with the requested overrides; the contract itself SHALL NOT be mutated.

The threshold SHALL be validated to lie in `[0.0, 1.0]` inclusive; values outside this range fail fast with a clear error before any rrd is opened.

#### Scenario: Default invocation binarizes gripper at 0.7

- **WHEN** the CLI is invoked without gripper flags
- **THEN** the resulting frames have `frame["action"][gripper_slot] in {0.0, 1.0}` (binarized)
- **AND** the threshold used was `0.7` (Piper contract default)

#### Scenario: --no-binarize-gripper preserves raw gripper position in action

- **WHEN** `--no-binarize-gripper` is passed
- **THEN** every `frame["action"][gripper_slot]` matches the raw recorded `/action/gripper` value (allowing float precision)
- **AND** every `frame["observation.state"][gripper_slot]` also matches the raw recorded value (no rescaling applied)

#### Scenario: --gripper-threshold overrides the contract default

- **WHEN** `--gripper-threshold 0.5` is passed
- **AND** a recorded gripper sample normalizes to fraction-open `0.6`
- **THEN** `frame["action"][gripper_slot] == 1.0`

#### Scenario: Threshold outside [0, 1] fails fast

- **WHEN** `--gripper-threshold 1.5` is passed
- **THEN** the script exits non-zero before opening any rrd file
- **AND** the error message names the valid range

### Requirement: Task description is required and supplied at conversion time

The CLI SHALL accept exactly one of:

- `--task "<single string>"` — applied to every episode.
- `--task-per-episode <path/to/file.jsonl>` — JSONL file with one `{"episode": "<filename_stem>", "task": "<description>"}` object per line. The episode names in the file SHALL match the rrd file stems (e.g. `"episode_001"` for `episode_001.rrd`).

The CLI SHALL fail fast with a clear error when:

- Neither flag is provided.
- Both flags are provided.
- `--task-per-episode` references a file that does not exist or contains malformed JSON.
- `--task-per-episode` is used and one or more processed rrd files have no entry in the JSONL.

Task strings SHALL be passed to `LeRobotDataset.save_episode(task=...)` so they appear in the dataset's `tasks.jsonl`.

#### Scenario: --task applies one task to every episode

- **WHEN** `--task "pick the red block"` is passed with a 3-episode session
- **THEN** all three episodes in the resulting LeRobot dataset have task `"pick the red block"`

#### Scenario: --task-per-episode reads per-episode JSONL

- **WHEN** `--task-per-episode tasks.jsonl` is passed and the file contains:
  ```
  {"episode": "episode_001", "task": "pick"}
  {"episode": "episode_002", "task": "place"}
  ```
- **AND** the input contains exactly `episode_001.rrd` and `episode_002.rrd`
- **THEN** the resulting dataset has `episode_001` tagged `"pick"` and `episode_002` tagged `"place"`

#### Scenario: Missing both task flags fails fast

- **WHEN** neither `--task` nor `--task-per-episode` is provided
- **THEN** the script exits non-zero before opening any rrd
- **AND** the error message names both flags

#### Scenario: --task-per-episode missing an entry for a processed rrd fails fast

- **WHEN** `--task-per-episode tasks.jsonl` contains only `episode_001` but the input directory has `episode_001.rrd` and `episode_002.rrd`
- **THEN** the script exits non-zero before writing any dataset frames
- **AND** the error names the missing episode stem

### Requirement: Frames are camera-rate gated via Rerun chunk-based latest-at lookups

The converter SHALL read each rrd via `rerun.experimental.RrdReader(path).store().stream()` (rerun-sdk >= 0.32). For each entity path declared by `contract.rerun_entities()`, the converter SHALL collect every chunk's per-row `(log_time_ns, value)` pairs into a single sorted series.

For each camera arrival timestamp `t_cam`, the converter SHALL produce one frame whose scalar slots come from a binary-search `latest-at` lookup on each scalar series (largest log_time ≤ `t_cam`). Frames whose required scalar slots have no preceding sample SHALL be skipped (not emitted with NaN/zero placeholders).

The converter SHALL emit frames one at a time to `dataset.add_frame(frame)` rather than buffering all frames in memory before writing.

#### Scenario: Output frame count equals camera frame count per episode

- **WHEN** an rrd is recorded with N camera frames and ~3N joint-state samples
- **THEN** the resulting LeRobot episode has exactly N frames
- **AND** each frame's joint state and action values come from the most-recent samples preceding that camera tick

#### Scenario: A frame is skipped when no joint state has yet arrived

- **WHEN** the first camera frame in an rrd is logged before any joint-state sample
- **THEN** that camera frame is skipped (the converter does not emit a partial frame with NaN state)
- **AND** the skip is logged at INFO level naming the rrd file

### Requirement: One rrd file maps to exactly one LeRobot episode

The converter SHALL treat each rrd file as one LeRobot episode, calling `dataset.save_episode()` once per rrd processed.

The converter SHALL NOT split, merge, or re-segment episodes.

#### Scenario: Two rrd files produce two LeRobot episodes

- **WHEN** the input directory contains `episode_001.rrd` and `episode_002.rrd`
- **THEN** the resulting LeRobot dataset reports `total_episodes == 2` in `meta/info.json`
- **AND** the per-frame `episode_index` column ranges over exactly `{0, 1}` (LeRobot's 0-indexed convention)

### Requirement: Output is a LeRobotDataset v3.0 directory written via the LeRobot SDK

The converter SHALL write its output via `LeRobotDataset.create(repo_id=..., fps=..., features=contract.features(), root=<output_dir>)`, then for each frame call `dataset.add_frame(frame)` (with the task description carried inside the frame dict as `frame["task"]`), then `dataset.save_episode()` per rrd processed.

The CLI SHALL accept:

- `--output <dir>` (default `data/lerobot/<input_dir_name>/`) — LeRobot dataset root.
- `--repo-id <str>` (default `<contract_name>/<input_dir_name>`) — LeRobot dataset repo id.
- `--fps <int>` (default `30`) — frame rate stamped into the dataset's `info.json` and used for video encoding.

The converter SHALL NOT hand-write parquet or mp4 files. All on-disk format details are owned by the LeRobot SDK.

The output directory SHALL conform to the LeRobot v3.0 dataset layout: a single concatenated parquet at `data/chunk-000/file-000.parquet` containing every frame across all episodes (with `episode_index`, `frame_index`, `index`, `task_index`, plus the contract-declared features as columns), per-camera concatenated mp4s at `videos/observation.images.<cam>/chunk-000/file-000.mp4`, per-episode metadata at `meta/episodes/chunk-000/file-000.parquet`, the task table at `meta/tasks.parquet`, dataset stats at `meta/stats.json`, and the dataset descriptor at `meta/info.json` (which reports `codebase_version: v3.0`).

#### Scenario: Output directory contains LeRobot v3.0 layout

- **WHEN** the converter completes a 2-episode session run
- **THEN** `meta/info.json` exists and reports `codebase_version: "v3.0"` and `total_episodes: 2`
- **AND** `data/chunk-000/file-000.parquet` exists and contains rows for both episodes (distinguished by `episode_index`)
- **AND** `meta/tasks.parquet` exists and contains at least one task entry
- **AND** `meta/episodes/chunk-000/file-000.parquet` exists and contains 2 episode rows
- **AND** `videos/observation.images.usb/chunk-000/file-000.mp4` exists

#### Scenario: Default repo_id derives from contract and input directory

- **WHEN** `--input data/piper_data_collection/20260514T210114Z/` is passed without `--repo-id`
- **AND** `--contract piper` is used (default)
- **THEN** the resulting dataset's `repo_id` is `piper/20260514T210114Z`

### Requirement: LeRobot is an optional dependency under the manipulation extra

The `lerobot` package SHALL be declared as an optional dependency in `pyproject.toml` under the `manipulation` extra (e.g. `pip install dimos[manipulation]`).

The CLI script SHALL import `lerobot` lazily inside its entrypoint and produce a clear error message naming the install command when the import fails.

The contract package modules (`dimos.manipulation.policy.contract`, `dimos.manipulation.policy.contracts.piper`, `dimos.manipulation.policy.contracts.registry`) SHALL NOT import `lerobot` — they remain importable in environments without the extra installed.

#### Scenario: Running the CLI without lerobot installed fails with an install hint

- **WHEN** `python scripts/datasets/rrd_to_lerobot.py ...` is run in an environment where `lerobot` is not importable
- **THEN** the script exits non-zero
- **AND** stderr contains the string `pip install dimos[manipulation]` (or equivalent install hint)

#### Scenario: Contract package imports without lerobot

- **WHEN** `lerobot` is not installed
- **AND** a developer imports `dimos.manipulation.policy.contract` and `dimos.manipulation.policy.contracts.piper`
- **THEN** both imports succeed without error

### Requirement: Empty or unreadable rrd files are skipped with a logged warning

When the converter encounters an rrd file that is empty, contains no `/observation/camera/usb` rows, or fails to load via `rerun.dataframe.load_recording`, the converter SHALL:

- Log a `WARNING`-level message naming the file and the failure reason.
- Skip that file without aborting the run.
- Continue processing remaining rrd files.
- Exit non-zero only if every input rrd was skipped (i.e. zero episodes were written).

#### Scenario: Empty rrd in a session is skipped, others continue

- **WHEN** the input directory contains `episode_001.rrd` (valid), `episode_002.rrd` (empty), `episode_003.rrd` (valid)
- **THEN** the resulting LeRobot dataset has 2 episodes (from `001` and `003`)
- **AND** a WARNING about `episode_002.rrd` was logged
- **AND** the script exits with status 0

#### Scenario: All rrd files invalid causes non-zero exit

- **WHEN** every rrd in the input is empty or unreadable
- **THEN** the script exits non-zero
- **AND** the error message names how many rrd files were attempted and how many succeeded
