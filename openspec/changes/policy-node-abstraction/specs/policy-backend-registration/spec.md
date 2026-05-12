## ADDED Requirements

### Requirement: Policy backends are selected through a registry
The system SHALL provide a policy backend registry that maps configured backend names to backend implementations and allows the policy node to select a backend by name.

#### Scenario: Registered backend selection
- **WHEN** a policy node is configured with a registered backend name
- **THEN** it SHALL instantiate and use the corresponding backend implementation for policy inference

#### Scenario: Unknown backend name
- **WHEN** a policy node is configured with an unregistered backend name
- **THEN** startup SHALL fail with an error identifying the unknown backend

### Requirement: Policy backend interface isolates framework-specific inference
The system SHALL define a backend interface that receives the policy node observation and returns a policy command without exposing framework-specific tensors, feature dictionaries, or robot action dictionaries through the policy node public API.

#### Scenario: Backend produces policy command
- **WHEN** the policy node passes an assembled observation to a backend
- **THEN** the backend SHALL return a policy command representing joint positions, another enabled command family, or an explicit no-op

#### Scenario: Framework internals remain isolated
- **WHEN** a backend uses framework-specific preprocessing, inference, or postprocessing
- **THEN** those framework-specific data structures SHALL remain inside the backend implementation boundary

### Requirement: LeRobot backend is registered
The system SHALL register a LeRobot backend that can adapt policy node observations into LeRobot inference inputs and adapt LeRobot outputs into policy commands.

#### Scenario: LeRobot backend inference path
- **WHEN** the policy node is configured to use the LeRobot backend
- **THEN** the backend SHALL perform LeRobot-specific observation adaptation, policy action selection, postprocessing, and conversion into a policy command

#### Scenario: LeRobot dependency boundary
- **WHEN** the LeRobot backend is not selected
- **THEN** core policy node functionality SHALL not require importing or initializing LeRobot-specific dependencies

### Requirement: TestPolicy backend is registered
The system SHALL register a built-in `TestPolicy` backend that produces deterministic sinusoidal joint position commands for configured joints without external model dependencies.

#### Scenario: Sinusoidal joint command generation
- **WHEN** the policy node is configured to use `TestPolicy` with joint names, amplitude, frequency, phase, and optional center positions
- **THEN** the backend SHALL produce joint position policy commands whose values follow the configured sinusoid for each joint

#### Scenario: TestPolicy exercises registry path
- **WHEN** the policy node is configured to use `TestPolicy`
- **THEN** it SHALL select the backend through the same registry mechanism used for LeRobot and other policy backends

#### Scenario: TestPolicy has no external model dependency
- **WHEN** `TestPolicy` is selected
- **THEN** the backend SHALL run without requiring model files, GPU runtime, or external robot-learning framework packages
