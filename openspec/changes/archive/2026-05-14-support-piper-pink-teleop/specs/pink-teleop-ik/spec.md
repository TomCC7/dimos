## ADDED Requirements

### Requirement: Existing XArm7 Pink teleop uses shared single-arm implementation
The existing XArm7 Pink teleop behavior SHALL be preserved while its single-frame control flow is provided by the shared single-arm Pink teleop implementation.

#### Scenario: XArm7 task type remains available
- **WHEN** the coordinator constructs an `xarm7_pink_ik` task from existing XArm7 teleop blueprint configuration
- **THEN** the task SHALL construct a Pink single-arm IK task with XArm7 defaults and preserve the existing `teleop_xarm` routing behavior

#### Scenario: XArm7 validation remains strict
- **WHEN** the XArm7 Pink teleop task starts
- **THEN** it SHALL continue to validate XArm7 joint names and the configured XArm7 end-effector frame before accepting teleop commands

#### Scenario: XArm7 safety behavior remains unchanged
- **WHEN** XArm7 Pink teleop receives stale targets, missing joint state, solver failure, non-finite IK output, or excessive per-tick joint deltas
- **THEN** it SHALL reject output for that tick using the same safety behavior as before the shared single-arm refactor

### Requirement: Coordinator recognizes reusable single-arm Pink task type
The control coordinator SHALL route Cartesian teleop commands and Quest button state to the reusable single-arm Pink task type.

#### Scenario: Cartesian command target type includes single-arm Pink
- **WHEN** a `PoseStamped` Cartesian command has a `frame_id` matching a configured single-arm Pink task name
- **THEN** the coordinator SHALL deliver the command to that task using the same routing mechanism used for existing teleop IK tasks

#### Scenario: Button target type includes single-arm Pink
- **WHEN** Quest button state is received by the coordinator
- **THEN** the coordinator SHALL deliver the button state to configured single-arm Pink teleop tasks so engage and gripper trigger behavior works

### Requirement: Pink task configuration exposes reusable single-arm variables
The coordinator task configuration SHALL expose the robot-specific variables needed to instantiate a reusable single-arm Pink teleop task.

#### Scenario: Pink frame variables are configurable
- **WHEN** a blueprint defines a single-arm Pink teleop task
- **THEN** it SHALL be able to configure the model path, end-effector frame, controlled joint names, controller hand, frame position cost, frame orientation cost, frame LM damping, and frame gain

#### Scenario: Pink regularization variables are configurable
- **WHEN** a blueprint defines a single-arm Pink teleop task
- **THEN** it SHALL be able to configure posture cost, posture reference, posture LM damping, posture gain, damping-task cost, solver name, and Pink damping

#### Scenario: Teleop safety and gripper variables are configurable
- **WHEN** a blueprint defines a single-arm Pink teleop task
- **THEN** it SHALL be able to configure timeout, maximum joint delta, gripper joint, gripper open position, and gripper closed position

## MODIFIED Requirements

### Requirement: Robot-specific Pink IK defaults are task-local
Pink-backed robot-specific IK tasks SHALL own their robot-specific Pink solver, frame, objective, posture, damping, and target-slot defaults locally rather than requiring those defaults to be provided through coordinator-level task configuration. Reusable generic Pink IK task types that intentionally abstract multiple single-arm robots MAY expose the robot identity, model, frame, solver, and objective variables needed to instantiate that generic task.

#### Scenario: XArm7 Pink defaults are local to XArm7 task
- **WHEN** the coordinator constructs an `xarm7_pink_ik` task with only generic coordinator fields and the XArm7 task type
- **THEN** the XArm7 Pink IK task SHALL use its task-local defaults for solver damping, end-effector frame, frame objective costs, frame gain, posture objective settings, and damping-task setting

#### Scenario: OpenArm Pink defaults are local to OpenArm task
- **WHEN** the coordinator constructs an `openarm_bimanual_pink_ik` task with only generic coordinator fields and the OpenArm task type
- **THEN** the OpenArm Pink IK task SHALL use its task-local defaults for solver damping, left and right target task names, left and right end-effector frames, frame objective costs, and frame gain

#### Scenario: Generic single-arm Pink configuration is explicit
- **WHEN** the coordinator constructs a `single_arm_pink_ik` task
- **THEN** the task SHALL require an explicit model path and end-effector frame and MAY accept explicit Pink solver/objective settings because it has no robot-specific defaults of its own

### Requirement: Coordinator task config excludes Pink tuning internals
The coordinator task configuration SHALL NOT expose robot-specific Pink tuning fields for concrete robot task types such as XArm7 and OpenArm. For reusable generic Pink task types that are not tied to one robot, the coordinator task configuration MAY expose the Pink tuning and frame fields required to select the robot-specific behavior at the blueprint boundary.

#### Scenario: Coordinator config remains focused on orchestration
- **WHEN** a concrete robot Pink-backed IK task is declared through `TaskConfig`
- **THEN** the config SHALL include only coordinator-level task construction inputs such as task name, task type, joint names, priority, model path override, hand, gripper settings, timeout, and max joint delta

#### Scenario: Coordinator no longer forwards Pink internals to concrete robot tasks
- **WHEN** `ControlCoordinator` creates an XArm7 or OpenArm Pink IK task from `TaskConfig`
- **THEN** it SHALL stop requiring coordinator-level `pink_*` values and SHALL allow the concrete robot task config defaults to define Pink-specific behavior

#### Scenario: Coordinator forwards explicit generic single-arm Pink settings
- **WHEN** `ControlCoordinator` creates a `single_arm_pink_ik` task from `TaskConfig`
- **THEN** it SHALL forward the explicit model, end-effector frame, solver, frame objective, posture, and damping settings configured for that generic reusable task
