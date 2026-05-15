## Why

The current Viser path is modeled as a simulation backend even though it is only a browser visualization surface, which makes the teleop simulation selector blur physics, hardware feedback, and desired-state preview semantics. XArm7 Quest teleop needs a simpler default development path: when no real hardware IP is configured, `dimos --listen-host 0.0.0.0 run teleop-quest-xarm7` should use mock hardware and expose a Meshcat robot viewer without requiring `--simulation` or a Viser-specific backend.

## What Changes

- Add a Meshcat-backed XArm7 teleop preview path that visualizes the mock/coordinator robot state for `teleop-quest-xarm7` when no `xarm7_ip` is configured.
- Change `teleop-quest-xarm7` default selection so the no-IP path uses mock hardware plus Meshcat visualization, while an explicit `--xarm7-ip` path continues to target real hardware.
- Preserve MuJoCo dynamic simulation behind `--simulation` for cases that need physics, shared-memory simulated hardware feedback, or simulator cameras.
- **BREAKING**: Deprecate and remove the Viser simulation-backend setup, including the `viser` simulation backend selector behavior and Viser URDF simulator registration/tests/docs as the preferred no-dynamics teleop viewer.
- Update deprecated Rerun URDF robot-visualization migration guidance so users migrate to the Meshcat teleop preview path rather than Viser URDF simulation.

## Capabilities

### New Capabilities
- `meshcat-teleop-preview`: Defines the Meshcat-based no-hardware XArm7 Quest teleop preview, including mock hardware selection, browser-host behavior, robot model loading, and joint-state visualization.

### Modified Capabilities
- `viser-urdf-simulation`: Deprecate and remove Viser as a selectable DimOS simulation backend and desired-state teleop visualization path.
- `rerun-urdf-robot-visualization`: Update the deprecated Rerun URDF migration target from Viser URDF simulation to Meshcat teleop preview.

## Impact

- Affected configuration: `GlobalConfig.simulation_backend` and Viser-specific settings may be removed or narrowed back to MuJoCo-only simulation semantics; any CLI flags generated from those fields must be updated accordingly.
- Affected blueprints: `dimos/control/blueprints/teleop.py`, `dimos/teleop/quest/blueprints.py`, and generated `dimos/robot/all_blueprints.py`.
- Affected simulator/viewer code: `dimos/simulation/engines/viser_urdf_sim_module.py` removal/deprecation and a new Meshcat viewer module or helper for XArm7 teleop preview.
- Affected tests/docs: Viser simulator tests/specs/docs, teleop blueprint selection tests, CLI help/docs, and any Rerun deprecation guidance that currently points to Viser.
- Dependencies: evaluate whether `viser` can be removed from runtime dependencies after Viser simulator removal; Drake/Pydrake is already present for manipulation/Meshcat usage.
