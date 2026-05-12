## Context

The current teleop control path is built around one `PoseStamped` command per arm. `QuestTeleopModule` converts WebXR controller poses into robot-frame deltas, publishes only while the controller is engaged, and `ArmTeleopModule` stamps `PoseStamped.frame_id` with a task name so `ControlCoordinator._on_cartesian_command()` can route the command to one `TeleopIKTask`. The existing `TeleopIKTask` owns one end-effector, captures that end-effector pose on engage, applies incoming controller deltas relative to the captured pose, solves IK with the in-tree Pinocchio solver, and emits `JointCommandOutput` for its claimed joints.

Dual-arm teleop is currently composed as two independent `teleop_ik` tasks: one XArm task and one Piper task. That makes routing simple, but it also shows why the Pink integration should not be one flat generic task: each robot or robot combination needs different Pink problem construction, frame names, model loading, posture terms, limits, and controller mappings. Pink is still a good shared backend because it represents IK as weighted tasks over a Pinocchio configuration: one or more `FrameTask`s can be assigned targets, then `solve_ik(configuration, tasks, dt, solver=...)` returns a velocity to integrate into the next configuration.

The design must preserve the current passive control-task contract: tasks do not own threads, use `CoordinatorState.t_now`, compute only from current state, claim resources for arbitration, and publish joint commands through the coordinator.

## Goals / Non-Goals

**Goals:**

- Introduce a hierarchical Pink IK task structure with a shared base class for common control-task and Pink solver plumbing.
- Implement the first concrete task as an XArm7-only Pink IK task driven by the right controller pose.
- Leave room for later robot-specific and dual-arm subclasses whose IK problem construction differs from XArm7.
- Make the controller pose contract explicit: controller output is a robot-frame delta from controller engage, not an absolute world-frame end-effector target.
- Preserve existing single-arm XArm7 blueprint behavior where the right controller stream routes directly to the XArm7 teleop IK task.
- Keep safety behavior from the current implementation: timeout handling, joint-delta limiting, current-joint warm starts, gripper trigger handling, and resource arbitration.

**Non-Goals:**

- General-purpose motion planning, trajectory generation, collision avoidance, or whole-body control beyond Pink differential IK.
- Changing Quest/WebXR coordinate conversion. The controller stream remains robot-frame `PoseStamped` deltas after `webxr_to_robot()`.
- Implementing coordinated dual-arm solving in the first concrete task. Dual-arm support should be designed as a later subclass built on the same base class.
- Replacing non-teleop Cartesian IK tasks unless a later change chooses to share Pink utilities with them.
- Defining new LCM message types for the XArm7 milestone; the existing `PoseStamped` routing envelope is sufficient for the right-controller single-arm contract.

## Decisions

### 1. Split shared Pink plumbing from robot-specific IK problem construction

Create an abstract/shared base task, tentatively `BasePinkIKTask`, for behavior that is common across Pink-backed teleop IK tasks:

- implement the `BaseControlTask` lifecycle and passive `compute(state)` contract
- expose reusable hooks so concrete tasks can manage target state without forcing the shared base to assume a single end-effector target
- read current joint positions from `CoordinatorState` in configured joint order
- build/update Pink `Configuration` from current joints
- run `pink.solve_ik()` with configured solver settings
- integrate Pink velocity over `state.dt` into commanded joint positions
- apply joint-delta safety checks and emit `JointCommandOutput`
- provide hooks for robot-specific frame task construction, target update, posture/limit tasks, and model validation

Robot-specific subclasses own IK problem construction. They decide which Pink tasks exist, which frames are regulated, how controller deltas map to frame targets, and which additional posture/limit objectives are needed.

Alternative considered: make one generic `TeleopIKTask` configurable enough to describe every robot. That would push robot-specific problem construction into config dictionaries, making the first implementation harder to validate and obscuring differences between XArm7, Piper, and future dual-arm models.

### 2. Implement `XArm7IKTask` as the first concrete Pink task

The first concrete task should be an XArm7-only Pink IK task, tentatively `XArm7IKTask`, rather than a full dual-arm task. It should:

