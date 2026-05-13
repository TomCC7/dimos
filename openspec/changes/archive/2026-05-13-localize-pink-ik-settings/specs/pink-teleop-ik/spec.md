## ADDED Requirements

### Requirement: Robot-specific Pink IK defaults are task-local
Pink-backed robot IK tasks SHALL own their robot-specific Pink solver, frame, objective, posture, damping, and target-slot defaults locally rather than requiring those defaults to be provided through coordinator-level task configuration.

#### Scenario: XArm7 Pink defaults are local to XArm7 task
- **WHEN** the coordinator constructs an `xarm7_pink_ik` task with only generic coordinator fields and the XArm7 task type
- **THEN** the XArm7 Pink IK task SHALL use its task-local defaults for solver damping, end-effector frame, frame objective costs, frame gain, posture objective settings, and damping-task setting

#### Scenario: OpenArm Pink defaults are local to OpenArm task
- **WHEN** the coordinator constructs an `openarm_bimanual_pink_ik` task with only generic coordinator fields and the OpenArm task type
- **THEN** the OpenArm Pink IK task SHALL use its task-local defaults for solver damping, left and right target task names, left and right end-effector frames, frame objective costs, and frame gain

### Requirement: Coordinator task config excludes Pink tuning internals
The coordinator task configuration SHALL NOT expose robot-specific Pink tuning fields for solver/task costs, frame names, target-slot names, posture weights, posture references, or damping-task cost.

#### Scenario: Coordinator config remains focused on orchestration
- **WHEN** a Pink-backed IK task is declared through `TaskConfig`
- **THEN** the config SHALL include only coordinator-level task construction inputs such as task name, task type, joint names, priority, model path override, hand, gripper settings, timeout, and max joint delta

#### Scenario: Coordinator no longer forwards Pink internals
- **WHEN** `ControlCoordinator` creates an XArm7 or OpenArm Pink IK task from `TaskConfig`
- **THEN** it SHALL stop passing coordinator-level `pink_*` values and SHALL allow the concrete robot task config defaults to define Pink-specific behavior

### Requirement: Existing Pink IK behavior is preserved after localization
Moving Pink defaults out of coordinator configuration SHALL preserve the existing observable behavior of in-repository XArm7 and OpenArm Pink teleop task construction.

#### Scenario: XArm7 construction preserves previous defaults
- **WHEN** an XArm7 Pink IK task is created through the coordinator after Pink settings are localized
- **THEN** it SHALL still use the XArm7 model fallback, `link7` end-effector frame, existing frame/posture/damping defaults, timeout handling, joint-delta safety, and gripper behavior

#### Scenario: OpenArm construction preserves previous defaults
- **WHEN** an OpenArm bimanual Pink IK task is created through the coordinator after Pink settings are localized
- **THEN** it SHALL still use the OpenArm model fallback, existing left/right target names, existing left/right end-effector frames, existing frame objective defaults, timeout handling, and joint-delta safety

#### Scenario: Direct task-level tests can still tune Pink details
- **WHEN** a focused unit test or robot-specific caller directly instantiates a concrete Pink IK task config
- **THEN** it MAY still set task-local Pink options exposed by that concrete task config without reintroducing coordinator-level Pink fields
