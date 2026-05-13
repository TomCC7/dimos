## 1. XArm Damping Configuration

- [x] 1.1 Import `DampingTask` from `pink.tasks` in `dimos/control/tasks/pink_teleop_task.py` alongside the existing Pink task imports.
- [x] 1.2 Add `damping_task_cost: float = 0.0` to `XArm7IKTaskConfig` so damping is opt-in and existing XArm Pink teleop behavior remains unchanged by default.
- [x] 1.3 Validate `damping_task_cost` in the XArm7 numeric config path with the existing non-negative finite-value helper.

## 2. XArm Damping Task Construction

- [x] 2.1 Refactor `XArm7IKTask._create_extra_tasks()` to build a list of optional extra Pink tasks instead of returning immediately for posture-disabled cases.
- [x] 2.2 Preserve existing weighted posture construction and target-update behavior when `posture_cost > 0.0`.
- [x] 2.3 Append `DampingTask(cost=self._config.damping_task_cost)` when `damping_task_cost > 0.0` and omit it when the cost is zero.
- [x] 2.4 Ensure damping does not require target updates in `_update_extra_task_targets()` and does not affect OpenArm Pink IK task construction.

## 3. Tests and Verification

- [x] 3.1 Extend the XArm test helper in `dimos/control/tasks/test_pink_teleop_task.py` to accept `damping_task_cost`.
- [x] 3.2 Add tests that XArm damping is disabled by default and included in the Pink task list when configured with a positive cost.
- [x] 3.3 Add invalid numeric config coverage for negative and non-finite `damping_task_cost` values.
- [x] 3.4 Add or extend safety tests showing solver failure and unsafe joint delta rejection still return no command with damping enabled.
- [x] 3.5 Run `uv run pytest dimos/control/tasks/test_pink_teleop_task.py -v` and targeted diagnostics for changed files.

## 4. Manual QA

- [x] 4.1 Instantiate an `XArm7IKTask` with a positive `damping_task_cost`, send a `PoseStamped(frame_id="teleop_xarm")`, compute once with a valid `CoordinatorState`, and confirm the task surface returns either a safe `JointCommandOutput` or the existing no-command safety outcome without raising.
