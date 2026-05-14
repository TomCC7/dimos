## Context

`teleop_quest_piper` currently composes `ArmTeleopModule.blueprint(task_names={"left": "teleop_piper"})` with `coordinator_teleop_piper`, and the coordinator task is created as `task_type="teleop_ik"` using `PIPER_FK_MODEL`, `ee_joint_id=_piper_teleop_cfg.dof`, `hand="left"`, and Piper gripper limits. By contrast, `teleop_quest_xarm7` already routes right-controller deltas to `task_type="xarm7_pink_ik"` and uses `SingleFramePinkIKTask` / `XArm7IKTask` in `dimos/control/tasks/pink_teleop_task.py`.

The existing Pink path already has most of the reusable behavior: Pink model loading, `pink.Configuration`, solver selection, timeout handling, controller engage/disengage, delta-to-frame-target application, gripper trigger mapping, posture and damping objectives, joint delta safety checks, and coordinator-compatible `JointCommandOutput`. The non-reusable part is that the concrete task type and validation are named and shaped around XArm7 even though Piper needs the same single-end-effector pattern with different model, frame, hand, DOF, gripper limits, and adapter wiring.

Official Pink examples reinforce the same abstractions: configure a robot model and controlled frame, compose a `FrameTask` with optional regularization tasks such as `PostureTask`, call `solve_ik(configuration, tasks, dt, solver=..., damping=...)`, then integrate the velocity while respecting limits. Pink's Piper example uses a Piper robot description with a named end-effector frame, which makes Piper a natural target for the same configurable single-frame task rather than a second bespoke solver path.

## Goals / Non-Goals

**Goals:**

- Introduce a shared configurable Pink single-arm teleop task for one end-effector frame and one Quest controller hand.
- Preserve the current XArm7 Pink behavior and route key (`teleop_xarm`) while removing XArm-specific assumptions from the reusable single-frame implementation.
- Add Piper Pink teleop support with explicit robot-specific configuration for model path, end-effector frame, joint names, task name, hand, gripper, and simulation/hardware adapter.
- Modify `teleop_quest_piper` so the existing CLI blueprint uses Piper Pink IK through the current `PoseStamped` and `Buttons` LCM surfaces.
- Keep coordinator task creation and task-type registration explicit so unsupported robot configurations fail at startup with actionable errors.

**Non-Goals:**

- Changing Quest/WebXR coordinate conversion or the delta-pose contract published by `ArmTeleopModule`.
- Coordinated dual-arm Piper/XArm solving; `coordinator_teleop_dual` can remain on legacy `teleop_ik` unless explicitly migrated later.
- Collision avoidance, trajectory planning, or whole-body IK beyond Pink differential IK objectives already used by the Pink task.
- Removing the legacy `TeleopIKTask` implementation or changing `teleop_quest_xarm6` in this change.

## Decisions

1. **Create a generic single-arm Pink task config instead of a Piper-only subclass.**
   - Decision: introduce a `SingleArmPinkIKTaskConfig` / `SingleArmPinkIKTask` (or equivalent names) that extends the existing shared Pink config with the single-frame variables now embedded in `XArm7IKTaskConfig`: `model_path`, `joint_names`, `end_effector_frame`, `hand`, `gripper_joint`, `gripper_open_pos`, `gripper_closed_pos`, `position_cost`, `orientation_cost`, `lm_damping`, `gain`, `posture_cost`, `posture_reference`, `posture_lm_damping`, `posture_gain`, `damping_task_cost`, `solver`, `damping`, `timeout`, `max_joint_delta_deg`, and `priority`.
   - Rationale: Piper and XArm7 differ by configuration, not by control flow. Sharing the single-frame task avoids duplicating solver and safety code.
   - Alternative considered: add a `PiperPinkIKTask` that copies the XArm7 task. That would work quickly but would preserve the XArm/Piper split the request is trying to remove.

2. **Keep thin robot-specific aliases only where they provide defaults or compatibility.**
   - Decision: keep `XArm7IKTaskConfig` / `XArm7IKTask` as compatibility wrappers or aliases around the generic single-arm task, and add Piper defaults through coordinator task config rather than hardcoding a large Piper subclass.
   - Rationale: existing tests and task type `xarm7_pink_ik` can keep working while new code paths use a general `single_arm_pink_ik` task type. Piper configuration can remain explicit in the blueprint where hardware/sim settings already live.
   - Alternative considered: replace all XArm7 names immediately. That risks unnecessary churn in existing specs, tests, and blueprint behavior.

3. **Use one coordinator task type for reusable single-arm Pink IK.**
   - Decision: add `single_arm_pink_ik` to `CARTESIAN_TARGET_TASK_TYPES` and `TELEOP_BUTTON_TASK_TYPES`, and construct it in `_create_task_from_config()` from generic `TaskConfig` fields plus new Pink-specific fields.
   - Rationale: `ArmTeleopModule` already routes by `PoseStamped.frame_id`, so Piper can continue using `teleop_piper` while the coordinator dispatches Cartesian deltas and button state to the new task.
   - Alternative considered: overload `xarm7_pink_ik` to accept Piper. That would make logs, tests, and configuration misleading.

