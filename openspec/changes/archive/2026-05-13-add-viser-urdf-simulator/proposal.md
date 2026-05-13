## Why

Quest teleop users need a lightweight simulation mode that shows commanded robot intent without starting a physics engine, camera stack, or Rerun robot visualizer. The existing XArm7 simulation path is coupled to MuJoCo for `--simulation`, while the desired-state debug path is coupled to Rerun; replacing that with a Viser URDF viewer gives a browser-native, host-configurable visualization surface for teleop development.

## What Changes

- Add a Viser-based URDF visualization simulator module that loads a configured URDF and updates robot joint poses from desired `JointState` messages without running dynamics.
- Add simulator-selection wiring so `dimos --listen-host 0.0.0.0 --simulation run teleop-quest-xarm7` can use either the current MuJoCo-backed simulator or the new Viser visualization simulator as a swappable simulation backend.
- Provide an XArm7 Quest teleop Viser path that visualizes the desired IK output and debug target/controller poses through Viser instead of Rerun.
- Deprecate the Rerun URDF robot visualization feature and associated Rerun-specific teleop robot-vis blueprints in favor of the Viser simulator path.
- Preserve non-robot Rerun visualization infrastructure unless it is only used by the deprecated robot-vis feature.

## Capabilities

### New Capabilities
- `viser-urdf-simulation`: Defines the Viser URDF visualization-only simulator, how it loads robot models, accepts desired state, exposes a browser viewer using `listen_host`, and participates in teleop simulation selection.

### Modified Capabilities
- `rerun-urdf-robot-visualization`: Deprecates the Rerun URDF robot visualization behavior and redirects teleop desired-state visualization requirements to the new Viser simulator capability.

## Impact

- Affected blueprints: `dimos/teleop/quest/blueprints.py`, `dimos/control/blueprints/teleop.py`, generated `dimos/robot/all_blueprints.py`, and teleop documentation.
- Affected simulator code: `dimos/simulation/engines/mujoco_sim_module.py` patterns and a new Viser URDF simulator module under the simulation or visualization package.
- Affected visualization code: `dimos/visualization/rerun/urdf_robot.py`, its tests, and Rerun-specific XArm7/OpenArm teleop robot visualization blueprints become deprecated or migration targets.
- Affected configuration: simulator backend selection must work with existing `--simulation` and `--listen-host` CLI flags and should avoid introducing hardcoded viewer host/port values.
- Dependencies: may require adding or standardizing the Python `viser` dependency if it is not already part of the runtime extras used by teleop simulation.
