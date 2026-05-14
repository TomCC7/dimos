## MODIFIED Requirements

### Requirement: Shared Pink IK base task provides common solver plumbing
The system SHALL provide a shared Pink IK base task for teleoperation control tasks that owns common solver setup, current-joint extraction, target-update hooks, safety checks, and coordinator-compatible joint command output, while exposing one cohesive task-composition contract for frame and auxiliary Pink tasks.

#### Scenario: Base task composes Pink tasks through unified build contract
- **WHEN** a concrete Pink teleop task initializes
- **THEN** it SHALL build the solver task list through one composition contract that supports frame targets and auxiliary objectives without requiring separate ad-hoc frame/extra setup branches

#### Scenario: Base task emits coordinator-compatible joint commands
- **WHEN** Pink returns a valid IK velocity for active target state
- **THEN** the base task SHALL integrate velocity into ordered joint positions and return `JointCommandOutput` compatible with coordinator arbitration

#### Scenario: Base task enforces joint delta safety
- **WHEN** an IK result exceeds configured per-tick joint delta limits
- **THEN** the task SHALL reject the command for that tick and SHALL NOT publish unsafe joint positions
