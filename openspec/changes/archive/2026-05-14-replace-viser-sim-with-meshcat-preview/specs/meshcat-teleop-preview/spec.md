## ADDED Requirements

### Requirement: XArm7 Quest teleop defaults to mock preview without hardware IP
The system SHALL run `teleop-quest-xarm7` with mock XArm7 hardware and Meshcat visualization when no real XArm7 hardware address is configured and `--simulation` is not selected.

#### Scenario: No hardware IP starts mock preview
- **WHEN** a user runs `dimos --listen-host 0.0.0.0 run teleop-quest-xarm7` without configuring `xarm7_ip`
- **THEN** the blueprint SHALL use the mock XArm7 manipulator adapter and SHALL include the Meshcat teleop preview viewer

#### Scenario: Real hardware IP keeps hardware path
- **WHEN** a user runs `dimos --xarm7-ip <ip> run teleop-quest-xarm7` without `--simulation`
- **THEN** the blueprint SHALL use the real XArm7 hardware adapter and SHALL NOT include the mock-preview Meshcat viewer by default

#### Scenario: MuJoCo simulation remains explicit
- **WHEN** a user runs `dimos --simulation run teleop-quest-xarm7`
- **THEN** the blueprint SHALL use the MuJoCo simulation path rather than the mock Meshcat preview path

### Requirement: Meshcat preview loads the XArm7 robot model
The system SHALL provide a Meshcat teleop preview viewer that loads the configured XArm7 robot model for browser visualization.

#### Scenario: Valid XArm7 model starts Meshcat preview
- **WHEN** the Meshcat preview viewer starts with the configured XArm7 model path
- **THEN** it SHALL create a Meshcat browser server and display the XArm7 robot model

#### Scenario: Invalid model fails clearly
- **WHEN** the Meshcat preview viewer starts with a missing or unreadable robot model path
- **THEN** startup SHALL fail with an error that names the invalid model path

### Requirement: Meshcat preview honors listen host
The Meshcat teleop preview SHALL use the configured DimOS listen host for browser accessibility.

#### Scenario: Listen host configures Meshcat server host
- **WHEN** the Meshcat preview starts with `listen_host` set to `0.0.0.0`
- **THEN** the Meshcat server SHALL bind to an externally reachable host rather than hardcoding `127.0.0.1`

#### Scenario: Default listen host remains local
- **WHEN** the Meshcat preview starts without overriding `listen_host`
- **THEN** the Meshcat server SHALL use the DimOS default listen host

### Requirement: Meshcat preview visualizes coordinator joint state
The Meshcat teleop preview SHALL update the displayed robot configuration from typed coordinator `JointState` messages.

#### Scenario: Joint state updates robot pose
- **WHEN** the coordinator publishes a `JointState` with XArm7 joint names and positions
- **THEN** the Meshcat robot model SHALL update to those joint positions

#### Scenario: Prefixed DimOS joint names map to model names
- **WHEN** a coordinator `JointState` contains DimOS joint names such as `arm/joint1`
- **THEN** the Meshcat preview SHALL map them to model joint names such as `joint1` before updating the robot configuration

#### Scenario: Preview does not command hardware
- **WHEN** the Meshcat preview receives joint state
- **THEN** it SHALL only update visualization and SHALL NOT publish joint commands, write to a manipulator adapter, or control real hardware
