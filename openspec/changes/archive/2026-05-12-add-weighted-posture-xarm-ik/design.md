## Context

`XArm7IKTask` currently builds one Pink `FrameTask` for the configured end-effector frame and passes that task list to `pink.solve_ik` each coordinator tick. The task warm-starts Pink from the current coordinator joint state, updates the frame target from the delta-based Quest controller contract, integrates the returned velocity, and rejects outputs that exceed `max_joint_delta_deg`.

This frame-only objective is sufficient for reachability but underconstrains redundant arm motion. The referenced GR00T WholeBodyControl solver addresses a similar issue by subclassing Pink `PostureTask` and applying per-joint weights to both posture error and posture Jacobian, then solving that posture objective together with frame tasks. DimOS can use the same concept through the existing Pink dependency without adopting the upstream solver structure.

## Goals / Non-Goals

**Goals:**

- Bias XArm7 IK toward more natural and smaller joint motion while keeping the Cartesian frame task active.
- Make posture behavior configurable per task, including objective cost, Levenberg-Marquardt damping, gain, reference posture, and per-joint weights.
- Preserve existing teleop contracts: route key, delta-based target interpretation, current-joint warm start, solver failure behavior, and joint-delta safety checks.
- Keep the implementation local to the Pink IK task path so existing coordinator arbitration and command output remain unchanged.

**Non-Goals:**

- Replacing Pink or changing the QP backend selection strategy.
- Importing or vendoring GR00T WholeBodyControl code.
- Adding a global whole-body posture controller, collision avoidance, or trajectory smoothing layer.
- Changing the xArm hardware adapter, controller mode, or Quest input message schema.

## Decisions

1. **Implement a local weighted posture task by subclassing Pink `PostureTask`.**
   - Rationale: Pink already provides posture residuals and Jacobians in model order; weighting those arrays locally matches the referenced approach while avoiding a new dependency or copied solver architecture.
   - Alternative considered: use plain Pink `PostureTask` with a scalar cost only. That cannot make some xArm joints more resistant to motion than others and does not satisfy the weighted-posture requirement.

2. **Append posture as an extra Pink task alongside the existing frame task.**
   - Rationale: `BasePinkIKTask` already composes `self._pink_tasks = [*self._frame_tasks, *self._create_extra_tasks()]`, so posture fits the existing extension seam and preserves the XArm7 frame task.
   - Alternative considered: post-process the integrated IK solution toward a reference posture. That would fight Pink's constrained solve and could invalidate the frame target or safety checks.

3. **Use full-model posture vectors with active-joint configuration fields.**
   - Rationale: Pink `Configuration` and `PostureTask` operate in Pinocchio model order, while DimOS command output uses configured xArm joint names. The implementation should map user-facing joint names to Pinocchio indices once during construction, then build full-length reference and weight vectors for the Pink task.
   - Alternative considered: weight only the command-output array after solve. That misses Pink's internal joint ordering and cannot affect the QP objective correctly.

4. **Default posture reference to the task's current joint state on first valid compute, with optional configured overrides.**
   - Rationale: current-posture default minimizes motion when teleop engages and avoids surprising jumps to a hardcoded pose. Optional reference values allow teams to tune a natural xArm rest posture when desired.
   - Alternative considered: always use `pinocchio.neutral(model)` as the target. For hardware teleop this can cause immediate bias toward a pose unrelated to the arm's engagement posture.

5. **Keep posture weaker than frame tracking and safety gates.**
   - Rationale: the feature should make redundant solutions more natural, not make reachable frame goals unsolvable. Configuration should use posture as a secondary cost and still reject unsafe per-tick deltas after integration.
   - Alternative considered: introduce hard joint-lock constraints for low-motion behavior. That would reduce reachability and is outside the stated need.

## Risks / Trade-offs

- **Poorly tuned posture cost can reduce frame accuracy** → Start with conservative defaults, keep all fields configurable, and test that the frame task remains in the task list.
- **Joint-name to Pinocchio-index mapping mistakes can bias the wrong joint** → Reuse existing model joint-name validation, add tests for configured per-joint weights/reference mapping, and fail fast on unknown posture keys.
- **Current-posture default may preserve an already awkward pose** → Allow explicit reference posture overrides for deployments that prefer a known natural pose.
- **Posture target updates at the wrong time can chase the solution instead of regularizing it** → Set the posture target only when configured reference changes or when a new engagement/current-joint baseline is established, not every integration step unless explicitly intended.

## Migration Plan

- Add posture fields with defaults that preserve existing behavior until posture is enabled or tuned.
- Surface the same fields in `XArm7PinkIkDesiredStateConfig` so visualization and live teleop can be configured consistently.
- Existing blueprints continue to instantiate `XArm7IKTask` with the same required arguments; rollback is disabling posture by setting its cost to zero or removing the extra task from configuration.

## Open Questions

- Exact production posture defaults should be validated on real xArm hardware; the implementation should make them easy to tune without changing code.
