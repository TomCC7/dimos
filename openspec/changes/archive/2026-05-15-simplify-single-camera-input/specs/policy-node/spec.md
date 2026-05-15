## MODIFIED Requirements

### Requirement: Policy node exposes unified observation inputs
The system SHALL provide a policy node module under `dimos.manipulation.policy` that accepts a single typed camera image input, the latest robot joint state, and a plain string task description as its policy observation inputs.

The camera input SHALL be exposed as a single class-level `image: In[Image]` stream slot on `PolicyNode`. The node SHALL NOT declare additional class-level image stream slots beyond `image`. The cam_key the backend sees in `PolicyObservation.images` SHALL be drawn from `PolicyNodeConfig.camera_key` (default `"main"`).

#### Scenario: Single-camera observation assembly
- **WHEN** the policy node receives an image on its `image` input, a `JointState`, and a string task description
- **THEN** it SHALL assemble a policy observation whose `images` dict contains exactly one entry, keyed by `PolicyNodeConfig.camera_key`, the latest joint state, and the task description string

#### Scenario: No image cached yet
- **WHEN** no image has yet arrived on the `image` input but a `JointState` is available
- **THEN** the assembled observation's `images` dict SHALL be empty
- **AND** the joint state SHALL be present so the backend can decide whether to no-op or proceed

#### Scenario: Task description is plain text
- **WHEN** a task description is provided to the policy node
- **THEN** the policy observation SHALL expose that description as a `str` value rather than requiring a LangChain message or custom task message

#### Scenario: No additional image slots exposed
- **WHEN** a tool or test inspects the `PolicyNode` class-level stream declarations
- **THEN** there SHALL be exactly one `In[Image]` stream slot named `image`
- **AND** there SHALL NOT be `image_aux1`, `image_aux2`, or any other auxiliary image slot
- **AND** there SHALL NOT be an `ALLOWED_CAMERA_SLOTS` module constant in `dimos.manipulation.policy.config`

## REMOVED Requirements

(None — the multi-camera commitment in the existing requirement is rolled back by the MODIFIED block above, not by a REMOVED requirement. The `camera_sources` config field and the `image_aux*` slots are implementation-level details whose removal is captured in the proposal and the modified scenarios above.)
