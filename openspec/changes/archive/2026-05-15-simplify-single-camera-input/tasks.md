## 1. PolicyNode: shrink to single camera

- [x] 1.1 In `dimos/manipulation/policy/config.py`: remove `ALLOWED_CAMERA_SLOTS` constant, remove `camera_sources` field, add `camera_key: str = "main"`. Update the validator to drop the `bad_slots` check (no longer needed)
- [x] 1.2 Update the `PolicyNodeConfig` docstring section on cameras to describe the single-camera `image` slot and `camera_key`
- [x] 1.3 In `dimos/manipulation/policy/node.py`: remove `image_aux1: In[Image]` and `image_aux2: In[Image]` class annotations; remove the `_IMAGE_SLOT_NAMES` module constant
- [x] 1.4 Simplify `_subscribe_inputs`: subscribe only to `self.image` via a single handler, drop the per-slot loop
- [x] 1.5 Replace `self._latest_images: dict[str, Image]` with `self._latest_image: Image | None`; update `_on_image(msg)` accordingly (drop the cam_key parameter and `_make_image_handler`)
- [x] 1.6 Update `assemble_observation()` to build `images={self.config.camera_key: self._latest_image}` when an image is cached, else `images={}`
- [x] 1.7 Update the `latest()` helper return shape to expose `image` as a scalar (or keep `images` dict with at most one entry) — pick whichever is least surprising for existing test consumers and document the call
- [x] 1.8 Remove the `ALLOWED_CAMERA_SLOTS` and `CommandMode` re-exports if `CommandMode` is also unrelated; otherwise keep them — only `ALLOWED_CAMERA_SLOTS` is removed

## 2. RerunDataRecorder: add typed camera slot

- [x] 2.1 In `dimos/visualization/rerun/recorder.py`: add `color_image: In[Image]` as a class-level annotation on `RerunDataRecorder`
- [x] 2.2 In `RerunDataRecorderConfig`: add `camera_entity_path: str = "/observation/camera/usb"`
- [x] 2.3 In `RerunDataRecorder.start()`: subscribe `self.color_image` to a new `_on_color_image(image)` handler; register the resulting disposable via `register_disposable(...)`
- [x] 2.4 Implement `_on_color_image(image)`: under `self._record_lock`, if `self._record_stream is not None` then call `rr.log(self.config.camera_entity_path, <archetype-from-image>, recording=stream)` and set `self._current_nonempty = True`. Use the same archetype path the generic flow uses today (look up how `_on_message` handles `Image`-typed values — the existing converter chain returns an Archetype via `RerunConvertible.to_rerun()` or `final_convert`)
- [x] 2.5 Confirm that the `Image` LCM message type satisfies `is_rerun_multi` is False and that `RerunConvertible` is implemented or `final_convert` produces the right archetype; reuse `self._compose_converter(self.config.camera_entity_path)` so converter chaining (no-op visual_override etc.) still applies if desired — OR call the converter pipeline directly for the typed path so behavior is decoupled from `visual_override` patterns
- [x] 2.6 Update the `RerunDataRecorder` class docstring to describe the typed `color_image` input vs the generic `pubsubs` path

## 3. data_collection_vis: drop camera-specific constants

- [x] 3.1 In `dimos/teleop/quest/data_collection_vis.py`: remove the `CAMERA_TOPIC` and `CAMERA_RECORDED_ENTITY_PATH` module constants
- [x] 3.2 Remove the `if name == CAMERA_TOPIC: return CAMERA_RECORDED_ENTITY_PATH` branch from `_piper_data_collection_topic_to_entity`
- [x] 3.3 Update `piper_data_collection_rerun_blueprint` to reference `"/observation/camera/usb"` directly (or pull from a small local constant) for the Rerun layout's `Spatial2DView(origin=...)`
- [x] 3.4 Confirm `piper_data_collection_rerun_config(...)` still works — it just stops contributing a camera branch to `topic_to_entity`. Joint-state visual overrides and recorder-only fields stay
- [x] 3.5 Update the module docstring to reflect that the camera path no longer goes through `topic_to_entity`

## 4. Blueprints: rewire camera + camera_key

- [x] 4.1 In `dimos/teleop/quest/blueprints.py` `teleop_quest_piper_data_collection`: confirm `CameraModule.color_image` and `RerunDataRecorder.color_image` autoconnect by name+type without an explicit remap; if a remap is required, add one
- [x] 4.2 Keep the transport map entry `("color_image", Image): LCMTransport("/piper_data_collection/color_image", Image)` — the LCM topic name is preserved
- [x] 4.3 Pass `camera_entity_path="/observation/camera/usb"` to `RerunDataRecorder.blueprint(...)` (explicit even though it's the default)
- [x] 4.4 In `_piper_policy_deployment`: keep the `.remappings([(PolicyNode, "image", "color_image")])` block (it's still how the typed `image` slot reaches `CameraModule.color_image`)
- [x] 4.5 In both `teleop_quest_piper_policy` and `teleop_quest_piper_policy_test`: replace `camera_sources={"image": "usb"}` with `camera_key="usb"`
- [x] 4.6 Grep for any other references to `camera_sources` / `image_aux1` / `image_aux2` / `ALLOWED_CAMERA_SLOTS` in the repo and update or delete

## 5. Tests

- [x] 5.1 Update `dimos/manipulation/policy/test_node.py::test_observation_assembly_with_multi_camera_inputs`: rename to `test_observation_assembly_with_single_camera_input`; assert `obs.images == {"main": <image>}` (or `"usb"` with appropriate `camera_key`)
- [x] 5.2 Update any test that constructs `PolicyNodeConfig(camera_sources=...)` to use `camera_key=...` instead
- [x] 5.3 In `test_blueprints.py` (or wherever the data-collection blueprint is exercised): assert that `RerunDataRecorder` deployed via the data-collection blueprint has a wired `color_image` input
- [x] 5.4 Add a recorder unit test: construct a `RerunDataRecorder` with a known `camera_entity_path`, simulate publishing an `Image` to its `color_image` stream while RECORDING, assert exactly one log under the configured entity path
- [x] 5.5 Add a recorder unit test for the no-double-logging invariant: register a `topic_to_entity` callback that would map to `/observation/camera/usb`, publish via the generic `pubsubs` path AND via `color_image`, assert only the typed path logged (or the blueprint-level rule prevents both paths being active — pick whichever the implementation enforces)
- [x] 5.6 Run `pytest dimos/manipulation/policy dimos/visualization/rerun dimos/teleop/quest` and confirm green

## 6. Documentation and validation

- [x] 6.1 Update `PolicyNode` docstring (the module-level docstring at the top of node.py) to reflect single-camera shape
- [x] 6.2 Update `RerunDataRecorder` module docstring noting the typed camera path vs the generic pubsub path
- [x] 6.3 Run `openspec validate simplify-single-camera-input --strict` and confirm green
- [x] 6.4 Run a smoke check that `teleop_quest_piper_data_collection` and `teleop_quest_piper_policy_test` both build (the blueprint config validates) — no need to actually deploy hardware
