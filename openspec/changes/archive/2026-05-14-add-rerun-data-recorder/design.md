## Context

Piper teleop demonstrations land on disk through `PiperDataRecorder` (`dimos/teleop/quest/data_collection.py:40`), which subscribes to three streams (`color_image`, `joint_state`, `desired_joint_action`) and writes them via `TimedSensorStorage` — currently aliased to `LegacyPickleStore` (`dimos/utils/testing/replay.py:322`). The output is one directory per stream with one pickle per frame. `Memory2ReplayAdapter` provides read-side access for legacy datasets but the write path remains pickle-only.

In parallel, the in-flight change `add-data-collection-rerun-vis` (15/18 tasks done) adds a live Rerun visualization sink to the same blueprint. That change deliberately treats visualization as a passive overlay: the same `to_rerun()` converters drive only the live viewer, and recording remains pickle-based.

Rerun 0.32 ships three primitives that change what's possible for the on-disk format:

- `rr.RecordingStream` + `rr.set_sinks(...)` — multiple independent recording streams can coexist in one process, each with its own sink set (`GrpcSink`, `FileSink`). `rr.log(..., recording=<stream>)` routes per call.
- `rerun.experimental.dataloader` — PyTorch `Dataset` (iterable + map-style) that streams encoded images, scalars, and h264/h265/av1 directly from `.rrd` with `window=(start, end)` action-chunk semantics, multi-worker prefetch, DDP. A LeRobot ACT training example ships with the release.
- Dataset Review UI + Catalog server — `DatasetEntry.register([uris...])`, `dataset.segment_store(...)`, `table_grid_with_flags` (clickable flag columns written back). One URI = one `.rrd` = one row.
- `rerun rrd optimize` — post-session GoP-boundary splitting and keyframe-marker insertion.

`rerun-sdk==0.32.0` is installed locally; the bridge already imports it pervasively. No new dependencies are required at collection time.

The architectural question this design answers: **where does the on-disk recording sink live — folded into the bridge, or as its own module?** Earlier iterations of this change folded a second `RecordingStream` into `RerunBridgeModule`. That conflates two responsibilities (live visualization for operators vs. on-disk capture for training) into one component, drags teleop-flavored configuration (episode rollover, LeRobot-shaped paths, operator metadata) into a generic visualization module, and ties recording lifecycle to whatever blueprint the bridge happens to run in. The decision below is to **keep them separate** and share only the small, well-defined converter logic.

## Goals / Non-Goals

**Goals:**
- Make `.rrd` the on-disk format for Piper data collection sessions. Pickle-dir recordings stop being produced for new sessions.
- Build a standalone `RerunDataRecorder` module that owns its own `rr.RecordingStream` + `FileSink`, subscribes to the same LCM topics the bridge does, and writes one `.rrd` per *episode* under a session directory.
- Keep `RerunBridgeModule` unchanged in scope: still a live-viewer sink, still throttleable, still generic. The bridge gains no recording responsibility.
- Leave `bridge.py` untouched. The recorder reimplements the small composition logic (visual_override chaining + entity-path derivation) locally, importing only the already-module-level types (`RerunMulti`, `RerunData`, `RerunConvertible`, `is_rerun_multi`) from `bridge.py`. The bridge stays the canonical home of those names; no bridge edit is required.
- Adopt LeRobot-shaped entity paths on the recording side (`/observation/...`, `/action/...`, `/meta/...`) so `rerun.experimental.dataloader` can select observations and actions by entity-path prefix without per-session metadata lookups. The viewer is retargeted to the same schema for consistency.
- Provide an in-session episode rollover RPC (`RerunDataRecorder.rotate_recording()`), wired to a Quest controller button via a small `EpisodeBoundary` module.

