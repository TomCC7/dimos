## MODIFIED Requirements

### Requirement: Policy node owns runtime observation and command cadence
The system SHALL run policy inference at a configured policy rate using latest available observations and SHALL keep model inference outside the `ControlCoordinator` tick loop.

The policy node SHALL gate command publication on an operator-controlled rollout state. Inference SHALL NOT publish a command unless `rollout_enabled` is true. The rollout state SHALL default to false at module construction so that operators must explicitly start rollout before the node drives the robot.

The policy node SHALL provide `start_rollout()` and `stop_rollout()` `@rpc` methods that respectively set the rollout state to true and false. Both methods SHALL call `backend.reset()` so that any buffered action chunk or recurrent state is discarded across rollout transitions. The policy node SHALL provide an `is_rollout_active()` getter for sibling modules.

#### Scenario: Policy runs independently from coordinator tick

- **WHEN** a policy node is connected to a control coordinator in a blueprint
- **THEN** the policy node SHALL publish coordinator-native commands from its own runtime loop without modifying the coordinator tick loop

#### Scenario: Missing observation data

- **WHEN** required observation inputs are not available for a policy step
- **THEN** the policy node SHALL avoid publishing a new command for that step

#### Scenario: Rollout disabled by default

- **WHEN** a `PolicyNode` is instantiated and `start()` is called
- **AND** `start_rollout()` has not yet been called
- **THEN** `is_rollout_active()` SHALL return `False`
- **AND** the inference loop SHALL NOT publish any joint commands even if inputs and the backend are ready

#### Scenario: start_rollout enables publication and resets backend

- **WHEN** `start_rollout()` is called on a node whose rollout state is currently disabled
- **THEN** `backend.reset()` SHALL be called
- **AND** `is_rollout_active()` SHALL return `True`
- **AND** the next inference tick with valid inputs SHALL publish a joint command

#### Scenario: stop_rollout suspends publication and resets backend

- **WHEN** `stop_rollout()` is called on a node whose rollout state is currently enabled
- **THEN** `backend.reset()` SHALL be called
- **AND** `is_rollout_active()` SHALL return `False`
- **AND** subsequent inference ticks SHALL NOT publish joint commands until `start_rollout()` is called again

### Requirement: Teleop preempts policy commands
The system SHALL ensure that any teleop control task sharing joints with the policy node has a higher coordinator arbitration priority than the policy's streaming servo task, so that engaged teleop always wins per-joint arbitration over policy output.

The policy node SHALL also re-check teleop engagement state AFTER `backend.select_action()` returns and BEFORE publishing the resulting command. When engagement transitions to true during an in-flight inference call, the produced command SHALL be dropped.

The policy package SHALL provide a `policy_engage_buttons(joint_names, teleop_tasks)` helper, alongside `policy_servo_task_config`, that returns the list of `Buttons` field names whose `True` value indicates teleop is engaged on joints overlapping the policy's `joint_names`. The helper SHALL filter teleop tasks by the same per-joint overlap rule used by `policy_servo_task_config`, then map each overlapping task's `hand` field to its corresponding `_primary` button name (`"left"` → `"left_primary"`, `"right"` → `"right_primary"`), returning a sorted, de-duplicated list. The helper SHALL return an empty list when no overlapping teleop tasks have a configured hand.

#### Scenario: Teleop engaged on overlapping joints

- **WHEN** a teleop task is engaged on joints that the policy node is also publishing commands for
- **THEN** the coordinator SHALL route the teleop task's output to those joints
- **AND** the policy node's commands for the same joints SHALL be ignored by per-joint arbitration

#### Scenario: Blueprint enforces priority invariant

- **WHEN** a policy node blueprint helper is constructed alongside a teleop task on overlapping joints
- **THEN** the helper SHALL configure the policy's streaming servo task with a lower priority than the teleop task, or SHALL fail to build with an error identifying the violating tasks

#### Scenario: Engage edge during in-flight inference drops the command

- **WHEN** `backend.select_action()` is running on the inference thread
- **AND** a `Buttons` frame arrives during that call indicating teleop has just engaged
- **THEN** the policy node SHALL NOT publish the command produced by that in-flight call
- **AND** SHALL call `backend.reset()` on the button-handler thread as before

