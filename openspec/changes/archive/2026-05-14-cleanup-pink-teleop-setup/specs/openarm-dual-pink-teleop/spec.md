## REMOVED Requirements

### Requirement: Quest hands route to target slots in one OpenArm IK solve
**Reason**: OpenArm-specific bimanual Pink teleop setup is being removed from the active teleop task setup path in favor of a single-arm-focused, registry-driven Pink task construction flow.
**Migration**: Use supported single-arm Pink teleop task types (`single_arm_pink_ik`, `xarm7_pink_ik`, `piper_pink_ik`) for active teleop setup; OpenArm dual-arm teleop behavior is no longer configured through this path.

### Requirement: OpenArm dual desired joint state is visualized safely
**Reason**: The OpenArm dual Pink desired-state teleop wiring is removed from this setup surface as part of teleop cleanup and branch elimination.
**Migration**: Consumers should migrate to maintained teleop blueprints/tasks that use the single-arm Pink task pipeline and explicit task registry mapping.
