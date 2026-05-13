## Purpose

Provide a Viser URDF simulation backend for visualization-only robot simulation, desired joint-state display, teleop pose markers, and browser-accessible robot visualization without starting MuJoCo dynamics.

## Requirements

### Requirement: Viser URDF simulator loads a configured robot model
The system SHALL provide a Viser URDF simulation backend that loads a configured URDF robot model for visualization-only simulation without starting MuJoCo dynamics.

#### Scenario: Valid URDF starts Viser simulator
- **WHEN** the Viser URDF simulator starts with a valid XArm7 URDF path
- **THEN** it SHALL create a Viser server and load the URDF robot model into the Viser scene

#### Scenario: Invalid URDF fails clearly
- **WHEN** the Viser URDF simulator starts with a missing or unreadable URDF path
- **THEN** startup SHALL fail with an error that names the invalid URDF path

#### Scenario: Simulator does not start physics
- **WHEN** the Viser URDF simulator is selected
- **THEN** it SHALL NOT start MuJoCo, step physics, create camera streams, or require a MuJoCo XML scene

### Requirement: Viser URDF simulator visualizes desired joint state
The system SHALL update the Viser robot configuration from typed desired `JointState` messages using joint names and joint positions.

#### Scenario: Desired joint state updates robot pose
- **WHEN** a desired `JointState` arrives with joint names matching the URDF actuated joints and positions in radians
- **THEN** the Viser robot model SHALL update to those desired joint positions

#### Scenario: Prefixed DimOS joint names map to URDF names
- **WHEN** a desired `JointState` contains DimOS joint names such as `arm/joint1`
- **THEN** the Viser simulator SHALL map them to URDF joint names such as `joint1` before updating the robot configuration

#### Scenario: Incomplete desired state preserves prior pose
- **WHEN** a desired `JointState` omits an actuated joint or lacks a matching position value
- **THEN** the Viser simulator SHALL preserve that joint's previous displayed value and SHALL NOT invent a new position

### Requirement: Viser URDF simulator visualizes desired teleop poses
The system SHALL show desired controller, desired target, and computed desired end-effector pose frames alongside the URDF robot when those typed pose streams are available.

#### Scenario: Desired controller pose is visible
- **WHEN** the teleop path publishes a desired controller `PoseStamped`
- **THEN** the Viser simulator SHALL render a distinct pose frame or marker for the desired controller pose without overwriting robot joint state

#### Scenario: Desired target pose is visible
- **WHEN** the teleop path publishes a desired target `PoseStamped`
- **THEN** the Viser simulator SHALL render a distinct pose frame or marker for the desired target pose without overwriting robot joint state

#### Scenario: Desired end-effector pose is visible
- **WHEN** desired joint state is visualized and an end-effector frame is configured
- **THEN** the Viser simulator SHALL render the desired end-effector pose derived from the displayed desired robot configuration

### Requirement: XArm7 Quest teleop keeps MuJoCo simulation backend
The system SHALL keep XArm7 Quest teleop simulation on the existing MuJoCo backend after removing the deprecated Pink IK visualization wrapper and related robot-vis blueprints.

#### Scenario: Existing MuJoCo simulation remains default
- **WHEN** a user runs `dimos --simulation run teleop-quest-xarm7` without selecting a simulator backend
- **THEN** the system SHALL use the existing MuJoCo-backed XArm7 teleop simulation behavior

#### Scenario: Real hardware path remains unchanged
- **WHEN** a user runs `dimos run teleop-quest-xarm7` without `--simulation`
- **THEN** the blueprint SHALL continue to use the real XArm7 hardware teleop path and SHALL NOT include the Viser URDF simulator

### Requirement: Viser server honors listen host
The Viser URDF simulator SHALL use the configured DimOS listen host for browser accessibility.

#### Scenario: Listen host configures Viser server host
- **WHEN** a Viser URDF simulator module starts with `listen_host` set to `0.0.0.0`
- **THEN** the Viser server SHALL bind to `0.0.0.0` rather than hardcoding `127.0.0.1`

#### Scenario: Default listen host remains local
- **WHEN** a Viser URDF simulator module starts without overriding `listen_host`
- **THEN** the Viser server SHALL use the DimOS default listen host
