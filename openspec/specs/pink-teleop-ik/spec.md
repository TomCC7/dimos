## Purpose

Define the accepted behavior for Pink-backed teleoperation IK control tasks, starting with the XArm7 teleop implementation.
## Requirements
### Requirement: Shared Pink IK base task provides common solver plumbing
The system SHALL provide a shared Pink IK base task for teleoperation control tasks that owns common solver setup, current-joint extraction, target-update hooks, safety checks, and coordinator-compatible joint command output, while exposing one cohesive task-composition contract for frame and auxiliary Pink tasks.

#### Scenario: Base task composes Pink tasks through unified build contract
- **WHEN** a concrete Pink teleop task initializes
- **THEN** it SHALL build the solver task list through one composition contract that supports frame targets and auxiliary objectives without requiring separate ad-hoc frame/extra setup branches

#### Scenario: Base task emits coordinator-compatible joint commands
- **WHEN** Pink returns a valid IK velocity for active target state
- **THEN** the base task SHALL integrate velocity into ordered joint positions and return `JointCommandOutput` compatible with coordinator arbitration

#### Scenario: Base task enforces joint delta safety
- **WHEN** an IK result exceeds configured per-tick joint delta limits
- **THEN** the task SHALL reject the command for that tick and SHALL NOT publish unsafe joint positions

### Requirement: XArm7 Pink IK task constructs an XArm7-specific IK problem
The system SHALL provide an XArm7-specific Pink teleop IK task that subclasses the shared Pink IK base and constructs the Pink problem for the XArm7 model used by existing XArm7 teleop blueprints.

#### Scenario: XArm7 task loads the XArm7 model
- **WHEN** the XArm7 Pink IK task is created from coordinator task configuration
- **THEN** it SHALL load the XArm7 FK model configured for `coordinator_teleop_xarm7` and validate that configured XArm7 joint names match the model actuated joints used for command output

#### Scenario: XArm7 task creates a single end-effector frame task
- **WHEN** the XArm7 Pink IK task initializes its robot-specific IK problem
- **THEN** it SHALL construct exactly one Pink frame task for the configured XArm7 end-effector frame and SHALL fail startup if that frame is absent from the model

#### Scenario: XArm7 task owns single-target state
- **WHEN** the XArm7 Pink IK task receives right-controller teleop deltas
- **THEN** the XArm7 task SHALL maintain the single target pose and captured baseline needed for its one configured end-effector without forcing that target shape on the shared Pink base

#### Scenario: XArm7 task owns only XArm7 resources
- **WHEN** the coordinator asks the XArm7 Pink IK task for its resource claim
- **THEN** the task SHALL claim the configured XArm7 arm joints and any configured XArm7 gripper joint using servo-position control mode

### Requirement: XArm7 Pink IK task consumes only the right controller pose
The system SHALL route only right-controller teleop pose deltas into the XArm7 Pink IK task for the initial implementation.

#### Scenario: Right controller route updates XArm7 target
- **WHEN** `teleop_quest_xarm7` publishes a right-controller `PoseStamped` with `frame_id` set to `teleop_xarm`
- **THEN** the coordinator SHALL route the command to the XArm7 Pink IK task and the task SHALL update its active IK target state from that pose

#### Scenario: Left controller is not an XArm7 IK input
- **WHEN** the XArm7 Pink IK task is used by the XArm7 teleop blueprint
- **THEN** the blueprint SHALL NOT route left-controller pose output to that task and the task SHALL NOT require left-controller pose data to compute IK

#### Scenario: Route key remains compatible
- **WHEN** existing XArm7 teleop routing uses `PoseStamped.frame_id == "teleop_xarm"`
- **THEN** the XArm7 Pink IK task SHALL remain reachable through that route key without introducing a new LCM message type

### Requirement: Controller pose contract remains delta-based
The system SHALL interpret controller `PoseStamped` commands consumed by the XArm7 Pink IK task as robot-frame deltas from controller engagement, not as absolute world-frame end-effector targets.

#### Scenario: Engage captures end-effector baseline
- **WHEN** the right controller engages and the XArm7 Pink IK task has current joint state for the XArm7 arm
- **THEN** the task SHALL capture the current XArm7 end-effector pose as the baseline for subsequent controller deltas

