## Context

`PolicyNode` is implemented (see `dimos/manipulation/policy/node.py`) and unit-tested via `test_node.py` and `test_blueprint.py`. The preempt and priority invariants from `policy-node-abstraction` are encoded but have small implementation gaps that emerge only under deployment conditions: an in-flight inference call that finishes after the engage edge still publishes; a silently-failed `buttons` subscription leaves the node running with no preempt; the default `teleop_engage_buttons` value treats *any* hand's primary as a preempt signal regardless of joint overlap.

Meanwhile, the node has no operator-facing rollout control. It begins publishing the moment its inference thread starts. For deployment, the human-in-the-loop needs an explicit "go" gesture distinct from teleop engage, mirroring the `EpisodeBoundary` pattern already in `dimos/teleop/quest/episode_boundary.py` (button-edge → `@rpc` on a sibling module).

Finally, there is no end-to-end deployable blueprint. `coordinator_teleop_piper` runs only the teleop task; a deployable composition needs a paired `servo` task on the coordinator with a strictly lower priority, plus a `CameraModule`, a `PolicyNode`, and a `RolloutToggle` connected together with the existing `autoconnect` pipeline.

## Goals / Non-Goals

**Goals:**

- Make `PolicyNode` safe to deploy alongside teleop with no manual safety checks at the wiring layer beyond what the blueprint helpers already enforce.
- Give the operator a single button to start and stop policy rollout, with `backend.reset()` on both transitions so handoff is always against a clean backend.
- Provide one reference deployment blueprint (Piper) that proves the wiring is correct end-to-end, including the autoconnect for `joint_command`, `buttons`, `joint_state`, and a camera stream remapped to the policy node's `image` slot.
- Keep all preempt logic local to `PolicyNode`; the `RolloutToggle` only flips the rollout gate.

**Non-Goals:**

- Recording, data collection, or dataset rotation in the same deployment blueprint. (`EpisodeBoundary` exists for that.)
- A second deployable blueprint for XArm or dual arms. (Pattern is established; other arms can copy it later.)
- Smoothing/ramp-in on the disengage edge. Hardware adapter velocity limits and the policy's own first inference against the post-disengage observation are the existing mitigations.
- A reactive `rollout_enabled: In[bool]` stream. The RPC + `RolloutToggle` pair is the smaller change and matches `EpisodeBoundary`'s shape.

## Decisions

### Re-check engagement after `backend.select_action()` returns

The inference path holds `_engage_lock` only briefly at the top of `_tick_once` to read `_engaged`. Between releasing the lock and calling `joint_command.publish()`, a `Buttons` frame can arrive and trigger `backend.reset()` on the button-handler thread while the inference thread still holds the locally-computed command. Adding a second `_engage_lock` check immediately before `_publish_if_valid` makes the engage edge fully strict: any command computed against pre-engage state is dropped.

The remaining window between the second check and the `publish()` call is microseconds and is covered by coordinator arbitration (the teleop task wins per-joint).

Alternatives considered:

- Hold `_engage_lock` for the whole tick: rejected because LeRobot inference can take 50–200ms; the button-handler thread would block on every engage edge during inference, delaying `backend.reset()` and possibly missing further button frames.
- Drop the lock inside `_publish_if_valid` and re-check there: deferred — keeping the recheck inline in `_tick_once` keeps the publish path simple to read and matches the existing one-tick contract.

### Mandatory `buttons` subscription when `teleop_engage_buttons` is non-empty

The current code catches `Exception` on `self.buttons.subscribe(...)` and logs `debug`. If transport wiring is broken or a remap is missing, the node runs with no preempt at all — the exact unsafe state the design called out. We change the contract: when `teleop_engage_buttons` is non-empty (the deployment case), failure to subscribe SHALL propagate from `start()` and abort module startup.

Alternatives considered:

- Validate at config-parse time: rejected because the subscription itself is what proves the upstream stream exists; static config can't see the missing publisher.
- Log error and continue: rejected because deployment correctness should fail-loud, not produce a robot that quietly has no kill switch.

### Startup grace period for the first `Buttons` message

