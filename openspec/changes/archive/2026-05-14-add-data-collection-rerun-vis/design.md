## Context

The `teleop_quest_piper_data_collection` blueprint in `dimos/teleop/quest/blueprints.py` wires together teleop input, the Piper control coordinator, a USB camera, and `PiperDataRecorder` so demonstration sessions land on disk as paired observations and actions. Today there is no live view of any of the recorded signals: the camera feed, the measured joint state from `/coordinator/joint_state`, the desired joint action published as `/coordinator/desired_joint_action`, and the gripper (which lives as the last joint inside both `JointState` streams under the name `arm/gripper`).

DimOS already ships a Rerun bridge — `RerunBridgeModule` (`dimos/visualization/rerun/bridge.py:186`) — that subscribes to a pubsub (LCM, in this stack), inspects every message, and logs it to Rerun. There is a `vis_module("rerun")` factory (`dimos/visualization/vis_module.py:66`) that bundles the bridge with the websocket viewer plumbing. Other teleop blueprints (`teleop_quest_rerun` in the quest blueprints, plus the `demo_camera` blueprint in `dimos/hardware/sensors/camera/module.py:124`) follow this exact pattern, so we have a precedent to copy.

Two constraints shape the design:

- **Recording must stay byte-identical.** Visualization is read-only; we do not transform any stream on the way to disk.
- **`JointState` has no `to_rerun()`.** Most DimOS messages used in this stack (`Image`, `PoseStamped`, `Transform`) implement `to_rerun()` and the bridge logs them automatically, but `JointState` does not (`grep` over `dimos/msgs/sensor_msgs/JointState.py` confirms). To get scalar timeseries — including the gripper, which is just the `arm/gripper` element — we route `JointState` through the bridge's `visual_override` hook, which the bridge already supports (`bridge.py:219`).

## Goals / Non-Goals

**Goals:**
- Add `vis_module("rerun")` to the `teleop_quest_piper_data_collection` blueprint, configured so the four signals the operator cares about (camera color image, measured joint state, desired joint action, gripper command/state) appear in the Rerun viewer as the session runs.
- Keep measured-vs-commanded comparable: the same joint name shows the measured value and the command on adjacent or overlaid scalar plots, so divergence (and a stuck gripper) is visible at a glance.
- Drive visualization off the existing LCM topics already in the blueprint's `transport_map` — no new application code paths, just a new sink.

**Non-Goals:**
- Any change to `PiperDataRecorder`, the on-disk recording format, or the LeRobot conversion path. Visualization is a passive sink.
- Visualization for the XArm6/XArm7 teleop blueprints, the dual-arm blueprint, or any non-data-collection blueprint.
- Adding a separate gripper topic. The gripper joint already rides inside both `JointState` streams; we visualize it from there.
- URDF/3D arm visualization. That capability is deprecated (`openspec/specs/rerun-urdf-robot-visualization/spec.md`). Scope here is camera image plus scalar plots only.

## Decisions

### Decision 1: Reuse `vis_module("rerun")` rather than instantiating `RerunBridgeModule` directly

The factory in `dimos/visualization/vis_module.py:66` already supplies the LCM pubsub, the `RerunWebSocketServer`, and the `WebsocketVisModule` web-dashboard wiring. The `teleop_quest_rerun` blueprint in `dimos/teleop/quest/blueprints.py:45` is the proof-of-pattern.

Alternative considered: hand-wire `RerunBridgeModule.blueprint(pubsubs=[LCM()], …)` to keep the data-collection blueprint visually distinct. Rejected — duplicating the factory's defaults would let them drift, and the websocket server is needed regardless if the operator wants to drive the viewer from the web dashboard.

### Decision 2: Convert `JointState` to Rerun scalars via `visual_override`, not by adding `to_rerun()` to `JointState`

Adding a method to `JointState` would commit every consumer in the codebase to a specific visualization. Instead, we register two entries in the bridge's `visual_override` map — one keyed by the entity path for `/coordinator/joint_state`, one for `/coordinator/desired_joint_action` — each returning a list of `(entity_path, rr.Scalars)` tuples (the `RerunMulti` shape the bridge already supports, see `bridge.py:288`). Entity paths are arranged so measured and commanded plots for the same joint sit side-by-side, e.g.:

```
world/piper/measured/joint1
world/piper/commanded/joint1
…
world/piper/measured/gripper
world/piper/commanded/gripper
```

Alternatives considered:
- *Add `JointState.to_rerun()` returning a single archetype:* loses the measured-vs-commanded distinction because both streams would log to the same path; would also force a styling choice on every other JointState consumer.
- *Write a dedicated visualizer module:* heavier than the override hook; the bridge already exists and overrides are how DimOS extends it (per the comment at `bridge.py:74`).

### Decision 3: Configure plotted joint names from the Piper robot model, not hard-coded

The Piper joint names (`arm/joint1` … `arm/joint6`, `arm/gripper`) are derivable from `make_gripper_joints("arm")` (`dimos/control/components.py:81`) and the Piper robot model config used elsewhere in the blueprint. We pass that list into the override closure so the visualization stays correct if joint naming changes.

Alternative considered: hard-coding `["arm/joint1", …, "arm/gripper"]` in `blueprints.py`. Rejected — duplicates the canonical naming and breaks silently if the model changes.

### Decision 4: Camera and PoseStamped use the bridge's default path

`Image` and `PoseStamped` already implement `to_rerun()`, so the bridge logs them automatically with no override. We rely on this and do not customize their visualization beyond what `vis_module("rerun")` provides out of the box.

### Decision 5: Ship a Rerun blueprint preset tuned for data collection

