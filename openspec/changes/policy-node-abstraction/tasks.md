## 1. Package and Core Types

- [ ] 1.1 Create the `dimos.manipulation.policy` package with public exports for the policy node, backend protocol, registry, observation model, command model, and built-in backends.
- [ ] 1.2 Define `PolicyObservation` with multi-camera images keyed by configured source name, latest `JointState`, plain `str` task description, timestamp metadata, and optional backend extras.
- [ ] 1.3 Define a tagged `PolicyCommand` model that supports joint position output for the initial implementation plus explicit no-op handling.
- [ ] 1.4 Define `PolicyNodeConfig` with backend name/config, policy rate, camera/source mapping, joint-name mapping, enabled command mode, and default task description settings.

## 2. Backend Registry and Interfaces

- [ ] 2.1 Define a narrow `PolicyBackend` protocol for initialization, action selection from `PolicyObservation`, and shutdown/cleanup.
- [ ] 2.2 Implement an in-repo backend registry with register/create/available behavior and clear errors for unknown backend names.
- [ ] 2.3 Register initial backend names for `lerobot` and `test` through the shared registry path.
- [ ] 2.4 Keep backend-specific dependencies out of core policy imports so the policy node can run without LeRobot installed when LeRobot is not selected.

## 3. TestPolicy Backend

- [ ] 3.1 Implement `TestPolicy` as a dependency-free backend that emits sinusoidal joint position `PolicyCommand` values for configured joint names.
- [ ] 3.2 Support `TestPolicy` parameters for amplitude, frequency, phase, and optional per-joint center positions.
- [ ] 3.3 Ensure `TestPolicy` uses the same backend registry and policy command validation path as other backends.

## 4. LeRobot Backend

- [ ] 4.1 Implement a LeRobot backend adapter that lazily imports LeRobot dependencies only when selected.
- [ ] 4.2 Map `PolicyObservation` images, joint state, and task description into the LeRobot inference input format configured for the selected model.
- [ ] 4.3 Run the LeRobot inference flow through model loading, preprocessing, `select_action`, postprocessing, and conversion into a `PolicyCommand`.
- [ ] 4.4 Surface configuration errors for missing model identifiers, feature mappings, or unsupported LeRobot action outputs before publishing commands.

## 5. Policy Node Module

- [ ] 5.1 Implement the `PolicyNode` DimOS `Module` with typed inputs for camera images, `JointState`, and `str` task description.
- [ ] 5.2 Support direct multi-camera observation assembly using configured camera/source names.
- [ ] 5.3 Run backend inference at the configured policy rate using latest available observations without modifying the `ControlCoordinator` tick loop.
- [ ] 5.4 Publish reference joint position commands as `JointState` values compatible with `ControlCoordinator.joint_command`.
- [ ] 5.5 Reject unsupported command families, unmapped joints, and action dimension mismatches before publishing coordinator commands.
- [ ] 5.6 Ensure module start/stop lifecycle initializes and closes the selected backend cleanly.

## 6. Integration and Verification

- [ ] 6.1 Add unit tests for backend registry selection, unknown backend errors, and registered `lerobot`/`test` backend availability.
- [ ] 6.2 Add unit tests for `TestPolicy` sinusoidal joint position generation.
- [ ] 6.3 Add unit tests for policy node observation assembly with multiple camera inputs, `JointState`, and plain string task description.
- [ ] 6.4 Add unit tests for policy node command validation and `JointState.position` publishing behavior.
- [ ] 6.5 Add an example or test blueprint wiring `PolicyNode` with `TestPolicy` into a coordinator-compatible joint command path.
- [ ] 6.6 Run targeted policy/manipulation tests and type diagnostics for changed files.
