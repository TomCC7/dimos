## ADDED Requirements

### Requirement: Data collection blueprint exposes recorded streams to a live Rerun visualization

The Piper data collection blueprint SHALL include a Rerun visualization sink driven from the same LCM transports that feed the on-disk recorder, so an operator can verify capture quality during the session without inspecting recorded files.

#### Scenario: Rerun visualization atom is part of the blueprint

- **WHEN** the `teleop_quest_piper_data_collection` blueprint is built
- **THEN** it SHALL include a Rerun-backed visualization sink obtained through the shared `vis_module("rerun", ...)` factory
- **AND** that sink SHALL subscribe to the same LCM topics used for camera image, measured joint state, and desired joint action recording

#### Scenario: Visualization is a passive sink

- **WHEN** the Rerun visualization sink processes a message
- **THEN** it SHALL NOT modify, drop, or delay the message on the recording path
- **AND** the on-disk recording produced by the data collection recorder SHALL be byte-identical to a session run without the visualization sink

#### Scenario: Visualization failure does not break recording

- **WHEN** the Rerun viewer is unreachable or fails to start
- **THEN** the data collection blueprint SHALL continue to run and record streams to disk
- **AND** the failure SHALL be surfaced through the visualization module's existing logging, not by raising into the data collection control path

### Requirement: Visualization renders the recorded camera stream

The Rerun visualization sink SHALL render the USB camera color image stream live, at the rate it is published by the camera module.

#### Scenario: Camera image is visible in the Rerun viewer

- **WHEN** the camera module publishes an `Image` on the data collection blueprint's camera image transport
- **THEN** the Rerun viewer SHALL display that image under an entity path corresponding to the camera image transport

#### Scenario: Camera visualization is not throttled below the publish rate

- **WHEN** the camera publishes at its configured rate
- **THEN** the Rerun visualization SHALL log every published frame, subject only to the bridge's standard backpressure, with no additional per-entity throttle applied to the camera path

### Requirement: Visualization renders measured joint state as per-joint scalar timeseries

The Rerun visualization sink SHALL convert the measured `JointState` on `/coordinator/joint_state` into one scalar timeseries per joint, including the gripper joint, so the operator can see each joint's measured position move in time.

#### Scenario: Each measured joint is plotted on its own entity path

- **WHEN** a `JointState` arrives on `/coordinator/joint_state`
- **THEN** the visualization SHALL emit one Rerun scalar per joint listed in the message
- **AND** each scalar SHALL be logged under a distinct entity path that identifies the joint and marks the value as a measured observation

#### Scenario: Joint name source matches the Piper robot model

- **WHEN** the visualization is constructed
- **THEN** the joint names used to build entity paths SHALL be derived from the same Piper robot model configuration that the blueprint already uses to drive control, not hard-coded in the visualization wiring

### Requirement: Visualization renders desired joint action as per-joint scalar timeseries

The Rerun visualization sink SHALL convert the desired `JointState` on `/coordinator/desired_joint_action` into one scalar timeseries per joint, including the gripper joint, using entity paths that pair with the measured-state paths.

#### Scenario: Each commanded joint is plotted on its own entity path

- **WHEN** a `JointState` arrives on `/coordinator/desired_joint_action`
- **THEN** the visualization SHALL emit one Rerun scalar per joint listed in the message
- **AND** each scalar SHALL be logged under a distinct entity path that identifies the joint and marks the value as a desired command

#### Scenario: Commanded and measured paths are distinct but joinable

- **WHEN** the measured and commanded paths are inspected
- **THEN** the entity path scheme SHALL allow a single Rerun view to display the measured and commanded series for the same joint together
- **AND** the measured and commanded scalars for the same joint SHALL NOT share an entity path (so series remain individually addressable)

### Requirement: Gripper command and state are visualized as part of the joint set

The Rerun visualization sink SHALL plot the Piper gripper command and gripper measured value using the same per-joint scalar mechanism as the arm joints, with no separate gripper-only stream.

#### Scenario: Gripper appears in the joint plot set

- **WHEN** the visualization renders measured and commanded joints
- **THEN** the gripper joint (as named by the Piper robot model) SHALL appear as one measured scalar series and one commanded scalar series
- **AND** the gripper SHALL use the same entity path conventions as the arm joints (no special-cased path)

### Requirement: Data collection blueprint ships a Rerun layout preset

The Piper data collection blueprint SHALL register a Rerun blueprint factory that lays out the visualization at startup so the operator sees the camera and per-joint plots without manually arranging panels.

#### Scenario: Layout pairs the camera with per-joint plots

- **WHEN** the operator opens the Rerun viewer for a data collection session
- **THEN** the default layout SHALL show the camera image and the per-joint scalar plots side-by-side
- **AND** each per-joint plot SHALL contain the measured and commanded scalar series for that joint in a single view

#### Scenario: Layout includes every Piper joint, ending with the gripper

- **WHEN** the layout is rendered
- **THEN** it SHALL contain one per-joint plot for every joint listed in the Piper robot model used by the blueprint
- **AND** the gripper joint SHALL be the last per-joint plot in the joint plot stack

#### Scenario: Layout is stable across the session

- **WHEN** entities arrive for the first time during a session (camera image, then individual joint scalars)
- **THEN** the Rerun viewer SHALL retain the preset layout
- **AND** the viewer SHALL NOT auto-rearrange panels as new entity paths appear
