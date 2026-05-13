## ADDED Requirements

### Requirement: XArm7 Pink IK supports a weighted posture objective
The XArm7 Pink IK task SHALL support an optional weighted posture objective that biases IK solutions toward a configured or captured posture while keeping the configured end-effector frame task in the Pink solve.

#### Scenario: Posture objective is included with the frame task
- **WHEN** the XArm7 Pink IK task is configured with a nonzero posture cost
- **THEN** the task SHALL pass both the configured XArm7 frame task and the weighted posture task to `pink.solve_ik`

#### Scenario: Posture objective can be disabled
- **WHEN** the XArm7 Pink IK task is configured with posture disabled or zero posture cost
- **THEN** the task SHALL solve with the same frame-task-only objective shape used before this change

### Requirement: Weighted posture uses per-joint weights in model order
The weighted posture objective SHALL apply configured per-joint weights to both the Pink posture error and posture Jacobian using the Pinocchio model joint order that Pink expects.

#### Scenario: Configured joint weights map to XArm7 model joints
- **WHEN** posture weights are configured for XArm7 joint names
- **THEN** the task SHALL map those weights to the corresponding Pinocchio model joints before solving and SHALL fail startup for unknown posture joint names

#### Scenario: Unspecified posture weights use defaults
- **WHEN** a configured controlled XArm7 joint has no explicit posture weight
- **THEN** the task SHALL use the configured default posture weight for that joint

### Requirement: Weighted posture target is initialized safely
The XArm7 Pink IK task SHALL initialize the posture target without causing an immediate jump away from the current teleop engagement posture.

#### Scenario: Current posture initializes target by default
- **WHEN** no explicit posture reference is configured and the task receives a valid current XArm7 joint state for IK compute
- **THEN** the task SHALL set the weighted posture target from that current joint state before solving

#### Scenario: Configured posture reference overrides current posture
- **WHEN** an explicit posture reference is configured for one or more XArm7 joints
- **THEN** the task SHALL use those configured reference values for the posture target and current values for any unspecified controlled joints

### Requirement: Weighted posture preserves existing IK safety behavior
The weighted posture objective SHALL NOT bypass existing solver failure handling, target timeout behavior, or per-tick joint delta safety checks.

#### Scenario: Unsafe posture-biased output is rejected
- **WHEN** the combined frame and posture solve produces joint positions exceeding the configured per-tick delta limit
- **THEN** the task SHALL reject the command for that tick and SHALL NOT publish unsafe joint positions

#### Scenario: Solver failure remains non-commanding
- **WHEN** Pink or the selected QP solver fails while the posture objective is enabled
- **THEN** the task SHALL return no joint command for that tick and preserve coordinator stability
