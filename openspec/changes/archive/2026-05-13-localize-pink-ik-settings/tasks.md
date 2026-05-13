## 1. Coordinator Config Simplification

- [x] 1.1 Remove Pink-specific fields from `TaskConfig` in `dimos/control/coordinator.py`, including solver, damping, frame, target-slot, objective-cost, posture, and damping-task fields.
- [x] 1.2 Keep generic task construction fields that are still coordinator concerns: task name/type, joint names, priority, model path, hand, gripper settings, timeout, and max joint delta.
- [x] 1.3 Update `ControlCoordinator._create_task_from_config()` for `xarm7_pink_ik` to stop passing removed `pink_*` fields and rely on `XArm7IKTaskConfig` defaults for Pink internals.
- [x] 1.4 Update `ControlCoordinator._create_task_from_config()` for `openarm_bimanual_pink_ik` to stop passing removed `pink_*` fields and rely on `OpenArmBimanualIKTaskConfig` defaults for Pink internals.

## 2. Task-Local Pink Defaults

- [x] 2.1 Confirm `XArm7IKTaskConfig` contains the previous effective XArm7 defaults for solver damping, `link7` frame, frame costs, LM damping, gain, posture settings, and damping-task cost.
- [x] 2.2 Confirm `OpenArmBimanualIKTaskConfig` contains the previous effective OpenArm defaults for joint names, target task names, end-effector frames, solver damping, frame costs, LM damping, and gain.
- [x] 2.3 Move any remaining coordinator-only fallback constants for Pink frames or target names into the corresponding task config defaults.
- [x] 2.4 Keep direct task config tuning available in the robot-specific config dataclasses where tests or future robot-specific code need it.

## 3. Tests and Verification

- [x] 3.1 Update Pink task tests that instantiate `TaskConfig` to stop using removed coordinator-level `pink_*` fields.
- [x] 3.2 Add or update tests showing coordinator-created XArm7 Pink tasks use task-local defaults for frame name and optional posture/damping behavior.
- [x] 3.3 Add or update tests showing coordinator-created OpenArm Pink tasks use task-local defaults for target slot names and left/right frame names.
- [x] 3.4 Keep focused direct-task tests for posture weighting, posture references, solver failure, damping-task inclusion, and invalid task-local numeric values.
- [x] 3.5 Run `uv run pytest dimos/control/tasks/test_pink_teleop_task.py -v` and targeted diagnostics for changed files.

## 4. Manual QA

- [x] 4.1 Drive the coordinator construction surface with minimal `TaskConfig(type="xarm7_pink_ik", ...)` and confirm an `XArm7IKTask` is created and computes through the existing safe command/no-command path without coordinator Pink fields.
- [x] 4.2 Drive the coordinator construction surface with minimal `TaskConfig(type="openarm_bimanual_pink_ik", ...)` and confirm an `OpenArmBimanualIKTask` is created with the expected left/right target route keys without coordinator Pink fields.
