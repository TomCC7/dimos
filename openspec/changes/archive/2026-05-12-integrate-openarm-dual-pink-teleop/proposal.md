## Why

DimOS already has OpenArm catalog/adapter blueprints and a Pink-backed XArm7 Quest Rerun teleop path, but there is no bimanual OpenArm Quest example that solves the dual-arm robot as one Pink IK problem. Adding this example gives developers a simulation-safe entry point for validating whole-robot bimanual IK, shared-joint behavior, controller routing, and Rerun visualization before touching CAN hardware.

## What Changes

- Add a dual-arm OpenArm Quest teleop example that maps left and right Quest controllers into one unified OpenArm Pink IK task.
- Add OpenArm-specific whole-robot Pink IK task/config wiring for two end-effector frame targets solved together in one robot configuration, allowing shared joints to participate coherently.
- Add a Rerun visualization path for the bimanual OpenArm desired joint output and debug target/controller poses.
- Simplify Rerun joint-name normalization by using the suffix after `/` as the default mapping from DimOS coordinator names such as `arm/joint1` to URDF names such as `joint1`, while leaving already-unqualified names such as `openarm_left_joint1` unchanged.
- Register a CLI blueprint entry runnable as `dimos --listen-host 0.0.0.0 --simulation run teleop-quest-openarm-rerun`.
- Preserve the existing `teleop-quest-xarm7-rerun` entry and ensure `dimos --listen-host 0.0.0.0 --simulation run teleop-quest-xarm7-rerun` remains available for the current XArm7 Rerun example.
- Add smoke coverage for the new blueprint and regenerate the auto-generated blueprint registry.

## Capabilities

### New Capabilities
- `openarm-dual-pink-teleop`: Bimanual OpenArm Quest teleop using a unified whole-robot Pink IK problem with Rerun visualization and a registered simulation CLI entry.

### Modified Capabilities
- `pink-teleop-ik`: Extend Pink-backed teleop IK from the existing XArm7 single-arm path to unified whole-robot OpenArm bimanual IK with multiple end-effector targets and possible shared joints.
- `rerun-urdf-robot-visualization`: Extend URDF Rerun visualization usage to a bimanual OpenArm desired-state teleop blueprint.

## Impact

- Affected code: `dimos/control/tasks/pink_teleop_task.py`, `dimos/control/coordinator.py`, `dimos/control/pink_ik_visualization.py`, `dimos/visualization/rerun/urdf_robot.py`, `dimos/teleop/quest/blueprints.py`, `dimos/robot/catalog/openarm.py`, `dimos/robot/manipulators/openarm/blueprints.py`, `dimos/robot/all_blueprints.py`, and teleop smoke tests.
- APIs/CLI: introduces the new blueprint registry key `teleop-quest-openarm-rerun`; keeps `--listen-host` behavior routed through `GlobalConfig.listen_host` for Quest web access.
- Dependencies: uses existing `pin-pink`, `pin`, `qpsolvers`, `daqp`, OpenArm LFS URDF assets, and Rerun visualization modules; no new external dependency is expected.
- Systems: Quest browser teleop server, ControlCoordinator task factory, Pink IK solver path, OpenArm simulation/mock hardware configs, and Rerun URDF visualization.