The whole point of the change is "verify capture live without thinking," so the operator must not have to drag panels around at the start of every session. We pass a `blueprint` factory into `vis_module("rerun", rerun_config={"blueprint": piper_data_collection_blueprint})` — the factory hook is already supported (`bridge.py:180`, `Config.blueprint: BlueprintFactory | None`).

Concrete preset (one `rerun.blueprint.Blueprint` returned by the factory; entity paths match Decision 2):

```
Blueprint(
    Horizontal(
        # Left half: live camera feed.
        Spatial2DView(
            origin="world/piper_data_collection/color_image",
            name="USB camera",
        ),
        # Right half: a vertical stack of per-joint scalar plots,
        # one row per joint, measured + commanded overlaid on the same plot.
        Vertical(
            TimeSeriesView(
                name="joint1",
                contents=[
                    "world/piper/measured/joint1",
                    "world/piper/commanded/joint1",
                ],
            ),
            TimeSeriesView(
                name="joint2",
                contents=[
                    "world/piper/measured/joint2",
                    "world/piper/commanded/joint2",
                ],
            ),
            # ... joint3..joint6 ...
            TimeSeriesView(
                name="gripper",
                contents=[
                    "world/piper/measured/gripper",
                    "world/piper/commanded/gripper",
                ],
            ),
        ),
        column_shares=[2, 1],  # camera gets ~2/3 of the width
    ),
    auto_layout=False,
    auto_views=False,
    collapse_panels=True,  # hide selection/time/blueprint panels by default
)
```

Layout rationale:

- **Camera on the left, plots on the right** — the camera is the largest single artifact and is what the operator stares at while teleoperating. Sticky left placement matches operator muscle memory from other DimOS teleop blueprints that use a single big spatial view.
- **One `TimeSeriesView` per joint, with measured + commanded overlaid** — overlaying on the same axis is what makes command-vs-state divergence visible (Decision 2's whole purpose). Rerun automatically picks distinct series colors per entity path within a view.
- **Gripper as the last row, not segregated** — the operator's question "is the gripper following the command?" is the same question as for any other joint; visually it should sit in the same column.
- **`column_shares=[2, 1]`** — gives the camera ~67% width. Plots stay readable but the camera dominates.
- **`auto_layout=False, auto_views=False`** — without these, Rerun will rearrange panels every time a new entity path appears (the camera, then each scalar arriving over the first few seconds). Locking the layout means the operator sees a stable view from frame one.
- **`collapse_panels=True`** — hides Rerun's blueprint/time/selection side panels so the viewer is mostly camera + plots. Operators can re-open via the View menu if they need to inspect a specific entity.

The factory lives in `dimos/teleop/quest/blueprints.py` (or a sibling helper module under `dimos/teleop/quest/`) alongside the joint-name list from Decision 3, so the joints listed in the preset and the joints emitted by the `visual_override` stay in sync — both iterate the same source list. If joints are added/removed in the Piper model config, the preset rebuilds automatically.

A small helper builds the `TimeSeriesView` per joint to keep the factory body tight:

```python
def _joint_plot(joint: str) -> rrb.TimeSeriesView:
    return rrb.TimeSeriesView(
        name=joint.split("/")[-1],  # "joint1", "gripper", ...
        contents=[
            f"world/piper/measured/{joint.split('/')[-1]}",
            f"world/piper/commanded/{joint.split('/')[-1]}",
        ],
    )
```

Out of scope for the preset: no joint torque plot (the data collection blueprint doesn't record torque), no controller-state plot (Quest buttons are already overlay metadata, not the recording payload), no Rerun `Tabs` (one screen, one job — verify capture).

### Decision 6: Visualization is a runtime sink, not a recorded stream

The new module subscribes only — it does not republish or insert into the recorder pipeline. If the Rerun viewer is unreachable, `RerunBridgeModule` already degrades to logs (see its `start()` behavior); the rest of the blueprint runs unchanged and recording continues.

## Risks / Trade-offs

- **[Risk]** Plot overload: streaming all seven Piper joints × two series (measured + commanded) at coordinator rate can produce dense plots. → **Mitigation:** rely on the bridge's existing per-entity throttle (`bridge.py:277`, the `max_hz`/`_min_intervals` machinery); set a sensible default (e.g. 30 Hz) for the scalar overrides while leaving the camera image at native rate.
- **[Risk]** Joint name drift between the override and the robot model. → **Mitigation:** read joint names from the same Piper model config the blueprint already imports; assert at module construction that the override list matches what arrives on the wire.
- **[Risk]** Rerun viewer is a developer-machine dependency; remote deployments may not have one. → **Mitigation:** the bridge already supports `rerun_open="none"` and a remote-connect mode; defaults come from `global_config.rerun_open`, so the existing `--rerun-open` CLI knob covers it without blueprint changes.
- **[Trade-off]** Tying gripper visualization to `JointState` rather than a dedicated gripper topic means there's no "gripper command" stream separate from the rest of the joint action. The operator sees the gripper as one row in the joint plot. This matches how the data collection layer already records it and avoids inventing a new topic just for visualization.
- **[Trade-off]** No URDF/3D view. Operators get an image + scalar plots, not a kinematic preview. Acceptable given scope and the deprecated state of `rerun-urdf-robot-visualization`.

## Migration Plan

No data migration. Deploying the change is the act of adding the visualization atom to the blueprint; rollback is removing it. Existing recorded sessions are unaffected because the recorder code path does not change.

## Open Questions

- Should the scalar throttle default be exposed as a config field on the visualization wiring, or hard-coded for now? Default to hard-coded with a comment, revisit if operators ask.
- Should the `column_shares` ratio in the preset (currently 2:1 camera vs. plots) be tuned after first operator session? Likely yes — leave the value in one place so it's a one-line change.
