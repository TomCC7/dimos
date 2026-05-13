## Why

Pink IK tuning options are robot/task implementation details, but they currently leak into `ControlCoordinator` task configuration as a long list of `pink_*` fields. This makes normal coordinator config too verbose for values that are rarely changed and are only meaningful to specific robot IK task implementations.

## What Changes

- Remove robot-specific Pink IK tuning fields from coordinator-level `TaskConfig`.
- Keep only the coordinator inputs needed to select and instantiate a task: task name/type, joints, priority, model path where applicable, gripper settings, timeout, and joint-delta safety limit.
- Move XArm7 Pink defaults for solver damping, end-effector frame, frame costs, gain, posture, and damping-task behavior into `XArm7IKTaskConfig` / `XArm7IKTask`.
- Move OpenArm Pink defaults for target slot names, end-effector frames, solver damping, frame costs, and gain into `OpenArmBimanualIKTaskConfig` / `OpenArmBimanualIKTask`.
- Preserve existing XArm7 and OpenArm Pink teleop behavior by hardcoding the same defaults in the robot-specific task configs instead of passing them through coordinator config.
- Remove tests that assert coordinator-level Pink tuning pass-through, and replace them with task-local default and coordinator construction coverage.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `pink-teleop-ik`: Pink-backed IK tasks will own robot-specific Pink solver/task defaults locally instead of requiring coordinator-level Pink tuning fields.

## Impact

- Affected coordinator code: `dimos/control/coordinator.py`, especially `TaskConfig` and `_create_task_from_config()` branches for `xarm7_pink_ik` and `openarm_bimanual_pink_ik`.
- Affected Pink task code: `dimos/control/tasks/pink_teleop_task.py`, especially `PinkIKTaskConfig`, `XArm7IKTaskConfig`, and `OpenArmBimanualIKTaskConfig` defaults.
- Affected tests: `dimos/control/tasks/test_pink_teleop_task.py` and any coordinator construction tests that configure or assert `pink_*` fields.
- API/config impact: coordinator-level `pink_*` fields are removed from in-repo config surfaces; callers should choose the robot-specific task type rather than tune Pink internals through coordinator config.
- Dependency impact: no new packages.
