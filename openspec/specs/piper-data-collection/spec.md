# piper-data-collection Specification

## Purpose
TBD - created by archiving change piper-data-collection. Update Purpose after archive.
## Requirements
### Requirement: Piper data collection blueprint is registered
The system SHALL provide a registered Piper data collection blueprint that preserves the current Piper Quest teleop control surface while adding native recording of demonstration streams.

#### Scenario: Launch by CLI registry key
- **WHEN** a user lists or runs the Piper data collection blueprint by its CLI registry key
- **THEN** the registry SHALL resolve the blueprint from the generated blueprint registry

#### Scenario: Teleop routing is preserved
- **WHEN** the Piper data collection blueprint is inspected
- **THEN** it SHALL route left Quest controller output to the Piper `teleop_piper` coordinator task through `/coordinator/cartesian_command`
- **AND** it SHALL route teleop buttons through `/teleop/buttons`

### Requirement: Data collection writes one Rerun recording file per episode
The Piper data collection blueprint SHALL write each demonstration episode to its own Rerun `.rrd` file at a stable, factory-produced path under the configured DimOS data directory, so each episode is a single addressable artifact for replay, optimization, dataset-viewer flagging, and training.

#### Scenario: Per-episode file path
- **WHEN** a Piper data collection session writes its Nth episode
- **THEN** the system SHALL write that episode's recording to `{data_dir}/piper_data_collection/<session_name>/episode_<NNN>.rrd`
- **AND** `<session_name>` SHALL default to a UTC timestamp of the form `YYYYMMDDTHHMMSSZ`
- **AND** `<NNN>` SHALL be the 1-indexed, zero-padded episode counter for that session

#### Scenario: Episodes within a session share a session directory
- **WHEN** multiple episodes are recorded within one bridge lifecycle
- **THEN** every episode's `.rrd` file SHALL be written under the same `<session_name>` directory
- **AND** the episode counter SHALL increment monotonically across the session

#### Scenario: Recording is replayable in the Rerun viewer
- **WHEN** an episode has completed
- **THEN** opening the resulting `.rrd` in the Rerun viewer SHALL reproduce the episode's logged entities under their original entity paths and timestamps

#### Scenario: Recording proceeds without a live viewer
- **WHEN** no live Rerun viewer is reachable
- **THEN** episode `.rrd` files SHALL still be written for the duration of the session (subject to operator toggling)
- **AND** the absence of a viewer SHALL NOT cause the recording sink to drop messages while RECORDING

#### Scenario: Session starts in IDLE
- **WHEN** the data collection blueprint starts
- **THEN** the recorder SHALL enter IDLE
- **AND** no `.rrd` file SHALL be opened until the operator presses the toggle button
- **AND** any messages dispatched before the first toggle SHALL NOT be written to disk

### Requirement: Operator can toggle recording on and off within a session
The data collection blueprint SHALL provide an operator-driven recording toggle so an operator can record a demonstration, pause to reset the scene at their own pace, then resume into the next demonstration — all within one running session.

The recorder is in one of two states: **RECORDING** (an episode `.rrd` is open and accepting messages) or **IDLE** (no `.rrd` is open; messages on the bus pass to the live viewer but are not written to disk). Session start enters IDLE — the first toggle press opens `episode_001.rrd`. This keeps warmup motion, scene setup, and gripper calibration from ever being baked into a recording. Each subsequent toggle event flips the state.

#### Scenario: Quest button toggles recording state
- **WHEN** the operator presses the configured Quest controller toggle button while the recorder is RECORDING
- **THEN** the recorder SHALL flush and close the current episode's `.rrd` file
- **AND** the recorder SHALL enter IDLE
- **AND** no new `.rrd` file SHALL be opened until the next toggle event

- **WHEN** the operator presses the configured Quest controller toggle button while the recorder is IDLE
- **THEN** the recorder SHALL open a new episode `.rrd` at the next path produced by the configured path factory
- **AND** the recorder SHALL enter RECORDING
- **AND** subsequent messages SHALL be logged to that new episode

