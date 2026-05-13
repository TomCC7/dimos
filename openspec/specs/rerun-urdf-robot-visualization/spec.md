## Purpose

This capability is deprecated. URDF robot loading, desired joint-state visualization, debug pose frame visualization, and no-dynamics teleop visualization have moved to the `viser-urdf-simulation` capability.

## Requirements

### Requirement: Rerun URDF robot visualization remains deprecated
The system SHALL treat Rerun URDF robot visualization as deprecated in favor of the `viser-urdf-simulation` capability.

#### Scenario: Users migrate to Viser URDF simulation
- **WHEN** desired-state URDF robot visualization is needed
- **THEN** users SHALL use the `viser-urdf-simulation` capability instead of Rerun-specific URDF visualization requirements
