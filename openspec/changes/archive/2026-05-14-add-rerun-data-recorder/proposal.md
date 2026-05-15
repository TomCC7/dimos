## Why

Piper teleop demonstrations are currently written to disk as pickle-per-frame directories via `PiperDataRecorder` → `LegacyPickleStore`. The format is opaque, bloats fast, requires a separate (not in-tree) LeRobot conversion step to be usable for training, and shares no machinery with the live Rerun visualization that the operator already watches. Rerun 0.32 ships native robot-learning data collection primitives — multi-sink `RecordingStream`s, an on-demand chunk-stream `.rrd` format, `rerun.experimental.dataloader` (PyTorch dataset reading directly from `.rrd` with `window=(...)` action-chunk semantics, demonstrated by a LeRobot ACT training example shipped with the release), and a Dataset Review UI whose addressable row is one `.rrd` URI (`DatasetEntry.register([uris...])`, `table_grid_with_flags`). The right architecture is a dedicated `RerunDataRecorder` module — separate from the live-viewer bridge — that writes one `.rrd` per demonstration *episode*, calling the same factored-out converter logic as the bridge so what's recorded is structurally identical to what's displayed.

## What Changes

- **BREAKING** Retire `PiperDataRecorder` and the pickle-dir recording path for Piper teleop. Existing pickle recordings remain readable through `Memory2ReplayAdapter` / `LegacyPickleStore`; no in-place migration.
- Add a standalone `RerunDataRecorder` module (`dimos/visualization/rerun/recorder.py`) that owns its own `rr.RecordingStream` + `FileSink`, subscribes to the same LCM topics the bridge does, and writes one `.rrd` per demonstration episode. The bridge is **not** modified to gain recording behavior; it stays a live-viewer sink. The two modules are independent and orthogonal.
- Leave `dimos/visualization/rerun/bridge.py` **untouched**. The recorder reimplements the small composition logic (visual_override chaining and entity-path derivation) locally, importing only the already-module-level types (`RerunMulti`, `RerunData`, `RerunConvertible`, `is_rerun_multi`) that `bridge.py` already exposes. No bridge edit; PR review burden against the bridge is zero.
- Record **one episode per `.rrd` file**, where an episode is the addressable row in Rerun 0.32's Dataset Review UI. A teleop session contains many episodes; each episode is one `.rrd` URI the catalog server can list, filter, and flag.
- Add an in-session **recording toggle** RPC `RerunDataRecorder.toggle_recording()` that flips the recorder between RECORDING (an episode `.rrd` is open) and IDLE (no `.rrd` is open; messages on the bus are silently discarded by the recorder so the live viewer is unaffected). The operator presses the button to stop, gets the time they need to reset the scene, presses again to resume into the next episode. Empty `.rrd` files produced by a toggle-off-before-payload are deleted, so button bounce is harmless.
- Add a small `EpisodeBoundary` module (`dimos/teleop/quest/episode_boundary.py`) that subscribes to the existing `Buttons` LCM stream and calls `recorder.toggle_recording()` on a configured button edge, with a 500 ms debounce. Default button is `right_secondary` (B on the right controller) — **not** A, which is the press-and-hold teleop engage button (`TeleopIKTask` / `PinkTeleopTask`). Teleop semantics live in the teleop module; the recorder stays generic.
- Wire the data collection blueprint to instantiate `RerunDataRecorder` with `record_path_factory=default_episode_path_factory(...)` producing `{data_dir}/piper_data_collection/<session_ts>/episode_<NNN>.rrd`, adopt LeRobot-aligned entity paths on the recording side, and consume a single shared `piper_data_collection_rerun_config()` so the recorder and the live viewer cannot drift:
  - `/observation/camera/usb` (was `/piper_data_collection/color_image`)
  - `/observation/state/<joint_short_name>` (was `world/piper/measured/<joint>`)
  - `/action/<joint_short_name>` (was `world/piper/commanded/<joint>`)
  - `/meta/episode_id`, `/meta/episode_index`, `/meta/session_id`, `/meta/operator` (static, re-logged at the start of each new episode `.rrd`)
- Retarget the live viewer's preset blueprint to the new entity-path schema so the recorder and the viewer show the same paths. Live viewer behavior is otherwise unchanged.
- Document the post-session `rerun rrd optimize <episode.rrd>` step as the recommended way to convert raw frames into GoP-split, keyframe-marked recordings suitable for `rerun.experimental.dataloader`. No in-tree wrapper in this change.
- **Out of scope (deferred to follow-up changes):** `rr.server.Server(datasets={...})` catalog hub, in-tree LeRobot ACT training example, in-stream camera video encoding (`VideoStream` / `EncodedImage`), pickle-to-rrd migrator, recorder support for any non-Piper blueprint.