#### Scenario: Messages during the IDLE gap are not persisted
- **WHEN** the recorder is in IDLE and any message is dispatched on a recorded transport
- **THEN** the recorder SHALL NOT write that message to any `.rrd` file
- **AND** no new `.rrd` file SHALL be created as a side effect of the message

#### Scenario: Toggle is debounced
- **WHEN** toggle button events occur within 500 milliseconds of a prior toggle
- **THEN** those subsequent events SHALL be ignored
- **AND** no extra state transition SHALL occur
- **AND** no extra empty `.rrd` file SHALL be produced as a result of the bounce

#### Scenario: Empty current episode is discarded on toggle-off
- **WHEN** the operator toggles to IDLE before any payload entity has been logged to the current episode
- **THEN** the current episode's `.rrd` file SHALL be removed instead of left as a zero-content artifact
- **AND** the recorder SHALL still enter IDLE

#### Scenario: Toggle preserves the recording across in-flight messages
- **WHEN** a toggle is requested while messages are being dispatched to the recording stream
- **THEN** no in-flight message SHALL be lost or duplicated across the boundary
- **AND** every message dispatched before the toggle SHALL appear only in the (now closing) episode if it was a toggle-off, or nowhere if it landed during a prior IDLE
- **AND** every message dispatched after the toggle SHALL appear only in the next opened episode (if any) — never in the closed one

### Requirement: Each episode carries identifying metadata
Every recorded episode `.rrd` SHALL contain static metadata that identifies the episode, its position in the session, the session itself, and (when known) the operator, so downstream catalog tooling can describe and filter episodes without inspecting payload data.

#### Scenario: Episode-level static metadata is present
- **WHEN** an episode `.rrd` is opened
- **THEN** it SHALL contain a static entity at `/meta/episode_id` whose value uniquely identifies the episode
- **AND** it SHALL contain a static entity at `/meta/episode_index` whose value is the 1-indexed position of the episode within its session
- **AND** it SHALL contain a static entity at `/meta/session_id` whose value identifies the session the episode belongs to

#### Scenario: Operator metadata is recorded when configured
- **WHEN** an operator identifier is configured for the session
- **THEN** every episode `.rrd` in that session SHALL contain a static entity at `/meta/operator` carrying that identifier

#### Scenario: Operator metadata is absent when unconfigured
- **WHEN** no operator identifier is configured for the session
- **THEN** episode `.rrd` files SHALL NOT contain a `/meta/operator` entity
- **AND** the absence SHALL NOT prevent the recording from starting

### Requirement: Live viewer and on-disk recording are independent modules
The data collection blueprint SHALL provide the live Rerun viewer and the on-disk Rerun recording as two distinct DimOS modules — a viewer module and a recorder module — each owning its own `rr.RecordingStream` and its own pubsub subscriptions, so the two sinks can be configured, throttled, and fail independently.

#### Scenario: Recording is full-rate by construction
- **WHEN** the data collection blueprint is running
- **THEN** every message published on the recorded transports SHALL be logged to the recorder's `.rrd` stream
- **AND** no live-viewer throttle SHALL apply to the recorder

#### Scenario: Live viewer remains throttleable
- **WHEN** an operator configures a live-viewer rate cap (`max_hz`) on the viewer module for an entity
- **THEN** the live viewer SHALL emit at most that rate for that entity
- **AND** the recorder SHALL be unaffected by the viewer's throttle

#### Scenario: Viewer failure is isolated from the recorder
- **WHEN** the live viewer connection is lost or the viewer module fails to start
- **THEN** the recorder SHALL continue to write `.rrd` files for the duration of the session
- **AND** the data collection blueprint SHALL continue to run

