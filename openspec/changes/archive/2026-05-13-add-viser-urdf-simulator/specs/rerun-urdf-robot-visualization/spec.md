## REMOVED Requirements

### Requirement: Rerun visualization loads a configured URDF robot model
**Reason**: Rerun URDF robot visualization is deprecated in favor of the Viser URDF simulation backend, which provides the desired-state, browser-native teleop visualization surface without coupling robot visualization to Rerun.
**Migration**: Use the `viser-urdf-simulation` capability for URDF robot loading and desired-state visualization.

### Requirement: Rerun visualization updates robot joints from typed JointState input
**Reason**: Desired joint visualization is moving to the Viser URDF simulator so teleop simulation can switch between MuJoCo dynamics and a no-dynamics visualization backend.
**Migration**: Route desired `JointState` messages to the Viser URDF simulator.

### Requirement: Rerun visualization logs debug pose frames
**Reason**: Debug pose frame visualization for teleop desired state is moving to Viser alongside the URDF robot model.
**Migration**: Route desired controller, target, and end-effector `PoseStamped` streams to the Viser URDF simulator.

### Requirement: XArm7 Quest teleop Rerun blueprint visualizes desired IK output without MuJoCo dynamics
**Reason**: Rerun-specific robot visualization blueprints are deprecated and should not be the primary desired-state teleop visualization entry point.
**Migration**: Use `teleop-quest-xarm7` with the existing MuJoCo simulation path; add a new desired-state producer before wiring Viser URDF visualization back into teleop.

### Requirement: Rerun visualization supports OpenArm bimanual desired state
**Reason**: Rerun-specific robot visualization examples are deprecated as a class; future desired-state URDF visualization should use the Viser simulator path.
**Migration**: Add a non-deprecated OpenArm desired-state producer before wiring OpenArm desired-state visualization to Viser.

### Requirement: Rerun joint-name normalization uses slash suffixes
**Reason**: Joint-name normalization remains necessary, but it belongs to the Viser URDF simulator after Rerun robot visualization is deprecated.
**Migration**: Implement slash-suffix normalization in the Viser URDF simulator's `JointState` mapping.
