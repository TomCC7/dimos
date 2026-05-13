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

### Requirement: Quest hands route to target slots in one OpenArm IK solve
The system SHALL route left and right Quest controller pose outputs to distinct target slots in one unified OpenArm Pink IK task so both end-effector targets are solved together against one robot configuration.

#### Scenario: Left controller drives left arm target
- **WHEN** the left Quest controller publishes an engaged teleop pose for `teleop_openarm_left`
- **THEN** the OpenArm Pink desired-state path SHALL update the left OpenArm end-effector target slot and solve the unified OpenArm IK problem without overwriting the right target slot

#### Scenario: Right controller drives right arm target
- **WHEN** the right Quest controller publishes an engaged teleop pose for `teleop_openarm_right`
- **THEN** the OpenArm Pink desired-state path SHALL update the right OpenArm end-effector target slot and solve the unified OpenArm IK problem without overwriting the left target slot

### Requirement: OpenArm dual desired joint state is visualized safely
The system SHALL publish OpenArm desired joint positions for visualization without sending commands to physical OpenArm CAN hardware in the Rerun example.

#### Scenario: Pink solve emits whole-robot desired state
- **WHEN** either OpenArm Pink IK target has an active pose and Pink returns a valid IK result
- **THEN** the desired-state module SHALL publish a single `JointState` containing named OpenArm joint positions from the unified whole-robot solve

#### Scenario: Rerun example avoids hardware command output
- **WHEN** `teleop-quest-openarm-rerun` is launched in simulation mode
- **THEN** the blueprint SHALL visualize desired OpenArm state through Rerun and SHALL NOT include OpenArm hardware adapters that command CAN motors

### Requirement: Existing XArm7 Rerun teleop entry remains available
The system SHALL keep the existing `teleop-quest-xarm7-rerun` blueprint entry available and compatible with `--listen-host` and `--simulation` CLI flags.

#### Scenario: XArm7 Rerun entry still resolves
- **WHEN** a user runs `dimos --listen-host 0.0.0.0 --simulation run teleop-quest-xarm7-rerun`
- **THEN** the CLI SHALL resolve the existing XArm7 Rerun teleop blueprint without requiring OpenArm modules
