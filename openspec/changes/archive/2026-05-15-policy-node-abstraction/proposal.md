## Why

Robot learning policies need a first-class DimOS module abstraction so perception/state/task-conditioned models can be composed into robot stacks without one-off glue code for each framework or robot. DimOS already has typed streams and a centralized `ControlCoordinator`; this change standardizes how learned policies consume observations and emit coordinator-compatible commands.

## What Changes

- Add a policy node capability with unified typed inputs for camera images, joint state, and task description.
- Add a unified policy output contract that emits a robot command compatible with existing coordinator command surfaces such as joint, Cartesian, or twist commands.
- Add backend registration/configuration so the same policy node interface can host multiple policy runtimes, including LeRobot, a built-in sinusoidal `TestPolicy`, and future policy frameworks.
- Add explicit observation/action adaptation boundaries so framework-specific tensors, feature names, and postprocessing stay behind backend adapters.
- No breaking changes to existing control coordinator, teleop, or blueprint behavior are intended.

## Capabilities

### New Capabilities

- `policy-node`: A standard module-level policy abstraction that accepts images, joint states, and task descriptions, then publishes coordinator-compatible robot commands.
- `policy-backend-registration`: A pluggable backend registration and selection contract for policy runtimes such as LeRobot, a deterministic sinusoidal `TestPolicy`, and other frameworks.

### Modified Capabilities

- None.

## Impact

- New policy module and backend interfaces under the DimOS module/control or policy package area.
- Integration points with existing typed streams (`In[T]`/`Out[T]`) and blueprint `autoconnect()` patterns.
- Compatibility with `ControlCoordinator` command inputs, currently including `joint_command: In[JointState]`, `cartesian_command: In[PoseStamped]`, and `twist_command: In[Twist]`.
- Message/model definitions for policy observations and robot command outputs if existing message types are insufficient for a unified contract.
- Optional dependency boundaries for external policy frameworks such as LeRobot, keeping backend-specific preprocessing/postprocessing isolated from the core policy node API.
- Built-in `TestPolicy` backend support for exercising policy-node wiring by publishing sinusoidal joint position commands without external model dependencies.
