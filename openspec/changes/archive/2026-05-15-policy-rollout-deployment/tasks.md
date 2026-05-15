## 1. Preempt-tightening in PolicyNode

- [x] 1.1 Remove the unused `_engage_pending_reset` flag from `PolicyNode.__init__` and `_on_buttons` in `dimos/manipulation/policy/node.py`.
- [x] 1.2 Add a second `_engage_lock`-guarded engagement check after `backend.select_action()` returns and before calling `_publish_if_valid()` in `_tick_once`. The check SHALL drop the command (return `None`) when `_engaged` is true.
- [x] 1.3 Change `_subscribe_inputs()` so that when `self.config.teleop_engage_buttons` is non-empty, failure to subscribe to `self.buttons` propagates from `start()` (do not catch + debug-log).
- [x] 1.4 Add a `buttons_grace_period: float = 2.0` field to `PolicyNodeConfig`.
- [x] 1.5 Track first-buttons-message-arrival state on `PolicyNode` (e.g., `_first_buttons_received: bool` plus the `start()` monotonic timestamp). Gate `_tick_once` to skip publication when `teleop_engage_buttons` is non-empty and no `Buttons` message has yet been received.
- [x] 1.6 When the grace period elapses without any `Buttons` message and `teleop_engage_buttons` is non-empty, log a warning each tick until the first message arrives. Avoid log spam by rate-limiting if necessary.

## 2. Rollout gating + RPCs in PolicyNode

- [x] 2.1 Add `_rollout_enabled: bool = False` state under `_engage_lock` on `PolicyNode`.
- [x] 2.2 Gate `_tick_once` to return `None` when `_rollout_enabled` is `False`, alongside the existing `_engaged` check.
- [x] 2.3 Add `@rpc start_rollout(self) -> None` that sets `_rollout_enabled = True` under the lock and calls `self._reset_backend("rollout started")`.
- [x] 2.4 Add `@rpc stop_rollout(self) -> None` that sets `_rollout_enabled = False` under the lock and calls `self._reset_backend("rollout stopped")`.
- [x] 2.5 Add `is_rollout_active(self) -> bool` getter that reads `_rollout_enabled` under the lock.
- [x] 2.6 Export `start_rollout`, `stop_rollout`, `is_rollout_active` in the docstring of `PolicyNode`.

## 3. policy_engage_buttons blueprint helper

- [x] 3.1 Add `policy_engage_buttons(joint_names, teleop_tasks)` in `dimos/manipulation/policy/blueprint.py` next to `policy_servo_task_config`. Reuse the existing `_overlapping_teleop_tasks` filter.
- [x] 3.2 Map each overlapping task's `hand` to `f"{hand}_primary"`. Return a sorted, de-duplicated `list[str]`. Skip tasks whose `hand` is `None`.
- [x] 3.3 Export `policy_engage_buttons` from `dimos.manipulation.policy.__init__`.

## 4. RolloutToggle module

- [x] 4.1 Create `dimos/manipulation/policy/rollout_toggle.py` with `RolloutToggleConfig` (fields: `button: str = "left_secondary"`, `debounce_seconds: float = 0.5`) and `RolloutToggle(Module)` (inputs: `buttons: In[Buttons]`; sibling reference: `policy_node: PolicyNode`).
- [x] 4.2 Implement `_on_buttons(msg)` with rising-edge detection (track `_prev_pressed`) and debounce (track `_last_toggle_at` against `time.monotonic()`).
- [x] 4.3 On accepted edge: read `self.policy_node.is_rollout_active()` and dispatch `start_rollout()` or `stop_rollout()`.
- [x] 4.4 Subscribe to `buttons` in `@rpc start()`; register the disposable so teardown unsubscribes.
- [x] 4.5 When `getattr(msg, self.config.button)` raises `AttributeError`, log a warning once and skip the message.
- [x] 4.6 Export `RolloutToggle` and `RolloutToggleConfig` from `dimos.manipulation.policy.__init__`.

## 5. Deployment blueprint (Piper)

