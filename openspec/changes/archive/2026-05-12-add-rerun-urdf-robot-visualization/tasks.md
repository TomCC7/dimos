## 1. Rerun URDF Visualization Core

- [x] 1.1 Add a reusable Rerun URDF robot visualization module/helper under `dimos/visualization/rerun/` with configuration for URDF path, entity path prefix, frame prefix, joint-name normalization, and optional debug frame names.
- [x] 1.2 Validate configured URDF paths at startup and load the URDF with `rr.log_file_from_path()` and `rr.urdf.UrdfTree.from_file_path()`.
- [x] 1.3 Build and cache a URDF joint lookup by joint name for revolute and continuous joints.
- [x] 1.4 Implement `JointState.name` + `JointState.position` mapping to Rerun joint `Transform3D` updates, including prefixed DimOS joint names such as `arm/joint1`.
- [x] 1.5 Preserve previous joint visual state when a `JointState` omits a joint or provides incomplete data, while warning on unmatched joint names.

## 2. Debug Pose and End-Effector Visualization

- [x] 2.1 Add support for logging configured `PoseStamped` debug inputs as distinct Rerun entities for desired controller/target poses.
- [x] 2.2 Add support for logging current or desired end-effector pose as a distinct Rerun entity.
- [x] 2.3 For XArm7 Pink IK debugging, compute the desired end-effector pose from the visualized desired joint configuration and configured end-effector frame when it is not provided as a stream.
- [x] 2.4 Use clear Rerun entity paths and colors/markers so desired target, end-effector pose, and robot joint transforms are visually distinguishable.

## 3. XArm7 Quest Teleop Rerun Debug Path

- [x] 3.1 Add a direct desired-joint-output path for Pink XArm7 IK suitable for visualization without MuJoCo or hardware feedback.
- [x] 3.2 Add `teleop_quest_xarm7_rerun` in `dimos/teleop/quest/blueprints.py` using Quest right-controller routing with `frame_id="teleop_xarm"`.
- [x] 3.3 Wire the new blueprint so Pink IK desired joint positions feed the Rerun URDF robot visualizer directly as `JointState` data.
- [x] 3.4 Preserve existing `teleop_quest_xarm7`, `coordinator_teleop_xarm7`, and generic `teleop_quest_rerun` behavior.
- [x] 3.5 Regenerate `dimos/robot/all_blueprints.py` so `dimos list` includes `teleop-quest-xarm7-rerun`.

## 4. Tests and Validation

- [x] 4.1 Add unit tests that load the XArm7 URDF through Rerun URDF utilities and compute transforms for representative joints.
- [x] 4.2 Add unit tests for `JointState` name-to-URDF joint mapping, including prefixed names, missing joints, and unmatched names.
- [x] 4.3 Add unit tests or smoke coverage for debug `PoseStamped` frame logging conversion.
- [x] 4.4 Add blueprint generation coverage proving `teleop-quest-xarm7-rerun` is registered.
- [x] 4.5 Run focused tests for Rerun visualization helpers, XArm7 teleop blueprint import/listing, and existing control/Pink tests affected by the debug path.
- [ ] 4.6 Manually QA the Rerun surface by running `dimos run teleop-quest-xarm7-rerun`, engaging the right Quest controller, and confirming the Rerun robot updates desired joint configuration immediately while target and end-effector frames are visible.
