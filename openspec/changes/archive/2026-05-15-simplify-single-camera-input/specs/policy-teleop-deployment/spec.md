## MODIFIED Requirements

### Requirement: teleop_quest_piper_policy deployment blueprint composes the full stack

The system SHALL provide a top-level deployment blueprint `teleop_quest_piper_policy` that composes via `autoconnect`:

- `ArmTeleopModule.blueprint(task_names={"right": "teleop_piper"})` — Quest controller input.
- `coordinator_teleop_piper_with_policy` — coordinator with paired teleop + policy servo tasks.
- `CameraModule.blueprint()` — color image source.
- `PolicyNode.blueprint(...)` — policy module configured for the Piper full joint set, using `policy_engage_buttons(...)` to derive `teleop_engage_buttons` from the overlapping Pink IK teleop task's hand.
- `RolloutToggle.blueprint()` — rollout start/stop button.
- `ManipulationModule.blueprint(robots=[piper_teleop_robot_model_config()], enable_viz=True)` — viz module already used by `teleop_quest_piper`.

The blueprint SHALL remap `CameraModule.color_image` to `PolicyNode.image` so the policy node receives the camera stream on its single typed `image` slot.

The blueprint SHALL configure `PolicyNode` with `backend="test"`, a per-joint `amplitude` list whose arm-joint entries are positive and whose gripper entry is strictly smaller than the arm entries, and `policy_rate=10.0` by default. The non-zero amplitudes produce visible motion in simulation; the bounded gripper amplitude avoids slamming the gripper open/closed each cycle.

The blueprint SHALL configure `PolicyNode` with `camera_key="usb"` so the camera frame appears under the `"usb"` key in `PolicyObservation.images`, matching `PiperRobotContract.cameras`.

The blueprint SHALL NOT wire any data-collection modules (`RerunDataRecorder`, `EpisodeBoundary`).

#### Scenario: Blueprint registered under teleop-quest-piper-policy

- **WHEN** the regenerated `all_blueprints` mapping is inspected
- **THEN** it SHALL contain an entry whose key is `"teleop-quest-piper-policy"` and whose value resolves to the deployment blueprint object

#### Scenario: Camera remapped to policy image slot

- **WHEN** the deployment blueprint is built
- **THEN** the blueprint's remapping map SHALL include a mapping from the `CameraModule`'s `color_image` output to the `PolicyNode`'s `image` input
- **AND** `PolicyNode.config.camera_key` SHALL be set to `"usb"` to align the observation key with `PiperRobotContract.cameras`

#### Scenario: Policy engage buttons derived from teleop hand

- **WHEN** the deployment blueprint constructs the `PolicyNode` config
- **THEN** `teleop_engage_buttons` SHALL be the value returned by `policy_engage_buttons(joint_names, teleop_tasks)` for the configured joint set and the overlapping Pink IK task
- **AND** SHALL contain `"right_primary"` (since the reference Piper teleop runs on the right hand)
- **AND** SHALL NOT contain `"left_primary"` (no left-hand teleop task is wired in this blueprint)

#### Scenario: No data-collection modules wired

- **WHEN** the deployment blueprint is built
- **THEN** the set of underlying module classes SHALL NOT include `RerunDataRecorder` or `EpisodeBoundary`
