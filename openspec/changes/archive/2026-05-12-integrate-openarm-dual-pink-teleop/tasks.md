## 1. Unified OpenArm Pink IK Core

- [x] 1.1 Add OpenArm whole-robot Pink IK config defaults that use the bimanual OpenArm model path, full controlled joint list, left/right end-effector frames, solver, damping, per-target costs, gain, timeout, and per-tick joint delta limit.
- [x] 1.2 Export or expose the bimanual OpenArm FK/URDF model path from the OpenArm catalog if needed so the IK task and Rerun blueprint do not depend on private catalog constants.
- [x] 1.3 Implement a unified OpenArm Pink IK task by reusing shared `BasePinkIKTask` plumbing while constructing two `FrameTask` targets in one Pink problem over one robot configuration.
- [x] 1.4 Validate configured whole-robot OpenArm joints and both end-effector frames at startup with clear errors for missing model names.
- [x] 1.5 Register the unified OpenArm Pink IK task type in the ControlCoordinator task factory if coordinator execution is needed beyond desired-state visualization.
- [x] 1.6 Add unit coverage for unified OpenArm Pink IK construction, frame validation, shared-configuration solving, and named whole-robot joint output ordering using the in-repo OpenArm model assets.

## 2. Desired-State Visualization Module

- [x] 2.1 Add an OpenArm dual Pink desired-state module that owns one unified OpenArm Pink IK task with left and right target slots.
- [x] 2.2 Route incoming `PoseStamped` commands by `frame_id` so `teleop_openarm_left` updates the left target slot and `teleop_openarm_right` updates the right target slot before running the unified solve.
- [x] 2.3 Maintain one whole-robot desired-position map and publish named `JointState` messages from the unified Pink configuration.
- [x] 2.4 Publish distinct left/right debug controller, target, and end-effector `PoseStamped` outputs for Rerun visualization.
- [x] 2.5 Add focused tests or a driver check for left-only, right-only, simultaneous/alternating hand updates, and preservation of the other target slot during one-hand updates.

## 3. Quest/Rerun Blueprint

- [x] 3.1 Add `teleop_quest_openarm_rerun` in `dimos/teleop/quest/blueprints.py` using `ArmTeleopModule.blueprint(task_names={"left": "teleop_openarm_left", "right": "teleop_openarm_right"})`.
- [x] 3.2 Compose the unified OpenArm dual desired-state module, `RerunUrdfRobotVisualizer`, and `vis_module("rerun")` without OpenArm CAN hardware adapters.
- [x] 3.3 Wire LCM transports for left/right controller outputs, buttons, desired joint state, and debug pose streams using existing teleop topic conventions.
- [x] 3.4 Configure Rerun entity paths and end-effector frames so left/right OpenArm debug poses do not overwrite each other.
- [x] 3.5 Keep `teleop_quest_xarm7_rerun` unchanged and verify its registry key still resolves under `--listen-host 0.0.0.0 --simulation`.

## 4. Registry, Documentation, and Tests

- [x] 4.1 Export the new blueprint in `dimos/teleop/quest/blueprints.py.__all__`.
- [x] 4.2 Simplify Rerun URDF joint-name normalization to use the suffix after `/` by default, while leaving names without `/` unchanged.
- [x] 4.3 Add or update Rerun visualizer tests for `arm/joint1 -> joint1`, `left_arm/joint1 -> joint1`, and `openarm_left_joint1 -> openarm_left_joint1`.
- [x] 4.4 Extend `dimos/teleop/quest/test_rerun_blueprints.py` to smoke-test the OpenArm Rerun blueprint module composition.
- [x] 4.5 Regenerate `dimos/robot/all_blueprints.py` with `pytest dimos/robot/test_all_blueprints_generation.py` so `teleop-quest-openarm-rerun` is available to the CLI.
- [x] 4.6 Update teleop/OpenArm documentation or README command examples to mention `dimos --listen-host 0.0.0.0 --simulation run teleop-quest-openarm-rerun` and clarify that it is a Rerun desired-state simulation/debug example.

## 5. Verification

- [x] 5.1 Run LSP diagnostics on all changed Python files.
- [x] 5.2 Run focused tests for Pink IK tasks, Quest Rerun blueprints, and blueprint registry generation.
- [x] 5.3 Manually QA the CLI surface by resolving or launching `dimos --listen-host 0.0.0.0 --simulation run teleop-quest-openarm-rerun` far enough to confirm blueprint/module construction without physical OpenArm hardware.
- [x] 5.4 Manually QA the existing `dimos --listen-host 0.0.0.0 --simulation run teleop-quest-xarm7-rerun` surface still resolves after registry regeneration.