#### Scenario: Controller delta produces frame target
- **WHEN** the task receives a right-controller pose delta after baseline capture
- **THEN** it SHALL compute the Pink frame target by applying that delta to the captured XArm7 end-effector baseline

#### Scenario: Re-engage resets baseline
- **WHEN** the right controller disengages and later re-engages
- **THEN** the task SHALL clear the previous baseline and capture a new XArm7 end-effector baseline before applying new deltas

### Requirement: XArm7 Pink IK task handles stale or missing target data safely
The system SHALL prevent stale or incomplete teleop target state from producing unintended XArm7 motion.

#### Scenario: Missing joint state prevents IK output
- **WHEN** the XArm7 Pink IK task lacks current positions for any configured controlled joint
- **THEN** it SHALL return no joint command for that tick

#### Scenario: Target timeout deactivates XArm7 command output
- **WHEN** no right-controller target update arrives within the configured teleop timeout
- **THEN** the XArm7 Pink IK task SHALL deactivate its target state, clear its captured baseline, and return no joint command until a new valid target is received

#### Scenario: Inactive task does not claim compute output
- **WHEN** the XArm7 Pink IK task is not active or has no current right-controller target
- **THEN** it SHALL report inactive behavior consistent with existing control tasks and SHALL NOT emit joint positions

### Requirement: Pink dependency and solver selection are explicit
The system SHALL declare and use the Pink dependency and a deterministic QP solver path required for Pink IK execution.

#### Scenario: Pink package is available to the task
- **WHEN** the XArm7 Pink IK task module imports Pink APIs
- **THEN** project dependency configuration SHALL include the Pink package needed for `pink.Configuration`, `pink.tasks.FrameTask`, and `pink.solve_ik`

#### Scenario: Solver selection is configured or deterministic
- **WHEN** the XArm7 Pink IK task solves an IK tick
- **THEN** it SHALL use a configured QP solver name or a deterministic fallback selected from installed `qpsolvers` backends

#### Scenario: Solver failure does not publish unsafe commands
- **WHEN** Pink or the selected QP solver fails to produce a valid IK velocity
- **THEN** the task SHALL return no joint command for that tick and SHALL preserve coordinator stability

### Requirement: XArm7 Pink IK supports a weighted posture objective
The XArm7 Pink IK task SHALL support an optional weighted posture objective that biases IK solutions toward a configured or captured posture while keeping the configured end-effector frame task in the Pink solve.

#### Scenario: Posture objective is included with the frame task
- **WHEN** the XArm7 Pink IK task is configured with a nonzero posture cost
- **THEN** the task SHALL pass both the configured XArm7 frame task and the weighted posture task to `pink.solve_ik`

#### Scenario: Posture objective can be disabled
- **WHEN** the XArm7 Pink IK task is configured with posture disabled or zero posture cost
- **THEN** the task SHALL solve with the same frame-task-only objective shape used before this change

### Requirement: Weighted posture uses per-joint weights in model order
The weighted posture objective SHALL apply configured per-joint weights to both the Pink posture error and posture Jacobian using the Pinocchio model joint order that Pink expects.

#### Scenario: Configured joint weights map to XArm7 model joints
- **WHEN** posture weights are configured for XArm7 joint names
- **THEN** the task SHALL map those weights to the corresponding Pinocchio model joints before solving and SHALL fail startup for unknown posture joint names

#### Scenario: Unspecified posture weights use defaults
- **WHEN** a configured controlled XArm7 joint has no explicit posture weight
- **THEN** the task SHALL use the configured default posture weight for that joint

### Requirement: Weighted posture target is initialized safely
The XArm7 Pink IK task SHALL initialize the posture target without causing an immediate jump away from the current teleop engagement posture.

#### Scenario: Current posture initializes target by default
- **WHEN** no explicit posture reference is configured and the task receives a valid current XArm7 joint state for IK compute
- **THEN** the task SHALL set the weighted posture target from that current joint state before solving

#### Scenario: Configured posture reference overrides current posture
- **WHEN** an explicit posture reference is configured for one or more XArm7 joints
- **THEN** the task SHALL use those configured reference values for the posture target and current values for any unspecified controlled joints

