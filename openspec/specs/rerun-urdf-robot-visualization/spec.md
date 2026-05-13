## Purpose

Provide a Rerun robot visualization capability for configured URDF robot models, typed joint state updates, debug pose frames, and an XArm7 Quest teleop blueprint that visualizes desired IK output without MuJoCo dynamics.

## Requirements

### Requirement: Rerun visualization loads a configured URDF robot model
The system SHALL provide a Rerun robot visualization capability that accepts a configured URDF path and logs the robot geometry and static frame structure into Rerun.

#### Scenario: URDF is logged once
- **WHEN** a Rerun robot visualizer starts with a valid URDF path
- **THEN** the visualizer SHALL log the URDF file to Rerun exactly once for static robot geometry loading

#### Scenario: Invalid URDF path fails startup
- **WHEN** the visualizer is configured with a missing or unreadable URDF path
- **THEN** the visualizer SHALL fail startup with a clear error naming the invalid path

### Requirement: Rerun visualization updates robot joints from typed JointState input
The system SHALL update the Rerun robot joint configuration from `JointState` messages using `JointState.name` and `JointState.position` as typed joint-name and joint-position data.

#### Scenario: Named joint positions update URDF transforms
- **WHEN** a `JointState` arrives with names matching URDF revolute joints and corresponding position values in radians
- **THEN** the visualizer SHALL log Rerun `Transform3D` updates for those joints using the URDF joint transform definitions

#### Scenario: Prefixed DimOS joint names map to URDF joint names
- **WHEN** a `JointState` contains DimOS joint names such as `arm/joint1`
- **THEN** the visualizer SHALL support mapping those names to URDF joint names such as `joint1` without relying on list position alone

#### Scenario: Missing joint data preserves last visual state
- **WHEN** a `JointState` omits a URDF joint or lacks a corresponding position value
- **THEN** the visualizer SHALL leave that joint at its previous visual value and SHALL NOT invent a new position

### Requirement: Rerun visualization logs debug pose frames
The system SHALL support logging configured `PoseStamped` debug frames into Rerun so desired controller pose, desired end-effector target, and computed robot end-effector pose can be inspected alongside the robot model.

#### Scenario: Desired controller pose is visualized
- **WHEN** a desired controller or target `PoseStamped` is received
- **THEN** the visualizer SHALL log a distinct Rerun transform or marker entity for that pose without overwriting robot joint transforms

#### Scenario: End-effector pose is visualized
- **WHEN** the visualizer computes or receives the current robot end-effector pose
- **THEN** it SHALL log a distinct Rerun transform or marker entity for the end-effector pose

### Requirement: XArm7 Quest teleop Rerun blueprint visualizes desired IK output without MuJoCo dynamics
The system SHALL provide a `teleop-quest-xarm7-rerun` blueprint that uses Quest right-controller teleop and Pink IK output to visualize the desired XArm7 robot configuration in Rerun without using MuJoCo actuator dynamics.

#### Scenario: Blueprint is listed by DimOS
- **WHEN** users run `dimos list`
- **THEN** `teleop-quest-xarm7-rerun` SHALL appear as a runnable blueprint

#### Scenario: Right-controller route remains teleop_xarm
- **WHEN** the Quest right controller publishes a `PoseStamped` command for XArm7 teleop
- **THEN** the command SHALL use the existing `frame_id="teleop_xarm"` route key for compatibility with the Pink IK task

#### Scenario: Desired joint state drives visualization directly
- **WHEN** Pink IK produces desired XArm7 joint positions
- **THEN** the Rerun robot visualizer SHALL update the displayed XArm7 URDF joints from those desired positions without waiting for MuJoCo or hardware feedback

### Requirement: Rerun visualization supports OpenArm bimanual desired state
The system SHALL visualize the OpenArm bimanual URDF from named whole-robot `JointState` desired positions published by the unified OpenArm Quest Rerun teleop example.

#### Scenario: OpenArm joint names update matching URDF joints
- **WHEN** a desired whole-robot `JointState` contains OpenArm joint names such as `openarm_left_joint1` or `openarm_right_joint1`
- **THEN** the Rerun URDF visualizer SHALL map those names to matching OpenArm URDF joints and update the corresponding transforms

#### Scenario: OpenArm debug poses use distinct Rerun entity paths
- **WHEN** the OpenArm desired-state module publishes controller, target, or end-effector debug poses for either hand
- **THEN** the Rerun visualization SHALL log those poses under distinct left/right entity paths without overwriting robot joint transforms or the other hand's debug frames

### Requirement: Rerun joint-name normalization uses slash suffixes
The system SHALL normalize DimOS coordinator-prefixed joint names for URDF visualization by using the suffix after the final `/`, while leaving names without `/` unchanged.

#### Scenario: Coordinator-prefixed xArm names map to URDF names
- **WHEN** a Rerun URDF visualizer receives a `JointState` joint name such as `arm/joint1` or `left_arm/joint1`
- **THEN** it SHALL look up the URDF joint as `joint1`

#### Scenario: Already-qualified OpenArm names remain unchanged
- **WHEN** a Rerun URDF visualizer receives a `JointState` joint name such as `openarm_left_joint1`
- **THEN** it SHALL look up the URDF joint as `openarm_left_joint1`
