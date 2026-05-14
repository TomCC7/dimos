## Context

`teleop_quest_xarm7` currently composes the Quest teleop module with `coordinator_teleop_xarm7`. The coordinator blueprint branches at import time from `GlobalConfig`: real hardware uses the XArm adapter, `--simulation` defaults to MuJoCo through `MujocoSimModule` plus the `sim_mujoco` SHM adapter, and `--simulation-backend viser` uses mock hardware plus `ViserUrdfSimModule`.

That Viser branch is a visualization-only path, not a simulator with hardware feedback semantics. It subscribes to typed joint and pose streams and displays a URDF in a browser, while MuJoCo owns physics state and exposes it through a hardware adapter. The desired replacement is closer to existing Drake/Meshcat practice: a browser visualization server observes a robot state source instead of becoming the simulator or hardware adapter.

Drake Meshcat is already available through the manipulation dependency set and existing utility code uses `pydrake.geometry.Meshcat` with `SetObject`/`SetTransform`. Meshcat can be started as a browser server and configured with host/port parameters, which makes it a good fit for `--listen-host 0.0.0.0` teleop preview.

## Goals / Non-Goals

**Goals:**

- Make `dimos --listen-host 0.0.0.0 run teleop-quest-xarm7` with no `--xarm7-ip` select mock XArm7 hardware and show the robot in Meshcat.
- Keep `dimos --xarm7-ip <ip> run teleop-quest-xarm7` on the real XArm7 hardware path.
- Keep `dimos --simulation run teleop-quest-xarm7` as the MuJoCo dynamic simulation path.
- Remove Viser as a `simulation_backend` and retire Viser URDF simulator docs/tests/registry entries.
- Keep the Meshcat viewer as an observer of joint state, not a hardware adapter.

**Non-Goals:**

- Replacing MuJoCo physics, sensors, shared-memory feedback, or camera streams with Meshcat.
- Adding a generic multi-robot Meshcat framework before the XArm7 teleop preview is working.
- Preserving backward compatibility for `--simulation-backend viser`; that selector is intentionally removed.
- Commanding real hardware from the Meshcat viewer.

## Decisions

### 1. Default no-IP teleop to mock hardware plus preview

`teleop-quest-xarm7` should treat the absence of `global_config.xarm7_ip` as an explicit local-preview mode. In that mode, the coordinator uses the existing mock manipulator adapter, so Pink IK still has a current joint-state warm start and coordinator-compatible write path.

Alternative considered: require `--simulation --simulation-backend meshcat`. That keeps preview behind simulation terminology, but repeats the Viser problem by making a no-physics viewer look like a simulator.

### 2. Keep MuJoCo behind `--simulation`

MuJoCo remains the dynamic simulator because it has a real engine, shared-memory adapter, and simulator state. The Meshcat preview is for fast teleop development without physics or hardware.

Alternative considered: remove `--simulation` for XArm7 teleop and make all no-hardware runs Meshcat-only. That would break users who need actuator tracking, dynamics, or simulated feedback.

### 3. Implement Meshcat as a Module that consumes `JointState`

The Meshcat preview should be a DimOS module with typed inputs, likely starting with coordinator `JointState`. It should load the XArm7 model and update Meshcat from observed joint positions. It should not publish joint state, write commands, or implement `ManipulatorAdapter`.

Alternative considered: implement a Meshcat hardware adapter. That would conflate visualization with hardware state and repeat the semantic mismatch being removed from the Viser path.

### 4. Use Drake model loading for robot visualization

The viewer should use Drake/MultibodyPlant/Parser or equivalent pydrake geometry support to load the XArm7 model and publish geometry into Meshcat. Joint updates should map DimOS names such as `arm/joint1` to model joint names such as `joint1`, matching the normalization used by the removed Viser/Rerun desired-state visualizers.

Alternative considered: manually add URDF meshes and frame transforms to Meshcat. That avoids Drake plant setup but duplicates model parsing, package resolution, and transform computation.

### 5. Remove Viser simulation configuration rather than aliasing it

`simulation_backend` should no longer include `viser`, and Viser-specific global settings should be removed if no other runtime user remains. Any generated CLI help, docs, and blueprint examples should stop advertising Viser as a simulation backend.

Alternative considered: leave `viser` accepted but internally route it to Meshcat. That hides the behavior change and preserves a misleading backend name.

## Risks / Trade-offs

- Meshcat host binding differs from Viser defaults → Use explicit Meshcat parameters derived from `GlobalConfig.listen_host` and verify `0.0.0.0` binding manually.
- Drake URDF/package loading may not resolve all XArm meshes the same way Viser did → Reuse existing `XARM7_FK_MODEL`/data paths and add a startup failure that names the missing model or package resource.
- Mock adapter publishes state after coordinator tick ordering, so the viewer may show a one-tick-delayed state → Treat this as acceptable for preview and test observable movement, not same-tick command emission.
- Removing Viser may break undocumented users of `viser-urdf-sim-module` by registry name → Mark the capability removal clearly and update docs to Meshcat preview; do not silently keep the old module under a deprecated name.
- Import-time blueprint branching can be stale if global config is updated after import → Keep CLI `run()` ordering in mind and add tests that import/resolve the blueprint after setting `global_config` for no-IP, real-IP, and MuJoCo paths.

## Migration Plan

1. Add the Meshcat preview module and wire it into the no-IP `teleop-quest-xarm7` path.
2. Update XArm7 teleop selection so real hardware is chosen only when `xarm7_ip` is configured and MuJoCo remains selected only with `--simulation`.
3. Remove Viser simulation backend configuration, blueprint wiring, registry entries, docs, tests, and dependency if unused.
4. Update OpenSpec main specs after implementation to make Meshcat preview the no-dynamics teleop visualization target and mark Viser URDF simulation removed.
5. Roll back by restoring the previous Viser change if needed, but prefer keeping the no-IP mock selection independent of any viewer implementation.

## Open Questions

- Should the Meshcat port get a new `GlobalConfig.meshcat_port` default, or should the implementation let Drake choose an available port and only control the listen host?
- Should the initial Meshcat preview show only the robot joint state, or also Quest/controller target frames equivalent to the old desired pose markers?
