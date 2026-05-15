## Context

DimOS modules communicate through typed `In[T]` and `Out[T]` streams and are composed with blueprints and `autoconnect()`. The existing `ControlCoordinator` already centralizes robot control through coordinator-native command inputs: `JointState` for joint position/velocity commands, `PoseStamped` for Cartesian task commands, and `Twist` for velocity-commanded bases.

Learned policy runtimes such as LeRobot use a different boundary: robot observations are converted into framework-specific batched dictionaries, passed through `policy.select_action()`, postprocessed, and converted into robot actions. The policy node should bridge these worlds without leaking framework-specific tensors or action dictionaries into DimOS control APIs.

## Goals / Non-Goals

**Goals:**

- Provide a standard DimOS policy module that consumes images, joint state, and task description as a unified observation.
- Preserve coordinator semantics by publishing existing command message types rather than introducing a parallel control path.
- Isolate policy-framework-specific preprocessing, inference, and postprocessing behind backend adapters.
- Support selecting backends such as LeRobot through module configuration and an in-repo backend registry.
- Make command mode and action-space mapping explicit so policy outputs can be validated before reaching the coordinator.

**Non-Goals:**

- Training, dataset recording, evaluation tooling, or policy fine-tuning workflows.
- Replacing or changing `ControlCoordinator` arbitration, task routing, or hardware adapter behavior.
- Direct robot hardware control from policy backends.
- A third-party plugin distribution mechanism for backends before external backend packages require it.
- A fully general multimodal schema beyond the requested image, joint-state, and task-description inputs.

## Decisions

### Use a canonical policy observation model inside the policy node

The policy node will assemble the latest input streams into a `PolicyObservation` model containing images keyed by camera/source name, the latest `JointState`, a plain `str` task description, timestamp metadata, and optional backend-specific extras. The first implementation will support multiple camera streams directly through configured camera/source names.

Rationale: DimOS already has separate typed streams for images and joint states, while policy frameworks usually want a single observation object or dict. A canonical internal model gives every backend the same semantic input while preserving native DimOS stream composition.

Alternatives considered:

- Expose framework-specific observation dictionaries directly: rejected because it would leak LeRobot-style feature names and tensors into the DimOS API.
- Require all upstream modules to publish one new observation message: deferred because existing camera and coordinator streams should remain directly reusable.
- Delegate multi-camera assembly to a separate observation-builder module: rejected for the first implementation because multi-camera policy support is a core requirement and should be represented directly in `PolicyObservation`.

### Publish coordinator-native command outputs

The policy node will expose coordinator-compatible output streams for supported command families, with the reference path using joint position commands as `JointState`. The design still permits later Cartesian commands as `PoseStamped` and base velocity commands as `Twist`. Internally, backends return a tagged `PolicyCommand` that the node validates and translates into exactly one output family or an explicit no-op.

Rationale: `ControlCoordinator` already routes these types and applies arbitration. Keeping the public output as existing message types avoids a new coordinator protocol and allows policy nodes to connect to existing blueprints and transports.

Alternatives considered:

- Add a new public `RobotCommand` message and teach `ControlCoordinator` to consume it: rejected for the first implementation because it expands coordinator scope and duplicates existing command surfaces.
- Let each backend publish directly to DimOS streams: rejected because it bypasses shared validation and would couple backend implementations to coordinator details.

### Make command mode and action mapping explicit in config

`PolicyNodeConfig` will define backend name/config, allowed command modes, control rate, camera/source mapping, joint/action-name mapping, and task routing details for future non-joint command families. The first reference configuration will map backend actions to joint names and publish joint positions through `JointState.position`. The node will validate that generated commands match the configured command family before publishing.

Rationale: Policy action spaces vary widely. Explicit mapping is safer than inferring whether an action vector means joint positions, joint velocities, Cartesian pose, or base twist.

Alternatives considered:

- Infer action semantics from output shape: rejected because vector shape alone is ambiguous and unsafe for robot control.
- Push all mapping into backend-specific config: rejected because DimOS-level validation still needs to know what command family will be emitted.