4. **Extend `TaskConfig` with Pink fields only where they are user-facing configuration.**
   - Decision: add task config fields for `end_effector_frame`, solver/frame costs, posture, damping task cost, and Pink damping; reuse existing fields for `joint_names`, `model_path`, `priority`, `timeout`, `max_joint_delta_deg`, `hand`, and gripper settings.
   - Rationale: these variables are the configurable differences across single-arm robots. Keeping them in `TaskConfig` makes blueprints declarative and avoids hidden defaults.
   - Variables to configure per robot:
     - Robot identity and routing: `task_type`, `task_name`, Quest hand, `PoseStamped.frame_id` route key.
     - Kinematic model: FK model path, controlled joint names/order, end-effector frame name, optional model/joint validation mode.
     - Solver: QP solver name, Pink damping, control-loop `dt` via coordinator state, frame task position/orientation costs, LM damping, gain.
     - Regularization: posture cost/reference/LM damping/gain, optional damping task cost.
     - Safety: timeout and max joint delta per tick.
     - Gripper: coordinator gripper joint name and open/closed trigger positions.
     - Runtime adapter: hardware adapter type/address and simulation backend/model path from the robot catalog/teleop blueprint.

5. **Configure Piper Pink teleop in the existing Piper blueprint.**
   - Decision: change `coordinator_teleop_piper` from `task_type="teleop_ik"` to the shared Pink task type, set `model_path=PIPER_FK_MODEL`, `end_effector_frame` to the Piper FK frame used for teleop (expected to be `gripper_base` or the frame verified from the Pinocchio model), keep `hand="left"`, keep route key `teleop_piper`, and retain Piper gripper limits (`0.0` open, `0.035` closed) unless model/hardware verification shows the catalog values should be used directly.
   - Rationale: this satisfies the requested `teleop_quest_piper` behavior with the smallest public-surface change.
   - Alternative considered: create a new `teleop_quest_piper_pink` blueprint. That would avoid changing current behavior but would not satisfy the request to modify `teleop_quest_piper` to use Pink IK.

6. **Validate Piper frames and joint order against the loaded model at startup.**
   - Decision: the shared task should validate model DOF against configured joints, ensure the configured end-effector frame exists, and compare unqualified configured joint names to Pinocchio model names when the model exposes a matching one-arm joint list.
   - Rationale: the highest-risk Piper variable is the frame name because the catalog end-effector link is `gripper_base` while Pink examples may target a joint/link frame such as `joint6`. Startup validation prevents silent wrong-frame teleop.
   - Alternative considered: trust blueprint constants and skip validation. That would push misconfiguration to runtime robot motion.

## Risks / Trade-offs

- **Piper end-effector frame mismatch** → Mitigation: inspect the loaded `PIPER_FK_MODEL` frames in tests or a smoke script and require startup failure for missing frames.
- **Generic task becomes too permissive** → Mitigation: keep validation strict and make every robot-specific variable explicit in the blueprint or wrapper defaults.
- **XArm7 regression while refactoring names** → Mitigation: preserve `xarm7_pink_ik` task type and existing XArm7 tests, adding compatibility tests before migrating internals.
- **Quest hand routing confusion** → Mitigation: keep `teleop_quest_piper` left-controller routing unchanged and add tests that only left-controller output is wired for Piper.
- **Different gripper units across adapters** → Mitigation: keep gripper open/closed values robot-specific and sourced from existing Piper/XArm blueprint or catalog defaults.

## Migration Plan

1. Add the shared single-arm Pink config/task and move XArm7 single-frame logic into it without changing XArm7 public behavior.
2. Wire `xarm7_pink_ik` through the shared implementation and keep all current XArm7 Pink tests passing.
3. Add the new `single_arm_pink_ik` coordinator task type and TaskConfig fields for Pink-specific options.
4. Switch `coordinator_teleop_piper` to the shared Pink task type with Piper-specific configuration, then keep `teleop_quest_piper` route key and transports unchanged.
5. Add/adjust tests for Piper construction, frame validation, routing, gripper claim, and blueprint registration.
6. Rollback is changing `coordinator_teleop_piper` back to `task_type="teleop_ik"`; XArm7 compatibility wrappers should allow the refactor to remain even if Piper rollout is reverted.

## Open Questions

- Which exact frame in `PIPER_FK_MODEL` should be the default teleop target: catalog `gripper_base`, Pink example-style `joint6`, or another model frame exposed by Pinocchio? Implementation should verify against the model and choose the frame that corresponds to the commanded gripper TCP.
- Should Piper gripper positions use the existing teleop values (`0.0` open, `0.035` closed) or catalog gripper values (`0.08` open, `0.0` closed)? The current blueprint behavior should be preserved unless hardware testing shows the catalog values are correct for the Pink path.
