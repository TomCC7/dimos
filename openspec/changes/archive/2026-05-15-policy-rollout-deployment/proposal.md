## Why

`PolicyNode` exists and unit-tests pass, but it is not yet deployable. The inference loop publishes commands as soon as the module starts, leaving the operator no explicit "go" signal. The teleop-preempts path has three small holes (a publish-after-engage race, a silent fallback when the `buttons` stream isn't connected, and an over-eager `teleop_engage_buttons` default that preempts on unrelated arms). And there is no end-to-end blueprint that composes teleop + policy + a low-priority servo task on the same coordinator.

This change closes those gaps so a policy can be brought up alongside teleop on real hardware with an operator-controlled rollout button and a teleop kill-switch that is correct by construction.

## What Changes

- Tighten teleop preempt in `PolicyNode`:
  - Re-check engagement after `backend.select_action()` returns, before publishing — drop the command if teleop engaged during inference.
  - Require the `buttons` subscription to succeed when `teleop_engage_buttons` is non-empty (raise at start, not log-and-continue).
  - Add a startup grace period gate: when `teleop_engage_buttons` is configured, refuse to publish until at least one `Buttons` message has been received.
  - Remove the unused `_engage_pending_reset` flag.
- Add operator-controlled rollout gating to `PolicyNode`:
  - Add `_rollout_enabled` state (default `False`) and gate `_tick_once` on it.
  - Add `start_rollout()` and `stop_rollout()` `@rpc` methods that flip the gate and call `backend.reset()` on both transitions.
- Add a new `RolloutToggle` module under `dimos/manipulation/policy/` that mirrors `EpisodeBoundary`: watches one configurable `Buttons` field for a debounced rising edge and toggles a target `PolicyNode`'s rollout state.
- Add a blueprint helper `policy_engage_buttons(joint_names, teleop_tasks)` next to `policy_servo_task_config` that derives the `teleop_engage_buttons` list from the overlapping teleop tasks' `hand` field, eliminating manual config.
- Add a deployment blueprint composing `ArmTeleopModule + ControlCoordinator(teleop + policy_servo) + CameraModule + PolicyNode + RolloutToggle` for the Piper reference path. No data-collection wiring.

## Capabilities

### New Capabilities

- `policy-rollout-toggle`: A button-edge module that calls `start_rollout()` / `stop_rollout()` on a target `PolicyNode` with debouncing and explicit single-button-toggle semantics.
- `policy-teleop-deployment`: A reference blueprint that composes teleop, camera, policy node, and a paired low-priority policy servo task on one coordinator, with the teleop-preempts priority invariant enforced at build time.

### Modified Capabilities

- `policy-node`: Tighten preempt requirements (post-inference engagement recheck, mandatory buttons subscription when configured, startup grace period before publishing), add rollout-gating state and RPCs, and add the `policy_engage_buttons` helper that derives engage buttons from overlapping teleop tasks.

## Impact

- `dimos/manipulation/policy/node.py`: new `_rollout_enabled` state, `start_rollout` / `stop_rollout` RPCs, post-inference engagement recheck, mandatory-buttons branch in `_subscribe_inputs`, grace-period gate in `_tick_once`, removal of `_engage_pending_reset`.
- `dimos/manipulation/policy/blueprint.py`: new `policy_engage_buttons` helper alongside `policy_servo_task_config`.
- `dimos/manipulation/policy/rollout_toggle.py` (new): `RolloutToggle` module + `RolloutToggleConfig`.
- `dimos/manipulation/policy/blueprints.py` (new) or extension of `dimos/teleop/quest/blueprints.py`: deployment blueprint `teleop_quest_piper_policy` and a coordinator variant `coordinator_teleop_piper_with_policy`.
- `dimos/control/blueprints/teleop.py`: new `coordinator_teleop_piper_with_policy` blueprint or factory.
- `dimos/robot/all_blueprints.py`: regenerated entry for the new top-level blueprint.
- Unit tests under `dimos/manipulation/policy/` for the post-inference recheck race, the mandatory-buttons error, the grace-period gate, the rollout RPCs, the `RolloutToggle` debounce + edge detection, and the `policy_engage_buttons` overlap derivation.
- No breaking changes to existing teleop, data-collection, or coordinator behavior. Existing `PolicyNode` callers that did not configure `teleop_engage_buttons` keep their behavior; callers that did configure it must now ensure `buttons` is wired.
