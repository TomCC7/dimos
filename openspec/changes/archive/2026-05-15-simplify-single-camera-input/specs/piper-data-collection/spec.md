## MODIFIED Requirements

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
