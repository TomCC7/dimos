## REMOVED Requirements

### Requirement: Viser URDF simulator loads a configured robot model
**Reason**: Viser is no longer the no-dynamics teleop visualization path and SHALL NOT be exposed as a DimOS simulation backend.
**Migration**: Use `meshcat-teleop-preview` for no-hardware XArm7 Quest teleop visualization, or use MuJoCo simulation when physics and simulated feedback are required.

### Requirement: Viser URDF simulator visualizes desired joint state
**Reason**: Desired-state URDF visualization through Viser is being replaced by Meshcat preview of coordinator/mock joint state.
**Migration**: Use the Meshcat teleop preview viewer, which consumes typed coordinator `JointState` messages.

### Requirement: Viser URDF simulator visualizes desired teleop poses
**Reason**: Viser debug pose visualization is part of the removed Viser simulator setup and is not required for the initial Meshcat mock preview.
**Migration**: Use Meshcat teleop preview for robot joint-state visualization; add Meshcat target/controller frame visualization separately if needed.

### Requirement: XArm7 Quest teleop keeps MuJoCo simulation backend
**Reason**: XArm7 Quest teleop selection is being redefined so no-IP default runs use mock hardware plus Meshcat preview, while MuJoCo remains the explicit `--simulation` backend.
**Migration**: Run `dimos --listen-host 0.0.0.0 run teleop-quest-xarm7` for mock Meshcat preview, or `dimos --simulation run teleop-quest-xarm7` for MuJoCo.

### Requirement: Viser server honors listen host
**Reason**: The Viser server is removed with the Viser simulator setup.
**Migration**: Meshcat teleop preview SHALL honor `GlobalConfig.listen_host` for browser access.
