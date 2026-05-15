## Context

DimOS already contains most of the pieces needed for a bimanual OpenArm teleop example:

- Quest controller input is exposed by `ArmTeleopModule`, with per-hand task routing through `task_names` and `GlobalConfig.listen_host` controlling the embedded web server bind host.
- Pink IK is already available through `pin-pink`, `pin`, `qpsolvers`, and `daqp`, and `BasePinkIKTask` provides shared solver setup, target activation, safety checks, and coordinator-compatible `JointCommandOutput` generation. Pink accepts multiple weighted tasks in one solve, which is the right model for bimanual robots with shared joints.
- The XArm7 Rerun path demonstrates the desired-output pattern: Quest pose input feeds a Pink task module, which publishes `JointState` for `RerunUrdfRobotVisualizer` without requiring hardware execution.
- OpenArm catalog entries already define bimanual and single-arm URDF paths, joint names, end-effector links, mock/hardware configs, and existing planner/coordinator blueprints.

The missing layer is an OpenArm-specific unified bimanual Pink task plus a registered Quest/Rerun blueprint that composes those existing systems into a simulation-safe example.

## Goals / Non-Goals

**Goals:**

- Provide a bimanual OpenArm Quest teleop example that can be launched with `dimos --listen-host 0.0.0.0 --simulation run teleop-quest-openarm-rerun`.
- Use Pink for the OpenArm bimanual robot as a whole, with one configuration, two left/right end-effector frame tasks, and one solve step that can coordinate shared joints.
- Publish desired joint states and debug pose frames to Rerun so users can inspect targets and IK output before using hardware.
- Keep Rerun joint-name mapping simple: use the suffix after `/` for coordinator-prefixed names and leave names without `/` unchanged.
- Reuse existing OpenArm catalog assets and the shared Pink IK base task rather than creating a parallel IK implementation.
- Ensure the existing `teleop-quest-xarm7-rerun` registry entry remains usable with `--listen-host 0.0.0.0 --simulation`.

**Non-Goals:**

- Do not add new external dependencies beyond the existing Pink/Pinocchio/qpsolvers stack.
- Do not implement physical OpenArm CAN execution for the Rerun example; the example visualizes desired state and remains safe by default.
- Do not replace the existing Drake Cartesian IK OpenArm keyboard teleop path.
- Do not change Quest controller web protocol or Rerun visualization APIs except where configuration is needed for OpenArm.

## Decisions

### Reuse `BasePinkIKTask` with an OpenArm-specific whole-robot task

Create an OpenArm bimanual Pink IK task/config that subclasses the shared Pink base and constructs two `FrameTask` instances in one Pink problem: one for the left end-effector frame and one for the right end-effector frame. The task should load the bimanual OpenArm model, use OpenArm catalog-provided joint names and end-effector links, and solve one full robot configuration so any shared joints are handled by Pink rather than by independent per-arm solvers.

Alternatives considered:

- Reuse `XArm7IKTask` by passing OpenArm paths and frames. This is too xArm-specific in naming and validation and cannot express two end-effector targets in one shared robot solve.
- Use the older `PinocchioIK` teleop task. That misses the user's explicit Pink requirement and would not exercise the newer shared Pink teleop capability.
- Run two independent single-arm OpenArm Pink tasks. This would fail the point of using Pink for a bimanual robot: shared joints and cross-arm trade-offs must be solved in one optimization problem.

### Model the Rerun example as desired-state visualization first

Follow `teleop_quest_xarm7_rerun` at the blueprint level, but replace the single-arm desired-state module with a unified OpenArm bimanual desired-state module. Quest pose deltas update left/right targets on one Pink task, the module publishes a single whole-robot `JointState`, and `RerunUrdfRobotVisualizer` renders the configured OpenArm bimanual URDF. This keeps the example runnable without OpenArm hardware and avoids accidental motor commands.

Alternatives considered:

- Compose directly with `coordinator_openarm_bimanual`. That would make the example hardware-oriented and less safe for first-run Quest testing.
- Require MuJoCo dynamics. OpenArm currently has URDF/catalog assets in-repo but no established OpenArm MuJoCo sim path comparable to xArm7's `XARM7_SIM_PATH`; Rerun visualization is the lower-risk surface.

### Route each Quest hand to a target slot in the unified task

Configure `ArmTeleopModule.blueprint(task_names={"left": "teleop_openarm_left", "right": "teleop_openarm_right"})`. The unified Pink desired-state module uses `PoseStamped.frame_id` to update the corresponding left or right target slot, then solves both active targets together in one Pink configuration.

Alternatives considered:

- Use one combined bimanual task name on the wire. That would require a new multi-target message format and does not match existing `PoseStamped` teleop streams.
- Use separate teleop modules per hand. That would duplicate the web server/controller input path and create unnecessary port and routing complexity.

### Register the CLI entry through the existing blueprint scan workflow

Define `teleop_quest_openarm_rerun` as a module-level blueprint in `dimos/teleop/quest/blueprints.py`, export it in `__all__`, and regenerate `dimos/robot/all_blueprints.py` via `pytest dimos/robot/test_all_blueprints_generation.py` so the CLI key becomes `teleop-quest-openarm-rerun`.

Alternatives considered:

- Manually edit `all_blueprints.py`. The repo explicitly marks this file as generated, and CI checks it against the scanner.
- Put the blueprint only under `dimos/robot/manipulators/openarm/blueprints.py`. Quest teleop blueprints currently live in `dimos/teleop/quest/blueprints.py`; keeping it there preserves discoverability with the existing teleop examples.

### Normalize Rerun joint names with slash-suffix heuristic

Use `joint_name.rsplit("/", maxsplit=1)[-1]` as the default Rerun URDF joint-name normalization. This maps DimOS coordinator names like `arm/joint1` or `left_arm/joint1` back to URDF names like `joint1`, and it leaves OpenArm-style whole-robot names like `openarm_left_joint1` unchanged because they contain no `/`.

Alternatives considered:

- Maintain configurable prefix lists such as `joint_name_prefixes=["arm/"]`. That works but adds configuration surface for the common case and is unnecessary while DimOS coordinator namespaces use `/`.
- Match `JointState.position` by array order. That is more fragile for multi-robot and bimanual cases, where explicit joint names are the safer contract.

## Risks / Trade-offs

- OpenArm bimanual URDF joint/frame naming may not match Pink's model names exactly → validate startup against configured whole-robot joint names and both end-effector frame names, and add a smoke test that instantiates the blueprint.
- Rerun visualization may need bimanual joint-name mapping beyond the existing xArm prefix stripping → configure names from the OpenArm catalog and add a smoke/driver check that both left and right joint names flow through one `JointState` stream.
- Slash-suffix normalization could collapse two different coordinator namespaces that share the same URDF suffix → keep this heuristic only at the URDF visualization boundary where the displayed robot has one URDF joint namespace, and rely on exact names for OpenArm whole-robot joints that do not contain `/`.
- Whole-robot IK can produce trade-offs when left/right targets conflict or shared joints are underconstrained → expose costs/gain/damping in config and start with conservative defaults that keep solves stable.
- `--simulation` may imply physical simulation to some users → document that this entry is a Rerun desired-state simulation/debug example, not OpenArm dynamics.
- Running the Quest web server on `0.0.0.0` is intentionally broader network exposure → preserve the secure default `127.0.0.1` and only bind externally when the user passes `--listen-host 0.0.0.0`.
