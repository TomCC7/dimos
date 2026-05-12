## Context

DimOS already has a Rerun visualization bridge that can log messages with `to_rerun()` methods, custom `visual_override` functions, and static helper entities through `vis_module("rerun")`. Some robot-specific helpers, such as the G1 static wireframe, are ad hoc and do not provide articulated robot visualization. Rerun now supports loading URDF files directly via `rr.log_file_from_path()` and updating joints by logging `rr.urdf.UrdfJoint.compute_transform(angle)` transforms with explicit parent/child frame IDs.

The immediate debugging need is XArm7 Quest teleop with Pink IK. MuJoCo is useful for dynamic simulation, but its position actuators, gains, and force limits obscure whether lag comes from Pink IK output or from actuator dynamics. A Rerun URDF path should visualize desired robot joint configuration directly from typed `JointState` values and overlay desired/controller/end-effector frames.

## Goals / Non-Goals

**Goals:**

- Provide a reusable Rerun robot visualization utility/module that loads a configured URDF and logs its static geometry once.
- Update articulated robot joint transforms from `JointState.name` and `JointState.position`, preserving typed joint-name mapping rather than relying on positional array order alone.
- Support debug frame overlays from `PoseStamped` values, especially desired controller target pose and robot end-effector pose.
- Add a `teleop-quest-xarm7-rerun` blueprint that runs Quest teleop and Pink IK visualization without MuJoCo dynamics, making solver output observable directly.
- Keep existing `teleop-quest-xarm7` and generic `RerunBridgeModule` behavior compatible.

**Non-Goals:**

- Replace MuJoCo simulation, Drake Meshcat planning visualization, or the generic Rerun bridge.
- Implement physics, actuator dynamics, collision checking, or controller tracking in the Rerun visualizer.
- Build a full ROS TF-compatible robot state publisher; this change only needs configured URDF frame updates and selected debug pose overlays.
- Add a new visualization dependency if the installed Rerun SDK URDF utilities are sufficient.

## Decisions

### 1. Use Rerun URDF importer and `rr.urdf.UrdfTree`

The visualizer should call `rr.log_file_from_path(urdf_path, static=True)` once and keep an in-memory `rr.urdf.UrdfTree` for joint metadata. For each incoming `JointState`, it should find matching URDF joints by name and log `joint.compute_transform(position)` to a common transform entity such as `world/robot/transforms`.

Alternative considered: manually load meshes and compute Pinocchio frame transforms. That would work, but it duplicates functionality Rerun already provides and increases maintenance around mesh paths and fixed joint transforms.

### 2. Match joints by name first, not array index

`JointState` carries both `name: list[str]` and `position: list[float]`. The visualizer should build `dict(zip(name, position))` and update URDF joints by exact joint name. If DimOS joint names are prefixed (for example `arm/joint1`) and URDF names are unqualified (`joint1`), the visualizer should support configured prefix stripping or default to the suffix after `/`.

Alternative considered: assume `JointState.position` order matches the URDF joint order. That is fragile and would make multi-robot or prefixed hardware configurations difficult to debug.

### 3. Keep robot visualization as a dedicated module/helper, not only bridge overrides

A dedicated module can subscribe to typed streams (`JointState`, `PoseStamped`) and own stateful URDF tree initialization. The generic bridge remains useful for normal topics, but URDF joint updates need persistent model metadata and explicit transform logging that is clearer in a purpose-built robot visualization module.

Alternative considered: implement everything as `visual_override` functions inside `RerunBridgeModule`. This would keep fewer modules, but it pushes stateful URDF tree handling into bridge config closures and makes blueprint configuration harder to validate.

### 4. The XArm7 Rerun teleop blueprint should visualize solver output directly

The debug blueprint should avoid MuJoCo hardware. It should route Quest right-controller `PoseStamped(frame_id="teleop_xarm")` into the Pink IK task path, then publish or expose the resulting desired `JointState` to the Rerun robot visualizer. The displayed robot is the commanded IK configuration, not simulated/hardware measured state. Desired target/controller and computed end-effector frames should be logged as distinct Rerun entities.

Alternative considered: keep using `coordinator_teleop_xarm7` and only add Rerun next to MuJoCo. That does not isolate solver output from actuator dynamics and would not solve the current debugging problem.

## Risks / Trade-offs

- [Risk] Rerun SDK URDF APIs differ across versions. → Mitigate with focused tests that import `rr.urdf.UrdfTree`, load XArm7 URDF, and compute transforms for representative joints.
- [Risk] URDF mesh paths may not resolve in all environments. → Use the existing LFS-backed URDF path (`XARM7_FK_MODEL`) and add a smoke test that `rr.log_file_from_path()` accepts it without opening a viewer.
- [Risk] Joint-name mismatch can silently produce a static robot. → Log warnings for unmatched `JointState.name` entries and for URDF revolute joints with no configured or incoming value.
- [Risk] Debug blueprint may be mistaken for dynamics simulation. → Name and docs should explicitly state it visualizes desired IK configuration only.
- [Risk] Direct Rerun logging from multiple modules can contend with the bridge. → Reuse `rerun_init()` conventions and run the robot visualizer alongside `vis_module("rerun")` or use a single dedicated Rerun module for this blueprint.
