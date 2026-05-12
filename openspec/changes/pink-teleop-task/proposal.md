## Why

DimOS teleoperation currently solves each end-effector target independently with the lightweight in-tree Pinocchio IK solver, which limits coordinated manipulation scenarios where both arms must satisfy targets in a shared optimization problem. Pink provides a task-based differential IK interface on top of Pinocchio that can solve multiple weighted frame targets together, making it a better fit for dual-arm teleop planning.

## What Changes

- Add a Pink-backed teleoperation IK task hierarchy with shared base behavior and an initial XArm7-specific task.
- Implement the first concrete Pink IK path for XArm7 using the right controller pose as the only end-effector target input.
- Preserve the existing control-task behavior expected by `ControlCoordinator`: passive tick-driven `compute()`, resource claims over controlled joints, `state.t_now` timing, joint-level arbitration, and `JointCommandOutput` publication.
- Add Pink as an IK dependency and integrate its `Configuration`, `FrameTask`, and `solve_ik` workflow with DimOS robot model loading and current joint-state warm starts.
- Keep existing XArm7 single-arm teleop routing compatible while leaving dual-arm coordinated solving for a later robot-specific subclass.

## Capabilities

### New Capabilities

- `pink-teleop-ik`: Teleoperation IK task behavior backed by Pink, including shared Pink solver plumbing, an XArm7 concrete IK task driven by the right controller pose, joint command generation, safety delta checks, engage/disengage semantics, and an extension point for future robot-specific or dual-arm subclasses.

### Modified Capabilities

<!-- No existing OpenSpec capabilities are present under openspec/specs/. -->

## Impact

- Affected control task code: `dimos/control/tasks/teleop_task.py`, `dimos/control/task.py`, and related IK utilities under `dimos/manipulation/planning/kinematics/`.
- Affected coordinator/configuration code: `dimos/control/coordinator.py` `TaskConfig` creation and cartesian-command routing, especially the current single `PoseStamped.frame_id == task_name` routing model.
- Affected teleop blueprints: `dimos/control/blueprints/teleop.py` and `dimos/teleop/quest/blueprints.py`, especially `coordinator_teleop_xarm7` and `teleop_quest_xarm7` right-controller routing.
- Dependency impact: add the Pink package (`pin-pink`) and ensure an available QP solver path compatible with project dependency management.
- Testing/validation impact: cover XArm7 single-arm compatibility, right-controller-only IK target updates, missing/stale target handling, resource arbitration, and manual teleop command routing through the coordinator surface.
