### Requirement: RobotContract is a Protocol in the policy package

The system SHALL provide a `RobotContract` Protocol at `dimos.manipulation.policy.contract.RobotContract` that declares the schema mapping between a robot's raw observations / actions and a LeRobot frame dict.

The protocol SHALL be a `typing.Protocol` (structural), not a base class. Concrete implementations SHALL NOT be required to inherit from it.

The protocol SHALL declare these attributes/methods:

- `cameras: Mapping[str, tuple[int, int, int]]` — camera key → `(height, width, channels)`.
- `state_joint_names: Sequence[str]` — ordered short joint names whose values populate the `observation.state` vector slot-by-slot.
- `action_joint_names: Sequence[str]` — ordered short joint names whose values populate the `action` vector slot-by-slot.
- `gripper_joint: str | None` — short name of the gripper joint (must appear in both joint-name sequences when present), or `None` for no-gripper robots.
- `gripper_binarization: GripperBinarization` — dataclass holding `enabled`, `threshold`, `open_pos`, `closed_pos`.
- `features() -> dict[str, dict]` — returns the LeRobot dataset feature schema.
- `rerun_entities() -> Sequence[str]` — entity paths to select from a `.rrd` recording (the columns `from_rerun_row` will read).
- `from_rerun_row(row) -> dict[str, Any]` — Arrow row → LeRobot frame dict. Used offline by the converter.
- `from_messages(images, state, *, action=None, task="") -> dict[str, Any]` — live messages → LeRobot frame dict. Used online by `PolicyNode` (in a later change).
- `to_command(action_vec) -> JointState` — backend action vector → coordinator-native `JointState`. Used online by `PolicyNode` (in a later change).

#### Scenario: Protocol is structural and importable

- **WHEN** a developer imports `from dimos.manipulation.policy.contract import RobotContract`
- **THEN** `RobotContract` is a `typing.Protocol` subclass
- **AND** the import succeeds without requiring the `lerobot` package to be installed

#### Scenario: Concrete class without inheritance satisfies the protocol

- **WHEN** a developer writes a class that defines all `RobotContract` attributes and methods with matching signatures
- **AND** does NOT inherit from `RobotContract`
- **THEN** `isinstance(instance, RobotContract)` returns `True` (via `runtime_checkable`)
- **AND** static type checkers accept the class as a `RobotContract`

### Requirement: LeRobotFrame TypedDict defines the cross-method shape

The system SHALL provide a `LeRobotFrame` TypedDict at `dimos.manipulation.policy.contract.LeRobotFrame` that declares the keys present in every frame dict returned by `from_rerun_row` and `from_messages`.

The TypedDict SHALL include at minimum:

- `observation.state: np.ndarray` — float32, shape `(state_dim,)`.
- `action: np.ndarray` — float32, shape `(action_dim,)`. Optional in inference-time frames built by `from_messages(action=None, ...)`.
- `task: str` — task description.
- `observation.images.<cam>: np.ndarray` — uint8, shape `(H, W, C)`, one entry per camera key declared in the contract's `cameras` mapping. The `<cam>` placeholder is the contract-declared camera key.

#### Scenario: Frame dict shape matches between offline and online translators

- **WHEN** `from_rerun_row` is called with a synthetic Arrow row
- **AND** `from_messages` is called with equivalent synthetic `Image` and `JointState` inputs
- **THEN** both return dicts with the same set of top-level keys (modulo `action`, which `from_messages` may omit)
- **AND** the array dtypes and shapes for shared keys match exactly

### Requirement: GripperBinarization is a dataclass with documented defaults

The system SHALL provide a `GripperBinarization` dataclass at `dimos.manipulation.policy.contract.GripperBinarization` with these fields and defaults:

- `enabled: bool = True`
- `threshold: float = 0.7` — fraction-open threshold; values strictly above threshold map to open (`1.0`), values at or below threshold map to closed (`0.0`).
- `open_pos: float` — robot raw units for fully-open gripper. Required (no default).
- `closed_pos: float` — robot raw units for fully-closed gripper. Required (no default).

The dataclass SHALL be used by both the offline converter and `from_messages` / `to_command` so that all three paths share the same rescaling and thresholding logic.

#### Scenario: Default threshold is 0.7

- **WHEN** a developer constructs `GripperBinarization(open_pos=0.85, closed_pos=0.0)` without specifying `threshold`
- **THEN** `instance.threshold == 0.7`
- **AND** `instance.enabled is True`