#### Scenario: Recorder failure is isolated from the viewer
- **WHEN** the recorder module fails to start (e.g., disk full, invalid path)
- **THEN** the live viewer SHALL continue to serve the operator
- **AND** the failure SHALL be surfaced through the recorder module's own logging, not through the viewer module's path

### Requirement: Recorded entity paths use a LeRobot-aligned schema
The data collection recording SHALL log each recorded signal under an entity path that identifies its semantic role using a LeRobot-style `observation` / `action` namespace, so downstream readers can locate signals by role without consulting topic metadata.

The camera observation entity path SHALL be configured on `RerunDataRecorderConfig.camera_entity_path` (default `/observation/camera/usb`). All other recorded signals SHALL continue to be routed through the recorder's `topic_to_entity` / `visual_override` mechanism.

#### Scenario: Camera image lives under the observation namespace
- **WHEN** the USB camera publishes an `Image` during a session
- **THEN** the recording SHALL log it under the entity path configured by `camera_entity_path` (default `/observation/camera/usb`)

#### Scenario: Measured joint state lives under the observation state namespace
- **WHEN** the coordinator publishes a `JointState` on `/coordinator/joint_state`
- **THEN** the recording SHALL emit one scalar per joint under entity paths of the form `/observation/state/<short_joint_name>`
- **AND** the gripper joint SHALL appear under `/observation/state/<gripper_short_name>` using the same scheme

#### Scenario: Desired joint action lives under the action namespace
- **WHEN** the coordinator publishes a `JointState` on `/coordinator/desired_joint_action`
- **THEN** the recording SHALL emit one scalar per joint under entity paths of the form `/action/<short_joint_name>`
- **AND** the gripper joint SHALL appear under `/action/<gripper_short_name>` using the same scheme

#### Scenario: Episode metadata uses the meta namespace
- **WHEN** static metadata is logged for an episode
- **THEN** the recording SHALL place those entities under `/meta/...` (the namespace covered in detail by the per-episode metadata requirement)

### Requirement: Recordings are directly readable by Rerun's dataframe and dataloader APIs
A Piper data collection session's `.rrd` file SHALL be readable by Rerun's dataframe and experimental PyTorch dataloader APIs without an intermediate conversion step at training time, so collected demonstrations are training-ready as written.

#### Scenario: Dataframe read of recorded streams
- **WHEN** a downstream consumer opens an episode `.rrd` via `rerun.dataframe`
- **THEN** the consumer SHALL be able to select all entities under `/observation/state/`, `/observation/camera/`, and `/action/` by entity-path prefix
- **AND** each selected entity SHALL surface its values as Arrow chunks indexed by recorded time

#### Scenario: Dataloader windowing over an episode
- **WHEN** a downstream consumer opens an episode `.rrd` via `rerun.experimental.dataloader` with a `window=(start_offset, end_offset)` configuration
- **THEN** each yielded sample SHALL include the recorded camera frames and joint observations from the window
- **AND** the corresponding `/action/...` values from the same window SHALL be aligned to the observation timestamps

#### Scenario: Catalog server enumerates episodes as rows
- **WHEN** an operator points `rr.server.Server(datasets={...})` at the `piper_data_collection` directory
- **THEN** every episode `.rrd` under that directory SHALL be discoverable as an individual entry in the resulting dataset
- **AND** each entry SHALL be addressable as a single URI by downstream catalog tooling

#### Scenario: No collection-time training dependency
- **WHEN** running data collection
- **THEN** the system SHALL NOT require any training-side dependency (`rerun.experimental.dataloader`, LeRobot, PyTorch) to be importable for the session to start or record

### Requirement: Data collection records camera observation
The system SHALL record a single USB camera image stream as the visual observation for Piper data collection by logging it to the recorder module's `.rrd` stream under a configured entity path.

The camera image SHALL reach the recorder through a typed `color_image: In[Image]` input slot on `RerunDataRecorder`, wired by the data-collection blueprint via the standard blueprint transport map. The recorder SHALL log each frame received on this slot under `RerunDataRecorderConfig.camera_entity_path` (defaulting to `/observation/camera/usb`, the LeRobot-aligned schema). The camera path SHALL NOT be routed through the recorder's generic `pubsubs` + `topic_to_entity` mechanism.

