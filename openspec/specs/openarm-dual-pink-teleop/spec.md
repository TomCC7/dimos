## Purpose

Define the accepted behavior for the OpenArm dual Quest Rerun teleop workflow, where Quest controller input drives one unified whole-robot OpenArm Pink IK solve and visualizes desired state in Rerun without commanding hardware.
## Requirements
### Requirement: OpenArm dual Quest Rerun teleop blueprint is registered
The system SHALL provide a registered blueprint named `teleop-quest-openarm-rerun` that composes Quest controller input, unified whole-robot OpenArm Pink IK desired-state computation, Rerun URDF visualization, and the standard Rerun viewer module.

#### Scenario: Launch by CLI registry key
- **WHEN** a user runs `dimos --listen-host 0.0.0.0 --simulation run teleop-quest-openarm-rerun`
- **THEN** the CLI SHALL resolve the `teleop-quest-openarm-rerun` blueprint from the generated blueprint registry

#### Scenario: Blueprint includes expected modules
- **WHEN** the `teleop_quest_openarm_rerun` blueprint is inspected
- **THEN** it SHALL include the Quest arm teleop module, the unified OpenArm Pink desired-state module, the Rerun URDF robot visualizer, and the Rerun viewer module

### Requirement: Existing XArm7 Rerun teleop entry remains available
The system SHALL keep the existing `teleop-quest-xarm7-rerun` blueprint entry available and compatible with `--listen-host` and `--simulation` CLI flags.

#### Scenario: XArm7 Rerun entry still resolves
- **WHEN** a user runs `dimos --listen-host 0.0.0.0 --simulation run teleop-quest-xarm7-rerun`
- **THEN** the CLI SHALL resolve the existing XArm7 Rerun teleop blueprint without requiring OpenArm modules