#### Scenario: Threshold is exclusive on the open side

- **WHEN** the normalized fraction-open equals exactly the threshold value
- **THEN** the binarized output is `0.0` (closed)

### Requirement: PiperRobotContract implements the protocol for Piper

The system SHALL provide a `PiperRobotContract` class at `dimos.manipulation.policy.contracts.piper.PiperRobotContract` that implements `RobotContract` for the Piper teleop schema written by `RerunDataRecorder`.

`PiperRobotContract` SHALL declare:

- `cameras = {"usb": (480, 640, 3)}`.
- `state_joint_names = ["joint1", "joint2", "joint3", "joint4", "joint5", "joint6", "gripper"]`.
- `action_joint_names = ["joint1", "joint2", "joint3", "joint4", "joint5", "joint6", "gripper"]`.
- `gripper_joint = "gripper"`.
- `gripper_binarization = GripperBinarization(open_pos=0.85, closed_pos=0.0)`.

The joint name list SHALL be derived from the same source as `dimos.teleop.quest.data_collection_vis.piper_data_collection_joint_short_names()` (so renaming a joint in the robot model propagates to the contract through the existing single source of truth, not a duplicated literal).

#### Scenario: PiperRobotContract joint ordering matches the recorder

- **WHEN** a developer instantiates `PiperRobotContract`
- **THEN** `contract.state_joint_names == piper_data_collection_joint_short_names()`
- **AND** `contract.action_joint_names == piper_data_collection_joint_short_names()`
- **AND** `contract.cameras == {"usb": (480, 640, 3)}`

### Requirement: PiperRobotContract.from_rerun_row reads recorder-written entity paths

`PiperRobotContract.from_rerun_row(row)` SHALL read the following entity paths from the Arrow row produced by `rerun.dataframe.load_recording(path).view(...)`:

- `/observation/camera/usb` → `frame["observation.images.usb"]` as a `(H, W, 3)` uint8 array.
- `/observation/state/<joint>` for each `<joint>` in `state_joint_names` → packed in order into `frame["observation.state"]` as a `(7,)` float32 array.
- `/action/<joint>` for each `<joint>` in `action_joint_names` → packed in order into `frame["action"]` as a `(7,)` float32 array.

When `gripper_binarization.enabled` is `True`, the gripper slot of `frame["action"]` SHALL be set to `1.0` if `(raw - closed_pos) / (open_pos - closed_pos) > threshold` else `0.0`. The gripper slot of `frame["observation.state"]` SHALL be the raw value rescaled to fraction-open `[0, 1]` using the same `open_pos` / `closed_pos` (NOT thresholded).

When `gripper_binarization.enabled` is `False`, both gripper slots SHALL contain the raw recorded position in robot units (no rescaling, no thresholding).

#### Scenario: Frame populates state, action, and image keys

- **WHEN** `from_rerun_row` is called on an Arrow row containing all seven `/observation/state/*`, all seven `/action/*`, and `/observation/camera/usb`
- **THEN** the returned dict has keys `{"observation.images.usb", "observation.state", "action"}` plus any task / metadata keys
- **AND** `frame["observation.state"].shape == (7,)` and `frame["action"].shape == (7,)`
- **AND** `frame["observation.images.usb"].shape == (480, 640, 3)` and `dtype == uint8`

#### Scenario: Gripper binarization above threshold writes 1.0 to action

- **WHEN** the recorded `/action/gripper` value normalizes to `0.73` fraction-open with default threshold `0.7`
- **AND** `gripper_binarization.enabled is True`
- **THEN** `frame["action"][6] == 1.0`
- **AND** `frame["observation.state"][6] == 0.73` (rescaled but not thresholded)

#### Scenario: Gripper binarization below threshold writes 0.0 to action

- **WHEN** the recorded `/action/gripper` value normalizes to `0.65` fraction-open with default threshold `0.7`
- **THEN** `frame["action"][6] == 0.0`

#### Scenario: Binarization disabled preserves raw units

- **WHEN** `from_rerun_row` is called on a contract whose `gripper_binarization.enabled is False`
- **AND** the recorded `/action/gripper` value is `0.42`
- **THEN** `frame["action"][6] == 0.42`
- **AND** `frame["observation.state"][6] == <raw recorded state value>` (no rescaling)

### Requirement: PiperRobotContract.from_messages mirrors from_rerun_row shape