#### Scenario: policy_engage_buttons derives from overlapping teleop hands

- **WHEN** `policy_engage_buttons(["arm/j1", "arm/gripper"], [teleop_right_on_arm_j1, teleop_left_on_other_arm])` is called
- **AND** only the right-hand teleop task shares joints with the policy's `joint_names`
- **THEN** the helper SHALL return `["right_primary"]`
- **AND** SHALL NOT include `"left_primary"` even though a left-hand teleop task is present

#### Scenario: policy_engage_buttons returns empty when no teleop overlap

- **WHEN** `policy_engage_buttons(joint_names, teleop_tasks)` is called with teleop tasks whose joints do not overlap the policy's `joint_names`
- **THEN** the helper SHALL return `[]`

### Requirement: Policy node suspends and resets on teleop engagement
The system SHALL subscribe the policy node to the same `buttons` stream that drives teleop engage/disengage and SHALL suspend command publication and reset the backend while teleop is engaged on overlapping joints.

When `teleop_engage_buttons` is non-empty in the policy node configuration, the `buttons` input subscription SHALL be a hard requirement of `PolicyNode.start()`. Failure to subscribe SHALL propagate from `start()` and abort module startup; the failure SHALL NOT be swallowed as a debug log.

When `teleop_engage_buttons` is non-empty, the policy node SHALL also gate command publication on having received at least one `Buttons` message since `start()`. Until the first `Buttons` message is received, the inference loop SHALL NOT publish commands. If no `Buttons` message arrives within a configured `buttons_grace_period` (default 2.0 seconds), the policy node SHALL log a warning each tick until a message arrives, without publishing commands.

When `teleop_engage_buttons` is empty, the `buttons` subscription remains optional and absent buttons SHALL NOT gate publication.

#### Scenario: Teleop engagement suspends publication and resets backend

- **WHEN** the `buttons` input indicates teleop has engaged on joints that the policy node controls
- **THEN** the policy node SHALL stop publishing coordinator commands for those joints
- **AND** SHALL call `backend.reset()` so that any buffered actions, action chunks, or recurrent state are discarded

#### Scenario: Teleop disengagement resumes from fresh inference

- **WHEN** the `buttons` input indicates teleop has disengaged from joints that the policy node controls
- **THEN** the policy node SHALL resume publishing commands using a fresh inference pass against the current observation
- **AND** SHALL NOT replay any actions that were buffered before teleop engaged

#### Scenario: Missing buttons subscription with non-empty teleop_engage_buttons fails start

- **WHEN** `PolicyNode.start()` is called on a node whose config has `teleop_engage_buttons=["right_primary"]`
- **AND** the `buttons` input cannot be subscribed (no upstream publisher, transport error, etc.)
- **THEN** `start()` SHALL raise an exception identifying the missing subscription
- **AND** the inference thread SHALL NOT be started

#### Scenario: Missing buttons subscription with empty teleop_engage_buttons is allowed

- **WHEN** `PolicyNode.start()` is called on a node whose config has `teleop_engage_buttons=[]`
- **AND** the `buttons` input cannot be subscribed
- **THEN** `start()` SHALL complete normally
- **AND** the inference loop SHALL be free to publish commands without a teleop-preempt gate

#### Scenario: No published commands before first Buttons message

- **WHEN** `PolicyNode.start()` returns with `teleop_engage_buttons=["right_primary"]` configured
- **AND** no `Buttons` message has yet been received
- **THEN** any inference tick that would otherwise produce a publishable command SHALL be suppressed
- **AND** once any `Buttons` message arrives, subsequent ticks SHALL be free to publish

#### Scenario: Buttons grace period exceeded without message

- **WHEN** more than `buttons_grace_period` seconds elapse after `start()` without any `Buttons` message arriving
- **AND** `teleop_engage_buttons` is non-empty
- **THEN** the policy node SHALL log a warning each tick describing the missing first `Buttons` message
- **AND** SHALL continue to suppress publication until a `Buttons` message arrives
