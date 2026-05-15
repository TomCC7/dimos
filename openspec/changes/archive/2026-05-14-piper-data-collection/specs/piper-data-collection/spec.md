## ADDED Requirements

### Requirement: Piper data collection blueprint is registered
The system SHALL provide a registered Piper data collection blueprint that preserves the current Piper Quest teleop control surface while adding native recording of demonstration streams.

#### Scenario: Launch by CLI registry key
- **WHEN** a user lists or runs the Piper data collection blueprint by its CLI registry key
- **THEN** the registry SHALL resolve the blueprint from the generated blueprint registry

#### Scenario: Teleop routing is preserved
- **WHEN** the Piper data collection blueprint is inspected
- **THEN** it SHALL route left Quest controller output to the Piper `teleop_piper` coordinator task through `/coordinator/cartesian_command`
- **AND** it SHALL route teleop buttons through `/teleop/buttons`

### Requirement: Data collection records camera observation
The system SHALL record a USB camera image stream as the visual observation for Piper data collection.

#### Scenario: USB camera stream is present
- **WHEN** the Piper data collection blueprint is built
- **THEN** it SHALL include a USB webcam camera module that publishes `Image` messages for recording

#### Scenario: Camera recording uses native storage
- **WHEN** the data collection recorder is active and camera images are published
- **THEN** the recorder SHALL save the camera image stream using DimOS-native timestamped storage

### Requirement: Data collection records measured joint state
The system SHALL record Piper measured joint state from the control coordinator as the robot state observation.

#### Scenario: Measured state uses coordinator output
- **WHEN** the Piper coordinator publishes measured joint state
- **THEN** the data collection recorder SHALL save the `/coordinator/joint_state` `JointState` stream as measured robot state

### Requirement: Data collection records desired joint action
The system SHALL expose and record the post-arbitration desired Piper joint action produced by the control coordinator.

#### Scenario: Coordinator publishes desired action
- **WHEN** the coordinator computes and arbitrates active task outputs for a tick
- **THEN** it SHALL publish the desired joint action as a typed `JointState` stream containing the command values that will be routed to hardware

#### Scenario: Desired action is distinct from measured state
- **WHEN** both measured state and desired action are recorded
- **THEN** measured robot state and desired joint action SHALL use distinct stream names or topics so downstream conversion can distinguish `observation.state` from `action`

### Requirement: Native recordings are compatible with later LeRobot conversion
The system SHALL record enough native stream metadata and stable stream naming for a later converter to map collected data to LeRobot-style observations and actions.

#### Scenario: Recorded streams have stable semantic roles
- **WHEN** a Piper data collection session is recorded
- **THEN** the native recording SHALL contain separate streams for camera observation, measured joint state observation, and desired joint action
- **AND** those streams SHALL be documented or named so they can map to `observation.images.*`, `observation.state`, and `action`

#### Scenario: Collection does not require LeRobot dependency
- **WHEN** a user runs Piper data collection
- **THEN** the system SHALL record native DimOS data without requiring LeRobot dataset-writing dependencies at collection time
