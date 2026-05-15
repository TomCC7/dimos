## Why

Piper teleop can drive the arm today, but there is no dedicated blueprint that records synchronized demonstrations from the teleop surface for downstream imitation-learning datasets. Adding a Piper data-collection route lets operators capture USB camera observations, measured joint state, and the coordinator's desired joint action using DimOS-native stream recording before converting the recording to LeRobot format.

## What Changes

- Add a registered Piper data-collection blueprint based on the current `teleop_quest_piper` composition.
- Include a USB webcam camera stream in the collection route so demonstrations capture visual observations alongside teleop control.
- Route the Piper robot joint state from the control coordinator into the native recording surface.
- Expose or route the coordinator's desired joint command/action state so the recorded demonstration contains the action target, not only measured robot state.
- Use the existing native DimOS recording/storage mechanism for capture, with stream naming compatible with later conversion to LeRobot-style keys: camera frames as `observation.images.*`, joint state as `observation.state`, and desired joint action as `action`.

## Capabilities

### New Capabilities
- `piper-data-collection`: Piper teleop data-collection blueprint and recording contract for USB camera observations, measured joint state, and desired joint action.

### Modified Capabilities
- None.

## Impact

- Affected code: Piper/Quest teleop blueprint wiring in `dimos/teleop/quest/blueprints.py`, Piper coordinator wiring in `dimos/control/blueprints/teleop.py`, control coordinator or tick-loop output surface if desired joint action is not currently published, USB camera modules under `dimos/hardware/sensors/camera/`, the generated blueprint registry `dimos/robot/all_blueprints.py`, and related blueprint/tests.
- Public behavior: users should be able to run a Piper data-collection blueprint that preserves current Piper teleop behavior while recording the selected observation and action streams.
- Recording surface: the capture should use DimOS-native recording/storage rather than writing a LeRobot dataset directly; LeRobot conversion remains a later step that consumes the native recording.
- Data contract: each recorded timestep needs a USB camera image stream, Piper measured joint positions/state from `/coordinator/joint_state`, and the coordinator's desired joint action after task computation/arbitration.
- Dependencies: no new third-party dependency is expected for collection; LeRobot-specific tooling is only needed for the later conversion path.
