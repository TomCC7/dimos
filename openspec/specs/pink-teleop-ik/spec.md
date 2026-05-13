## Purpose

Define the accepted behavior for Pink-backed teleoperation IK control tasks, starting with the XArm7 teleop implementation.

## Requirements

### Requirement: Shared Pink IK base task provides common solver plumbing
The system SHALL provide a shared Pink IK base task for teleoperation control tasks that owns common Pink solver setup, current-joint extraction, target-update hooks, safety checks, and coordinator-compatible joint command output.

#### Scenario: Base task uses coordinator timing
- **WHEN** the control coordinator calls a Pink-backed teleop IK task with `CoordinatorState`
- **THEN** the task SHALL use `CoordinatorState.t_now` and `CoordinatorState.dt` for timeout and Pink integration behavior rather than calling wall-clock time directly

#### Scenario: Base task emits coordinator-compatible joint commands
- **WHEN** Pink returns a valid IK velocity for the active target state
- **THEN** the base task SHALL integrate the velocity into joint positions ordered by configured joint names and return a `JointCommandOutput` compatible with coordinator arbitration

#### Scenario: Base task enforces joint delta safety
- **WHEN** an IK result would move any controlled joint beyond the configured per-tick delta limit
- **THEN** the task SHALL reject that command for the tick and SHALL NOT publish unsafe joint positions

#### Scenario: Base task does not assume a single end-effector target
- **WHEN** a Pink-backed task constructs one or more robot-specific frame tasks
- **THEN** the shared base SHALL allow the concrete task to update its own frame targets before solving and SHALL NOT require all subclasses to use only `frame_tasks[0]`, one target pose, or one captured end-effector baseline

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
