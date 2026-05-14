## 1. Pink task construction cleanup

- [x] 1.1 Add a registry/factory mapping for Pink teleop task types so coordinator dispatch does not use per-robot `if/elif` construction branches.
- [x] 1.2 Bind registry construction to existing `RobotConfig.to_task_config()` and catalog defaults (`dimos/robot/catalog/piper.py`, `dimos/robot/catalog/ufactory.py`) instead of introducing a duplicate robot metadata abstraction.
- [x] 1.3 Keep task-specific validation in Pink task config/task-class constructors (`SingleArm` variants) while leaving robot identity/default ownership in catalog + `RobotConfig`.
- [x] 1.4 Update coordinator task creation tests to cover registry-driven creation for `single_arm_pink_ik`, `xarm7_pink_ik`, and `piper_pink_ik` with catalog-backed defaults.

## 2. Pink task composition simplification

- [x] 2.1 Refactor `dimos/control/tasks/pink_teleop_task.py` so frame-task and auxiliary-task setup flow through one cohesive task composition/value-binding path.
- [x] 2.2 Preserve single-arm teleop behavior (engage/disengage, timeout, delta target updates, gripper mapping) while adapting tests for the unified composition contract.
- [x] 2.3 Validate no behavioral regressions in existing Pink teleop tests (`dimos/control/tasks/test_pink_teleop_task.py`) for XArm7 and Piper routes.

## 3. Remove OpenArm teleop setup from active path

- [x] 3.1 Remove OpenArm bimanual Pink teleop task wiring from coordinator and related active teleop setup paths.
- [x] 3.2 Remove or update stale OpenArm Pink teleop references in teleop setup code/tests/spec-related fixtures affected by this path.
- [x] 3.3 Confirm task/blueprint surfaces no longer advertise the removed OpenArm teleop setup path while retaining supported single-arm Pink routes.

## 4. Verification and docs alignment

- [x] 4.1 Run targeted control task/coordinator tests for modified paths and fix regressions.
- [x] 4.2 Ensure OpenSpec artifacts and capability deltas match final implementation scope before applying.
