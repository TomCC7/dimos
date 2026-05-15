## Why

Piper Quest teleop still uses the older `TeleopIKTask` path while XArm7 uses the Pink-backed teleop task, so single-arm teleop behavior is split across two IK implementations. Adding a shared Pink single-arm task lets Piper use the same solver, safety, gripper, and Quest routing contract while keeping robot-specific frames and model details configurable.

## What Changes

- Add a shared Pink single-frame teleop task/configuration that covers single-arm robots instead of keeping XArm7 behavior in an XArm-only concrete class.
- Preserve the existing XArm7 Pink teleop behavior by making XArm7 a configured instance or thin subclass of the shared single-arm task.
- Add Piper Pink teleop support with Piper-specific model path, controlled joints, end-effector frame, controller hand, gripper settings, and simulator/hardware adapter wiring.
- Modify `teleop_quest_piper` to route Quest input to the Piper Pink IK task while keeping the existing `/coordinator/cartesian_command` and `/teleop/buttons` surface.
- Keep existing non-Pink `teleop_ik` task support available for other paths until they are explicitly migrated.

## Capabilities

### New Capabilities
- `single-arm-pink-teleop`: Shared Pink-backed Quest teleop IK for configurable single-arm robots, including Piper.

### Modified Capabilities
- `pink-teleop-ik`: Existing Pink teleop behavior expands from XArm7-specific support to reusable single-arm robot support while preserving XArm7 behavior.

## Impact

- Affected code: `dimos/control/tasks/pink_teleop_task.py`, `dimos/control/coordinator.py`, `dimos/control/blueprints/teleop.py`, `dimos/teleop/quest/blueprints.py`, `dimos/robot/catalog/piper.py`, `dimos/robot/catalog/ufactory.py`, tests under `dimos/control/tasks/`, and generated blueprint registry if public blueprint names change.
- Public behavior: `dimos --simulation run teleop-quest-piper` and `dimos run teleop-quest-piper` should drive Piper through Pink IK instead of the legacy Pinocchio teleop task.
- Configuration surface: robot model path, joint names, task name, controller hand, end-effector frame, gripper joint/open/closed positions, solver, timeout, per-tick joint delta, frame task costs, posture objective, damping objective, adapter type/address, and simulation backend remain explicit per robot.
- Dependencies: no new third-party dependency is expected because Pink, Pinocchio, and qpsolvers are already used by the existing Pink teleop task.
