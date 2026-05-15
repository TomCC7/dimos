## MODIFIED Requirements

### Requirement: Rerun URDF robot visualization remains deprecated
The system SHALL treat Rerun URDF robot visualization as deprecated in favor of the `meshcat-teleop-preview` capability for XArm7 no-hardware teleop visualization.

#### Scenario: Users migrate to Meshcat teleop preview
- **WHEN** no-dynamics XArm7 Quest teleop robot visualization is needed
- **THEN** users SHALL use the `meshcat-teleop-preview` capability instead of Rerun-specific URDF visualization requirements
