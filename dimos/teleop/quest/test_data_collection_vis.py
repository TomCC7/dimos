# Copyright 2026 Dimensional Inc.
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

from __future__ import annotations

import pickle
from typing import Any

import rerun as rr
import rerun.blueprint as rrb

from dimos.msgs.sensor_msgs.JointState import JointState
from dimos.teleop.quest.data_collection_vis import (
    CAMERA_ENTITY_PATH,
    joint_state_to_rerun_scalars,
    piper_data_collection_joint_short_names,
    piper_data_collection_rerun_blueprint,
    piper_data_collection_rerun_config,
)


def _walk(node: Any) -> list[Any]:
    """Depth-first walk of a Rerun blueprint container/view tree."""
    out: list[Any] = [node]
    contents = getattr(node, "contents", None)
    if isinstance(contents, list | tuple):
        for child in contents:
            out.extend(_walk(child))
    return out


def test_joint_state_to_rerun_scalars_emits_one_entry_per_joint() -> None:
    names = [
        "arm/joint1",
        "arm/joint2",
        "arm/joint3",
        "arm/joint4",
        "arm/joint5",
        "arm/joint6",
        "arm/gripper",
    ]
    positions = [0.1, -0.2, 0.3, -0.4, 0.5, -0.6, 0.05]
    msg = JointState(name=names, position=positions)

    measured = joint_state_to_rerun_scalars("measured")(msg)
    commanded = joint_state_to_rerun_scalars("commanded")(msg)

    assert len(measured) == len(names)
    assert len(commanded) == len(names)

    measured_paths = [path for path, _ in measured]
    commanded_paths = [path for path, _ in commanded]
    assert measured_paths == [
        "world/piper/measured/joint1",
        "world/piper/measured/joint2",
        "world/piper/measured/joint3",
        "world/piper/measured/joint4",
        "world/piper/measured/joint5",
        "world/piper/measured/joint6",
        "world/piper/measured/gripper",
    ]
    assert commanded_paths == [p.replace("/measured/", "/commanded/") for p in measured_paths]
    # Gripper specifically lands under .../gripper, not a special-cased path.
    assert measured_paths[-1].endswith("/gripper")
    # Archetypes are Rerun Scalars carrying the position values.
    for (_, arch), _pos in zip(measured, positions, strict=True):
        assert isinstance(arch, rr.Scalars)


def test_joint_state_to_rerun_scalars_skips_missing_joints() -> None:
    """Helper must not raise on partial JointStates — emit only what's present."""
    msg = JointState(name=["arm/joint1", "arm/gripper"], position=[0.0, 0.5])
    result = joint_state_to_rerun_scalars("measured")(msg)
    paths = [p for p, _ in result]
    assert paths == [
        "world/piper/measured/joint1",
        "world/piper/measured/gripper",
    ]


def test_preset_factory_returns_blueprint_with_one_view_per_joint() -> None:
    bp = piper_data_collection_rerun_blueprint()
    assert isinstance(bp, rrb.Blueprint)

    nodes = _walk(bp.root_container)
    time_series_views = [n for n in nodes if isinstance(n, rrb.TimeSeriesView)]
    spatial_views = [n for n in nodes if isinstance(n, rrb.Spatial2DView)]

    expected_joints = piper_data_collection_joint_short_names()
    # One TimeSeriesView per joint, named by short name, in order.
    assert [v.name for v in time_series_views] == expected_joints
    # Gripper is the last joint plot.
    assert time_series_views[-1].name == "gripper"

    # Each TimeSeriesView pairs measured + commanded paths for that joint.
    for view, short in zip(time_series_views, expected_joints, strict=True):
        contents = [str(c) for c in (view.contents or [])]
        assert any(f"world/piper/measured/{short}" in c for c in contents), (short, contents)
        assert any(f"world/piper/commanded/{short}" in c for c in contents), (short, contents)

    # Camera Spatial2DView uses the data-collection topic-derived entity path.
    assert len(spatial_views) == 1
    assert str(spatial_views[0].origin) == CAMERA_ENTITY_PATH


def test_rerun_config_is_picklable() -> None:
    """The override + blueprint factory must pickle so the bridge can be deployed
    into a multiprocessing worker. A bare local closure would silently break
    `dimos run teleop-quest-piper-data-collection` at startup."""
    cfg = piper_data_collection_rerun_config()
    restored = pickle.loads(pickle.dumps(cfg))

    msg = JointState(name=["arm/joint1", "arm/gripper"], position=[0.1, 0.5])
    measured = restored["visual_override"]["world/coordinator/joint_state"](msg)
    assert [p for p, _ in measured] == [
        "world/piper/measured/joint1",
        "world/piper/measured/gripper",
    ]
    assert callable(restored["blueprint"])
    assert isinstance(restored["blueprint"](), rrb.Blueprint)