### Use a narrow backend protocol and simple registry

Backends will implement a small protocol such as load/initialize, `select_action(observation) -> PolicyCommand`, and close/shutdown. A simple in-repo registry maps backend names to backend classes, initially including `"lerobot"` for the LeRobot adapter and `"test"` for a built-in `TestPolicy` backend.

Rationale: This is enough to support multiple frameworks while keeping the first implementation understandable and type-checkable. LeRobot can preserve its native flow inside the adapter: build inference frame, preprocess, call `policy.select_action()`, postprocess, and convert to a `PolicyCommand`. `TestPolicy` provides a deterministic local backend that emits sinusoidal joint position commands for configured joints, making policy-node wiring testable without model files, GPUs, or external framework dependencies.

Alternatives considered:

- Python entry points or dynamic plugin loading: deferred as over-designed until backend implementations need to live outside the repository.
- Subclassing `PolicyNode` per backend: rejected because it duplicates stream handling, validation, and coordinator publishing logic.

### Include a deterministic TestPolicy backend

The backend registry will include a `TestPolicy` backend that emits joint position `PolicyCommand` values by applying a sinusoid over configured joint names, amplitude, frequency, phase, and optional center positions.

Rationale: A deterministic test backend gives developers a fast way to verify policy node startup, backend selection, command validation, joint-name mapping, blueprint wiring, and `ControlCoordinator.joint_command` integration without requiring LeRobot, model downloads, or robot-learning infrastructure.

Alternatives considered:

- Put sinusoidal playback in a separate demo module: rejected because it would not exercise the backend registration path.
- Mock the backend only in tests: rejected because operators also need a runnable backend for manual wiring checks and examples.

### Teleop always preempts policy commands

When a teleop task and a policy node share joints on the same `ControlCoordinator`, the teleop task SHALL have a higher arbitration priority than the policy's streaming servo task so that engaged teleop always wins per-joint arbitration. Blueprint helpers that wire a policy node alongside teleop are responsible for enforcing this invariant (lower-priority policy servo task by construction, or a build-time error).

Rationale: `ControlCoordinator` arbitrates per joint by priority, and `TeleopIKTask` / `BasePinkIKTask` become active on engage-button frames. Without a configured priority gap, two same-priority claimers silently fight, which is unsafe for a human-in-the-loop preempt.

Alternatives considered:

- Introduce a coordinator-level "teleop override" mode flag that bypasses arbitration: rejected because per-joint priority already expresses the relationship and a global override would conflict with multi-arm setups where only one arm is teleoperated.
- Let operators pick priorities freely: rejected because the safety guarantee should not depend on a configuration choice that is easy to invert.

### Policy node resets when teleop takes over

The policy node SHALL subscribe to the same `buttons` stream that drives teleop engage/disengage. When buttons indicate teleop is engaged on overlapping joints, the policy node SHALL suspend command publication and call `backend.reset()`; when buttons indicate disengage, the node SHALL resume by running a fresh inference pass against the current observation. The backend protocol SHALL therefore define a `reset()` hook that clears any buffered action chunk, recurrent state, or queued commands.

