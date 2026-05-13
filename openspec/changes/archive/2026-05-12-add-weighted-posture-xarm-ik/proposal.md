## Why

The current XArm7 Pink IK task solves only the end-effector frame target, so reachable teleop commands can still produce unnecessarily large or unnatural arm motion when multiple joint configurations satisfy the same Cartesian goal. Adding a posture objective gives the solver a configurable preference for staying near a natural/rest pose while preserving the frame task as the primary behavior.

## What Changes

- Add an optional weighted posture objective to the XArm7 Pink IK problem so lower-priority joint preferences bias redundant IK solutions toward natural, small-movement postures.
- Expose posture cost, damping, gain, reference posture, and per-joint weights through the existing Pink IK task configuration path.
- Keep end-effector reachability and existing safety behavior intact: frame targets remain active, solver failures still publish no command, and per-tick joint delta checks still gate outputs.
- Add coverage showing the posture task is constructed, tracks the current/reference posture correctly, and does not replace the XArm7 frame task.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `pink-teleop-ik`: XArm7 Pink IK gains an optional weighted posture objective for natural, smaller-motion IK solutions while preserving the existing teleop frame-target contract.

## Impact

- Affected code: `dimos/control/tasks/pink_teleop_task.py`, `dimos/control/pink_ik_visualization.py`, and Pink IK tests under `dimos/control/tasks/`.
- Affected APIs: `PinkIKTaskConfig` / `XArm7IKTaskConfig` gain posture-related configuration fields; existing defaults must preserve current behavior unless posture is explicitly enabled or defaulted by design.
- Dependencies: uses existing `pink.tasks.PostureTask`, `pink.solve_ik`, Pinocchio model ordering, and installed `qpsolvers` backends; no new runtime dependency is expected.
- Systems: XArm7 teleop and visualization paths that instantiate `XArm7IKTask` may need to pass or surface the posture configuration.
