## ADDED Requirements

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
