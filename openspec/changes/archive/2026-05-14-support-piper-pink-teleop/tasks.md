## 1. Shared Single-Arm Pink Task

- [x] 1.1 Introduce a reusable single-arm Pink teleop config/task in `dimos/control/tasks/pink_teleop_task.py` for one controlled frame and one Quest hand.
- [x] 1.2 Move the XArm7 single-frame target state, engage/disengage handling, baseline capture, frame target update, posture task, damping task, and gripper trigger handling into the shared single-arm implementation.
- [x] 1.3 Keep `XArm7IKTaskConfig` and `XArm7IKTask` as compatibility defaults or thin wrappers over the shared single-arm task.
- [x] 1.4 Validate shared task startup for non-empty joint names, model DOF, configured end-effector frame existence, finite/non-negative solver costs, posture reference names, and posture reference limits.
- [x] 1.5 Preserve existing Pink safety behavior for missing joint state, target timeout, solver failure, non-finite IK output, and max per-tick joint delta rejection.

## 2. Coordinator Configuration and Routing

- [x] 2.1 Extend `TaskConfig` with Pink single-arm fields: `end_effector_frame`, `solver`, `damping`, `position_cost`, `orientation_cost`, `lm_damping`, `gain`, `posture_cost`, `posture_reference`, `posture_lm_damping`, `posture_gain`, and `damping_task_cost`.
- [x] 2.2 Add a reusable `single_arm_pink_ik` coordinator task type that instantiates the shared single-arm Pink task from `TaskConfig`.
- [x] 2.3 Add `single_arm_pink_ik` to coordinator Cartesian-command and teleop-button routing so `PoseStamped.frame_id` and Quest button messages reach the task.
- [x] 2.4 Preserve `xarm7_pink_ik` task creation by mapping it through the shared implementation with XArm7 defaults.
- [x] 2.5 Update docstrings or task configuration comments so the supported task types and Pink-specific fields are discoverable.

## 3. Piper Pink Teleop Blueprint

- [x] 3.1 Verify the correct Piper end-effector frame in gripper-inclusive `PIPER_FK_MODEL` by loading the model and inspecting Pinocchio frame names.
- [x] 3.2 Change `coordinator_teleop_piper` to create a `single_arm_pink_ik` task named `teleop_piper` with `model_path=PIPER_FK_MODEL`, Piper controlled arm joints, `end_effector_frame="gripper_base"`, `hand="left"`, and Piper gripper settings.
- [x] 3.6 Reduce/lock Piper finger joints from the Pink IK model so the six controlled arm joints can target the gripper frame without requiring physical finger joint state.
- [x] 3.3 Keep `teleop_quest_piper` routing unchanged at the public surface: left controller output to `/coordinator/cartesian_command`, `frame_id="teleop_piper"`, and buttons to `/teleop/buttons`.
- [x] 3.4 Preserve Piper real/simulation adapter selection using `_piper_teleop_cfg`, `PIPER_SIM_PATH`, `global_config.can_port`, and existing MuJoCo simulation wiring.
- [x] 3.5 Leave `teleop_quest_xarm6` and `coordinator_teleop_dual` on legacy `teleop_ik` unless explicitly migrated in a later change.

## 4. Tests and Regression Coverage

- [x] 4.1 Add unit tests that the shared single-arm Pink task constructs a `FrameTask` from configurable model path, joint names, and end-effector frame.
- [x] 4.2 Add tests that invalid Piper/XArm-style joint names or missing end-effector frames fail startup with clear errors.
- [x] 4.3 Update existing XArm7 Pink tests so `xarm7_pink_ik` still claims the same arm/gripper resources, accepts `teleop_xarm`, and preserves timeout/safety behavior.
- [x] 4.4 Add Piper Pink tests that `coordinator_teleop_piper` creates a single-arm Pink task named `teleop_piper`, claims Piper arm plus gripper resources, and uses the left controller hand.
- [x] 4.5 Add coordinator routing tests that `single_arm_pink_ik` receives Cartesian commands and Quest buttons through the same paths as existing teleop tasks.
- [x] 4.6 Add or update blueprint tests so `teleop-quest-piper` remains registered and composes the Pink-backed Piper coordinator.

## 5. Verification and Manual QA

- [x] 5.1 Run focused tests for Pink teleop tasks and coordinator task creation.
- [x] 5.2 Run blueprint registry generation/checks if blueprint exports or registrations change.
- [x] 5.3 Run type diagnostics on changed Python files.
- [x] 5.4 Smoke-test `dimos --simulation run teleop-quest-piper` far enough to confirm the blueprint starts, the Quest web teleop surface is available, and Piper Pink IK task construction succeeds.
- [x] 5.5 Exercise the manual teleop surface by publishing or driving a left-controller pose/button sequence and verifying the coordinator accepts the `teleop_piper` Pink target without requiring the right controller.

## 6. Piper No-CAN Visualization Fallback

- [x] 6.1 Update the single-arm Pink teleop spec so non-simulation Piper teleop without a CAN port uses mock hardware plus the existing ManipulationModule Drake/Meshcat visualization.
- [x] 6.2 Configure `coordinator_teleop_piper` to use a mock manipulator adapter when `global_config.can_port` is unset in non-simulation mode.
- [x] 6.3 Compose `ManipulationModule(enable_viz=True)` into `teleop_quest_piper` when Piper is in the no-CAN mock preview mode and connect it to `/coordinator/joint_state`.
- [x] 6.4 Add blueprint tests for no-CAN mock preview, CAN hardware mode, and MuJoCo simulation mode.
- [x] 6.5 Keep `ManipulationModule(enable_viz=True)` wired for non-simulation Piper Quest teleop even when CAN hardware is configured, matching `keyboard_teleop_piper`.
