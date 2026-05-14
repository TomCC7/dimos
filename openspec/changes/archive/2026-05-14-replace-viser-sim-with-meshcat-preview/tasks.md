## 1. Meshcat Preview Module

- [x] 1.1 Add a Meshcat teleop preview module that starts a Meshcat server using `GlobalConfig.listen_host` and loads the configured XArm7 model.
- [x] 1.2 Implement typed `JointState` handling that maps DimOS-prefixed joint names to model joint names and updates the displayed Meshcat robot pose.
- [x] 1.3 Ensure invalid model paths fail startup with an error naming the invalid path.
- [x] 1.4 Keep the Meshcat preview read-only: no joint command publishing, no manipulator adapter writes, and no hardware-control semantics.

## 2. XArm7 Teleop Blueprint Selection

- [x] 2.1 Update `coordinator_teleop_xarm7` selection so no `xarm7_ip` and no `--simulation` uses the mock XArm7 adapter.
- [x] 2.2 Wire the Meshcat preview module into `teleop_quest_xarm7` only for the no-IP mock preview path.
- [x] 2.3 Preserve the explicit real hardware path when `--xarm7-ip` is provided.
- [x] 2.4 Preserve the explicit MuJoCo path for `dimos --simulation run teleop-quest-xarm7`.
- [x] 2.5 Route coordinator `JointState` to the Meshcat preview with a typed transport that does not collide with real hardware command outputs.

## 3. Remove Viser Simulator Setup

- [x] 3.1 Remove `viser` from the `SimulationBackend` type and remove the `--simulation-backend viser` behavior from XArm7 teleop selection.
- [x] 3.2 Remove Viser-specific global config fields if no remaining runtime code uses them.
- [x] 3.3 Remove `ViserUrdfSimModule` registration, implementation, and tests, or mark any intentionally retained compatibility surface as deprecated and unreachable from simulator selection.
- [x] 3.4 Remove the `viser` runtime dependency if no remaining non-test code imports it.
- [x] 3.5 Regenerate `dimos/robot/all_blueprints.py` after removing Viser module registration and adding the Meshcat preview module.

## 4. Documentation and Spec Migration

- [x] 4.1 Update teleop docs and CLI examples to advertise `dimos --listen-host 0.0.0.0 run teleop-quest-xarm7` as the no-hardware Meshcat preview path.
- [x] 4.2 Update simulation docs so MuJoCo remains the explicit `--simulation` path and Viser is no longer listed as a simulator backend.
- [x] 4.3 Update Rerun URDF deprecation guidance to point to Meshcat teleop preview instead of Viser URDF simulation.

## 5. Verification

- [x] 5.1 Add unit tests for Meshcat preview startup configuration, invalid model path failure, and joint-name normalization.
- [x] 5.2 Add blueprint tests for no-IP mock Meshcat preview, real-IP hardware path, and explicit MuJoCo simulation path.
- [x] 5.3 Add removal tests or assertions proving `--simulation-backend viser` is no longer accepted and Viser simulator blueprints are not registered.
- [x] 5.4 Run focused tests for Meshcat preview behavior, XArm7 teleop blueprint selection, global config CLI generation, and blueprint registry generation.
- [ ] 5.5 Manually smoke-test `dimos --listen-host 0.0.0.0 run teleop-quest-xarm7` and verify the Quest teleop server and Meshcat viewer are reachable and the XArm7 model moves under mock teleop input.
