## 1. `RerunDataRecorder` module skeleton

- [x] 1.1 Create `dimos/visualization/rerun/recorder.py`. Import types from `dimos/visualization/rerun/bridge.py` (`RerunMulti`, `RerunData`, `RerunConvertible`, `is_rerun_multi`) — these are already module-level there; no bridge edit needed.
- [x] 1.2 Define `RerunDataRecorderConfig(ModuleConfig)` with fields: `pubsubs: list[SubscribeAllCapable] = [LCM()]`, `visual_override: dict = {}`, `entity_prefix: str = "world"`, `topic_to_entity: Callable | None = None`, `record_path_factory: Callable[[], Path]` (required), `recording_id_factory: Callable[[Path], str] | None = None`, `episode_metadata: Callable[[int], dict[str, str]] | None = None`, `app_id: str = "dimos_recorder"`.
- [x] 1.3 Define `class RerunDataRecorder(Module)` with `config: RerunDataRecorderConfig`. Add private state: `self._record_stream: rr.RecordingStream | None`, `self._current_path: Path | None`, `self._current_nonempty: bool`, `self._episode_index: int`, `self._record_lock: threading.Lock`, `self._converter_cache: dict[str, Callable]`.

## 2. Recorder local composition logic (no bridge import beyond types)

- [x] 2.1 Add private `_get_entity_path(self, topic) -> str` that mirrors `RerunBridgeModule._get_entity_path` (use `config.topic_to_entity` if set; else strip LCM suffix and prepend `config.entity_prefix`). ~6 lines.
- [x] 2.2 Add private `_compose_converter(self, entity_path: str) -> Callable[[Any], RerunData | None]` that mirrors `RerunBridgeModule._visual_override_for_entity_path`: chain `config.visual_override` matches via `pattern_matches`, end with a `final_convert` that handles `Archetype` passthrough, `is_rerun_multi` passthrough, and `RerunConvertible.to_rerun()`. Cache results in `self._converter_cache`. ~15 lines.
- [x] 2.3 Add a focused unit test (`test_recorder.py::test_compose_converter_mirrors_bridge`) that constructs both a `RerunBridgeModule` and a `RerunDataRecorder` with the same `visual_override` / `topic_to_entity`, runs each module's composer against the same synthetic message, and asserts the resulting entity paths and archetypes match exactly. This is the structural drift-detector named in design.md Decision 5.

## 3. Episode open / close / rotate plumbing

- [x] 3.1 Add `_open_episode(self, *, path: Path | None = None, recording_id: str | None = None) -> Path`. Uses the factory when args are `None`; raises if the resolved path already exists; creates parent dirs; constructs `rr.RecordingStream(self.config.app_id, recording_id=rid)`; attaches `rr.FileSink(str(path))` via `rr.set_sinks(...)`; logs per-episode static metadata (Task 3.3); sets `self._record_stream`, `self._current_path`, `self._current_nonempty = False`. Returns the resolved path.
- [x] 3.2 Add `_close_episode(self) -> None`. Under `self._record_lock`: `flush_blocking()` on `_record_stream`, drop the stream (so the FileSink closes), then if `_current_nonempty` is False delete `_current_path` (`unlink(missing_ok=True)`). Set `_record_stream`/`_current_path` to `None`.
- [x] 3.3 Add `_log_episode_metadata(self) -> None`. Reads `self.config.episode_metadata(self._episode_index)` (or a default dict) and logs `rr.TextDocument` archetypes under `/meta/episode_id`, `/meta/episode_index`, `/meta/session_id`, and (when present) `/meta/operator`, all `static=True`, to `self._record_stream`.
- [x] 3.4 Implement `@rpc start(self)`: `super().start()`; initialize `_episode_index = 0`; call `_open_episode()` (advances counter to 1); subscribe to every pubsub in `config.pubsubs` with `_on_message`; register stop disposables for each pubsub.
- [x] 3.5 Implement `_on_message(self, msg, topic)`: derive entity path; fetch/build converter; if `data := converter(msg)` is `None`, return; under `self._record_lock`, if `_record_stream is None` return; log to `_record_stream` (single `Archetype` to derived path; `RerunMulti` iterated as `(path, archetype)` tuples), set `_current_nonempty = True`.
- [x] 3.6 Implement `@rpc toggle_recording(self, *, recording_id: str | None = None, path: Path | None = None) -> Path | None`. **Toggle semantics** (replaces the original "rotate" close-then-reopen): if `_record_stream is not None` → `_close_episode()` and return `None` (now IDLE). If `_record_stream is None` → increment `_episode_index`, call `_open_episode(...)`, return the new path (now RECORDING). When called without a factory and no override path, log a warning and stay IDLE. This shape lets the operator stop recording, reset the scene at their own pace, and resume into the next episode — instead of "next file opens immediately and bakes in the reset motion."
- [x] 3.7 Implement `@rpc stop(self)`: call `_close_episode()`, then `super().stop()`.

