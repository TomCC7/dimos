## 1. Weighted Posture Task Core

- [x] 1.1 Add a local `WeightedPostureTask` subclass in `dimos/control/tasks/pink_teleop_task.py` that extends Pink `PostureTask` and applies per-joint weights to both `compute_error` and `compute_jacobian`.
- [x] 1.2 Add posture configuration fields to `PinkIKTaskConfig` / `XArm7IKTaskConfig` for enablement or cost, default weight, per-joint weights, reference posture, LM damping, and gain.
- [x] 1.3 Implement XArm7 joint-name to Pinocchio model-index mapping for posture weights and references, including startup validation for unknown posture joint names.

## 2. Solver Integration

- [x] 2.1 Extend `XArm7IKTask._create_extra_tasks()` to include the weighted posture task when posture is enabled while preserving the existing frame task.
- [x] 2.2 Initialize the posture target from the first valid current joint state by default, and merge configured reference posture values when provided.
- [x] 2.3 Ensure target timeout, solver exception handling, and `max_joint_delta_deg` rejection continue to apply to posture-enabled solves.

## 3. Configuration Surfaces

- [x] 3.1 Surface posture fields through `XArm7PinkIkDesiredStateConfig` and pass them into `XArm7IKTaskConfig` for visualization parity.
- [x] 3.2 Update any coordinator task factory/config mapping needed so `xarm7_pink_ik` task configs can provide posture options without changing existing route keys or message types.

## 4. Verification

- [x] 4.1 Add tests for weighted posture task construction, disabled posture behavior, and preservation of the frame task in the Pink solve task list.
- [x] 4.2 Add tests for per-joint weight/reference mapping and failure on unknown posture joint names.
- [x] 4.3 Add tests or extend existing tests proving posture-enabled unsafe deltas and solver failures still return no command.
- [x] 4.4 Run `uv run pytest dimos/control/tasks/test_pink_teleop_task.py -v` and any affected visualization/coordinator tests.
