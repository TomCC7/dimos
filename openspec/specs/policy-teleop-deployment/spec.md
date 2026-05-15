# policy-teleop-deployment Specification

## Purpose
TBD - created by archiving change policy-rollout-deployment. Update Purpose after archive.
## Requirements
### Requirement: Piper teleop+policy coordinator blueprint composes teleop and policy servo tasks

The system SHALL provide a control-coordinator blueprint named `coordinator_teleop_piper_with_policy` at `dimos.control.blueprints.teleop` (or equivalent location reachable from `dimos.manipulation.policy.blueprints`) that extends `coordinator_teleop_piper` with a `servo` task derived from `policy_servo_task_config`.

The servo task SHALL:

- Claim every joint in the Piper arm's full joint set as returned by `piper_data_collection_joint_short_names()` prefixed with the arm joint prefix (e.g., `"arm/joint1"`, ..., `"arm/joint6"`, `"arm/gripper"`).
- Be built by calling `policy_servo_task_config(name=..., joint_names=..., teleop_tasks=[piper_pink_ik_task])` so its priority is auto-derived to one less than the Piper Pink IK teleop task's priority.

The coordinator blueprint SHALL preserve all transports and modules from `coordinator_teleop_piper` (joint state, cartesian command, buttons, optional MuJoCo simulation).

#### Scenario: Coordinator includes both teleop_pink_ik and servo tasks

- **WHEN** `coordinator_teleop_piper_with_policy` is built
- **THEN** the resulting `ControlCoordinatorConfig.tasks` SHALL contain at least one task with `type="single_arm_pink_ik"` (or `"piper_pink_ik"`)
- **AND** SHALL contain exactly one task with `type="servo"` whose `joint_names` equal the Piper full joint set
- **AND** the servo task's `priority` SHALL be strictly less than the Pink IK task's `priority`

#### Scenario: Coordinator preserves teleop transports

- **WHEN** `coordinator_teleop_piper_with_policy` is built
- **THEN** the blueprint's transport map SHALL include `("joint_state", JointState)`, `("cartesian_command", PoseStamped)`, and `("buttons", Buttons)` mapped to the same LCM channels used by `coordinator_teleop_piper`

### Requirement: teleop_quest_piper_policy deployment blueprint composes the full stack

The system SHALL provide a top-level deployment blueprint `teleop_quest_piper_policy` that composes via `autoconnect`:

- `ArmTeleopModule.blueprint(task_names={"right": "teleop_piper"})` — Quest controller input.
- `coordinator_teleop_piper_with_policy` — coordinator with paired teleop + policy servo tasks.
- `CameraModule.blueprint()` — color image source.
- `PolicyNode.blueprint(...)` — policy module configured for the Piper full joint set, using `policy_engage_buttons(...)` to derive `teleop_engage_buttons` from the overlapping Pink IK teleop task's hand.
- `RolloutToggle.blueprint()` — rollout start/stop button.
- `ManipulationModule.blueprint(robots=[piper_teleop_robot_model_config()], enable_viz=True)` — viz module already used by `teleop_quest_piper`.

The blueprint SHALL remap `CameraModule.color_image` to `PolicyNode.image` so the policy node receives the camera stream on its `image` slot.

The blueprint SHALL configure `PolicyNode` with `backend="test"`, a per-joint `amplitude` list whose arm-joint entries are positive and whose gripper entry is strictly smaller than the arm entries, and `policy_rate=10.0` by default. The non-zero amplitudes produce visible motion in simulation; the bounded gripper amplitude avoids slamming the gripper open/closed each cycle.

The blueprint SHALL be registered in `dimos.robot.all_blueprints.all_blueprints` under the key `"teleop-quest-piper-policy"`.

The blueprint SHALL NOT wire any data-collection modules (`RerunDataRecorder`, `EpisodeBoundary`).

#### Scenario: Blueprint registered under teleop-quest-piper-policy

- **WHEN** the regenerated `all_blueprints` mapping is inspected
- **THEN** it SHALL contain an entry whose key is `"teleop-quest-piper-policy"` and whose value resolves to the deployment blueprint object

#### Scenario: Camera remapped to policy image slot

- **WHEN** the deployment blueprint is built
- **THEN** the blueprint's remapping map SHALL include a mapping from the `CameraModule`'s `color_image` output to the `PolicyNode`'s `image` input
- **AND** `PolicyNode.config.camera_sources` SHALL contain at least one entry whose slot is `"image"`

#### Scenario: Policy engage buttons derived from teleop hand

- **WHEN** the deployment blueprint constructs the `PolicyNode` config
- **THEN** `teleop_engage_buttons` SHALL be the value returned by `policy_engage_buttons(joint_names, teleop_tasks)` for the configured joint set and the overlapping Pink IK task
- **AND** SHALL contain `"right_primary"` (since the reference Piper teleop runs on the right hand)
- **AND** SHALL NOT contain `"left_primary"` (no left-hand teleop task is wired in this blueprint)

#### Scenario: No data-collection modules wired

- **WHEN** the deployment blueprint is built
- **THEN** the set of underlying module classes SHALL NOT include `RerunDataRecorder` or `EpisodeBoundary`

#### Scenario: Default backend is test with bounded per-joint amplitude

- **WHEN** the deployment blueprint constructs the `PolicyNode` config without overrides
- **THEN** `PolicyNode.config.backend` SHALL equal `"test"`
- **AND** `PolicyNode.config.backend_config["amplitude"]` SHALL be a length-7 list whose first 6 entries (arm joints) are strictly positive
- **AND** the seventh entry (gripper) SHALL be strictly less than each arm-joint amplitude