#### Scenario: USB camera stream is present
- **WHEN** the Piper data collection blueprint is built
- **THEN** it SHALL include a USB webcam camera module that publishes `Image` messages on the transport routed to the recorder's `color_image` input
- **AND** there SHALL be exactly one camera in the deployment

#### Scenario: Camera recording goes through the typed slot
- **WHEN** the data collection blueprint is active and the camera publishes a frame
- **THEN** the recorder SHALL receive that frame on its `color_image` `In[Image]` input
- **AND** it SHALL log the frame under `RerunDataRecorderConfig.camera_entity_path`
- **AND** the same frame SHALL NOT be logged a second time through the generic `_on_message` / `topic_to_entity` path

#### Scenario: Default entity path matches the recorder schema
- **WHEN** the data collection blueprint does not override `camera_entity_path`
- **THEN** camera frames SHALL be logged under `/observation/camera/usb`
- **AND** that entity path SHALL remain consistent with the LeRobot-aligned schema defined in this capability, so existing `.rrd` recordings remain comparable

### Requirement: Data collection records measured joint state
The system SHALL record Piper measured joint state from the control coordinator as the robot state observation by logging per-joint scalars to the recorder module's `.rrd` stream.

#### Scenario: Measured state uses coordinator output
- **WHEN** the Piper coordinator publishes measured joint state on `/coordinator/joint_state`
- **THEN** the recorder module SHALL log one scalar per joint listed in the message to the current episode's `.rrd`
- **AND** those scalars SHALL be logged under entity paths consistent with the LeRobot-aligned schema for measured observations defined in this capability

### Requirement: Data collection records desired joint action
The system SHALL expose and record the post-arbitration desired Piper joint action produced by the control coordinator by logging per-joint scalars to the recorder module's `.rrd` stream.

#### Scenario: Coordinator publishes desired action
- **WHEN** the coordinator computes and arbitrates active task outputs for a tick
- **THEN** it SHALL publish the desired joint action as a typed `JointState` stream containing the command values that will be routed to hardware

#### Scenario: Desired action is recorded under the action namespace
- **WHEN** a desired joint action `JointState` arrives on `/coordinator/desired_joint_action`
- **THEN** the recorder module SHALL log one scalar per joint to the current episode's `.rrd` under the LeRobot-aligned action entity paths defined in this capability
- **AND** the recorded measured-state and recorded action entity paths SHALL be distinct so a downstream reader can separate `observation.state` from `action`

### Requirement: Data collection blueprint exposes recorded streams to a live Rerun visualization

The Piper data collection blueprint SHALL include a Rerun visualization sink driven from the same LCM transports that feed the on-disk recording, so an operator can verify capture quality during the session without inspecting the recorded `.rrd` file.

#### Scenario: Rerun visualization atom is part of the blueprint

- **WHEN** the `teleop_quest_piper_data_collection` blueprint is built
- **THEN** it SHALL include a Rerun-backed visualization sink obtained through the shared `vis_module("rerun", ...)` factory
- **AND** that sink SHALL subscribe to the same LCM topics used for camera image, measured joint state, and desired joint action recording

#### Scenario: Viewer and recorder consume the same conversion contract

- **WHEN** the data collection blueprint is built
- **THEN** the viewer module and the recorder module SHALL be configured from the same source-of-truth conversion dictionary (the same `visual_override` map, `entity_prefix`, and `topic_to_entity` callback)
- **AND** any recorded entity path SHALL match what the viewer would log for the same incoming message

#### Scenario: Visualization failure does not break recording

- **WHEN** the Rerun viewer is unreachable or fails to start
- **THEN** the data collection blueprint SHALL continue to run and the recorder module SHALL continue to write its `.rrd` files to disk
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