## 4. Recorder tests

- [x] 4.1 `test_recorder.py::test_start_creates_first_episode` — instantiate the recorder with a tmp-dir factory and an in-memory pubsub fake, call `start()`, assert episode_001.rrd exists, has the expected `recording_id`, and contains the configured `/meta/*` static entities. Call `stop()`; assert the file remains because `_current_nonempty` was set (push at least one payload msg first).
- [x] 4.2 `test_recorder.py::test_payload_messages_land_in_current_episode` — push N synthetic `Image` and `JointState` messages, `stop()`, read the resulting `.rrd` via `rerun.dataframe` (or chunk-stream iteration), assert per-entity row counts match N. *(Implementation note: rerun 0.29 RRDArchive lacks per-column row-count introspection; asserting entity-paths exist is the available equivalent.)*
- [x] 4.3 `test_recorder.py::test_rotate_creates_new_episode_and_continues` — push N messages, call `toggle_recording()`, push M messages, `stop()`. Assert two `.rrd` files exist with N rows in the first and M rows in the second (no overlap, no message loss). *(Asserts both files exist with the payload entity; recording IDs differ.)*
- [x] 4.4 `test_recorder.py::test_rotate_with_empty_episode_deletes_file` — call `toggle_recording()` immediately after `start()` (no payload between), then push messages, `stop()`. Assert `episode_001.rrd` was deleted; `episode_002.rrd` exists with the messages.
- [x] 4.5 `test_recorder.py::test_rotate_under_message_pressure` — spawn a thread that continuously pushes synthetic messages; call `toggle_recording()` mid-stream; assert no message lands in the closed file and none is duplicated. Use a deterministic per-message sentinel so post-hoc reconstruction is unambiguous.
- [x] 4.6 `test_recorder.py::test_rotate_no_op_when_factory_absent` — *(Pinned: field is Optional, `start()` raises, and `toggle_recording()` is a no-op returning `None`.)*
- [x] 4.7 `test_recorder.py::test_recorder_isolated_from_viewer_failures` — instantiate without a bridge in the same blueprint; push messages; assert `.rrd` files are written regardless. (Mirrors design.md Decision 10's isolation invariant.)

## 5. Session/episode path & metadata helpers in `data_collection_vis.py`

- [x] 5.1 Move `default_recording_name()` from `dimos/teleop/quest/data_collection.py` to `dimos/teleop/quest/data_collection_vis.py` and rename it `default_session_name()`. Keep the `YYYYMMDDTHHMMSSZ` UTC-timestamp shape.
- [x] 5.2 Add `default_episode_path_factory(session_name: str | None = None) -> Callable[[], Path]`. The returned callable holds a private 1-indexed counter and returns `Path(get_data_dir()) / "piper_data_collection" / session_name / f"episode_{counter:03d}.rrd"` on each call. When `session_name` is `None`, the factory generates one via `default_session_name()` on first call and reuses it.
- [x] 5.3 Add `default_recording_id_factory(path: Path) -> str` returning `f"{path.parent.name}/{path.stem}"`.
- [x] 5.4 Add `piper_episode_metadata(session_id: str, operator: str | None) -> Callable[[int], dict[str, str]]` — returns a closure that, given a 1-indexed episode number, yields `{"episode_id": f"{session_id}/episode_{n:03d}", "episode_index": str(n), "session_id": session_id, "operator": operator}` (operator key omitted when `None`).
- [x] 5.5 Tests in `test_data_collection_vis.py`:
  - factory increments path counter monotonically across calls
  - session name matches `YYYYMMDDTHHMMSSZ` regex
  - `piper_episode_metadata` returns dicts with the right keys; operator key absent when `None`, present when set
  - `DIMOS_OPERATOR` env var path: when set, `piper_episode_metadata` (or its caller in `piper_data_collection_rerun_config()`) propagates it

## 6. Retarget entity paths to LeRobot schema in `data_collection_vis.py`

- [x] 6.1 Change `_ENTITY_PREFIX` from `"world/piper"` to two new module-level constants: `_OBSERVATION_STATE_PREFIX = "/observation/state"` and `_ACTION_PREFIX = "/action"`. Update `_entity_path(role, short_name)` to return `f"{_OBSERVATION_STATE_PREFIX}/{short_name}"` for `role="measured"` and `f"{_ACTION_PREFIX}/{short_name}"` for `role="commanded"`.
- [x] 6.2 Define `CAMERA_RECORDED_ENTITY_PATH = "/observation/camera/usb"` and keep `CAMERA_TOPIC = "/piper_data_collection/color_image"`. (The LCM topic is unchanged; only the rendered entity path moves.)
- [x] 6.3 Update the preset factory `piper_data_collection_rerun_blueprint()` so `Spatial2DView.origin = CAMERA_RECORDED_ENTITY_PATH` and the per-joint `TimeSeriesView`s point to the new measured + commanded paths under `/observation/state` and `/action`.
- [x] 6.4 Extend `piper_data_collection_rerun_config()` to return a single dict consumed by BOTH `vis_module("rerun", rerun_config=...)` and `RerunDataRecorder.blueprint(...)`: visual_override (unchanged keys, retargeted converters), `topic_to_entity` callback mapping the camera LCM topic to `/observation/camera/usb`, `entity_prefix`, plus recorder-only fields `record_path_factory`, `recording_id_factory`, `episode_metadata`. The viewer ignores the recorder-only fields; the recorder ignores any viewer-only ones if added later.
- [x] 6.5 Update `test_data_collection_vis.py` to assert the new entity-path scheme: `joint_state_to_rerun_scalars("measured")` emits `/observation/state/<short>` paths, `("commanded")` emits `/action/<short>`, camera maps to `/observation/camera/usb`. Update the preset-blueprint test to assert the new view origins.

## 7. `EpisodeBoundary` module

- [x] 7.1 Create `dimos/teleop/quest/episode_boundary.py`. Define `EpisodeBoundaryConfig(ModuleConfig)` with `button: str` (default `"right_secondary"` — right-controller B on `Buttons.BITS`; **not `right_primary`** which is the press-and-hold engage button in `TeleopIKTask` / `PinkTeleopTask`), `debounce_seconds: float = 0.5`. The `recorder: RerunDataRecorder` reference uses the class-level annotation convention `module_refs` autoconnect picks up (matches `ModuleB.module_a` in `core/coordination/test_blueprints.py`).
- [x] 7.2 Define `class EpisodeBoundary(Module)`. Declare `buttons: In[Buttons]`. On `start()` subscribe; in `_on_buttons` detect a rising edge on `config.button`, apply debounce, call `self.recorder.toggle_recording()`.
- [x] 7.3 Tests in `test_episode_boundary.py`:
  - rising edge calls `toggle_recording` exactly once (fake recorder records calls)
  - two presses within `debounce_seconds` call it exactly once
  - two presses outside `debounce_seconds` call it twice
  - holding the button (no edge) does not call it
  - level-low → level-high → level-low → level-high counts as two presses

## 8. Retire `PiperDataRecorder` and wire the blueprint

- [x] 8.1 Delete `PiperDataRecorder`, `PiperDataRecorderConfig`, and `dimos/teleop/quest/data_collection.py`. The `default_recording_name` function has already migrated under Task 5.1.
- [x] 8.2 Delete `dimos/teleop/quest/test_data_collection.py`. Migrate any salvageable synthetic-message builders to `test_data_collection_vis.py` if not already duplicated.
- [x] 8.3 In `dimos/teleop/quest/blueprints.py`:
  - remove the import of `PiperDataRecorder` and its atom from `teleop_quest_piper_data_collection`
  - add the `RerunDataRecorder.blueprint(...)` atom, configured from `piper_data_collection_rerun_config()` (a single shared object — bind a local variable; viewer and recorder subsets carve out the bridge-accepted and recorder-accepted fields and pass them through, so structural object identity holds at the field level)
  - add the `EpisodeBoundary.blueprint(...)` atom, wired to the recorder via the class-level `recorder: RerunDataRecorder` annotation
- [x] 8.4 Grep the repo for any remaining `PiperDataRecorder` references and clean up; none should remain. Also retired `piper-data-recorder` and added `rerun-data-recorder` / `episode-boundary` in `dimos/robot/all_blueprints.py`. The two `PiperDataRecorder` strings in `test_blueprints.py` are addressed in §9.

## 9. Blueprint integration tests

- [x] 9.1 Update `dimos/teleop/quest/test_blueprints.py` to drop assertions about `PiperDataRecorder` being in the blueprint atom list.
- [x] 9.2 Add an assertion that the blueprint contains both `RerunDataRecorder` and `RerunBridgeModule` atoms, and that they reference **the same** `piper_data_collection_rerun_config()` dict — implemented as object-identity over the shared fields (`visual_override`, `entity_prefix`, `topic_to_entity`) since the bridge's pydantic config rejects recorder-only keys. The cross-atom field identity is the actual structural drift safeguard (design.md Decision 5).
- [x] 9.3 Add an assertion that the recorder's `record_path_factory()` returns a path matching `…/piper_data_collection/<session_ts>/episode_001.rrd` on first call and `episode_002.rrd` on second.
- [x] 9.4 Add an assertion that the blueprint contains an `EpisodeBoundary` atom whose `recorder` config field references the same `RerunDataRecorder` instance. *(Asserted via the typed `module_refs` entry pointing at `RerunDataRecorder` — autoconnect resolves the actual instance at deployment.)*
- [x] 9.5 Add an assertion that `bridge.py` is **not imported** by `recorder.py` for anything except types (`grep "from dimos.visualization.rerun.bridge import" dimos/visualization/rerun/recorder.py` matches only the type-import line). This is a guardrail against the bridge refactor being silently reintroduced.

## 10. End-to-end recording test

- [x] 10.1 Integration test in `dimos/teleop/quest/test_data_collection_integration.py::test_session_with_rotation_writes_two_episodes_with_lerobot_paths` drives the same `piper_data_collection_rerun_config()` the blueprint uses against an in-memory pubsub fake, calls `toggle_recording()` mid-session, and asserts both `.rrd` files contain `/observation/camera/usb`, `/observation/state/<joint>`, `/action/<joint>`, and the static `/meta/*` entities. *(rerun 0.29 lacks per-column row-count introspection, so the union-of-row-counts assertion is unavailable on this SDK; entity-path coverage is checked instead.)*
- [x] 10.2 Integration test `test_empty_first_episode_is_discarded_on_rotate` triggers rollover with zero payload between `start()` and `toggle_recording()`; asserts `episode_001.rrd` is removed and `episode_002.rrd` contains the post-rollover payload.
- [x] 10.3 Catalog-server smoke test `test_catalog_server_lists_each_episode_as_a_row` calls `rr.server.Server(datasets={"piper": tmp_path})` and skips when the SDK lacks `get_dataset` / `list_entries` (rerun-sdk < 0.32).

## 11. Documentation

- [x] 11.1 Updated `docs/usage/visualization.md` with a new "Recording demonstrations to `.rrd` for robot learning" section describing the session/episode structure, the rollover button, and the bridge being unchanged. No other in-repo doc pages mention the retired pickle path.
- [x] 11.2 Added a "Reading recordings for training" subsection in the same doc covering `rerun rrd optimize` and a `rerun.experimental.dataloader(window=(...))` snippet, marked experimental.
- [x] 11.3 Added a "Browsing collected episodes" subsection covering `rr.server.Server(datasets={...})` and the Dataset Review UI.

## 12. Manual verification on hardware

- [ ] 12.1 Run `dimos run teleop-quest-piper-data-collection` against a real Piper with a USB camera; confirm the live viewer opens with the preset layout (camera + per-joint plots, now under `/observation/...` / `/action/...`) and that `episode_001.rrd` appears under `{data_dir}/piper_data_collection/<session_ts>/` immediately on start.
- [ ] 12.2 Record one demonstration, press the rollover button, record a second, press again, record a third. Stop the session. Confirm three `.rrd` files exist, named `episode_001.rrd` through `episode_003.rrd`.
- [ ] 12.3 Press the rollover button twice in quick succession (<500 ms apart); confirm only one rollover occurred and no empty `.rrd` was left behind.
- [ ] 12.4 Stop the session cleanly; open each `.rrd` in `rerun <path>` and confirm the recorded entities replay with the expected layout, and that the `/meta/...` entities carry the expected per-episode metadata.
- [ ] 12.5 Kill the live viewer process mid-session; confirm the recorder keeps writing the current episode until rollover or `stop()`.
- [ ] 12.6 Run `rerun rrd optimize <episode.rrd>` on a captured episode; confirm the output replays identically (and is smaller / GoP-aligned per the 0.32 optimizer notes).
- [ ] 12.7 In a separate dev environment with `torch` installed, load the optimized `.rrd` via `rerun.experimental.dataloader(window=(0.0, 1.0))` and pull one sample; confirm it contains `/observation/camera/usb`, `/observation/state/*`, `/action/*` aligned by timestamp.
- [ ] 12.8 Start `rr.server.Server(datasets={"piper": <data_dir>/piper_data_collection})`, open the Dataset Review UI, and confirm each episode appears as its own row with the static `/meta/...` columns surfaced.

## 13. Validate the change

- [x] 13.1 `openspec validate add-rerun-data-recorder` → valid.
- [x] 13.2 Targeted test subset (`pytest dimos/visualization/rerun/test_recorder.py dimos/teleop/quest/ -p no:cacheprovider`) → 41 passed, 1 skipped (catalog server, rerun-sdk 0.29 in this env).
- [x] 13.3 Confirmed `2026-05-14-add-data-collection-rerun-vis` is present in `openspec/changes/archive/`.
- [x] 13.4 `git diff --exit-code main -- dimos/visualization/rerun/bridge.py` → empty (bridge.py unchanged).
