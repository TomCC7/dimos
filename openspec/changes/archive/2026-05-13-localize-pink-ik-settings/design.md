## Context

`ControlCoordinator` currently uses a generic `TaskConfig` dataclass to construct all control tasks. The Pink IK integration added many Pink-specific fields to that generic config: solver selection, solver damping, frame names, target task names, frame costs, posture costs and weights, posture references, posture gains, and XArm damping-task cost. The coordinator does not interpret those values; it only forwards them to `XArm7IKTaskConfig` or `OpenArmBimanualIKTaskConfig`.

The Pink task hierarchy already has the right ownership boundary. `BasePinkIKTask` owns common Pink solve plumbing and safety behavior, while concrete tasks such as `XArm7IKTask` and `OpenArmBimanualIKTask` construct robot-specific frame tasks and target update semantics. Pink's own examples keep solver task composition close to the robot IK problem definition (`FrameTask`, optional `PostureTask`, optional `DampingTask`, then `solve_ik(...)`), which matches making these settings task-local rather than coordinator-wide.

## Goals / Non-Goals

**Goals:**

- Simplify coordinator task configuration by removing Pink-internal `pink_*` fields from `TaskConfig`.
- Keep current runtime behavior for XArm7 and OpenArm Pink IK by preserving existing defaults in robot-specific task config classes.
- Make each concrete robot IK task the owner of its solver/task defaults and frame names.
- Preserve externally useful coordinator knobs that are not Pink internals: task type/name, joint list, priority, model path override, timeout, max joint delta, hand, and gripper settings.
- Keep test coverage focused on observable coordinator construction and task-local defaults.

**Non-Goals:**

- Retuning Pink IK costs, posture behavior, or damping behavior.
- Removing constructor-level task config fields that unit tests or future direct task instantiation can still use.
- Adding new runtime configuration systems for rare Pink tuning changes.
- Changing Quest teleop routing, target frame semantics, resource arbitration, or Pink dependency management.

## Decisions

### Remove Pink-specific fields from coordinator `TaskConfig`

The coordinator should not expose fields such as `pink_position_cost`, `pink_orientation_cost`, `pink_posture_joint_weights`, or `pink_left_end_effector_frame` because they are meaningful only inside particular Pink robot tasks. Removing them makes coordinator config represent orchestration rather than solver internals.

Alternative considered: group the fields into a nested `pink` config object on `TaskConfig`. That reduces visual clutter but still keeps rare robot-specific tuning at the coordinator boundary, which does not solve the ownership problem.

### Preserve defaults inside robot-specific task configs

Existing defaults should move into `XArm7IKTaskConfig` and `OpenArmBimanualIKTaskConfig`. `ControlCoordinator._create_task_from_config()` should instantiate those configs with only generic coordinator values plus the default model fallback, allowing task config defaults to fill Pink details.

Alternative considered: hardcode all defaults directly in `_create_task_from_config()`. That would remove dataclass fields but leave coordinator responsible for robot IK defaults, which is the coupling this change is meant to remove.

### Keep direct task configurability for tests and rare code-level tuning

The user asked to remove coordinator config verbosity, not to make Pink tasks impossible to tune in code. Constructor-level config fields can remain on robot-specific task configs where they are local to the task and useful for focused unit tests or future robot-specific subclasses.

Alternative considered: delete every optional Pink field from all task config dataclasses. That would force constants into method bodies and make tests less focused without improving coordinator config ergonomics.

### Let task defaults define frame and target names

XArm7 should continue defaulting its end-effector frame to `link7`. OpenArm should continue defaulting left/right target task names to `teleop_openarm_left` and `teleop_openarm_right`, and left/right end-effector frames to `openarm_left_link7` and `openarm_right_link7`. These defaults belong with the corresponding robot task because each value is robot-model-specific.

Alternative considered: keep frame names on `TaskConfig` because they affect routing and model validation. Routing uses task names and `target_task_names`, and validation happens inside the task, so coordinator-level frame fields are not required.

## Risks / Trade-offs

- Existing out-of-tree configs that set `pink_*` fields on `TaskConfig` will need to move those changes into task-local code or direct task config construction. Mitigation: this repository treats these as internal task details and the change preserves in-repo behavior.
- Hardcoded defaults make ad-hoc tuning less convenient from coordinator config. Mitigation: the request explicitly says these values are rarely changed; direct robot task config remains the escape hatch for code-level tuning.
- Removing pass-through fields can hide accidental behavior changes if defaults differ. Mitigation: add tests that coordinator-created XArm7/OpenArm tasks still use the expected task-local defaults.

## Migration Plan

1. Remove `pink_*` fields from `TaskConfig`.
2. Update coordinator task construction to stop forwarding Pink internals and rely on task config defaults.
3. Ensure robot-specific task configs contain the previous effective defaults.
4. Update tests to instantiate task-local configs directly when testing Pink tuning and to verify coordinator construction uses default robot-specific Pink settings.
5. Run focused Pink teleop task tests and a minimal coordinator construction/manual driver path.

Rollback is straightforward: restore the coordinator `TaskConfig` fields and forwarding if a specific deployment requires runtime tuning before a task-local API is added.