## Capabilities

### New Capabilities
<!-- None: extends an existing capability. -->

### Modified Capabilities
- `piper-data-collection`: Replaces the DimOS-native pickle recording path with per-episode `.rrd` files written through a standalone `RerunDataRecorder` module; renames recorded entity paths to a LeRobot-aligned schema; introduces in-session episode rollover semantics (one `.rrd` per episode, operator-driven boundary, empty-file discard); declares that the live visualization sink and on-disk recorder are independent DimOS modules that share only their converter utilities, replacing the prior "byte-identical recording with/without visualization" invariant with a structural "viewer and recorder are orthogonal sinks on the same source streams"; retires the requirement that recording be readable without LeRobot dependencies in favor of "recording is directly readable by `rerun.dataframe` / `rerun.experimental.dataloader`."

## Impact

- **Code:**
  - `dimos/visualization/rerun/recorder.py` *(new)*: `RerunDataRecorder` module + `Config` (`pubsubs`, `visual_override`, `entity_prefix`, `topic_to_entity`, `record_path_factory`, `recording_id_factory`, `episode_metadata`, `app_id`). Owns one `rr.RecordingStream` per episode and a `rotate_recording` RPC. Reimplements `_get_entity_path` and `_compose_converter` privately (~20 lines), importing types from `bridge.py`.
  - `dimos/visualization/rerun/bridge.py`: **unchanged**.
  - `dimos/teleop/quest/episode_boundary.py` *(new)*: `EpisodeBoundary` module subscribing to `Buttons` and dispatching to `recorder.rotate_recording()` with debounce.
  - `dimos/teleop/quest/blueprints.py`: drop the `PiperDataRecorder.blueprint()` atom; add `RerunDataRecorder.blueprint(...)` and `EpisodeBoundary.blueprint(...)` atoms; both consume the same `piper_data_collection_rerun_config()`.
  - `dimos/teleop/quest/data_collection.py`: deleted entirely (`PiperDataRecorder`, `PiperDataRecorderConfig`, `default_recording_name`). Helpers move to `data_collection_vis.py`.
  - `dimos/teleop/quest/data_collection_vis.py`: retarget `_ENTITY_PREFIX` to `/observation/state` / `/action`; add `default_session_name()`, `default_episode_path_factory()`, `default_recording_id_factory()`, `piper_episode_metadata()`.
  - Tests: new `test_recorder.py`, new `test_episode_boundary.py`; update `test_blueprints.py`, `test_data_collection_vis.py`; delete `test_data_collection.py`. Bridge tests are untouched (no bridge change to test).
- **Specs:** delta on `piper-data-collection` (this change).
- **Dependencies:** none new at collection time. `rerun-sdk` is already in `pyproject.toml` and is now pinned (or floats) to a release that supports independent `rr.RecordingStream`s (≥0.30; 0.32.0 is installed locally and verified). `rerun.experimental.dataloader` is a training-time concern, not a collection-time dependency.
- **Runtime:** new sessions write `.rrd` files under `{data_dir}/piper_data_collection/<session_ts>/episode_<NNN>.rrd`. With raw `rr.Image` frames at 640×480 @ 30 Hz a file grows ~30 MB/min uncompressed; operators are expected to run `rerun rrd optimize` post-session if storing long-term. The live viewer behaves as today. The pubsub bus carries one extra subscribe-all (recorder alongside bridge); per-message converter cost is paid in each module independently.
- **Migration:** old pickle datasets remain readable via existing `Memory2ReplayAdapter` / `LegacyPickleStore` paths. New data goes through Rerun's dataframe/dataloader path. No in-place migrator.
- **Sequencing:** depends on `add-data-collection-rerun-vis` landing first. That change introduces the `vis_module("rerun")` atom, the visual_override JointState→scalars helper, and the preset blueprint factory — all of which this change retargets to new entity paths and re-consumes from the recorder.
- **Backwards compatibility for the bridge:** the bridge gains no new config fields and no behavioral changes. Existing non-data-collection blueprints (`teleop_quest_rerun`, `demo_camera`, etc.) are unaffected; they continue to instantiate only `RerunBridgeModule`.