### Requirement: Weighted posture preserves existing IK safety behavior
The weighted posture objective SHALL NOT bypass existing solver failure handling, target timeout behavior, or per-tick joint delta safety checks.

#### Scenario: Unsafe posture-biased output is rejected
- **WHEN** the combined frame and posture solve produces joint positions exceeding the configured per-tick delta limit
- **THEN** the task SHALL reject the command for that tick and SHALL NOT publish unsafe joint positions

#### Scenario: Solver failure remains non-commanding
- **WHEN** Pink or the selected QP solver fails while the posture objective is enabled
- **THEN** the task SHALL return no joint command for that tick and preserve coordinator stability

### Requirement: XArm7 Pink IK supports optional joint velocity damping
The XArm7 Pink IK task SHALL support an optional Pink damping objective that minimizes unnecessary joint velocity while preserving the existing end-effector frame objective and optional weighted posture objective.

#### Scenario: Damping objective is included when configured
- **WHEN** the XArm7 Pink IK task is configured with a positive damping-task cost
- **THEN** the task SHALL pass a Pink `DampingTask` together with its configured XArm7 frame task and any enabled posture task to `pink.solve_ik`

#### Scenario: Damping objective can be disabled
- **WHEN** the XArm7 Pink IK task is configured with a zero damping-task cost
- **THEN** the task SHALL solve with the same Pink task list shape used before damping support, excluding `DampingTask`

#### Scenario: Damping configuration is validated
- **WHEN** the XArm7 Pink IK task is configured with a negative or non-finite damping-task cost
- **THEN** task startup SHALL fail with a clear configuration error and SHALL NOT create the Pink IK task

### Requirement: XArm7 damping preserves existing IK safety behavior
The XArm7 Pink damping objective SHALL NOT bypass existing solver failure handling, target timeout behavior, missing joint-state handling, non-finite velocity rejection, or per-tick joint delta safety checks.

#### Scenario: Damping-enabled solver failure remains non-commanding
- **WHEN** Pink or the selected QP solver fails while the damping objective is enabled
- **THEN** the task SHALL return no joint command for that tick and preserve coordinator stability

#### Scenario: Unsafe damping-enabled output is rejected
- **WHEN** the combined frame, posture, and damping solve produces joint positions exceeding the configured per-tick delta limit
- **THEN** the task SHALL reject the command for that tick and SHALL NOT publish unsafe joint positions

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

### Requirement: OpenArm Pink IK task constructs a unified bimanual IK problem
The system SHALL provide an OpenArm-specific Pink teleop IK task that reuses the shared Pink IK base and constructs one whole-robot Pink problem with left and right frame tasks for the configured OpenArm model, joint names, and end-effector frames.

#### Scenario: OpenArm task validates configured model joints
- **WHEN** an OpenArm Pink IK task is created from coordinator or visualization configuration
- **THEN** it SHALL load the configured bimanual OpenArm URDF/MJCF model and validate that configured OpenArm whole-robot joint names match actuated model joints used for command output

#### Scenario: OpenArm task validates both end-effector frames
- **WHEN** the OpenArm Pink IK task initializes its robot-specific frame tasks
- **THEN** it SHALL fail startup with a clear error if either configured OpenArm end-effector frame is absent from the model

### Requirement: OpenArm Pink IK supports left and right targets in one solve
The system SHALL support distinct left and right Quest target updates while solving both targets through one Pink `solve_ik` call over one OpenArm robot configuration.

#### Scenario: Independent target state
- **WHEN** only one Quest hand updates its OpenArm target
- **THEN** the other OpenArm target SHALL remain at its last desired pose while the next Pink solve still considers all active targets in the same robot configuration

#### Scenario: Shared joints are coordinated by one optimization
- **WHEN** the OpenArm model includes joints that influence both end-effector targets or otherwise couple the two arms
- **THEN** the OpenArm Pink IK task SHALL solve those joints as part of the same optimization rather than commanding them from independent per-arm solves

#### Scenario: Shared solver plumbing remains coordinator-compatible
- **WHEN** an OpenArm Pink IK task returns a valid solve result
- **THEN** it SHALL emit `JointCommandOutput` or desired `JointState` data ordered by configured OpenArm whole-robot joint names and compatible with existing coordinator/visualization consumers

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