Even with a successful subscription, the publisher might not be up yet at module start. To avoid a window between `PolicyNode.start()` and the first `Buttons` frame in which the policy publishes commands without a preempt signal, the node gates publication on having seen at least one `Buttons` message when `teleop_engage_buttons` is configured. The gate flips on the first message; if no message arrives within the configured `buttons_grace_period` (default 2.0s), the node logs a warning every tick and refuses to publish.

Alternatives considered:

- No grace period: rejected for the same reason as the silent-fallback fix — preempt invariants must hold from the first tick.
- Polling the upstream publisher's health: rejected as over-coupling; receiving any `Buttons` message is sufficient proof that the kill-switch path is alive.

### Derive `teleop_engage_buttons` from overlapping teleop tasks

`teleop_engage_buttons` currently defaults to `["left_primary", "right_primary"]`. In a dual-arm setup where the policy controls only the right arm, engaging the left arm's teleop would needlessly preempt the policy. The `policy_servo_task_config` helper already knows which teleop tasks overlap with the policy's joints via `_overlapping_teleop_tasks`. We add a sibling helper `policy_engage_buttons(joint_names, teleop_tasks)` that:

- Calls the existing `_overlapping_teleop_tasks` filter.
- Reads each overlapping task's `hand` field (`"left"` / `"right"`).
- Returns the corresponding `_primary` button names (sorted for determinism).

The default config value stays the same to avoid surprising existing tests; deployment blueprints opt into the derivation by calling the helper.

Alternatives considered:

- Change the default to derive at `PolicyNode.__init__`: rejected — the node doesn't know about its sibling tasks. Derivation belongs at the blueprint layer.
- Encode joint→button mapping in the `Buttons` type: rejected as over-coupling Quest semantics to the policy layer.

### Add `start_rollout` / `stop_rollout` RPCs and a `_rollout_enabled` gate

`_tick_once` becomes:

```
with _engage_lock:
    if _engaged: return None
    if not _rollout_enabled: return None
```

`start_rollout()` and `stop_rollout()` are `@rpc` methods that flip `_rollout_enabled` and call `backend.reset()` on both transitions. Reset on *both* transitions is intentional:

- *start*: previously buffered chunks are stale against the current world.
- *stop*: an in-flight `select_action()` should not publish after the gate closes; the publish path's post-inference recheck already covers `_engaged`, so we add the rollout check there too.

Alternatives considered:

- Reset only on start: rejected because mid-rollout backends may hold partially-emitted chunks that would replay on the next start.
- Use a single `set_rollout(bool)` RPC: rejected because two-method RPCs are easier to wire from edge-detectors (one button → one method) and easier to read in logs.

### `RolloutToggle` module mirrors `EpisodeBoundary`

A new `dimos/manipulation/policy/rollout_toggle.py` defines `RolloutToggle(Module)` with:

- `buttons: In[Buttons]` input.
- `policy_node: PolicyNode` (sibling reference, same pattern as `EpisodeBoundary.recorder`).
- Config: `button: str = "left_secondary"`, `debounce_seconds: float = 0.5`.
- Internal `_prev_pressed` and `_last_toggle_at` for edge detection + debounce.
- On rising edge: read `policy_node._rollout_enabled` (via an `is_rollout_active()` getter), call `start_rollout()` or `stop_rollout()` accordingly.

Default button is `left_secondary` (Y) because `right_primary` is teleop engage, `right_secondary` is the episode-boundary rollover, and `right_trigger` is the gripper.

Alternatives considered:

- Two separate buttons (one start, one stop): rejected — toggle on one button matches the recorder rotate idiom and reduces cognitive load during deployment.
- Long-press to stop: deferred — adds debounce complexity without a clear deployment win.
- Place under `dimos/teleop/quest/` next to `EpisodeBoundary`: rejected — the toggle is policy-coupled (it imports `PolicyNode`), so co-locating it under `dimos/manipulation/policy/` keeps the dependency graph one-directional.

### Deployment blueprint composition

A new file `dimos/manipulation/policy/blueprints.py` (or an addition to an existing one) defines:

