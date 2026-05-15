## Context

Current Pink teleop wiring uses multiple robot-specific branches in coordinator task construction (`single_arm_pink_ik`, `piper_pink_ik`, `xarm7_pink_ik`, `openarm_bimanual_pink_ik`) and additional setup branching in teleop blueprints. At the same time, `pink_teleop_task.py` already has a useful polymorphic structure (`BasePinkIKTask` plus robot-specific subclasses), but construction still leaks robot choices into factory conditionals.

The requested cleanup has three concrete pressures:
1. Remove OpenArm-specific teleop setup from this path.
2. Simplify `frame_task` + `extra_task` composition into one coherent task creation/value-binding flow.
3. Avoid adding another `if` block whenever a new robot config is introduced.

## Goals / Non-Goals

**Goals:**
- Make Pink teleop task creation class/config-driven so coordinator and teleop setup do not need per-robot branching for every new robot.
- Remove OpenArm bimanual teleop setup from the active Pink teleop setup route.
- Keep XArm7 and Piper teleop behavior stable while refactoring construction/composition internals.
- Clarify task composition API so frame + auxiliary tasks are built and bound in one place.

**Non-Goals:**
- Replacing Pink IK solver behavior or tuning gains/cost defaults.
- Introducing a new teleop protocol or changing Quest message contracts.
- Reworking non-Pink coordinator task types (`trajectory`, `servo`, `velocity`, etc.).

## Decisions

### 1) Replace per-robot factory branching with Pink task registry + config constructors
- **Decision**: Introduce a small registry mapping task type strings to Pink task classes (or class-level constructors) so coordinator dispatch is uniform, and bind task construction inputs to existing `RobotConfig`/catalog values rather than a new parallel robot-description layer.
- **Rationale**: Today, coordinator owns robot-specific defaults/validation. Moving that to config/task classes while sourcing defaults from `RobotConfig.to_task_config()` and catalog constants (`piper.py`, `ufactory.py`) aligns with current architecture and removes recurring if-branch expansion without duplicate abstraction.
- **Alternative considered**: Keep if/elif chain and only deduplicate helper functions.
  - Rejected because it still grows conditionals linearly with each robot.

### 1.1) Reuse existing robot catalog responsibilities
- **Decision**: Keep robot identity/default ownership in `dimos.robot.catalog.*` and `RobotConfig`; the Pink registry only maps task type -> constructor and performs no robot catalog duplication.
- **Rationale**: Catalog files already own model/joint/gripper defaults. The registry should compose these values, not redefine them.
- **Alternative considered**: Introduce a Pink-specific robot profile dataclass.
  - Rejected because it duplicates responsibilities already handled by `RobotConfig` + catalog modules.

### 2) Collapse frame/extra task setup into unified task composition hook
- **Decision**: Refactor Pink task composition so concrete tasks return one ordered list of Pink tasks (frame and non-frame), while still preserving access to the primary controlled frame target for single-arm teleop.
- **Rationale**: Current split (`_create_frame_tasks`, `_create_extra_tasks`) makes extensions awkward and obscures binding flow. A unified composition contract simplifies subclassing and test expectations.
- **Alternative considered**: Keep split hooks but add helper wrappers.
  - Rejected because it keeps dual-path mental model and does not fully address requested simplification.

### 3) Remove OpenArm bimanual Pink teleop wiring from active setup
- **Decision**: Remove OpenArm-specific task type construction/wiring from coordinator and teleop setup paths covered by this change; update specs/tests accordingly.
- **Rationale**: Explicit user request to remove OpenArm teleop setup throughout project for this path.
- **Alternative considered**: Keep OpenArm implementation but deprecate only.
  - Rejected for now; request is removal-oriented, not deprecation-oriented.

## Risks / Trade-offs

- **[Risk] Task type compatibility drift for existing configs** -> **Mitigation**: keep existing task type names for supported single-arm routes, add compatibility tests in coordinator/task config creation.
- **[Risk] Regressions in teleop engage/disengage behavior after composition refactor** -> **Mitigation**: preserve existing SingleFrame behavior contract and run current Pink teleop tests with focused additions.
- **[Risk] OpenArm removal breaks internal examples still referencing bimanual path** -> **Mitigation**: update or remove stale references in blueprints/tests/spec deltas within the same change.

## Migration Plan

1. Introduce registry-based Pink task creation and class/config-owned validation/defaulting.
   - Source model path, end-effector frame, joint names, and gripper defaults from existing `RobotConfig` values produced by catalog helpers.
2. Refactor Pink task composition contract and update single-arm implementations/tests.
3. Remove OpenArm bimanual Pink setup branches/references in coordinator and related teleop setup.
4. Run Pink teleop task tests and coordinator tests; fix impacted blueprints/spec references.

Rollback strategy: revert registry/composition commits and restore prior coordinator `if/elif` branches plus OpenArm wiring references.

## Open Questions

- Should OpenArm bimanual Pink classes be fully deleted now, or retained internally but unregistered from coordinator surfaces?
- Should task registry live in `coordinator.py` or `pink_teleop_task.py` (class-local ownership vs coordinator-local ownership)?