- load the `XARM7_FK_MODEL` model used by `coordinator_teleop_xarm7`
- construct one Pink `FrameTask` for the XArm7 end-effector frame
- claim only the XArm7 arm joints plus the configured XArm7 gripper joint, if present
- accept only the right controller pose stream for IK target updates
- preserve the current single-arm route key, where `PoseStamped.frame_id == "teleop_xarm"` routes to the XArm7 task
- compute IK from the right controller delta and ignore/unconfigure left controller input for this task

This creates a small, testable milestone: prove Pink IK works for XArm7 and one controller stream before adding XArm6, Piper, or dual-arm composition.

Alternative considered: implement the dual-arm XArm + Piper Pink task first. That would exercise the final motivation sooner, but it couples Pink integration risk with combined-model and multi-target routing risk.

### 3. Keep dual-arm as a later subclass, not the initial implementation

The base class should be shaped so a later dual-arm subclass can create multiple Pink `FrameTask`s over a combined model. That later subclass should own the combined-model assumptions and per-target routing. The XArm milestone should not require solving those choices.

For dual-arm XArm + Piper, coordinated solving will still require a combined kinematic model when both arms are optimized in one Pink problem. If a blueprint continues using separate robot models, it should remain two independent single-target tasks and should not claim to provide coordinated dual-arm IK.

Alternative considered: keep one task per arm and merge the solutions. This would be simpler for existing hardware definitions but cannot resolve target conflicts or shared constraints in one optimization.

### 4. Define controller `PoseStamped` as a delta command, not an absolute target

The runtime pose contract is:

- `PoseStamped.position` and `PoseStamped.orientation` are the controller delta from controller engage, expressed in the robot frame after WebXR conversion.
- `XArm7IKTask` consumes the right controller delta only.
- The concrete task captures the XArm7 end-effector initial pose from current robot state when the right controller engages or when its baseline is reset.
- The desired Pink frame target is computed from the captured end-effector pose plus the incoming controller delta.
- Releasing and re-engaging the right controller resets the captured XArm7 end-effector baseline.

This matches current Quest behavior, where `_get_output_pose()` publishes `current_pose - initial_pose`, and current `TeleopIKTask` behavior, where deltas are applied relative to an end-effector pose captured after engage.

Alternative considered: have Quest publish absolute desired end-effector poses. That would make task computation simpler, but it would mix controller tracking space with robot task space and break the current press-and-hold relative teleop behavior.

### 5. Keep XArm routing compatible and reserve explicit multi-target routing for later

Keep the existing `PoseStamped` transport surface, but define `frame_id` as a logical cartesian-command route key, not as a physical coordinate frame.

- XArm7 milestone: `ArmTeleopModule.task_names={"right": "teleop_xarm"}` stamps right-controller commands with the task route key, and `ControlCoordinator._on_cartesian_command()` routes `frame_id == "teleop_xarm"` to `XArm7IKTask.on_cartesian_command()`.
- Left-controller commands are not routed to `XArm7IKTask`; the XArm7 blueprint should not connect or configure a left-hand route for this task.
- Future multi-target routing: coordinator configuration can later map route keys to `(task_name, target_id)`, for example `teleop_dual/xarm -> (teleop_dual, xarm)` and `teleop_dual/piper -> (teleop_dual, piper)`.

This keeps the XArm7 wire format stable while reserving an explicit route-key model for later dual-arm subclasses.

Alternative considered: encode `target_id` directly in `frame_id` by parsing strings without coordinator configuration. That is less explicit and makes blueprint contracts harder to validate.

### 6. Keep target-shape policy out of the base class

For the XArm7 milestone, `XArm7IKTask` manages one target state for the right controller:

- latest controller delta pose
- last update time
- active/inactive flag
- captured initial end-effector pose
- previous primary-button state if needed for edge detection

The shared Pink base should not encode `frame_tasks[0]`, a single `_target_pose`, or a single captured end-effector baseline as its default behavior. Those assumptions belong in a single-target concrete task or a small single-frame intermediate class. The base should own Pink solver plumbing and expose hooks for concrete tasks to update one or more Pink frame targets before solving.

If the right-controller target times out, the XArm7 task is deactivated and its captured baseline is cleared. Future multi-target subclasses can reuse the same target-state container per target so one stale target does not necessarily stop the entire task. To avoid unconstrained joint drift, concrete tasks may include a low-cost posture/hold objective over controlled joints, initialized from the current joint state.

