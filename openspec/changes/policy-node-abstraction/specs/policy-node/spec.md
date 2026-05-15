## ADDED Requirements

### Requirement: Policy node exposes unified observation inputs
The system SHALL provide a policy node module under `dimos.manipulation.policy` that accepts multi-camera image inputs, the latest robot joint state, and a plain string task description as its policy observation inputs.

#### Scenario: Multi-camera observation assembly
- **WHEN** the policy node receives images from configured camera streams, a `JointState`, and a string task description
- **THEN** it SHALL assemble a policy observation containing images keyed by configured camera/source name, the latest joint state, and the task description string

#### Scenario: Task description is plain text
- **WHEN** a task description is provided to the policy node
- **THEN** the policy observation SHALL expose that description as a `str` value rather than requiring a LangChain message or custom task message

### Requirement: Policy node publishes coordinator-compatible joint position commands
The system SHALL support joint position as the reference policy command output by publishing a `JointState` command whose `name` and `position` fields are compatible with `ControlCoordinator.joint_command`.

#### Scenario: Joint position policy output
- **WHEN** the selected policy backend returns joint position targets for configured joints
- **THEN** the policy node SHALL publish a `JointState` with matching joint names and positions on its joint-command output

#### Scenario: Coordinator command compatibility
- **WHEN** the policy node publishes a joint position command
- **THEN** the command SHALL be usable by `ControlCoordinator.joint_command` without requiring changes to coordinator task routing or arbitration

### Requirement: Policy node validates command mappings before publishing
The system SHALL validate policy command mode, joint names, and action dimensions against policy node configuration before publishing commands to coordinator-compatible outputs.

#### Scenario: Invalid joint mapping
- **WHEN** a policy backend returns a joint position command with missing, extra, or unmapped action values
- **THEN** the policy node SHALL reject the command and not publish a coordinator command for that policy step

#### Scenario: Unsupported command family
- **WHEN** a policy backend returns a command family that is not enabled in the policy node configuration
- **THEN** the policy node SHALL reject the command and not publish it to any coordinator-compatible output

### Requirement: Policy node owns runtime observation and command cadence
The system SHALL run policy inference at a configured policy rate using latest available observations and SHALL keep model inference outside the `ControlCoordinator` tick loop.

#### Scenario: Policy runs independently from coordinator tick
- **WHEN** a policy node is connected to a control coordinator in a blueprint
- **THEN** the policy node SHALL publish coordinator-native commands from its own runtime loop without modifying the coordinator tick loop

#### Scenario: Missing observation data
- **WHEN** required observation inputs are not available for a policy step
- **THEN** the policy node SHALL avoid publishing a new command for that step

### Requirement: Teleop preempts policy commands
The system SHALL ensure that any teleop control task sharing joints with the policy node has a higher coordinator arbitration priority than the policy's streaming servo task, so that engaged teleop always wins per-joint arbitration over policy output.

#### Scenario: Teleop engaged on overlapping joints
- **WHEN** a teleop task is engaged on joints that the policy node is also publishing commands for
- **THEN** the coordinator SHALL route the teleop task's output to those joints
- **AND** the policy node's commands for the same joints SHALL be ignored by per-joint arbitration

#### Scenario: Blueprint enforces priority invariant
- **WHEN** a policy node blueprint helper is constructed alongside a teleop task on overlapping joints
- **THEN** the helper SHALL configure the policy's streaming servo task with a lower priority than the teleop task, or SHALL fail to build with an error identifying the violating tasks

### Requirement: Policy node suspends and resets on teleop engagement
The system SHALL subscribe the policy node to the same `buttons` stream that drives teleop engage/disengage and SHALL suspend command publication and reset the backend while teleop is engaged on overlapping joints.

#### Scenario: Teleop engagement suspends publication and resets backend
- **WHEN** the `buttons` input indicates teleop has engaged on joints that the policy node controls
- **THEN** the policy node SHALL stop publishing coordinator commands for those joints
- **AND** SHALL call `backend.reset()` so that any buffered actions, action chunks, or recurrent state are discarded

#### Scenario: Teleop disengagement resumes from fresh inference
- **WHEN** the `buttons` input indicates teleop has disengaged from joints that the policy node controls
- **THEN** the policy node SHALL resume publishing commands using a fresh inference pass against the current observation
- **AND** SHALL NOT replay any actions that were buffered before teleop engaged
