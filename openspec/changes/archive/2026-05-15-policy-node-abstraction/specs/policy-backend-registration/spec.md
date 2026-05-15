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

### Requirement: Backends expose a reset hook for preemption and chunk invalidation
The system SHALL require every policy backend to expose a `reset()` method that clears any buffered action chunk, cached recurrent state, or queued commands, so that the next `select_action` call computes a fresh action from the next observation.

#### Scenario: Reset discards buffered action chunks
- **WHEN** a backend has buffered a multi-step action chunk from a previous `select_action` call
- **AND** the policy node invokes `backend.reset()`
- **THEN** the backend SHALL discard the buffered chunk
- **AND** the next call to `select_action` SHALL produce an action computed from the next observation rather than the discarded buffer

#### Scenario: Reset clears recurrent or hidden state
- **WHEN** a backend maintains recurrent, history, or hidden state across `select_action` calls
- **AND** the policy node invokes `backend.reset()`
- **THEN** the backend SHALL reinitialize that state so subsequent inferences do not depend on observations from before the reset

#### Scenario: TestPolicy reset is well-defined
- **WHEN** the policy node invokes `reset()` on the `TestPolicy` backend
- **THEN** the backend SHALL deterministically restart its sinusoidal trajectory (e.g., reset the phase clock) without erroring

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