Alternative considered: deactivate the whole dual-arm task when either hand times out. That is safer in the narrow sense, but it makes one dropped controller stream interrupt the other arm and weakens single-hand operation during dual-arm sessions.

### 7. Resource claims remain joint-based and task-level

`XArm7IKTask` claims all configured XArm7 arm joints, plus any configured XArm7 gripper joint, with `SERVO_POSITION` mode. Future dual-arm Pink tasks should claim all joints listed in their combined config as one arbitration unit. This is intentional: coordinated IK should not run concurrently with another task controlling any included arm.

Single-arm tasks continue to claim only their arm joints. Blueprints must not configure both a dual-arm Pink task and independent per-arm teleop tasks for the same joints at the same priority.

Alternative considered: dynamic claims based only on currently active targets. That would allow finer concurrency, but it risks arbitration changing while Pink is solving a shared configuration and makes dual-arm behavior harder to reason about.

### 8. Dependency and solver selection

Add Pink via the PyPI package `pin-pink`. Pink depends on Pinocchio and `qpsolvers`; the implementation should choose a deterministic QP solver from available solvers, preferring a configured solver when present and a known installed solver otherwise. Solver selection belongs in task configuration or a small IK utility, not in the Quest teleop layer.

Alternative considered: vendor Pink-like logic into the existing `PinocchioIK` helper. That would avoid a dependency but would duplicate a maintained task/QP abstraction and still require solving multi-task weighting and limits.

## Risks / Trade-offs

- **Base class becomes too generic too early** → Keep only shared solver/control plumbing in `BasePinkIKTask`; put XArm frame-task construction in `XArmIKTask` and leave dual-arm construction for a later subclass.
- **XArm7 model/frame mismatch** → Validate at `XArm7IKTask` construction that configured `joint_names` match the Pink model’s expected actuated joints and that the XArm7 end-effector `frame_name` exists.
- **Ambiguous route keys** → For the XArm7 milestone, accept only the existing `teleop_xarm` task route from the right controller; reserve explicit `(task_name, target_id)` route maps for later multi-target subclasses.
- **Controller delta semantics misunderstood** → Document in code and specs that `PoseStamped` is a controller delta in robot frame; keep absolute-target support out of this change.
- **Right-controller-only contract regresses other blueprints** → Limit the first concrete class to XArm7 teleop blueprints and keep XArm6, Piper, and dual-arm blueprints on the existing implementation until their subclasses are designed.
- **QP solver unavailable or slow** → Add dependency checks and benchmark the selected solver at the coordinator tick rate; keep existing timeout/joint-delta safety limits.
- **Future dual-arm task preempts more resources than before** → Make this explicit when the dual-arm subclass is introduced and avoid running dual-arm Pink teleop alongside per-arm tasks for the same hardware.
- **Backwards compatibility drift** → Preserve the single-target `frame_id == task_name` adapter and update existing single-arm blueprints before changing dual-arm routing.

## Migration Plan

1. Add Pink dependency and any required mypy ignore/typing configuration for Pink modules.
2. Add `BasePinkIKTask` shared infrastructure for model loading, Pink configuration updates, solver invocation, target-update hooks, safety checks, and `JointCommandOutput` generation.
3. Add a single-frame Pink teleop layer and `XArm7IKTask` as the first concrete subclass with XArm7-specific frame-task construction and right-controller-only target state.
4. Register an XArm7 Pink task type in `ControlCoordinator` and update XArm7 teleop blueprints to route the right controller to that task.
5. Validate manually through `teleop-quest-xarm7` before changing XArm6, Piper, or dual-arm blueprints.
6. Design later XArm6, Piper, and dual-arm subclasses using what the XArm7 implementation proves about the base class.

Rollback is straightforward before deployment: point XArm7 blueprints back to the existing single-target `TeleopIKTask` configuration and route key.

## Open Questions

- What exact XArm7 end-effector frame name should `XArm7IKTask` regulate (`link7` vs `link_tcp` when gripper configuration differs)?
- Which QP solver should be pinned or preferred for real-time teleop in the project environment?
- Should XArm6 later reuse the XArm7 subclass through shared XArm-family helpers, or should it become a separate concrete subclass if its Pink problem construction diverges?
- Which combined XArm + Piper model should be the canonical dual-arm Pink model when the later dual-arm subclass is introduced?
