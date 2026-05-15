## ADDED Requirements

### Requirement: Pink teleop task creation is registry-driven and RobotConfig-backed
The system SHALL create Pink teleop tasks through a centralized registry/factory contract where each task class owns task-specific validation while robot defaults come from existing `RobotConfig`/catalog sources, so coordinator task construction does not require per-robot `if/elif` branches or duplicate robot profile abstractions.

#### Scenario: Coordinator dispatches Pink task without robot-specific branch logic
- **WHEN** a task config targets a supported Pink teleop task type
- **THEN** the coordinator SHALL resolve the task class from a registry and construct it through the class/config contract rather than hardcoding robot-specific constructor branches

#### Scenario: New robot-specific Pink single-arm task plugs in without coordinator edits
- **WHEN** a new robot-specific Pink single-arm task class is added with a registered task type
- **THEN** the coordinator SHALL instantiate it without requiring a new robot-specific branch in the task factory

#### Scenario: Piper and xArm defaults are sourced from catalog-backed RobotConfig
- **WHEN** constructing Pink teleop task configuration for Piper or xArm
- **THEN** model path, joint names, and end-effector defaults SHALL be sourced from existing catalog/`RobotConfig` pathways rather than duplicated in a new registry-owned robot metadata layer
