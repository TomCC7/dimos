## Why

Pink teleop setup currently spreads robot-specific decisions across coordinator factories, teleop blueprints, and OpenArm-only task classes, which makes each new robot require another conditional branch. We need to simplify task construction so robot onboarding is config/class-driven instead of if-block-driven.

## What Changes

- Remove OpenArm bimanual Pink teleop task wiring from the active teleop task setup path (task type construction and related teleop setup references).
- Refactor Pink teleop task composition so frame task creation and additional task creation are expressed as one cohesive task-build + binding flow, rather than separate ad-hoc setup branches.
- Shift robot-specific selection from coordinator/blueprint conditionals into task-class/config contracts that are derived from existing `RobotConfig` sources (`dimos/robot/config.py` + catalog defaults in `dimos/robot/catalog/piper.py` and `dimos/robot/catalog/ufactory.py`) so new robot variants can be introduced without adding new construction if-blocks or duplicate config abstractions.
- Keep existing single-arm Pink teleop behavior (XArm7/Piper surfaces) while simplifying how task configs are instantiated.

## Capabilities

### New Capabilities
- `pink-teleop-task-factory`: Centralized, class/config-driven Pink teleop task creation contract that removes per-robot conditional task instantiation.

### Modified Capabilities
- `single-arm-pink-teleop`: Task instantiation path and internal task-binding structure are simplified while preserving controller-delta teleop behavior.
- `pink-teleop-ik`: Shared Pink base composition is clarified to support unified task build/binding patterns without per-robot branching.
- `openarm-dual-pink-teleop`: OpenArm-specific teleop setup is removed from the active Pink teleop setup path.

## Impact

- Affected code: `dimos/control/tasks/pink_teleop_task.py`, `dimos/control/coordinator.py`, `dimos/control/blueprints/teleop.py`, and Pink teleop tests.
- Affected task surfaces: `single_arm_pink_ik`, `xarm7_pink_ik`, `piper_pink_ik`, and current OpenArm bimanual Pink setup references.
- Runtime risk: medium (task factory and task-type routing changes).
- No new external dependencies expected.
