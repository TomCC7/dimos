## ADDED Requirements

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