**Non-Goals:**
- Catalog hub. `rr.server.Server(datasets={...})` for cross-session SQL/Arrow queries is a separate later change; it is a training-time concern and does not affect how a session is recorded.
- In-tree training example. Documenting the `rerun.experimental.dataloader` recipe is in scope; shipping a working LeRobot ACT trainer is not.
- In-stream camera video encoding. Raw `rr.Image` frames are recorded; `rerun rrd optimize` is the documented post-session step for h264/h265/av1 transcoding. `VideoStream` / `EncodedImage` at log time is deferred.
- Pickle-to-`.rrd` migrator. Legacy recordings stay accessible through existing replay adapters; no in-place conversion.
- Recording support for any non-Piper blueprint. The `RerunDataRecorder` module is generic, but only `teleop_quest_piper_data_collection` instantiates it in this change.
- Removing `LegacyPickleStore` or the `TimedSensorStorage` alias. Other parts of the stack (nav, audio) still use it; only the Piper teleop callsite goes away.

## Decisions

### Decision 1: A standalone `RerunDataRecorder` module, separate from the bridge

Architecture:

```
                      Streams (LCM)
                        /         \
       subscribe-all   /           \  subscribe-all
                      /             \
       RerunBridgeModule        RerunDataRecorder
       (live viewer)            (on-disk .rrd)
                      \             /
                       \           /
                        ↘         ↙
            dimos/visualization/rerun/converter.py
               (compose_converter, derive_entity_path,
                is_rerun_multi, RerunConvertible)
```

`RerunDataRecorder` lives at `dimos/visualization/rerun/recorder.py`. It is a normal DimOS `Module` with:

- `Config.pubsubs: list[SubscribeAllCapable]` — same shape as the bridge's `pubsubs`. Default `[LCM()]`. Recorder subscribes independently; it does not share a subscription with the bridge.
- `Config.visual_override`, `Config.entity_prefix`, `Config.topic_to_entity` — same shape and semantics as the bridge's fields. The recorder runs the same `compose_converter(...)` against the same input config, so what gets recorded is structurally identical to what the bridge would have logged for the same message — except routed to its own `RecordingStream`.
- `Config.record_path_factory: Callable[[], Path]` — required (no default; absent factory means no recorder).
- `Config.recording_id_factory: Callable[[Path], str] | None = None`.
- `Config.episode_metadata: Callable[[int], dict[str, str]] | None = None` — given a 1-indexed episode number, returns a metadata dict (`episode_id`, `episode_index`, `session_id`, optionally `operator`).
- `Config.app_id: str = "dimos_recorder"` — the Rerun application id for the recorder's `RecordingStream`. Distinct from the bridge's app id so the catalog can tell viewer-side and recorder-side recordings apart.

On `start()` the recorder calls `_open_episode()`, subscribes to its pubsubs, and starts pumping messages into its own `RecordingStream`. On `stop()` it flushes, closes, and (if the current episode is empty) deletes the file.

Why a separate module, not a second stream on the bridge:

| Concern | Bridge with 2 streams | Separate recorder module |
|---|---|---|
| Single-responsibility | viewer + recorder bundled | clean split |
| Bridge config bloat | gains 3-4 recorder fields | bridge unchanged |
| Lifecycle independence | recording lives or dies with the bridge | recorder can be started/stopped on its own |
| Generic-blueprint reuse | non-recording blueprints carry recording config they don't use | non-recording blueprints don't instantiate the recorder |
| Test surface | one big module with mixed responsibilities | recorder testable without standing up a viewer |
| Pubsub bus cost | 1 subscribe-all | 2 subscribe-all (one per module) |
| Converter cost | 1 invocation per message | 2 invocations per message (one per module) |
| "What I see = what's recorded" | enforced structurally | enforced by sharing `compose_converter` |

The added cost (double subscribe-all, double converter invocation) is small in absolute terms: the converters are pure functions over already-deserialized messages, and one extra subscribe-all is one extra callback registration per pubsub. The structural benefits — bridge stays generic, recorder evolves on its own (custom batchers, catalog push, in-stream encoding) without touching viewer code — are large.

Drift is the one real concern (live viewer and recording could end up showing different things if the converter input config differs between the two modules). The mitigation is structural: both modules construct their converters from the same `visual_override` / `entity_prefix` / `topic_to_entity` config values, and the blueprint passes the same dictionary into both. The `data_collection_vis.py` module exposes a single `piper_data_collection_rerun_config()` that both `vis_module("rerun")` and `RerunDataRecorder.blueprint(...)` consume; there is no second source of truth.

