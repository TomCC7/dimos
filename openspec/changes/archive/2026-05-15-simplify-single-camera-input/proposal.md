## Why

`PolicyNode` carries three `In[Image]` slots (`image`, `image_aux1`, `image_aux2`) and a `camera_sources: dict[str, str]` slot-to-cam-key mapping (config.py:30, 78; node.py:108-110) — scaffolding for a multi-camera future that no production blueprint exercises. Both `_aux` slots are dead in `dimos/teleop/quest/blueprints.py`; the only real configuration is `camera_sources={"image": "usb"}` on the policy deployment.

`RerunDataRecorder` makes the inverse trade: it has *no* typed camera input. The camera path goes through `pubsubs: list[SubscribeAllCapable]` + `topic_to_entity` (recorder.py:62-73, data_collection_vis.py:68-69, 232-243) — fully general, but the camera's identity is implicit in a callback and a string-matched LCM topic name. The single camera the system actually has is hidden behind two redirections.

Both modules are over-shaped for a single-camera reality. Simplifying them now — typed single-camera input on each — lands a clearer baseline. When a deployment actually needs multi-camera, a future change can extend either module from a clean starting point, instead of competing with leftover speculative scaffolding.

## What Changes

- **BREAKING**: `PolicyNode` drops the `image_aux1: In[Image]` and `image_aux2: In[Image]` class-level slots, the `ALLOWED_CAMERA_SLOTS` module constant, and the `camera_sources: dict[str, str]` config field.
- `PolicyNode` keeps a single `image: In[Image]` slot. Adds a `camera_key: str = "main"` config field — the key the backend sees in `PolicyObservation.images`. The node assembles `{camera_key: image}` when `image` has produced a value.
- **NEW**: `RerunDataRecorder` gains a single typed `color_image: In[Image]` slot for the camera path. Adds a `camera_entity_path: str = "/observation/camera/usb"` config field naming the entity path under which incoming images are logged.
- `RerunDataRecorder` keeps `pubsubs` / `topic_to_entity` / `visual_override` exactly as today for everything that is NOT the camera image (joint state scalars, action scalars, episode metadata). Only the camera path moves to the typed slot.
- `data_collection_vis.py` drops the `CAMERA_TOPIC` / `CAMERA_RECORDED_ENTITY_PATH` module constants and the camera branch of `_piper_data_collection_topic_to_entity`. The joint-scalar visual overrides stay.
- The `teleop_quest_piper_data_collection` blueprint wires `RerunDataRecorder.color_image` to the same LCM camera transport via the standard blueprint transport map (the camera topic is no longer named in `topic_to_entity`).
- The `teleop_quest_piper_policy*` blueprints replace `camera_sources={"image": "usb"}` with `camera_key="usb"`. The existing `(PolicyNode, "image", "color_image")` blueprint remap stays — that's how the single camera reaches the typed `image` slot.
- `PiperRobotContract` is unchanged. Its `cameras={"usb": (480, 640, 3)}` default already represents single-camera behavior; the multi-camera dict shape stays on the contract for future use without forcing it on the runtime modules.

## Capabilities

### New Capabilities

(None.)

### Modified Capabilities

- `policy-node`: The "Policy node exposes unified observation inputs" requirement rolls back from "multi-camera image inputs" to "a single typed camera image input"; the multi-camera scenario is replaced by a single-camera scenario.
- `piper-data-collection`: The "Data collection records camera observation" requirement keeps its semantics (one camera, logged under `/observation/camera/usb`) but the wiring contract changes — the camera arrives through the recorder's typed `color_image` input rather than through `topic_to_entity` matching on the LCM topic name.

## Impact

- **Code**:
  - `dimos/manipulation/policy/config.py` — drop `ALLOWED_CAMERA_SLOTS` + `camera_sources`; add `camera_key`.
  - `dimos/manipulation/policy/node.py` — drop `image_aux1`, `image_aux2`, `_IMAGE_SLOT_NAMES`; simplify `_subscribe_inputs` + `assemble_observation`.
  - `dimos/visualization/rerun/recorder.py` — add `color_image: In[Image]` + `camera_entity_path` config + subscription that logs to the configured entity path.
  - `dimos/teleop/quest/data_collection_vis.py` — drop `CAMERA_TOPIC` / `CAMERA_RECORDED_ENTITY_PATH` + the camera branch of `_piper_data_collection_topic_to_entity`.
  - `dimos/teleop/quest/blueprints.py` — wire `RerunDataRecorder.color_image` to the camera LCM topic in the data-collection blueprint; replace `camera_sources={"image": "usb"}` with `camera_key="usb"` in both policy blueprints.
- **APIs**: `PolicyNodeConfig.camera_sources` and the `image_aux1` / `image_aux2` stream slots are removed (breaking). The recorder gains a new `In[Image]` slot and a new config field.
- **Dependencies**: None new.
- **Tests**: `test_node.py::test_observation_assembly_with_multi_camera_inputs` is rewritten as a single-camera assembly test. Recorder tests gain a `color_image` typed-input case.
- **Specs**: rolls back the multi-camera commitment in `policy-node` and re-pins `piper-data-collection` to a typed camera input — both honest about what the codebase actually ships.
- **Deferred**: any multi-camera support. Re-add as a future change when there's a concrete deployment requirement (wrist + overhead, stereo, etc.), at which point the typed `image` / `color_image` slots become the starting point of either an N-slot expansion or a config-driven dict.
