## Context

Two related modules carry multi-camera scaffolding that the production blueprints do not exercise:

- `PolicyNode` declares `image`, `image_aux1`, `image_aux2` as class-level `In[Image]` slots and exposes `camera_sources: dict[str, str]` as a slot → cam_key mapping. Only the `image` slot is wired (with `camera_sources={"image": "usb"}`). The `_aux*` slots and the mapping mechanism are dead code.
- `RerunDataRecorder` has no typed camera input at all. It receives the camera image via the generic `pubsubs: list[SubscribeAllCapable]` + `topic_to_entity` path that also handles joint-scalar streams. The camera's identity ("usb", entity path `/observation/camera/usb`, source topic `/piper_data_collection/color_image`) lives in `dimos/teleop/quest/data_collection_vis.py` module constants and a callback branch.

Both shapes were defensible in isolation. Together they pull in opposite directions: the policy node *exposes* multi-camera, the recorder *hides* its single camera. Neither matches the system today, where exactly one USB webcam streams to both consumers.

A previous exploration (since discarded) proposed lifting a shared `cameras: dict[str, CameraSource]` schema across both modules + the Piper contract. The user pushed back: defer the dynamic-config work, simplify to single-camera-only as the baseline, and re-introduce multi-camera from a clean starting point when there's an actual deployment that needs it.

## Goals / Non-Goals

**Goals:**
- Land one typed camera input per module — `image: In[Image]` on `PolicyNode`, `color_image: In[Image]` on `RerunDataRecorder` — that participates in the blueprint dep graph and the transport map.
- Delete dead multi-camera scaffolding (`image_aux*` slots, `ALLOWED_CAMERA_SLOTS`, slot-mapping).
- Keep `RerunDataRecorder`'s generic `pubsubs` + `visual_override` + `topic_to_entity` path intact for non-camera streams (joint scalars, action scalars). The recorder remains a general message recorder; only the camera path moves to a typed slot.
- Preserve every recorded entity path and every LCM topic name so existing `.rrd` recordings stay loadable by `PiperRobotContract.from_rerun_row` without migration.

**Non-Goals:**
- Any multi-camera support. A future change re-introduces it from this baseline.
- Removing or restructuring the recorder's `pubsubs` / `visual_override` / `topic_to_entity` mechanism for non-camera streams.
- Changing `PiperRobotContract`. The contract's `cameras={"usb": (480, 640, 3)}` default already represents single-camera; the multi-camera dict shape stays *as configuration capacity* without forcing it on the runtime modules.
- Reworking the camera-side transport, frame rate, or LCM topic name. The change is structural, not behavioral.

## Decisions

### Decision 1: PolicyNode keeps a single typed `image: In[Image]` slot

Drop `image_aux1: In[Image]` and `image_aux2: In[Image]`. Drop `ALLOWED_CAMERA_SLOTS`. Drop `camera_sources: dict[str, str]`. Replace with a single `camera_key: str = "main"` config field — the key the backend sees in `PolicyObservation.images`.

`assemble_observation()` becomes: if `self._latest_image is not None`, return `images={self.config.camera_key: self._latest_image}`; otherwise `images={}`. `_subscribe_inputs` subscribes to `self.image` and stores into `self._latest_image`.

**Alternative considered**: keep `image_aux1` / `image_aux2` as "available but unwired" slots. Rejected — unused class-level `In[T]` slots show up in module introspection (`module_info`, `inputs` dict), and every blueprint inspecting the policy graph gets misleading inputs. The cost of removal is small, the cost of keeping is permanent.

**Alternative considered**: drop `camera_key` too and hardcode `"main"` (or `self.frame_id`). Rejected — `PiperRobotContract` expects the key `"usb"` to land in `observation.images.usb`. Hardcoding forces the policy node to also know "this is a Piper deployment"; an explicit string config keeps the contract-side identity (`"usb"`) lined up at the blueprint call site, where the rest of the Piper wiring lives.

### Decision 2: RerunDataRecorder gains a typed `color_image: In[Image]` slot