Alternative rejected: a `RerunRecordingSink` mixin that both modules import. Mixins on DimOS `Module`s would couple the lifecycle ordering and `ModuleConfig` shapes; a free-function utility module is simpler and sufficient.

Alternative rejected: a shared `RecordingStream` owned by neither module, brokered via a third "stream manager" module. Rejected — overengineered; the recorder owning its own stream is the simpler invariant, and the bridge does not need to know recordings exist.

### Decision 2: `record_path_factory`, `recording_id_factory`, `episode_metadata` live on the recorder

`RerunDataRecorder.Config`:

- `record_path_factory: Callable[[], Path]` — called on `start()` for the first episode and on every `rotate_recording()` for subsequent ones. Returning the same path twice raises (refuses to overwrite). Parent directories are created if missing.
- `recording_id_factory: Callable[[Path], str] | None = None` — derives the `recording_id` for each episode's `RecordingStream` from its file path. When `None`, the recorder uses a default derivation: `f"{path.parent.name}/{path.stem}"`.
- `episode_metadata: Callable[[int], dict[str, str]] | None = None` — given the 1-indexed episode number, returns the metadata dict to log statically at the start of that episode. When `None`, only a generic `episode_index` is logged.

The blueprint constructs the factories and metadata closure (see Decision 9) and passes them into `RerunDataRecorder.blueprint(...)`. The bridge's `Config` does **not** gain any of these fields.

For blueprints that record only one file per session, the factory returns a constant path on its first call and raises on subsequent calls.

Alternative rejected: a fixed `Path` and an internal episode counter inside the recorder. That bakes the data-collection naming convention into a generic recording module; the factory keeps naming concerns in the blueprint layer.

### Decision 3: Entity-path schema is LeRobot-aligned

Recorded entity paths use:

```
/observation/camera/usb                Image
/observation/state/<short_joint>       Scalars   (one entity per joint)
/action/<short_joint>                  Scalars   (one entity per joint)
/meta/episode_id                       TextDocument (static, per episode)
/meta/episode_index                    TextDocument (static, per episode)
/meta/session_id                       TextDocument (static, per episode)
/meta/operator                         TextDocument (static, per episode, optional)
```

`<short_joint>` is the last `/`-segment of the joint name (e.g. `joint1`, `gripper`). The joint-name source remains `piper_data_collection_joint_short_names()` from `dimos/teleop/quest/data_collection_vis.py:55` — the visualization override, the recording override, and the viewer preset all iterate the same list.

This schema is chosen so:
- `rerun.experimental.dataloader` can select observations / actions by entity-path prefix without consulting per-session metadata.
- The split between `observation` (sensor + measured state) and `action` (commanded state) is visible at the path level — the only structural information `dataloader`'s `window=` semantics need.
- The gripper is one row in the joint stack at both `/observation/state/<gripper>` and `/action/<gripper>` — gripper is just another joint.

The viewer preset (`piper_data_collection_rerun_blueprint()`) is retargeted to the same paths in the same edit, so live and recorded entities match.

Alternative rejected: keep `world/piper/measured/...` and project at training. Pushes the rename to every downstream consumer forever; breaks "training-ready as written."

Alternative rejected: prefix recorded paths with the session id (`/sessions/<id>/observation/...`). `recording_id` already addresses sessions; encoding it in entity paths prevents `dataloader` from selecting consistently across sessions.

### Decision 4: Camera image topic stays — only its recorded entity path moves