- [x] 5.1 Add `coordinator_teleop_piper_with_policy` in `dimos/control/blueprints/teleop.py` (next to `coordinator_teleop_piper`). It SHALL extend the existing coordinator with a `policy_servo_task_config(...)`-derived servo task whose `joint_names` cover the Piper full joint set (catalog-derived, not literal).
- [x] 5.2 Add `teleop_quest_piper_policy` in `dimos/teleop/quest/blueprints.py` (or a new `dimos/manipulation/policy/blueprints.py`) composing `ArmTeleopModule + coordinator_teleop_piper_with_policy + CameraModule + PolicyNode + RolloutToggle + ManipulationModule` via `autoconnect`.
- [x] 5.3 Use `policy_engage_buttons(...)` to derive `teleop_engage_buttons` for the `PolicyNode` config in the deployment blueprint.
- [x] 5.4 Remap `CameraModule.color_image` to `PolicyNode.image` via the `Blueprint.remap` (or equivalent `remapping_map`) surface.
- [x] 5.5 Default `PolicyNode` config: `backend="test"`, `backend_config={"joint_names": piper_full_joints, "amplitude": 0.0, "frequency": 0.5, "center": [...]}`, `policy_rate=10.0`.
- [x] 5.6 Run `pytest dimos/robot/test_all_blueprints_generation.py` (or whichever regenerator) to refresh `dimos/robot/all_blueprints.py` and add the `"teleop-quest-piper-policy"` entry.
- [x] 5.7 Export the deployment blueprint from the module's `__all__`.

## 6. Tests

- [x] 6.1 Extend `dimos/manipulation/policy/test_node.py` with a test that simulates an engage frame mid-`select_action()` and asserts no command is published (uses a slow stub backend whose `select_action` sleeps while a `Buttons` frame is delivered).
- [x] 6.2 Add a test that `PolicyNode.start()` raises when `teleop_engage_buttons` is non-empty and the `buttons` subscription fails (mock the stream to raise on `subscribe`).
- [x] 6.3 Add a test that with `teleop_engage_buttons` non-empty and no `Buttons` message, `_tick_once` returns `None` even when inputs and backend are ready; after a `Buttons` message arrives, the next tick publishes.
- [x] 6.4 Add a test that elapsed `buttons_grace_period` without a `Buttons` message logs a warning (capture via `caplog`).
- [x] 6.5 Add tests for `start_rollout`/`stop_rollout`/`is_rollout_active` covering: default state is inactive; `start_rollout` calls `backend.reset()` and enables publication; `stop_rollout` calls `backend.reset()` and disables publication; toggling enables/disables `_tick_once` publishing.
- [x] 6.6 Add tests for `policy_engage_buttons` in `dimos/manipulation/policy/test_blueprint.py`: right-hand overlap returns `["right_primary"]`; left+right overlap returns `["left_primary", "right_primary"]`; non-overlapping teleop returns `[]`; tasks with `hand=None` are skipped.
- [x] 6.7 Create `dimos/manipulation/policy/test_rollout_toggle.py` mirroring `dimos/teleop/quest/test_episode_boundary.py`: rising edge toggles state; sustained press does not retoggle; falling edge ignored; debounce window suppresses repeated edges; unknown button name logs and skips.
- [x] 6.8 Add a deployment-blueprint generation test (or extend `test_all_blueprints_generation.py`) verifying `"teleop-quest-piper-policy"` registers, the camera remap is present, no `RerunDataRecorder`/`EpisodeBoundary` modules are wired, and the servo task's priority is strictly less than the Pink IK task's priority.

## 7. Verification

- [x] 7.1 Run `pytest dimos/manipulation/policy/ dimos/teleop/quest/test_episode_boundary.py dimos/robot/test_all_blueprints_generation.py -q`.
- [x] 7.2 Run `dimos --simulation run teleop-quest-piper-policy` (manual smoke) and confirm: with no rollout button press, no policy commands publish; pressing `left_secondary` once starts rollout (test policy emits motion at 10Hz); pressing it again stops rollout; holding `right_primary` while rollout is active preempts (no jitter, no resume-jerk on release). _Performed live: surfaced and fixed a missing `@rpc` on `is_rollout_active`, the open-loop static-zero `TestPolicy` center, and the phase-induced first-sample jump on resume._
- [x] 7.3 Run `pyright dimos/manipulation/policy dimos/control/blueprints/teleop.py dimos/teleop/quest/blueprints.py` (or the project's type-check command) and confirm no new diagnostics.
- [x] 7.4 Run `openspec validate policy-rollout-deployment --strict` and confirm the change is valid.
