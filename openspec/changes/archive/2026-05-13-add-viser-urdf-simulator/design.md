## Context

`teleop_quest_xarm7` currently composes `ArmTeleopModule` with `coordinator_teleop_xarm7`. In simulation mode, `dimos/control/blueprints/teleop.py` switches the XArm7 hardware adapter to `sim_mujoco`, points it at `XARM7_SIM_PATH`, and adds `MujocoSimModule.blueprint(address=..., headless=False, dof=...)`. That path is useful for dynamics, but it is heavier than needed when the user only wants to see the desired teleop pose and desired IK joint configuration.

The former visualization-only teleop paths routed Quest input through `dimos/control/pink_ik_visualization.py` wrappers and into `RerunUrdfRobotVisualizer`. Those wrappers and related Rerun robot-vis blueprints are removed; the reusable Viser URDF module remains available for future visualization-only sources without preserving the Pink visualization wrapper layer.

Viser supports this shape directly: `viser.ViserServer(host=..., port=...)` exposes a browser UI, and `viser.extras.ViserUrdf(server, urdf_or_path=...)` loads a URDF path or `yourdfpy.URDF` object. `ViserUrdf.update_cfg(np.array([...]))` updates actuated joint positions without physics, which matches desired-state visualization.

## Goals / Non-Goals

**Goals:**

- Add a DimOS simulation backend that loads a URDF in Viser and visualizes desired joint positions without dynamic simulation, actuator tracking, cameras, contacts, or physics stepping.
- Make the Viser backend swappable with the existing MuJoCo backend for XArm7 Quest teleop launched through `dimos --listen-host 0.0.0.0 --simulation run teleop-quest-xarm7`.
- Accept typed `JointState`/`PoseStamped` streams rather than inventing a new Viser-specific command format.
- Respect `GlobalConfig.listen_host` for the Viser server so Quest/browser clients can reach it when `--listen-host 0.0.0.0` is used.
- Deprecate Rerun URDF robot visualization and Rerun-specific teleop robot-vis blueprints in favor of Viser URDF simulation.

**Non-Goals:**

- Replace MuJoCo dynamic simulation where physics, camera streams, shared-memory joint feedback, or actuator behavior are required.
- Remove the generic Rerun bridge, Rerun websocket server, or non-robot Rerun visualization features.
- Command real hardware from the Viser visualization backend.
- Build a generic multi-robot simulator abstraction beyond the selection needed for the XArm7 teleop simulation path.

## Decisions

### 1. Implement Viser URDF simulation as a Module, not as a viewer-only helper

Create a module such as `ViserUrdfSimModule` with typed inputs for desired `JointState` and debug `PoseStamped` values. This keeps it swappable in blueprints next to `MujocoSimModule` and lets the teleop stack treat it as a simulation backend rather than a visualization add-on.

Alternative considered: add a Viser replacement under `dimos/visualization/`. That would mirror the deprecated Rerun robot visualizer, but it would not satisfy the requested “simulation type” semantics and would keep the simulation selector coupled to visualization naming.

### 2. Use existing desired-state IK output as the source of truth

The Viser module should subscribe to typed desired joint state from whatever producer owns the desired-state computation. It should not consume MuJoCo shared memory, and it should not publish simulated hardware feedback. This avoids confusing desired state with physics-tracked actual state without preserving the removed Pink visualization wrapper.

Alternative considered: adapt the existing `sim_mujoco` adapter interface and emulate a hardware component. That would make it appear closer to MuJoCo, but it would imply feedback and control semantics that a no-dynamics viewer cannot provide.

### 3. Add explicit simulator backend selection while preserving `--simulation`

`--simulation` should continue to mean “use a non-real backend.” Since the Pink desired-state wrappers are removed, `teleop-quest-xarm7` keeps the existing MuJoCo simulation path and the Viser module is not wired as an alternate teleop backend until a non-deprecated desired-state producer exists.

Alternative considered: create only a new `teleop-quest-xarm7-viser` blueprint. That is useful as an alias or smoke target, but by itself it does not make the simulator swappable for the requested `teleop-quest-xarm7` command.

### 4. Load URDF with `viser.extras.ViserUrdf` and maintain deterministic joint ordering

The Viser module should load `XARM7_FK_MODEL` or a configured URDF path through `ViserUrdf`, derive actuated joint names and limits from `get_actuated_joint_limits()`, and maintain a stable joint-name-to-index map. Incoming `JointState.name` values should be normalized the same way the Rerun visualizer handled `arm/joint1` to `joint1`, then converted into the ordered vector passed to `update_cfg()`.

Alternative considered: manually compute Pinocchio FK and add individual meshes/frames to Viser. That would duplicate Viser's URDF loader and increase mesh/package resolution work.

### 5. Deprecate Rerun robot-vis by capability and migration path

Remove `teleop_quest_xarm7_rerun`, `teleop_quest_openarm_rerun`, and their Pink IK visualization wrapper dependency. Generic Rerun bridge functionality remains outside this deprecation.

Alternative considered: remove Rerun robot-vis immediately. That is cleaner, but it is riskier because existing specs and blueprints still reference it; deprecation gives implementation room to migrate tests and docs without breaking unrelated Rerun users.

## Risks / Trade-offs

- [Risk] Viser URDF loading may require `viser`, `yourdfpy`, and mesh path support not currently installed in DimOS core. → Mitigation: add the dependency to the correct runtime/visualization extra and verify XArm7 URDF mesh loading with existing LFS model paths.
- [Risk] A visualization-only backend may be mistaken for real simulation feedback. → Mitigation: name config, docs, and logs clearly as desired-state/no-dynamics, and avoid publishing hardware-like joint feedback unless explicitly designed later.
- [Risk] Adding simulator selection at import-time blueprints can be brittle because current blueprints read `global_config.simulation` during module import. → Mitigation: follow the existing pattern for initial implementation, but keep the selection centralized in a small helper so future runtime config refactors are localized.
- [Risk] Deprecating Rerun robot-vis may affect OpenArm Rerun teleop examples. → Mitigation: include OpenArm Rerun references in the deprecation tasks and either migrate them to Viser or document them as legacy during the deprecation window.