`PiperRobotContract.from_messages(images, state, *, action=None, task="") -> dict[str, Any]` SHALL produce a frame dict with the same keys, shapes, and dtypes as `from_rerun_row`, applying the same gripper binarization to `action` (when provided) and the same rescaling to `state` gripper slot.

When `action is None`, the returned dict SHALL omit the `"action"` key (inference-time use).

When a camera key declared in `contract.cameras` is missing from `images`, the call SHALL raise `KeyError` with a message naming the missing camera.

When `state.name` does not contain every joint in `state_joint_names`, the call SHALL raise `KeyError` with a message naming the missing joints.

#### Scenario: from_messages produces the same shape as from_rerun_row

- **WHEN** synthetic `Image` and `JointState` inputs are constructed to match a recorded frame
- **AND** both `from_rerun_row` and `from_messages` are invoked with the equivalent data
- **THEN** the returned dicts have identical keys, identical numpy dtypes, and identical shapes for every shared key

#### Scenario: Inference call with action=None omits the action key

- **WHEN** `from_messages(images, state, action=None, task="pick the block")` is called
- **THEN** the returned dict does NOT contain the key `"action"`
- **AND** the returned dict contains `"observation.images.usb"`, `"observation.state"`, and `"task" == "pick the block"`

### Requirement: PiperRobotContract.to_command emits a coordinator-native JointState

`PiperRobotContract.to_command(action_vec: np.ndarray) -> JointState` SHALL convert a backend-emitted action vector of shape `(7,)` into a `dimos.msgs.sensor_msgs.JointState.JointState` whose:

- `name` field equals the configured arm-prefixed joint names (e.g. `["arm/joint1", ..., "arm/joint6", "arm/gripper"]`).
- `position` field equals the action vector with the gripper slot mapped from `{0.0, 1.0}` back to `{closed_pos, open_pos}` when `gripper_binarization.enabled is True`, or copied through unchanged when disabled.

The method SHALL raise `ValueError` when `action_vec.shape != (7,)`.

#### Scenario: Binary 1.0 in gripper slot maps to open_pos in JointState

- **WHEN** `to_command(np.array([0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 1.0]))` is called on a Piper contract with `open_pos=0.85`
- **THEN** the returned `JointState.position[6] == 0.85`
- **AND** `JointState.name[6] == "arm/gripper"`

#### Scenario: Binary 0.0 in gripper slot maps to closed_pos in JointState

- **WHEN** `to_command(np.array([..., 0.0]))` is called on a Piper contract with `closed_pos=0.0`
- **THEN** the returned `JointState.position[6] == 0.0`

#### Scenario: Wrong action vector length raises ValueError

- **WHEN** `to_command(np.zeros(6))` is called
- **THEN** `ValueError` is raised with a message naming the expected length (7) and the received length (6)

### Requirement: Contract registry resolves implementations by name

The system SHALL provide a registry at `dimos.manipulation.policy.contracts.registry` exposing:

- `register_contract(name: str, factory: Callable[[], RobotContract]) -> None`.
- `get_contract(name: str) -> RobotContract`.
- `available_contracts() -> Sequence[str]`.

The registry SHALL register `"piper"` → `PiperRobotContract` at import time of `dimos.manipulation.policy.contracts`.

`get_contract` SHALL raise `KeyError` listing available names when called with an unknown name.

#### Scenario: piper is registered by default

- **WHEN** a developer imports `dimos.manipulation.policy.contracts`
- **AND** calls `available_contracts()`
- **THEN** the result contains `"piper"`
- **AND** `get_contract("piper")` returns a `PiperRobotContract` instance

#### Scenario: Unknown contract raises with the available list

- **WHEN** `get_contract("does-not-exist")` is called
- **THEN** `KeyError` is raised
- **AND** the error message names the available registered contracts

### Requirement: Core contract imports do not depend on LeRobot

The modules `dimos.manipulation.policy.contract`, `dimos.manipulation.policy.contracts.piper`, and `dimos.manipulation.policy.contracts.registry` SHALL import successfully in environments where the `lerobot` package is NOT installed.

The `features()` method SHALL be implementable using only standard library types and numpy (returning a plain `dict[str, dict]` whose values describe shape / dtype / kind without importing LeRobot dataset feature classes).

#### Scenario: Importing the contract package works without LeRobot

- **WHEN** the `lerobot` package is not installed in the environment
- **AND** a developer imports `from dimos.manipulation.policy.contracts.piper import PiperRobotContract`
- **THEN** the import succeeds
- **AND** `PiperRobotContract().features()` returns without error