Rationale: Priority arbitration alone is insufficient — even when teleop wins, the policy keeps publishing and the servo task's `_target` keeps getting overwritten, so the moment teleop disengages the servo fires the policy's last stale command. Policies that buffer multi-step action chunks (e.g., LeRobot's diffusion/action-chunk pattern) make this worse: a chunk computed before teleop engaged is no longer aligned with the post-teleop world state. Resetting the backend on takeover guarantees the policy starts from the human-handed-back state on the next tick.

Resume policy is "press-and-hold mirror": as soon as `buttons` reports disengage, the policy may resume on the next observation tick. The configurable `policy_rate` plus a fresh inference call mute the handoff jerk. A separate "policy re-engage" button is deferred until a use case requires it.

Alternatives considered:

- New `Coordinator.control_authority: Out[ControlAuthority]` output listing the winning task per joint: deferred because it expands coordinator scope and the `buttons` stream is already sufficient for the engage/disengage case.
- Infer preemption from the existing `desired_joint_action` output by checking whether the policy's published values appear in the post-arbitration action: rejected because it is a leaky inference and would silently break if multiple tasks happen to converge on similar values.
- Backend keeps state across preemption: rejected because action chunks and recurrent state computed before teleop are no longer aligned with the post-teleop world.

### Keep safety and timing boundaries at the DimOS node layer

The policy node owns rate control, latest-observation buffering, command validation, and lifecycle cleanup. Backend adapters own model loading and framework conversion only.

Rationale: Coordinator behavior is deterministic and command consumers expect valid messages. The policy node is the correct boundary to reject malformed joint names, missing Cartesian task names, unsupported command families, stale observations, or backend no-op outputs before they reach control.

Alternatives considered:

- Let backends handle timing and validation: rejected because each backend would reimplement DimOS-specific safety checks inconsistently.
- Move policy execution into `ControlCoordinator` tasks: rejected because model inference and framework dependencies should remain outside the coordinator tick loop.

### Place the abstraction under manipulation policy

Policy abstractions will live under `dimos.manipulation.policy`.

Rationale: The initial reference path is joint-position manipulation policy execution, and this location keeps learned policy concerns near manipulation planning/control without expanding the generic control coordinator package.

Alternatives considered:

- A top-level `dimos.policy` package: deferred until policy abstractions clearly span non-manipulation domains such as mobile base and aerial robots.
- A subpackage under `dimos.control`: rejected because the policy node performs model inference and observation adaptation rather than coordinator arbitration or hardware routing.

## Risks / Trade-offs

- Action-space ambiguity → Require explicit command mode and action-name mappings in `PolicyNodeConfig`; fail fast when backend outputs do not match the configured command family.
- Stale or mismatched observations → Track timestamps in `PolicyObservation` and allow the node to no-op rather than publish commands from incomplete input.
- Backend dependencies can be heavy or optional → Keep framework integrations behind optional adapters and avoid importing backend packages from the core policy API.
- Test backend motion can be unsafe on real hardware if configured with large amplitudes → Keep `TestPolicy` parameters explicit and document that it is intended for controlled test setups, simulation, or low-amplitude validation.
- Multiple camera inputs are harder than scalar streams → Use configured camera/source names in the observation assembly and keep backend feature-name mapping explicit.
- Inference latency may conflict with control timing → Run policy inference at the configured policy rate and publish coordinator-native commands without modifying the coordinator tick loop.
- A new `RobotCommand` type may still be useful later → Start with existing coordinator-native outputs, then revisit a public command union only if multiple consumers need a single transport type.
- Stale policy commands fire when teleop disengages → Subscribe the policy node to `buttons`, suspend publication on engage, call `backend.reset()` to discard buffered chunks/recurrent state, and resume only with a fresh inference pass on disengage.
- Same-priority teleop and policy claimers silently fight → Blueprint helpers SHALL configure teleop with a higher priority than the policy's servo task or fail to build.

## Migration Plan

1. Add policy observation, internal policy command, backend protocol, and registry types without changing existing coordinator APIs.
2. Add the generic policy node module with coordinator-native outputs and validation.
3. Add a LeRobot backend adapter behind optional dependency boundaries and a built-in dependency-free `TestPolicy` backend that emits sinusoidal joint position commands.
4. Add or update example blueprints to connect multi-camera image streams, coordinator joint state, and a plain string task-description stream to the policy node, then connect joint-position output to `ControlCoordinator.joint_command`.
5. Rollback is removing the new policy node/backend usage from blueprints; existing teleop and coordinator flows remain unchanged.

## Resolved Questions

- Task description input will be a plain `str` stream for now.
- The initial reference command family will be joint position output via `JointState.position`.
- The policy node will support multiple camera streams directly.
- Policy abstractions will live under `dimos.manipulation.policy`.
