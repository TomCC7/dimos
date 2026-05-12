## 1. Dependencies and Module Structure

- [ ] 1.1 Add the Pink dependency (`pin-pink`) and any required QP solver dependency/configuration to project dependency files.
- [ ] 1.2 Add typing configuration for Pink/qpsolvers imports if required by strict type checking.
- [ ] 1.3 Create a Pink teleop IK task module under `dimos/control/tasks/` with public exports for shared base types and the XArm7 task.

## 2. Shared Pink IK Base Task

- [ ] 2.1 Define a shared Pink IK task config for common solver settings, controlled joint names, model path, timeout, max joint delta, priority, and optional gripper settings.
- [ ] 2.2 Implement `BasePinkIKTask` with the `BaseControlTask` lifecycle, `name`, `claim`, `is_active`, `start`, `stop`, and preemption behavior.
- [ ] 2.3 Implement thread-safe right-controller target state management, including latest pose, active flag, last update time, and captured end-effector baseline.
- [ ] 2.4 Implement current joint extraction from `CoordinatorState` in configured joint order and return no command when any required joint state is missing.
- [ ] 2.5 Implement Pink configuration update, solver invocation, velocity integration over `state.dt`, joint delta safety checks, and `JointCommandOutput` generation.
- [ ] 2.6 Add base-class hooks for robot-specific Pink frame task construction, target update, model validation, and optional posture/hold objectives.

## 3. XArm7 Pink IK Task

- [ ] 3.1 Implement `XArm7IKTaskConfig` with XArm7-specific end-effector frame configuration and defaults matching `coordinator_teleop_xarm7`.
- [ ] 3.2 Implement `XArm7IKTask` as a `BasePinkIKTask` subclass that loads `XARM7_FK_MODEL` and validates configured XArm7 joint names and end-effector frame presence.
- [ ] 3.3 Construct exactly one Pink `FrameTask` for the XArm7 end-effector and update its target from the captured baseline plus right-controller delta pose.
- [ ] 3.4 Preserve gripper target handling compatible with existing XArm7 teleop trigger behavior.
- [ ] 3.5 Ensure right-controller timeout clears XArm7 active target state and captured baseline without emitting joint commands.

## 4. Coordinator and Blueprint Integration

- [ ] 4.1 Add a coordinator task type for the XArm7 Pink IK task and instantiate it from `TaskConfig` without affecting existing `teleop_ik` tasks.
- [ ] 4.2 Extend task configuration fields only as needed for XArm7 Pink IK solver/frame settings while keeping existing XArm7 route key compatibility.
- [ ] 4.3 Update `coordinator_teleop_xarm7` to use the XArm7 Pink IK task type with `task_name="teleop_xarm"`, `XARM7_FK_MODEL`, right hand, and existing gripper settings.
- [ ] 4.4 Keep `teleop_quest_xarm7` routing as right controller output to `/coordinator/cartesian_command` with `frame_id="teleop_xarm"`.
- [ ] 4.5 Leave XArm6, Piper, and dual-arm teleop blueprints on their existing task implementation until their robot-specific Pink subclasses are designed.

## 5. Tests and Validation

- [ ] 5.1 Add unit tests for `BasePinkIKTask` missing joint state, timeout, inactive state, and unsafe joint-delta rejection behavior.
- [ ] 5.2 Add unit tests for XArm7 task construction validating model load, joint-name compatibility, and missing end-effector frame failure.
- [ ] 5.3 Add tests showing right-controller `PoseStamped` updates XArm7 target state while left-controller data is not required.
- [ ] 5.4 Add coordinator/blueprint coverage proving `coordinator_teleop_xarm7` creates the XArm7 Pink IK task and preserves `teleop_xarm` routing.
- [ ] 5.5 Run focused tests for control tasks and XArm7 teleop blueprints.
- [ ] 5.6 Manually QA the XArm7 teleop surface by running the XArm7 teleop blueprint in simulation/replay-safe mode, sending a right-controller cartesian command through `/coordinator/cartesian_command`, and confirming joint command output or safe no-output behavior for invalid state.
