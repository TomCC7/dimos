## 1. Package and Core Types

- [x] 1.1 Create the `dimos.manipulation.policy` package with public exports for the policy node, backend protocol, registry, observation model, command model, and built-in backends.
- [x] 1.2 Define `PolicyObservation` with multi-camera images keyed by configured source name, latest `JointState`, plain `str` task description, timestamp metadata, and optional backend extras.
- [x] 1.3 Define a tagged `PolicyCommand` model that supports joint position output for the initial implementation plus explicit no-op handling.
- [x] 1.4 Define `PolicyNodeConfig` with backend name/config, policy rate, camera/source mapping, joint-name mapping, enabled command mode, and default task description settings.

## 2. Backend Registry and Interfaces

- [x] 2.1 Define a narrow `PolicyBackend` protocol for initialization, action selection from `PolicyObservation`, shutdown/cleanup, and a `reset()` hook for clearing buffered action chunks / recurrent state on preemption.
- [x] 2.2 Implement an in-repo backend registry with register/create/available behavior and clear errors for unknown backend names.
- [x] 2.3 Register initial backend names for `lerobot` and `test` through the shared registry path.
- [x] 2.4 Keep backend-specific dependencies out of core policy imports so the policy node can run without LeRobot installed when LeRobot is not selected.

## 3. TestPolicy Backend

- [x] 3.1 Implement `TestPolicy` as a dependency-free backend that emits sinusoidal joint position `PolicyCommand` values for configured joint names.
- [x] 3.2 Support `TestPolicy` parameters for amplitude, frequency, phase, and optional per-joint center positions.
- [x] 3.3 Ensure `TestPolicy` uses the same backend registry and policy command validation path as other backends.
- [x] 3.4 Implement `TestPolicy.reset()` so the sinusoid phase deterministically restarts without erroring.

## 4. LeRobot Backend

- [x] 4.1 Implement a LeRobot backend adapter that lazily imports LeRobot dependencies only when selected.
- [x] 4.2 Map `PolicyObservation` images, joint state, and task description into the LeRobot inference input format configured for the selected model.
- [x] 4.3 Run the LeRobot inference flow through model loading, preprocessing, `select_action`, postprocessing, and conversion into a `PolicyCommand`.
- [x] 4.4 Surface configuration errors for missing model identifiers, feature mappings, or unsupported LeRobot action outputs before publishing commands.
- [x] 4.5 Implement `LeRobotBackend.reset()` so any buffered action chunk and recurrent/hidden state are cleared and the next `select_action` recomputes from the next observation.

## 5. Policy Node Module

- [x] 5.1 Implement the `PolicyNode` DimOS `Module` with typed inputs for camera images, `JointState`, and `str` task description.
- [x] 5.2 Support direct multi-camera observation assembly using configured camera/source names.
- [x] 5.3 Run backend inference at the configured policy rate using latest available observations without modifying the `ControlCoordinator` tick loop.
- [x] 5.4 Publish reference joint position commands as `JointState` values compatible with `ControlCoordinator.joint_command`.
- [x] 5.5 Reject unsupported command families, unmapped joints, and action dimension mismatches before publishing coordinator commands.
- [x] 5.6 Ensure module start/stop lifecycle initializes and closes the selected backend cleanly.
- [x] 5.7 Add a `buttons: In[Buttons]` input on `PolicyNode` and subscribe to it on start; on engage frames overlapping the policy's joints, suspend command publication and call `backend.reset()`.
- [x] 5.8 On disengage frames, resume command publication on the next observation tick using a fresh `backend.select_action()` call; do not replay any pre-engage buffered actions.
- [x] 5.9 Provide a blueprint helper (e.g., `PolicyNode.blueprint(...).with_servo_task(...)`) that auto-configures a paired `JointServoTask` with matching `joint_names` and a priority strictly lower than any teleop task on overlapping joints; fail to build with a clear error when the invariant cannot be satisfied.

## 6. Integration and Verification

- [x] 6.1 Add unit tests for backend registry selection, unknown backend errors, and registered `lerobot`/`test` backend availability.
- [x] 6.2 Add unit tests for `TestPolicy` sinusoidal joint position generation.
- [x] 6.3 Add unit tests for policy node observation assembly with multiple camera inputs, `JointState`, and plain string task description.
- [x] 6.4 Add unit tests for policy node command validation and `JointState.position` publishing behavior.
- [x] 6.5 Add an example or test blueprint wiring `PolicyNode` with `TestPolicy` into a coordinator-compatible joint command path.
- [x] 6.6 Add unit tests for the teleop-takeover path: simulate engage button frames, assert `backend.reset()` is invoked and the node stops publishing; simulate disengage, assert publication resumes from a fresh `select_action` and no pre-engage buffered command is emitted.
- [x] 6.7 Add a unit test for the blueprint priority invariant: building a `PolicyNode` blueprint alongside a teleop task with priority ≤ the policy servo task's priority MUST raise a clear error.
- [x] 6.8 Run targeted policy/manipulation tests and type diagnostics for changed files.
