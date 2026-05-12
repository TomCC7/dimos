## Why

Rerun visualization currently supports generic message logging and one-off static helpers, but there is no reusable robot visualization capability that can load a URDF and update articulated joint transforms from `JointState` data. This makes teleop and IK debugging harder because developers cannot separate desired robot joint configuration from MuJoCo dynamics or hardware controller response.

## What Changes

- Add a reusable Rerun robot visualization capability that loads robot geometry from a configured URDF path.
- Add support for updating the Rerun robot joint configuration from incoming `JointState.name` and `JointState.position` values.
- Add support for logging auxiliary debugging frames such as desired controller pose and current/end-effector pose alongside the robot model.
- Add a debug teleop blueprint, `teleop-quest-xarm7-rerun`, that uses Quest right-controller teleop and Rerun URDF visualization to inspect Pink IK output without MuJoCo actuator dynamics.
- Preserve existing RerunBridge generic topic logging and existing MuJoCo-backed `teleop-quest-xarm7` behavior.

## Capabilities

### New Capabilities
- `rerun-urdf-robot-visualization`: Configure Rerun visualization with a URDF-backed articulated robot model and update its joint transforms from typed joint-state input.

### Modified Capabilities
<!-- No existing OpenSpec capabilities are present under openspec/specs/. -->

## Impact

- Affected visualization code: `dimos/visualization/rerun/`, `dimos/visualization/vis_module.py`, and any new robot visualization helper/module.
- Affected teleop blueprints: `dimos/teleop/quest/blueprints.py` for `teleop-quest-xarm7-rerun`.
- Affected robot assets/config: XArm7 URDF path from `dimos.robot.catalog.ufactory.XARM7_FK_MODEL`.
- Affected messages and streams: `JointState` for joint configuration updates and `PoseStamped` for desired/controller/end-effector debug frames.
- Testing impact: add unit coverage for URDF joint transform generation and blueprint/registry coverage for the new Rerun debug blueprint.