Today the recorder logs the camera via the generic `_on_message` path (subscribe_all on `pubsubs[0]`, look up the entity path via `topic_to_entity`, log under that path). Move the camera path off this generic mechanism onto a dedicated handler:

```
RerunDataRecorder
  color_image: In[Image]          ← NEW typed slot
  config:
    camera_entity_path: str = "/observation/camera/usb"   ← NEW
    pubsubs: list[SubscribeAllCapable] = [LCM()]          ← unchanged
    visual_override: dict[Glob | str, ...] = {}           ← unchanged
    topic_to_entity: Callable[[Any], str] | None = None   ← unchanged
```

The recorder's `start()` subscribes to `self.color_image` and routes each frame into a new `_on_color_image(image)` handler that logs `rr.log(self.config.camera_entity_path, image, recording=stream)`. The existing `_on_message` path is unchanged and continues to drive joint-scalar logging.

**Alternative considered**: route everything through typed `In[T]` slots — add `measured_joint_state: In[JointState]`, `desired_joint_action: In[JointState]` too, then drop `pubsubs` / `visual_override` / `topic_to_entity` entirely. Rejected for this change — that's a larger architectural shift the user didn't ask for; the recorder's generic mechanism is well-tested (`test_recorder.py`'s drift detector relies on it) and supports use cases beyond Piper data collection.

**Alternative considered**: keep the camera on the generic path; just rename constants and tighten the callback. Rejected — leaves the asymmetry where the recorder hides its primary input while the policy node exposes it. Goal is symmetry between the two.

### Decision 3: The blueprint wires `color_image` via the standard transport map

```python
teleop_quest_piper_data_collection = autoconnect(
    ...,
    CameraModule.blueprint(),
    RerunDataRecorder.blueprint(**recorder_kwargs),
    ...,
).remappings(
    [
        # CameraModule publishes color_image; recorder also exposes color_image.
        # autoconnect already pairs them by name+type — no explicit remap needed.
    ],
).transports(
    {
        ...
        # The camera topic on the wire is unchanged.
        ("color_image", Image): LCMTransport("/piper_data_collection/color_image", Image),
    }
)
```

Both `CameraModule.color_image: Out[Image]` and `RerunDataRecorder.color_image: In[Image]` use the same stream name and type, so `autoconnect` pairs them without an explicit `remappings(...)` entry. The transport map entry keeps the LCM topic name identical so existing `.rrd` recordings produced under the old wiring remain comparable.

**Alternative considered**: keep the recorder's `pubsubs` subscribing to `/piper_data_collection/color_image` for the camera AND have the typed slot. Rejected — double-subscription would log each frame twice. The blueprint must arrange exactly one path.

The data-collection blueprint's existing `topic_to_entity` callback drops the `CAMERA_TOPIC == name` branch. Joint state and desired action keep using `topic_to_entity` because they still come through the generic path.

### Decision 4: PiperRobotContract is unchanged

The contract's `cameras = {"usb": (480, 640, 3)}` default is already single-camera. It happens to support N cameras at the contract level (the dict iteration in `from_rerun_row` / `features()` / `rerun_entities()`), but that's an *unused capacity* of the contract, not a runtime requirement on the modules. We're not pushing single-camera-ness down into the contract — the contract stays a more general type, and the runtime modules speak its single-camera default.

`_CAMERA_KEY = "usb"` and `_CAMERA_ENTITY_PATH = "/observation/camera/usb"` stay as module-level constants. They're plumbing for the contract's default; leaving them keeps the contract test surface stable.

**Alternative considered**: also pin the contract to single-camera (remove the dict, replace with scalar fields). Rejected — would force a multi-camera follow-up to undo it.

### Decision 5: Camera entity path moves from a `data_collection_vis` constant to a recorder config field

`CAMERA_RECORDED_ENTITY_PATH = "/observation/camera/usb"` in `data_collection_vis.py` becomes the default of `RerunDataRecorderConfig.camera_entity_path`. The recorder owns the entity-path string because the recorder is what writes it. Deployments that need a different LeRobot schema (e.g., `/observation/images.usb` in some newer revisions) override on the blueprint side.