The data collection blueprint already publishes camera frames on `LCMTransport("/piper_data_collection/color_image", Image)`. We do **not** rename the LCM topic. Instead, the `topic_to_entity` callback (supplied by the blueprint and consumed by both the bridge and the recorder via `compose_converter`'s `derive_entity_path`) maps that topic's entity path to `/observation/camera/usb`.

### Decision 5: Recorder duplicates the small composition logic locally; bridge is not modified

The conversion contract DimOS messages already encapsulate is the `to_rerun()` method on each message class (`Image.to_rerun()`, `PoseStamped.to_rerun()`, the in-flight vis change's JointState → scalars helper, etc.). That is the *encapsulated* logic the recorder calls. The handful of lines in `RerunBridgeModule._visual_override_for_entity_path` and `_get_entity_path` that compose `visual_override` glob matches and pipe them into the `to_rerun()` passthrough are small and stable; the recorder reimplements them locally rather than refactoring the bridge.

What this means concretely:

- `bridge.py` is **not modified** by this change. No file moves, no signature changes, no new imports. The bridge ships exactly as today; PR review burden against the bridge is zero.
- `RerunDataRecorder` imports the already-module-level types from `bridge.py` — `RerunMulti`, `RerunData`, `RerunConvertible`, `is_rerun_multi` — because those are already top-level symbols, no bridge edit is needed to make them so. Bridge stays the canonical home for those names.
- `RerunDataRecorder` implements its own `_get_entity_path(topic)` and `_compose_converter(entity_path)` as private methods. The implementations mirror the bridge's by intent. The bodies are ~10 lines each.

Trade-off accepted: two implementations of the same small composition logic exist in the codebase. Drift between them is possible. The mitigation is structural, not code-sharing:

- The blueprint passes the same `piper_data_collection_rerun_config()` (visual_override dict, entity_prefix, topic_to_entity) to both `vis_module("rerun")` and `RerunDataRecorder.blueprint(...)`. The shared *input* is the contract; the duplicated *implementation* is a leaf detail.
- A blueprint integration test asserts both modules in the data collection blueprint resolve from the same config object identity, so they cannot diverge at wiring time.
- Per-message agreement is exercised by the end-to-end recording test: it pushes synthetic messages, opens the resulting `.rrd`, and asserts the recorded entity paths match the entity paths the live viewer would log for the same messages (i.e. the entity paths the bridge would derive). If the recorder drifts, this test fails.

Why not extract a shared utility module: the user has explicit constraints to minimize bridge churn for PR-review reasons, and extracting `_visual_override_for_entity_path` / `_get_entity_path` would move bridge code into a new module and rewrite the bridge call sites. That is exactly the kind of bridge-adjacent edit being avoided here. The cost — 20 duplicated lines guarded by a structural test — is small enough that the bridge-touch cost is the dominant factor.

When the bridge does eventually need a related refactor (e.g., a future contributor extracts converter utilities for a third consumer), the recorder can switch to importing them then. This change does not force that timing.

### Decision 6: Recorder is full-rate by construction; throttling is bridge-only

The recorder does not implement a `max_hz` throttle and does not honor any throttle config the bridge has. Every message that flows into `_on_message` is logged to the recording stream. This is the structural counterpart to the user-facing invariant: **viewer is throttleable; recording is not.**

Operators who want to record at a reduced rate use Rerun's offline tools after the fact (`rerun rrd optimize` or the chunk-stream APIs). They do not configure a throttle at collection time.

The bridge's `max_hz` field stays as-is and continues to throttle the viewer. No new bridge fields. The recorder has no field by which a throttle could even be configured.

### Decision 7: Episode boundary is a recording toggle, not a rollover

The original design called this RPC `rotate_recording` and made it close-and-reopen: one press → file finalized → next file opened immediately. In practice that's wrong for demonstration capture, because **the operator needs time between demonstrations to reset the scene** — return the robot to a start pose, place the object, get back into position. During that window the recorder is still pumping messages onto the bus from teleop motion, image stream, and joint state — and rotating-into-the-next-file means all of that ends up baked into the head of `episode_NNN.rrd` with no clean cut.

The corrected shape is a **two-state toggle**:

```
              press                       press
RECORDING  ─────────►  IDLE  ─────────►  RECORDING
   ▲       (flush+close)  │  (open new ep)    │
   │                      │                   │
   └──────────────────────┴───────────────────┘
                  press                press
```

- **RECORDING**: an episode `.rrd` is open and accepting messages.
- **IDLE**: no `.rrd` is open. Messages on the bus continue to flow to the live viewer; the recorder's `_on_message` short-circuits before any `rr.log` call.

`RerunDataRecorder.toggle_recording(*, recording_id=None, path=None) -> Path | None` is the single `@rpc` for both transitions:

```
if self._record_stream is not None:        # → IDLE
    self._close_episode()
    return None
self._episode_index += 1                   # → RECORDING
return self._open_episode(path=path, recording_id=recording_id)
```

Return value:

- `None` ⇒ recorder just entered IDLE.
- `Path` ⇒ recorder just entered RECORDING; this is the new episode's path.

`start()` enters **IDLE** — the operator must press the toggle button once to open `episode_001.rrd`. This was a deliberate revision from an earlier "auto-start on session begin" design: in practice the period between launching the blueprint and the first demo includes scene setup, gripper calibration, and warmup motion, none of which belongs in a training recording. Defaulting to IDLE makes recording an explicit operator decision and means the first `.rrd` file in a session always corresponds to a deliberate demo, never an accident.

Concurrency: `_close_episode` and `_on_message` share `self._record_lock`. Drop-state (`_record_stream is None`) is checked inside the lock in `_on_message`, so a message that arrives during a toggle-off is either logged to the closing file (lock acquired before the close) or silently discarded (lock acquired after the close set the stream to `None`). No message is split across the boundary or duplicated.

Counter behavior: the episode counter advances only on toggle-on (the `_episode_index += 1` line). If a toggle-off discards an empty file, the file path's slot number is consumed by the factory but the episode metadata index doesn't double-count. In practice file slots and episode indices track 1:1 in the happy path; an extra toggle press with no payload between leaves an honest hole (`episode_001.rrd, episode_003.rrd`).

The optional kwargs allow tests and an eventual `dimos toggle-recording` admin RPC to inject specific identifiers; when both are `None`, the factory drives.

Default disk layout:

```
{data_dir}/piper_data_collection/<session_ts>/episode_001.rrd
{data_dir}/piper_data_collection/<session_ts>/episode_002.rrd
...
```

`<session_ts>` = `YYYYMMDDTHHMMSSZ`. Episode counter zero-pads to 3 digits.

Alternative rejected: keep "one file per session" and use Rerun's multi-store-per-file support. Rejected — Dataset Review UI's row unit and `DatasetEntry.register` URI list both assume one store per file. Multi-store inside a single file gets you off the happy path of every consumer-facing API in 0.32.

Alternative rejected: heuristic episode boundaries (idle detection, time-based). Rejected — fragile; the operator knows when an episode ends.

### Decision 8: Episode rollover is triggered by a Quest button, dispatched by a tiny module

A new module `EpisodeBoundary` (`dimos/teleop/quest/episode_boundary.py`) subscribes to the `Buttons` stream and calls `recorder.rotate_recording()` on a specific button-edge event. It does not depend on the bridge.

`EpisodeBoundary.Config`:

- `button: str` — the field name in `Buttons` to watch (e.g. `"right.a"`; resolved against `dimos.teleop.quest.quest_types`).
- `debounce_seconds: float = 0.5`.
- `recorder: RerunDataRecorder` — typed reference to the recorder it drives. The blueprint's `autoconnect(...)` wires this. (Or the connection is made via a typed in-channel; pick whichever convention the rest of `dimos/teleop/quest/` uses for module-to-module references.)

The choice of button is a single config constant. Default is **`right_secondary`** (the B button on the right controller). **Not `right_primary` (A)**: that is the press-and-hold engage button used by `TeleopIKTask.handle_buttons` and `PinkTeleopTask.handle_buttons` (`dimos/control/tasks/teleop_task.py:300`, `dimos/control/tasks/pink_teleop_task.py:…`). Reusing A would rotate the recording every time the operator engages the arm — a catastrophic collision. B sits on the same hand (so the operator already has it committed) but a deliberate thumb-reach away from A.

Visual / haptic feedback: out of scope. The live viewer will show new `/meta/episode_index` increments; that suffices to confirm a rollover. A follow-up change can add haptic pulses.

Alternative rejected: bake the Buttons subscription into the recorder. Rejected — couples a generic recording module to teleop semantics; the `Buttons` type lives in `dimos.teleop.quest`.

Alternative rejected: a dedicated LCM topic for episode events (`/teleop/episode_boundary`). Rejected — adds a transport for an event that is already a button press.

### Decision 9: Session/episode helpers live next to the blueprint, not in the recorder

`PiperDataRecorder` is deleted. The `default_recording_name()` helper migrates to `dimos/teleop/quest/data_collection_vis.py` and is renamed `default_session_name()` (it now names a directory, not a file). New helpers in the same module:

- `default_episode_path_factory(session_name: str | None = None) -> Callable[[], Path]` — returns a stateful factory that yields `Path(get_data_dir()) / "piper_data_collection" / session_name / f"episode_{counter:03d}.rrd"` on each call. When `session_name` is `None`, the factory generates one via `default_session_name()` on first call and reuses it.
- `default_recording_id_factory(path: Path) -> str` — returns `f"{path.parent.name}/{path.stem}"`.
- `piper_episode_metadata(session_id: str, operator: str | None) -> Callable[[int], dict[str, str]]` — returns the per-episode metadata closure.

These helpers live in `data_collection_vis.py` because that module already encapsulates the Piper data-collection layout (joint name list, visual_override, preset blueprint). Keeping them together means there is one place to change the data-collection naming convention.

The blueprint instantiates them and passes them into `RerunDataRecorder.blueprint(...)`. The recorder itself knows nothing about timestamps, "piper", or "session" names.

`data_collection.py` becomes empty enough that it is removed entirely; its tests are migrated to `test_data_collection_vis.py`.

### Decision 10: Recorder is truly independent of the viewer

Because the recorder owns its own `RecordingStream` and subscribes to pubsubs independently of the bridge, the failure modes decouple cleanly:

- Bridge viewer process unreachable → recorder unaffected; `.rrd` continues to grow.
- Bridge module fails on `start()` → recorder still subscribes and records; the data is captured even if the operator has no live view.
- Recorder fails on `start()` (e.g., disk full, invalid path) → bridge still serves the live viewer; the operator sees a degraded state at the recorder level and can stop the session.
- Either module can be omitted from the blueprint without affecting the other.

This is the replacement for the old "byte-identical recording with vs. without visualization" invariant. The new structural invariant: **recorder and viewer are orthogonal sinks driven from the same source streams**. The operator's "did the recording capture what I saw?" question reduces to "did the same LCM messages flow through both modules?" — testable by comparing message counts on the wire to row counts in the `.rrd`.

## Risks / Trade-offs

- **[Risk]** Disk footprint of raw `rr.Image` frames. 640×480 @ 30 Hz ≈ 30 MB/min uncompressed. A 30-minute collection session is ~1 GB.
  → **Mitigation:** document `rerun rrd optimize` as the post-session step; defer in-stream `VideoStream` / `EncodedImage` to a follow-up change. Operators with disk constraints can chain `optimize` automatically (out of scope).

- **[Risk]** `rerun.experimental.dataloader` is experimental. Format or import path may change in 0.33+.
  → **Mitigation:** `.rrd` format was declared backward-compatible in 0.23 and reaffirmed in 0.32. The dataloader is a read-side concern; if its API changes, recorded sessions remain valid and only the (not yet written) trainer adapts.

- **[Risk]** Drift between viewer and recorder converters. If a future contributor changes `visual_override` in one place but not the other, the operator sees one thing and records another.
  → **Mitigation:** one source-of-truth `piper_data_collection_rerun_config()` in `data_collection_vis.py` is consumed by both `vis_module("rerun", rerun_config=...)` and `RerunDataRecorder.blueprint(...)`. Blueprint tests assert both modules resolve to the same config object.

- **[Risk]** Two `subscribe_all` callbacks (bridge + recorder) double pubsub bus dispatch cost.
  → **Mitigation:** measure during hardware verification; acceptable in absolute terms (LCM dispatch is microseconds per message, the bridge already does this work). If it becomes a bottleneck, a future change can introduce a shared bus-side dispatcher; not needed at current message rates.

- **[Risk]** Two converter invocations per message.
  → **Mitigation:** converters are pure functions over already-deserialized DimOS messages; cost is dominated by archetype construction, not parsing. Same answer as above — measure, optimize only if measurable.

- **[Risk]** Lifecycle ordering. If `EpisodeBoundary` starts before `RerunDataRecorder`, a button press could call `rotate_recording` before the recorder is up.
  → **Mitigation:** the recorder's `rotate_recording` is a no-op when `self._record_stream is None` (warns and returns `None`). Module start order is captured in the blueprint's autoconnect graph; tests assert the order.

- **[Risk]** Crash safety. If the process dies mid-session, is the `.rrd` salvageable?
  → **Mitigation:** Rerun's `.rrd` files have always been streamable / chunk-recoverable; 0.32's footer makes partial files inspectable. Accept that an unflushed tail may be lost (≤ chunk batcher window). Document; do not fsync-per-message.

- **[Trade-off]** No "byte-identical recording without visualization" invariant. Replacement: viewer and recorder are independent modules driven from the same pubsub; either can be omitted to isolate behavior.

- **[Trade-off]** Slightly more code than a folded-into-bridge approach: `recorder.py`, `converter.py`, and the EpisodeBoundary module. The corresponding gain is a clean separation that pays off as soon as someone wants to record without a viewer, or visualize without recording, or use the recorder against a different blueprint.

## Migration Plan

There is no data-side migration. Legacy pickle recordings under `{data_dir}/piper_data_collection/<old_name>/{observation.images.usb,observation.state,action}/` remain readable through `Memory2ReplayAdapter` / `LegacyPickleStore`; we explicitly do not touch them. New sessions write to `{data_dir}/piper_data_collection/<session_ts>/episode_<NNN>.rrd` — different filename pattern, so collision is impossible.

Code-side deployment:

1. Land `add-data-collection-rerun-vis` first (its 3 remaining tasks are manual hardware verification). The vis change provides the `vis_module("rerun")` atom, the JointState → scalar override helper, and the preset blueprint factory that this change retargets.
2. Land this change as a single PR. Diff highlights: new `dimos/visualization/rerun/recorder.py`; new `dimos/teleop/quest/episode_boundary.py`; `bridge.py` is **not** modified; `PiperDataRecorder` deleted; `data_collection_vis.py` entity paths shift to `/observation/...` / `/action/...` and gain the path/id/metadata helpers; blueprint adds `RerunDataRecorder.blueprint(...)` and `EpisodeBoundary.blueprint(...)` atoms; tests update.
3. Rollback is removing the new modules and re-introducing `PiperDataRecorder` from git. No production state to unwind.

Operator-side migration: collection commands stay the same (`dimos run teleop-quest-piper-data-collection`). Output path moves from a pickle-dir tree to per-episode `.rrd` files under a session directory. Replay command becomes `rerun <data_dir>/piper_data_collection/<session_ts>/episode_001.rrd` (or open any episode). New affordance: a controller button rolls over to the next episode mid-session.

## Open Questions

- Where does `/meta/operator` come from? `dimos run` does not currently take an operator identity. Option A: leave it unset by default; only populate when `DIMOS_OPERATOR=<name>` env var is set. Option B: prompt at start. Lean A; defer prompting to a future "session metadata" change.

- Should the recorder also send its blueprint preset to the `.rrd` (`rr.send_blueprint(..., recording=record_stream)`) so the recorded session opens in the viewer with the same layout? Inclined yes — replaying an episode is just opening the `.rrd` in `rerun`. Decide before implementation.

- Should we expose a `record_chunk_batcher` config to operators with disk-IO concerns? Default Rerun batcher is fine; if disk is slow, batches grow. Probably leave as a follow-up if anyone reports issues; don't pre-engineer.

- ~~Which Quest button is the rollover trigger?~~ Resolved during implementation: **B (`right_secondary`)**. A (`right_primary`) collides with the teleop engage button, so the original "right A" default would have rotated the recording every time the operator engaged the arm. The choice remains a single `EpisodeBoundary.Config` field so retuning is trivial.

- Should `rotate_recording()` accept caller-supplied `recording_id` / `path` overrides (for tests and the eventual `dimos rotate-recording` admin RPC)? Leaning yes — both kwargs default to `None` and let the factory drive.

- Module-to-module wiring for `EpisodeBoundary → RerunDataRecorder`: do we use a typed `Config.recorder` field, or does DimOS already have a convention for injecting a sibling module reference into an autoconnect graph? Confirm by reading neighboring teleop modules during implementation; either works.

- Should `RerunDataRecorder` share a `RerunInit` (`rerun_init(...)`) call with the bridge or call its own? Two independent `rr.init(...)`s in one process is supported (each creates its own application/recording), but worth confirming there are no side-effects from the global init.