```
coordinator_teleop_piper_with_policy   # extends coordinator_teleop_piper with a
                                       # policy_servo_task_config()-derived servo task

teleop_quest_piper_policy = autoconnect(
    ArmTeleopModule.blueprint(task_names={"right": "teleop_piper"}),
    coordinator_teleop_piper_with_policy,
    CameraModule.blueprint(),
    PolicyNode.blueprint(...),
    RolloutToggle.blueprint(),
    ManipulationModule.blueprint(robots=[...], enable_viz=True),
).transports({...}).remap({
    ("policy_node", "image"): ("camera_module", "color_image"),
})
```

The `joint_names` and `teleop_engage_buttons` on the `PolicyNode` config are derived from the catalog (`piper_data_collection_joint_short_names`) and from the overlapping teleop task (`policy_engage_buttons` helper), respectively. `backend` defaults to `"test"` with `amplitude=0.0` so the first wiring run is a no-motion shakedown.

The new blueprint is registered in `dimos/robot/all_blueprints.py` so `dimos run teleop-quest-piper-policy` works.

Alternatives considered:

- Extend the existing `teleop_quest_piper` blueprint with policy modules conditionally: rejected — the data-collection variant already adds enough conditional wiring, and operators need a clear name to know what's running.
- Skip the blueprint and rely on docs: rejected — the test that the all-blueprints registry stays generation-clean is exactly the safeguard for "did this wiring work end-to-end".

### Remove `_engage_pending_reset`

The flag is set on the engage edge and never read. Either delete it or wire it to mean "the next disengage should re-reset defensively." Since the backend's `reset()` contract already guarantees full state clearing on the engage edge, the flag has no work to do — delete it.

## Risks / Trade-offs

- **Post-inference recheck still has a publish-window race** → coordinator per-joint arbitration covers it; the policy's stale value loses to teleop's live one on the same tick.
- **Mandatory buttons subscription breaks existing tests that construct `PolicyNode` without a transport** → mitigated by gating the strictness on `teleop_engage_buttons` being non-empty; tests that set it to `[]` (or omit it) keep their behavior.
- **Grace period adds a 2-second window where the policy is silent at startup** → acceptable; teleop is also silent for the same reason (first `Buttons` frame must arrive before engage can fire). Configurable via `buttons_grace_period`.
- **`policy_engage_buttons` returns `[]` when teleop is on a disjoint set of arms** → the policy will run without preempt for that arm. This is the *correct* behavior (no joint overlap → no preempt needed), but operators should still wire the all-hands kill button manually if they want a global stop.
- **Single-button toggle can be miss-pressed during a maneuver** → the 0.5s debounce + the engage button as a hard preempt make accidental stops recoverable.
- **Adding RPCs to `PolicyNode`** → consistent with `EpisodeBoundary.recorder.toggle_recording()`; no new RPC infra needed.
- **Reset on stop_rollout could be expensive for LeRobot backends** → it's a clearing operation, not a re-load; same cost as the engage-edge reset that already exists.

## Migration Plan

1. Land the preempt-tightening changes to `node.py` first. Existing unit tests in `test_node.py` already cover the engage/disengage edges and can be extended with a new race test (engage during in-flight inference).
2. Add `_rollout_enabled` + `start_rollout` / `stop_rollout` RPCs + `is_rollout_active` getter. Default `rollout_enabled=False`; existing tests that drove the node directly via `_tick_once` will need a call to `start_rollout()` first.
3. Add `policy_engage_buttons` helper alongside `policy_servo_task_config`.
4. Add `RolloutToggle` module + unit tests (mirror `test_episode_boundary.py`).
5. Add the deployment blueprint and regenerate `all_blueprints.py`.
6. Rollback: revert blueprint registration first (operator can no longer run `teleop-quest-piper-policy`), then revert the RPC / preempt changes if needed. Existing data-collection and pure-teleop blueprints are unaffected at every step.

## Open Questions

- Should `buttons_grace_period` default to 2.0s (matches typical Quest topic discovery time on LCM) or longer (covers slow network bring-up)? Leaning 2.0s with the value documented in config.
- Should `RolloutToggle` log a warning when toggled while teleop is engaged? Probably yes — the rollout state changes, but no command will publish until disengage; a one-line log makes the operator's mental model match reality.
- Should the deployment blueprint hard-code `backend="test"` or expose backend selection via a top-level CLI flag? Defaulting to `"test"` with `amplitude=0.0` keeps the first run safe; backend selection can be a follow-up using the same pattern `--simulation` already uses.