The Piper data-collection blueprint passes `camera_entity_path="/observation/camera/usb"` explicitly — even though that's the default — so the blueprint stays self-describing about which entity path it's contributing.

### Decision 6: No backwards compatibility for `camera_sources` or the `image_aux*` slots

Removed cleanly in the same commit as the rest of the change. Reasons:

- No external (non-dimos) blueprint depends on `image_aux*` or `camera_sources`; they're consumed only by `dimos/teleop/quest/blueprints.py`.
- Keeping them as deprecation shims doubles the runtime paths in `PolicyNode._subscribe_inputs` and the config validation.
- The spec rollback (multi-camera → single-camera) is the load-bearing change; the API removals follow it cleanly.

## Risks / Trade-offs

- **[Spec rollback may signal the wrong direction]** → Mitigation: the proposal is explicit that multi-camera is *deferred*, not *abandoned*. When re-added, the typed `image` / `color_image` slots are the natural starting point. The new spec language pins single-camera as a baseline, not a final state.
- **[Recorder gains a second logging code path]** → The typed-slot path lives alongside the generic `_on_message` path. Mitigation: the typed path is ~10 lines, lives in its own handler, and is exercised by its own test. The generic path continues to handle every non-camera stream so no module-wide split occurs.
- **[Camera double-logging if a deployment misconfigures both paths]** → If a downstream blueprint passes both a `color_image` wire AND a `topic_to_entity` mapping that points to `/observation/camera/usb`, frames get logged twice. Mitigation: the data-collection blueprint drops the camera branch from `topic_to_entity` in the same commit; document the rule in the recorder docstring; add a unit test asserting exactly one log per frame for the typed path.
- **[Off-tree code that imports `CAMERA_TOPIC` / `CAMERA_RECORDED_ENTITY_PATH`]** → Mitigation: a grep over the repo at change-apply time. These constants only have callers within `data_collection_vis.py` and its tests.
- **[Single-camera-only forces the next deployment that needs N cameras to do a larger refactor]** → Accepted. The cost of carrying speculative multi-camera scaffolding indefinitely outweighs the cost of revisiting it when the need is concrete. Multi-camera proposals can pick between the per-instance subclass-synthesis approach, the recorder's `pubsubs+visual_override` approach, or a config-driven dict — that decision is better made with a specific deployment in hand.

## Migration Plan

Single commit. No on-disk format changes.

1. Update `PolicyNodeConfig` and `PolicyNode` (remove `image_aux*`, `ALLOWED_CAMERA_SLOTS`, `camera_sources`; add `camera_key`).
2. Update `RerunDataRecorderConfig` and `RerunDataRecorder` (add `color_image` slot, `camera_entity_path` field, the new handler).
3. Update `data_collection_vis.py` (drop camera constants and the camera branch).
4. Update `dimos/teleop/quest/blueprints.py` (transport map for `color_image` in data-collection, `camera_key` in both policy blueprints).
5. Update tests (`test_node.py`, `test_recorder.py`, blueprint smoke tests).
6. `openspec validate simplify-single-camera-input --strict`.

Rollback strategy: revert the commit. Existing `.rrd` files stay readable — `PiperRobotContract.from_rerun_row` still reads `/observation/camera/usb`, which is the entity path the new typed slot writes. No data migration.

## Open Questions

- **Does the recorder's typed `color_image` need backpressure or rate-limiting**? The existing camera path was running through `pubsubs[0].subscribe_all` with whatever queueing LCM provided. The typed slot uses the framework's `In[Image]` machinery, which has standard `backpressure()` semantics. Probably equivalent in practice; flag for verification under sustained recording load.
- **Should `camera_entity_path` default to `/observation/images.usb`** (newer LeRobot schema, matching the dataset feature key) instead of `/observation/camera/usb` (the current path on disk)? Out of scope here — keeping the current path preserves replay compatibility. A future schema-alignment change can flip the default.
