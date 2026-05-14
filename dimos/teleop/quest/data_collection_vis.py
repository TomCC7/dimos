#!/usr/bin/env python3
# Copyright 2025-2026 Dimensional Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Rerun visualization wiring for the Piper data collection blueprint.

Provides the JointState → Rerun scalar override and the layout preset used by
`teleop_quest_piper_data_collection`. Joint name source is shared between the
override and the preset so they cannot drift.
"""

from collections.abc import Callable
from functools import partial
from typing import Literal

import rerun as rr
import rerun.blueprint as rrb

from dimos.control.blueprints.teleop import piper_teleop_robot_model_config
from dimos.control.components import make_gripper_joints
from dimos.msgs.sensor_msgs.JointState import JointState
from dimos.visualization.rerun.bridge import RerunMulti

JointRole = Literal["measured", "commanded"]

# Entity-path layout used by the override and preset:
#   <prefix>/<role>/<short_joint_name>
# Short name = the part after the last "/" in the JointState.name entry.
_ENTITY_PREFIX = "world/piper"

# Camera image topic on the data collection blueprint. The Rerun bridge derives
# the entity path by prepending its entity_prefix ("world" by default), so the
# camera lands at "world/piper_data_collection/color_image". Kept here so the
# preset and any future override stay in sync with the transport_map.
CAMERA_TOPIC = "/piper_data_collection/color_image"
CAMERA_ENTITY_PATH = f"world{CAMERA_TOPIC}"

# Pattern keys used in RerunBridgeModule.visual_override. The bridge constructs
# the entity path as f"{entity_prefix}{topic}" so these match the default prefix.
JOINT_STATE_ENTITY_PATH = "world/coordinator/joint_state"
DESIRED_JOINT_ACTION_ENTITY_PATH = "world/coordinator/desired_joint_action"


def piper_data_collection_joint_short_names() -> list[str]:
    """Ordered short joint names plotted by the data collection visualization.

    Arm joints come first (from the Piper robot model), gripper last. The
    "short" name is what the JointState-to-scalar override emits as the leaf
    entity-path segment, so this list must match what the override produces.
    """
    arm_short = [name.split("/")[-1] for name in piper_teleop_robot_model_config().joint_names]
    gripper_short = make_gripper_joints("arm")[0].split("/")[-1]
    return [*arm_short, gripper_short]


def _entity_path(role: JointRole, short_name: str) -> str:
    return f"{_ENTITY_PREFIX}/{role}/{short_name}"


def _convert_joint_state(role: JointRole, msg: JointState) -> RerunMulti:
    """Module-level converter (picklable so worker subprocesses can deploy it)."""
    out: RerunMulti = []
    for joint_name, position in zip(msg.name, msg.position, strict=False):
        short = joint_name.split("/")[-1]
        out.append((_entity_path(role, short), rr.Scalars([position])))
    return out


def joint_state_to_rerun_scalars(role: JointRole) -> Callable[[JointState], RerunMulti]:
    """Build a visual_override converter that emits per-joint scalars.

    The returned callable takes a `JointState` and produces a list of
    `(entity_path, rr.Scalars)` tuples — one per joint in the incoming message.
    Joints not present in the message are skipped (never raises). Joint names
    are short-cut to their last `/`-segment to match the preset layout.

    Returns a ``functools.partial`` (not a closure) so the result is picklable
    and can survive `multiprocessing` deployment to worker subprocesses.
    """
    return partial(_convert_joint_state, role)


def _joint_plot(short_name: str) -> rrb.TimeSeriesView:
    """Build the per-joint plot pairing measured and commanded series."""
    return rrb.TimeSeriesView(
        name=short_name,
        contents=[
            _entity_path("measured", short_name),
            _entity_path("commanded", short_name),
        ],
    )


def piper_data_collection_rerun_blueprint() -> rrb.Blueprint:
    """Default Rerun layout for `teleop_quest_piper_data_collection`.

    Camera on the left, one TimeSeriesView per joint stacked on the right with
    measured + commanded overlaid. Layout is locked (`auto_layout=False`,
    `auto_views=False`) so panels do not rearrange as entities arrive.
    """
    joint_plots = [_joint_plot(name) for name in piper_data_collection_joint_short_names()]
    return rrb.Blueprint(
        rrb.Horizontal(
            rrb.Spatial2DView(
                origin=CAMERA_ENTITY_PATH,
                name="USB camera",
            ),
            rrb.Vertical(*joint_plots),
            column_shares=[2, 1],
        ),
        auto_layout=False,
        auto_views=False,
        collapse_panels=True,
    )


def piper_data_collection_rerun_config() -> dict[str, object]:
    """Bundle the visual_override map and blueprint factory for vis_module()."""
    return {
        "visual_override": {
            JOINT_STATE_ENTITY_PATH: joint_state_to_rerun_scalars("measured"),
            DESIRED_JOINT_ACTION_ENTITY_PATH: joint_state_to_rerun_scalars("commanded"),
        },
        "blueprint": piper_data_collection_rerun_blueprint,
    }
