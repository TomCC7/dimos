## Purpose

This capability is deprecated. No-dynamics XArm7 Quest teleop robot visualization has moved to the `meshcat-teleop-preview` capability.

## Requirements

### Requirement: Rerun URDF robot visualization remains deprecated
The system SHALL treat Rerun URDF robot visualization as deprecated in favor of the `meshcat-teleop-preview` capability.

#### Scenario: Users migrate to Meshcat teleop preview
- **WHEN** no-dynamics XArm7 Quest teleop robot visualization is needed
- **THEN** users SHALL use the `meshcat-teleop-preview` capability instead of Rerun-specific URDF visualization requirements
