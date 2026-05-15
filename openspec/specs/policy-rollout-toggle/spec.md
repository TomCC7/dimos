# policy-rollout-toggle Specification

## Purpose
TBD - created by archiving change policy-rollout-deployment. Update Purpose after archive.
## Requirements
### Requirement: RolloutToggle module dispatches a button edge to PolicyNode rollout RPCs

The system SHALL provide a `RolloutToggle` module at `dimos.manipulation.policy.rollout_toggle.RolloutToggle` that watches a single configured `Buttons` field and toggles a target `PolicyNode`'s rollout state on rising-edge presses.

The module SHALL:

- Expose `buttons: In[Buttons]` as its input stream.
- Hold a sibling reference `policy_node: PolicyNode` (same pattern `EpisodeBoundary` uses for its `recorder`).
- Use a configurable digital button name (default `"left_secondary"`). The button name SHALL be a string corresponding to an attribute on `Buttons` whose value is `bool`.
- Apply a configurable debounce window (default `0.5` seconds) so two rising edges within the window are treated as one.
- Detect rising edges by tracking the previous pressed state per message and dispatching on the `False → True` transition only.
- On each accepted rising edge, read `policy_node.is_rollout_active()` and call `policy_node.stop_rollout()` if active or `policy_node.start_rollout()` if inactive.
- Subscribe to the `buttons` stream from `start()` and unsubscribe at module teardown (via `register_disposable`).
- Log a warning when the configured `button` name is not a digital attribute on `Buttons`.

The default button SHALL be `"left_secondary"` so as not to collide with `right_primary` (teleop engage), `right_secondary` (episode rollover), or `right_trigger` (gripper).

#### Scenario: Rising-edge press toggles rollout on

- **WHEN** a `RolloutToggle` is wired to a `PolicyNode` whose rollout is currently inactive
- **AND** a `Buttons` message arrives with the configured button transitioning from `False` to `True`
- **THEN** the module SHALL call `policy_node.start_rollout()` exactly once

#### Scenario: Rising-edge press toggles rollout off

- **WHEN** a `RolloutToggle` is wired to a `PolicyNode` whose rollout is currently active
- **AND** a `Buttons` message arrives with the configured button transitioning from `False` to `True`
- **THEN** the module SHALL call `policy_node.stop_rollout()` exactly once

#### Scenario: Sustained press does not retoggle

- **WHEN** a `Buttons` message arrives with the configured button `True`
- **AND** the previous message also had the button `True`
- **THEN** the module SHALL NOT call `start_rollout()` or `stop_rollout()`

#### Scenario: Falling edge is ignored

- **WHEN** a `Buttons` message arrives with the configured button transitioning from `True` to `False`
- **THEN** the module SHALL NOT call `start_rollout()` or `stop_rollout()`

#### Scenario: Debounce window suppresses repeated edges

- **WHEN** two rising edges of the configured button arrive within `debounce_seconds` of each other
- **THEN** the module SHALL dispatch only the first edge
- **AND** SHALL ignore the second edge until the debounce window has elapsed

#### Scenario: Unknown button name logs a warning

- **WHEN** the module is configured with a `button` name that does not exist on `Buttons`
- **AND** a `Buttons` message arrives
- **THEN** the module SHALL log a warning identifying the configured name
- **AND** SHALL NOT call `start_rollout()` or `stop_rollout()`

#### Scenario: Default button is left_secondary

- **WHEN** a `RolloutToggle` is instantiated with no `button` override
- **THEN** its configured `button` SHALL be `"left_secondary"`
