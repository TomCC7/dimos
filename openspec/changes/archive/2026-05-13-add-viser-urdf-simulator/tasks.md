## 1. Configuration and Dependency Setup

- [x] 1.1 Add a simulator backend config field to `GlobalConfig` with CLI/env support and a default that preserves current MuJoCo behavior.
- [x] 1.2 Add or standardize the `viser` runtime dependency, including any required URDF loader dependency, in the appropriate project dependency group.
- [x] 1.3 Define Viser simulator defaults for host, port, label, and robot URDF path without hardcoding `listen_host`.

## 2. Viser URDF Simulator Module

- [x] 2.1 Add a `ViserUrdfSimModule` module with config for URDF path, server host/port, entity/frame names, end-effector frame, and package or mesh loading options.
- [x] 2.2 Start a `viser.ViserServer` using `global_config.listen_host` and load the configured URDF with `viser.extras.ViserUrdf`.
- [x] 2.3 Build a stable actuated-joint ordering from the loaded URDF and maintain current displayed joint values.
- [x] 2.4 Implement desired `JointState` handling with DimOS slash-suffix joint-name normalization and preservation of previous values for omitted joints.
- [x] 2.5 Implement desired controller, desired target, and desired end-effector pose visualization as distinct Viser frames or markers.
- [x] 2.6 Compute desired end-effector pose from the displayed desired joint configuration when an end-effector frame is configured and no explicit pose stream is provided.
- [x] 2.7 Ensure the Viser module does not start MuJoCo, publish camera streams, step dynamics, or expose hardware-command semantics.

## 3. XArm7 Teleop Simulator Selection

- [x] 3.1 Centralize XArm7 teleop simulation backend selection so `--simulation` can choose either MuJoCo or Viser while real hardware remains unchanged.
- [x] 3.2 Preserve the current MuJoCo path as the default backend for `dimos --simulation run teleop-quest-xarm7`.
- [x] 3.3 Remove the Pink desired-state wrapper dependency from `teleop_quest_xarm7`; keep the Viser URDF module available but no longer wire it through the removed Pink visualization path.
- [x] 3.4 Route Quest controller, desired target/controller pose, desired joint state, and Viser joint-state inputs with typed `LCMTransport` topics that do not collide with real hardware command output.
- [x] 3.5 Regenerate `dimos/robot/all_blueprints.py` after blueprint changes and verify `teleop-quest-xarm7` remains registered.

## 4. Rerun Robot Visualization Deprecation

- [x] 4.1 Mark `RerunUrdfRobotVisualizer` and Rerun URDF robot visualization docs/tests as deprecated without removing generic Rerun bridge functionality.
- [x] 4.2 Remove `teleop_quest_xarm7_rerun` and `teleop_quest_openarm_rerun` with the deprecated Pink IK visualization wrapper.
- [x] 4.3 Update teleop and visualization documentation to describe Viser as the desired-state/no-dynamics simulator and Rerun robot-vis as legacy.
- [x] 4.4 Remove or update tests that assert Rerun robot-vis is the preferred desired-state teleop path, replacing them with Viser simulator coverage.

## 5. Validation

- [x] 5.1 Add unit tests for Viser URDF startup path validation and joint-name-to-index mapping, including prefixed names such as `arm/joint1`.
- [x] 5.2 Add unit tests for incomplete `JointState` updates preserving prior displayed joint values.
- [x] 5.3 Add blueprint tests for MuJoCo default selection, Viser backend selection, and real hardware path exclusion of simulator modules.
- [x] 5.4 Run focused tests for Viser simulator module behavior, XArm7 teleop blueprint registration, and Rerun robot-vis deprecation coverage.
- [x] 5.5 Manually launch or smoke-test `dimos --listen-host 0.0.0.0 --simulation run teleop-quest-xarm7` with the Viser backend selected and verify the browser viewer loads the XArm7 URDF and updates desired poses.
