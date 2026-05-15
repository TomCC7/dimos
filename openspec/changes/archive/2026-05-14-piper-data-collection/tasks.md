## 1. Coordinator Desired Action Stream

- [x] 1.1 Add a typed desired joint action output to `ControlCoordinator` using `JointState`.
- [x] 1.2 Extend `TickLoop` to publish post-arbitration command values as desired joint action after commands are computed and before/after hardware routing.
- [x] 1.3 Preserve existing measured `joint_state` publication behavior and keep desired action on a distinct stream/topic.
- [x] 1.4 Add or update tests that verify desired action contains the post-arbitration winning command values and remains distinct from measured state.

## 2. Native Recording Module

- [x] 2.1 Add a small DimOS module for Piper data collection that subscribes to camera image, measured joint state, and desired joint action streams.
- [x] 2.2 Use `TimedSensorStorage` to save each stream under stable recording paths for camera observation, measured state, and action.
- [x] 2.3 Make recording name/path configurable enough to avoid collisions across sessions.
- [x] 2.4 Add focused tests for recorder stream subscriptions and storage path naming without requiring real hardware.

## 3. Piper Data Collection Blueprint

- [x] 3.1 Compose a new Piper data collection blueprint from current Piper Quest teleop, USB `CameraModule`/`Webcam`, and the native recording module.
- [x] 3.2 Route left Quest controller output to `/coordinator/cartesian_command`, buttons to `/teleop/buttons`, measured state to `/coordinator/joint_state`, and desired action to a distinct coordinator desired-action topic.
- [x] 3.3 Register the blueprint in the generated blueprint registry.
- [x] 3.4 Add or update blueprint tests so the data collection blueprint is registered and composes the expected teleop, camera, coordinator, and recorder pieces.

## 4. Verification

- [x] 4.1 Run the relevant control coordinator tests for desired action publication.
- [x] 4.2 Run the relevant teleop/blueprint tests for Piper data collection registration and routing.
- [x] 4.3 Run the blueprint registry generation test and update generated files if needed.
- [x] 4.4 Smoke-test the CLI surface far enough to confirm the new blueprint resolves by name without requiring real Piper hardware.
