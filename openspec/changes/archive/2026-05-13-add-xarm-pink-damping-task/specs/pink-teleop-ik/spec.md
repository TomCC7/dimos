## ADDED Requirements

### Requirement: XArm7 Pink IK supports optional joint velocity damping
The XArm7 Pink IK task SHALL support an optional Pink damping objective that minimizes unnecessary joint velocity while preserving the existing end-effector frame objective and optional weighted posture objective.

#### Scenario: Damping objective is included when configured
- **WHEN** the XArm7 Pink IK task is configured with a positive damping-task cost
- **THEN** the task SHALL pass a Pink `DampingTask` together with its configured XArm7 frame task and any enabled posture task to `pink.solve_ik`

#### Scenario: Damping objective is disabled by default
- **WHEN** the XArm7 Pink IK task is configured without an explicit damping-task cost or with a zero damping-task cost
- **THEN** the task SHALL solve with the same Pink task list shape used before damping support, excluding `DampingTask`

#### Scenario: Damping configuration is validated
- **WHEN** the XArm7 Pink IK task is configured with a negative or non-finite damping-task cost
- **THEN** task startup SHALL fail with a clear configuration error and SHALL NOT create the Pink IK task

### Requirement: XArm7 damping preserves existing IK safety behavior
The XArm7 Pink damping objective SHALL NOT bypass existing solver failure handling, target timeout behavior, missing joint-state handling, non-finite velocity rejection, or per-tick joint delta safety checks.

#### Scenario: Damping-enabled solver failure remains non-commanding
- **WHEN** Pink or the selected QP solver fails while the damping objective is enabled
- **THEN** the task SHALL return no joint command for that tick and preserve coordinator stability

#### Scenario: Unsafe damping-enabled output is rejected
- **WHEN** the combined frame, posture, and damping solve produces joint positions exceeding the configured per-tick delta limit
- **THEN** the task SHALL reject the command for that tick and SHALL NOT publish unsafe joint positions
