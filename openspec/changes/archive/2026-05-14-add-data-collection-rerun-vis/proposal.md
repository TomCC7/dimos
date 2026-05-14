## Why

Operators currently record Piper teleop demonstrations blind — there is no live view of what the camera sees, where the arm is, what command is being sent, or what the gripper is doing. Misframed recordings or sticky grippers are only discovered after the session, wasting collection time and producing unusable trajectories. Adding a Rerun visualization to the data collection blueprint gives the operator a single in-session display to verify each recorded stream as it is captured.

## What Changes

- Add a Rerun visualization module to the `teleop_quest_piper_data_collection` blueprint so the operator sees the recorded streams live during collection.
- Visualize four logical signals against a shared timeline:
  - The USB camera color image stream (the same `Image` stream that is recorded).
  - Measured joint position from `/coordinator/joint_state`.
  - Desired joint action (joint command) from `/coordinator/desired_joint_action`.
  - Gripper command and gripper measured state, plotted alongside the arm joints so command-vs-state divergence is visible.
- Route the new visualization through the existing Rerun bridge transport pattern so it does not interfere with on-disk recording — visualization is a sink, not a transform.

## Capabilities

### New Capabilities
<!-- None: this change extends an existing capability. -->

### Modified Capabilities
- `piper-data-collection`: Adds a requirement that the blueprint surfaces the recorded streams (camera image, measured joint state, desired joint action, gripper command/state) to a Rerun visualization sink in parallel with on-disk recording, so an operator can verify capture quality live.

## Impact

- Code: `dimos/teleop/quest/blueprints.py` (add Rerun bridge atom and transport entries to `teleop_quest_piper_data_collection`); possibly small wiring in `dimos/teleop/quest/data_collection.py` if the gripper command/state is not already exposed as a publishable stream.
- Specs: delta on `piper-data-collection`.
- Dependencies: no new packages — Rerun and its DimOS bridge are already in-repo (`dimos/visualization/rerun/`).
- Runtime: the data collection blueprint will start a Rerun bridge on launch; operators without a Rerun viewer reachable get logs only, no functional regression to recording itself.
- Out of scope: changes to the on-disk recording format, the LeRobot conversion path, or visualization of non-Piper blueprints.
