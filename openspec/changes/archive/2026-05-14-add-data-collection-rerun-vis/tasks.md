## 1. Joint-name source

- [x] 1.1 Locate the Piper robot model config the data-collection blueprint already imports (currently `piper_teleop_robot_model_config()` in `dimos/control/blueprints/teleop.py`) and confirm it exposes the arm joint names and the gripper joint name (`arm/gripper`).
- [x] 1.2 Add or expose a small helper that returns the ordered list of Piper joint names (arm joints followed by the gripper joint) for reuse by both the visualization override and the preset factory. Place it next to the data-collection blueprint so visualization wiring and layout cannot drift apart.

## 2. JointState visual override

- [x] 2.1 Add a `to_rerun_scalars(joint_state, role, joints)` helper that converts a `JointState` message into a list of `(entity_path, rerun.Scalars)` tuples, one per joint in `joints`, using entity paths of the form `world/piper/<role>/<short_joint_name>` (where `role` ∈ `{measured, commanded}` and `short_joint_name` is the part after the last `/`).
- [x] 2.2 Make the helper robust to messages that carry only a subset of joints: emit a scalar only for joints that are actually present in the incoming message; never raise.
- [x] 2.3 Unit-test the helper: given a synthetic `JointState` with the full Piper joint set (including `arm/gripper`), assert the helper returns one tuple per joint with the expected entity paths and values for both `role="measured"` and `role="commanded"`.

## 3. Rerun blueprint preset factory

- [x] 3.1 Add a `piper_data_collection_rerun_blueprint()` factory that returns a `rerun.blueprint.Blueprint` matching Decision 5 of `design.md`: `Horizontal(Spatial2DView(camera), Vertical(TimeSeriesView per joint), column_shares=[2, 1])` with `auto_layout=False`, `auto_views=False`, `collapse_panels=True`.
- [x] 3.2 Build the per-joint `TimeSeriesView`s from the shared joint-name list (Task 1.2) so the preset stays in sync with the override; each view contains both the measured and commanded entity paths for that joint.
- [x] 3.3 Use the camera image transport's entity path (whatever the bridge derives from the data-collection blueprint's camera image topic) as the `origin` for the `Spatial2DView` — do not hard-code the entity path, derive it from the same source the bridge uses.

## 4. Wire visualization into the blueprint

- [x] 4.1 In `dimos/teleop/quest/blueprints.py`, add `vis_module("rerun", rerun_config={...})` as an atom in the `teleop_quest_piper_data_collection` `autoconnect(...)` call.
- [x] 4.2 Pass the visual-override map into `rerun_config["visual_override"]`: one entry binding the `/coordinator/joint_state` entity-path pattern to the JointState-to-scalars helper with `role="measured"`, and one entry for `/coordinator/desired_joint_action` with `role="commanded"`.
- [x] 4.3 Pass the preset factory from Task 3.1 into `rerun_config["blueprint"]`.
- [x] 4.4 Do NOT alter the existing `transport_map` for `joint_state`, `desired_joint_action`, `right_controller_output`, `buttons`, or `color_image` — the visualization is a sink on the existing topics.

## 5. Tests

- [x] 5.1 Extend `dimos/teleop/quest/test_blueprints.py` so the existing `test_piper_data_collection_blueprint_routes_recorded_streams` style test asserts the blueprint now contains a `RerunBridgeModule` atom in addition to the existing modules (camera, recorder, etc.) and that the `transport_map` is unchanged from before this change for every key it previously had.
- [x] 5.2 Add a test that instantiates the preset factory from Task 3.1 and asserts it returns a `rerun.blueprint.Blueprint` whose container tree contains one `TimeSeriesView` per Piper joint (matching the joint-name source from Task 1.2), with the gripper as the last per-joint view.
- [x] 5.3 Add a test that calls the override helper from Task 2.1 with a synthetic `JointState` covering the full Piper joint set and asserts: (a) one entry per joint, (b) entity paths follow `world/piper/<role>/<short_joint_name>`, (c) the gripper produces an entry under `.../gripper`.

## 6. Manual verification on hardware

- [ ] 6.1 Run `dimos run teleop-quest-piper-data-collection` against a real Piper with a USB camera connected and confirm that the Rerun viewer opens with the camera on the left and per-joint plots on the right, panels do not auto-rearrange as entities arrive, and the gripper plot updates when the operator squeezes/releases the trigger.
- [ ] 6.2 Verify that a recording produced with the visualization sink is byte-identical (or equivalently, that its stream contents match) a recording produced with the visualization atom temporarily removed — confirming visualization is a passive sink.
- [ ] 6.3 Kill the Rerun viewer process mid-session and confirm the data collection blueprint continues to record without raising into the control path; the visualization module should log the disconnect and the rest of the stack should keep running.
