## Why

The XArm7 Pink teleop task currently balances only the end-effector frame objective and optional posture objective, so redundant joint motion can remain under-regularized during Cartesian teleoperation. Pink's own 7-DOF arm example includes a `DampingTask` alongside `FrameTask` and `PostureTask` to minimize unnecessary joint velocities, and XArm7 should expose the same stabilizing objective through DimOS task configuration.

## What Changes

- Add optional XArm7 Pink joint-velocity damping support based on `pink.tasks.DampingTask`.
- Extend XArm7 Pink IK configuration with a non-negative damping-task cost that defaults to disabled to preserve current behavior.
- Include the damping task in the XArm7 Pink task list when enabled, alongside the existing frame task and optional weighted posture task.
- Validate the new damping configuration during XArm7 task startup and keep existing solver failure, timeout, and joint-delta safety behavior unchanged.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `pink-teleop-ik`: Add optional XArm7 Pink joint-velocity damping behavior to the existing Pink-backed teleoperation IK capability.

## Impact

- Affected control task code: `dimos/control/tasks/pink_teleop_task.py`, especially `XArm7IKTaskConfig`, `XArm7IKTask._create_extra_tasks()`, and XArm7 numeric validation.
- Affected tests/validation: XArm7 Pink task construction should cover damping disabled by default, damping task inclusion when configured, invalid damping cost rejection, and preservation of compute safety behavior.
- Dependency impact: no new package is expected because DimOS already depends on Pink for `FrameTask`, `PostureTask`, and `solve_ik`; the implementation only imports another Pink task class.
