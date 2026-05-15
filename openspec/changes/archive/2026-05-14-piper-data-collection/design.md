## Context

`teleop_quest_piper` currently composes `ArmTeleopModule.blueprint(task_names={"left": "teleop_piper"})` with `coordinator_teleop_piper`, then routes left-controller `PoseStamped` messages to `/coordinator/cartesian_command`, button state to `/teleop/buttons`, and measured coordinator state to `/coordinator/joint_state`. `coordinator_teleop_piper` already builds a Piper `single_arm_pink_ik` task named `teleop_piper` with Piper hardware/simulation wiring, so the data-collection path should reuse that teleop route rather than introduce a parallel controller.

USB camera capture already exists through `CameraModule`, whose default hardware is `Webcam`; it publishes `color_image: Out[Image]` and `camera_info: Out[CameraInfo]`. DimOS stream storage exists through `TimedSensorStorage`, which records subscribed stream frames with timestamps and can replay them later. The current storage API is per-stream and primitive, so the collection blueprint should explicitly subscribe the needed streams rather than assume a general module-I/O recorder exists.

The main missing surface is the action stream. `TickLoop` reads hardware, computes active task outputs, arbitrates per-joint winners into `joint_commands`, routes those commands to hardware, writes them, and publishes only the measured `JointState`. The desired joint action requested for learning is the post-compute/post-arbitration command that is actually sent to hardware, not the raw Quest pose input and not the measured state.

## Goals / Non-Goals

**Goals:**

- Add a registered Piper data-collection blueprint that preserves the current Piper Quest teleop behavior.
- Compose Piper teleop with a USB `CameraModule`/`Webcam` observation stream.
- Record three native DimOS streams: USB camera image, measured Piper joint state, and post-arbitration desired joint action.
- Make desired joint action observable as a typed `JointState` stream from the control coordinator.
- Store native DimOS recordings with stable stream names that can later map to LeRobot keys: `observation.images.*`, `observation.state`, and `action`.

**Non-Goals:**

- Writing a LeRobot dataset directly during teleop collection.
- Implementing the later native-recording-to-LeRobot conversion tool.
- Changing Quest/WebXR teleop input semantics, Piper IK behavior, or robot safety logic.
- Adding a new camera driver beyond the existing USB webcam support.
- Solving cross-stream resampling/alignment beyond preserving each stream's native timestamps for later conversion.

## Decisions

### Decision: Build collection as a new blueprint derived from Piper Quest teleop

Create a new public blueprint, for example `teleop-quest-piper-data-collection`, near the existing Quest teleop blueprints. It should compose the same Piper teleop modules used by `teleop_quest_piper`, plus a USB `CameraModule` and a recorder module/container for the selected streams.

This keeps the user-facing control surface unchanged: the left Quest controller still drives `teleop_piper` through `/coordinator/cartesian_command`, and button engagement still flows through `/teleop/buttons`. The alternative, creating a separate Piper coordinator or controller path for collection, would risk diverging demonstrations from normal teleop behavior.

### Decision: Publish desired action from the coordinator after arbitration

Add a coordinator output such as `desired_joint_action: Out[JointState]` and extend `TickLoop` with a second publish callback for the post-arbitration `joint_commands`. The published message should use the same joint names and active command values that are routed to hardware, with `position`, `velocity`, or `effort` populated according to the winning control mode.

This captures the action a policy should learn: the desired state sent to the robot after task computation, priority arbitration, mode conflict handling, and unknown-joint filtering. Alternatives considered:

- Record `/coordinator/cartesian_command`: rejected because it is controller pose input, not joint action.
- Record `joint_command: In[JointState]`: rejected because Piper Pink teleop produces task outputs internally and does not use the streaming joint-command input path.
- Recompute task outputs in a recorder: rejected because it duplicates coordinator logic and can disagree with arbitration.

### Decision: Keep recording native and per-stream

Use `TimedSensorStorage`-style native storage for each recorded stream, with explicit stream names for camera, measured state, and action. The design should not add LeRobot as a collection-time dependency; conversion can load the native recordings later and map them to LeRobot dataset fields.

The recorder should subscribe to:

- USB camera `color_image` for `observation.images.<camera_name>`.
- Coordinator `joint_state` for `observation.state`.
- Coordinator `desired_joint_action` for `action`.

Recording these as separate timestamped streams matches the existing storage/replay model and avoids forcing a single tick rate across camera and control. The later converter can align samples using timestamps.

### Decision: Use explicit transports and stable topic names

The blueprint should bind streams with explicit transports, following existing teleop patterns. Reuse current topics for compatibility where behavior already exists, and add a distinct topic for desired action, such as `/coordinator/desired_joint_action`, instead of overloading `/coordinator/joint_state`.

Using a distinct topic avoids ambiguity between measured state and action. Existing examples that map multiple visualization inputs to the same topic are not appropriate for dataset collection because the recording contract must distinguish observation state from action.

### Decision: Configure USB camera through existing `CameraModule`/`Webcam`

The collection blueprint should instantiate `CameraModule.blueprint(...)` with `Webcam` configuration for the desired `/dev/videoN` index, resolution, FPS, frame id, and optional frequency limiting. Defaults can mirror `WebcamConfig` where possible, but the blueprint should make camera selection configurable through existing config surfaces rather than hardcoding a device when practical.

This uses existing camera capture and metadata publication. The alternative, adding a Piper-specific camera module, would duplicate generic USB webcam support without improving the collection contract.

## Risks / Trade-offs

- Desired action stream may publish sparse or inactive ticks when teleop is disengaged → publish only the post-arbitration commands that would be routed to hardware, and let the recorder/converter decide whether to keep idle samples.
- Camera and control streams run at different rates → preserve native timestamps in separate stores and align during LeRobot conversion.
- Adding a coordinator output touches core control code used by other robots → keep the output optional and publish only when a transport/subscriber is configured, mirroring the existing `joint_state` callback pattern.
- Dataset consumers need unambiguous state/action naming → use a distinct desired-action topic and stable recording subdirectories rather than reusing `/coordinator/joint_state` for both measured and desired values.
- Native `TimedSensorStorage` prevents overwriting existing pickle directories → include the run or recording name in storage paths so repeated collection sessions do not collide.

## Migration Plan

1. Add the coordinator desired-action output and tick-loop callback without changing existing measured `joint_state` behavior.
2. Add the Piper data-collection blueprint by composing current Piper teleop, USB camera capture, and native per-stream recording.
3. Register/regenerate the blueprint registry so the CLI can launch the new blueprint.
4. Add focused tests for blueprint composition, desired-action publication, and recorder stream wiring.
5. Rollback by removing the new blueprint from the registry and leaving the optional coordinator output unused; existing Piper teleop should continue to run through the current route.

## Open Questions

- What should the public CLI blueprint name be: `teleop-quest-piper-data-collection`, `piper-data-collection`, or another project convention?
- Which config surface should provide recording name/path and USB camera index: new blueprint parameters, `GlobalConfig`, or environment variables?
- Should idle/disengaged samples be recorded and filtered later, or should collection pause until teleop engagement is active?
