# single-arm-pink-teleop Specification

## Purpose
TBD - created by archiving change support-piper-pink-teleop. Update Purpose after archive.
## Requirements
### Requirement: Shared single-arm Pink teleop task is configurable by robot
The system SHALL provide a shared Pink-backed teleop IK task for one manipulator arm and one end-effector frame, with robot-specific behavior selected by explicit task/config subclasses and registry-based construction rather than coordinator `if/elif` robot branches.

#### Scenario: Robot-specific model and frame are configured by task config
- **WHEN** a single-arm Pink teleop task is created for a robot
- **THEN** the task SHALL load the configured URDF or MJCF model path, validate configured controlled joint names against model DOF, and fail startup if the configured end-effector frame is absent

#### Scenario: New robot config avoids coordinator branch additions
- **WHEN** a new single-arm Pink task/config subclass is introduced and registered
- **THEN** creating that task SHALL NOT require adding a new robot-specific `if/elif` branch in coordinator task construction

### Requirement: Shared single-arm Pink teleop preserves Quest delta control
The system SHALL interpret Quest controller poses for the shared single-arm Pink teleop task as robot-frame deltas from controller engagement, matching existing XArm7/Piper control behavior.

#### Scenario: Controller engage captures robot baseline
- **WHEN** the configured controller hand engages and current joint state is available
- **THEN** the task SHALL capture the current configured end-effector pose as baseline for subsequent controller deltas

#### Scenario: Controller delta updates frame target through unified task binding
- **WHEN** an engaged controller publishes a routed `PoseStamped` delta
- **THEN** the task SHALL apply that delta to the captured baseline and bind the result into the active Pink task set through one composition flow that includes both frame and auxiliary tasks

### Requirement: Piper Quest teleop uses Pink IK
The `teleop_quest_piper` blueprint SHALL drive Piper through the shared single-arm Pink teleop task while preserving the existing Quest and coordinator transport surface.

#### Scenario: Piper blueprint routes left controller to Pink task
- **WHEN** `teleop_quest_piper` publishes an engaged left-controller `PoseStamped` with `frame_id` set to `teleop_piper`
- **THEN** the coordinator SHALL route that command to the Piper single-arm Pink teleop task

#### Scenario: Piper task uses Piper kinematic configuration
- **WHEN** the Piper Pink teleop task is created by `coordinator_teleop_piper`
- **THEN** it SHALL use Piper controlled arm joint names, gripper-inclusive `PIPER_FK_MODEL`, `gripper_base` as the Pink IK end-effector frame, the left Quest hand, and Piper-specific gripper open and closed positions

#### Scenario: Piper gripper model locks uncontrolled finger joints for arm IK
- **WHEN** the Piper Pink teleop task loads a gripper-inclusive model containing finger joints outside the configured arm joint set
- **THEN** it SHALL lock the uncontrolled finger joints out of the Pink model while preserving the gripper end-effector frame used as the IK target

#### Scenario: Piper teleop preserves public launch surface
- **WHEN** a user runs `dimos run teleop-quest-piper` or `dimos --simulation run teleop-quest-piper`
- **THEN** the registered blueprint SHALL start the same public `teleop-quest-piper` target while using the Pink-backed Piper teleop task internally

#### Scenario: Piper without CAN uses mock preview
- **WHEN** a user runs `teleop_quest_piper` on non-simulation hardware mode without a configured CAN port
- **THEN** the Piper coordinator SHALL use the mock manipulator adapter and `teleop_quest_piper` SHALL include the existing ManipulationModule Drake/Meshcat visualization connected to `/coordinator/joint_state`

#### Scenario: Piper with CAN uses hardware with manipulation visualization
- **WHEN** a user runs `teleop_quest_piper` on non-simulation hardware mode with a configured CAN port
- **THEN** the Piper coordinator SHALL use the Piper hardware adapter and `teleop_quest_piper` SHALL include the existing ManipulationModule Drake/Meshcat visualization connected to `/coordinator/joint_state`

#### Scenario: Piper simulation uses MuJoCo without preview
- **WHEN** a user runs `teleop_quest_piper` with simulation enabled
- **THEN** the Piper coordinator SHALL use the MuJoCo simulation adapter and `teleop_quest_piper` SHALL NOT include the ManipulationModule preview visualization

### Requirement: Shared single-arm Pink teleop claims arm and gripper resources
The shared single-arm Pink teleop task SHALL participate in coordinator arbitration by claiming its configured arm joints and optional gripper joint using servo-position control mode.

#### Scenario: Arm-only task claim
- **WHEN** a single-arm Pink teleop task is configured without a gripper joint
- **THEN** the task claim SHALL include exactly the configured arm joints

#### Scenario: Arm and gripper task claim
- **WHEN** a single-arm Pink teleop task is configured with a gripper joint
- **THEN** the task claim SHALL include the configured arm joints and the configured gripper joint

#### Scenario: Gripper trigger maps to robot-specific range
- **WHEN** the configured controller hand reports an analog trigger value
- **THEN** the task SHALL map that trigger value between the configured gripper open and closed positions before emitting the gripper joint command
