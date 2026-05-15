## MODIFIED Requirements

### Requirement: Shared single-arm Pink teleop task is configurable by robot
The system SHALL provide a shared Pink-backed teleop IK task for one manipulator arm and one end-effector frame, with robot-specific behavior selected by explicit task/config subclasses and registry-based construction rather than coordinator `if/elif` robot branches.

#### Scenario: Robot-specific model and frame are configured by task config
- **WHEN** a single-arm Pink teleop task is created for a robot
- **THEN** the task SHALL load the configured URDF or MJCF model path, validate configured controlled joint names against model DOF, and fail startup if the configured end-effector frame is absent

#### Scenario: New robot config avoids coordinator branch additions
- **WHEN** a new single-arm Pink task/config subclass is introduced and registered
- **THEN** creating that task SHALL NOT require adding a new robot-specific `if/elif` branch in coordinator task construction

### Requirement: Shared single-arm Pink teleop preserves Quest delta control
The system SHALL interpret Quest controller poses for the shared single-arm Pink teleop task as robot-frame deltas from controller engagement, matching existing XArm7/Piper control behavior.

#### Scenario: Controller engage captures robot baseline
- **WHEN** the configured controller hand engages and current joint state is available
- **THEN** the task SHALL capture the current configured end-effector pose as baseline for subsequent controller deltas

#### Scenario: Controller delta updates frame target through unified task binding
- **WHEN** an engaged controller publishes a routed `PoseStamped` delta
- **THEN** the task SHALL apply that delta to the captured baseline and bind the result into the active Pink task set through one composition flow that includes both frame and auxiliary tasks
