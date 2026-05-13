## Context

`dimos/control/tasks/pink_teleop_task.py` already centralizes Pink-backed teleop IK. `BasePinkIKTask` owns configuration updates, `solve_ik(...)`, velocity integration, joint-delta rejection, and coordinator-compatible `JointCommandOutput` generation. `XArm7IKTask` builds one `FrameTask` for `link7` and can append a `WeightedPostureTask` from `_create_extra_tasks()` when `posture_cost > 0.0`.

The requested behavior matches Pink's official `examples/arm_panda.py`, where a 7-DOF arm solves with `[end_effector_task, posture_task, damping_task]` and constructs the damping objective as `DampingTask(cost=1e-3)`. Pink's source defines `DampingTask` as a joint-velocity task that minimizes joint velocity with zero task error, so it does not need per-tick target updates and can be appended during task construction.

## Goals / Non-Goals

**Goals:**

- Add an optional XArm7 joint-velocity damping objective using `pink.tasks.DampingTask`.
- Preserve current XArm7 Pink teleop behavior by defaulting the new damping objective to disabled.
- Keep the implementation aligned with the existing optional posture-task pattern: config field, startup validation, conditional construction in `_create_extra_tasks()`, and focused tests in `dimos/control/tasks/test_pink_teleop_task.py`.
- Preserve existing coordinator safety behavior: missing joint state, stale targets, solver exceptions, non-finite velocities, and unsafe per-tick joint deltas still produce no command.

**Non-Goals:**

- Tuning a production damping cost for every XArm deployment.
- Adding per-joint damping weights or a custom DimOS damping implementation.
- Changing OpenArm Pink IK task behavior.
- Changing Quest teleop routing, frame-task target semantics, or the global Pink solver damping passed to `solve_ik()`.

## Decisions

### Use Pink's `DampingTask` directly

Import `DampingTask` from `pink.tasks` next to `FrameTask` and `PostureTask`. This follows the upstream arm example and avoids duplicating Pink's joint-velocity objective in DimOS.

Alternative considered: create a local weighted damping task class. That is unnecessary for the requested behavior and would introduce another objective implementation to maintain.

### Add `damping_task_cost` to `XArm7IKTaskConfig`

The new field should live on the XArm7 config rather than the shared `PinkIKTaskConfig` because the request is XArm-specific and OpenArm does not currently need this objective. The field should default to `0.0`; values `<= 0.0` disable task creation, while positive values construct `DampingTask(cost=...)`.

Alternative considered: reuse the existing `damping` field. That field is already passed to `solve_ik(..., damping=...)` as QP/solver regularization, not as a Pink task objective, so overloading it would make configuration ambiguous.

### Append damping in XArm extra tasks

`XArm7IKTask._create_extra_tasks()` should continue returning optional non-frame Pink tasks. It should build a list, append the existing `WeightedPostureTask` when `posture_cost > 0.0`, and append `DampingTask` when `damping_task_cost > 0.0`. No update hook is needed for damping because Pink's `DampingTask.compute_error()` returns zeros and its Jacobian comes from `JointVelocityTask`.

Alternative considered: add a new base-class hook dedicated to damping. The existing `_create_extra_tasks()` hook is sufficient and keeps the change small.

### Validate numeric configuration at startup

`_validate_numeric_config()` should reject non-finite or negative damping-task cost values using the existing `_require_non_negative(...)` helper. A zero value remains valid and means disabled.

Alternative considered: validate only when task construction reaches `_create_extra_tasks()`. Centralizing validation with the existing XArm numeric checks gives clearer startup failures and matches the posture validation style.

## Risks / Trade-offs

- Damping cost tuning is robot- and task-dependent → default to disabled and make the field explicit so deployments opt in after testing.
- Additional task cost can reduce responsiveness if set too high → document/test only objective inclusion, not a universal recommended value.
- Pink API changes could rename or move `DampingTask` → keep the implementation as a direct import from the same `pink.tasks` namespace used by the upstream example and existing DimOS imports.
- Damping plus posture changes the optimization problem shape → reuse existing safety checks and add tests that solver failure and unsafe deltas still return no command with damping enabled.
