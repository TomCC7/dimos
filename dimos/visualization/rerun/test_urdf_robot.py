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

"""Tests for Rerun URDF robot visualization."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import rerun as rr
import rerun.urdf as rr_urdf

from dimos.msgs.geometry_msgs.PoseStamped import PoseStamped
from dimos.msgs.sensor_msgs.JointState import JointState
from dimos.robot.catalog.ufactory import XARM7_FK_MODEL
from dimos.visualization.rerun import urdf_robot
from dimos.visualization.rerun.urdf_robot import (
    RerunUrdfRobotVisualizer,
    _resolve_package_uris,
    normalize_joint_name,
)


def test_xarm7_urdf_loads_and_computes_revolute_joint_transform() -> None:
    tree = rr_urdf.UrdfTree.from_file_path(Path(str(XARM7_FK_MODEL)))
    joint = tree.get_joint_by_name("joint1")

    transform = joint.compute_transform(0.25)

    assert joint.joint_type == "revolute"
    assert transform.parent_frame is not None
    assert transform.child_frame is not None


def test_normalize_joint_name_supports_dimos_prefixes() -> None:
    assert normalize_joint_name("arm/joint1", ["arm/"]) == "joint1"
    assert normalize_joint_name("right_arm/joint2", []) == "joint2"
    assert normalize_joint_name("joint3", ["arm/"]) == "joint3"


def test_package_uris_resolve_to_absolute_mesh_paths() -> None:
    package_path = Path(str(XARM7_FK_MODEL)).parents[2]
    text = 'filename="package://xarm_description/meshes/xarm7/visual/link1.stl"'

    resolved = _resolve_package_uris(text, {"xarm_description": package_path})

    assert "package://" not in resolved
    assert str(package_path / "meshes/xarm7/visual/link1.stl") in resolved


def test_joint_state_updates_named_urdf_joints_and_preserves_omitted_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    logged: list[tuple[str, Any]] = []

    monkeypatch.setattr(urdf_robot, "rerun_init", lambda *args, **kwargs: None)
    logged_urdfs: list[Path] = []
    monkeypatch.setattr(
        rr,
        "log_file_from_path",
        lambda path, **kwargs: logged_urdfs.append(Path(str(path))),
    )
    monkeypatch.setattr(rr, "log", lambda path, archetype: logged.append((path, archetype)))

    module = RerunUrdfRobotVisualizer(
        urdf_path=XARM7_FK_MODEL,
        entity_path_prefix="world/test_xarm7",
        end_effector_frame="link7",
    )
    try:
        module._load_urdf()

        module.update_joint_state(
            JointState(name=["arm/joint1", "arm/joint2"], position=[0.1, 0.2])
        )
        module.update_joint_state(
            JointState(name=["arm/joint1", "arm/missing"], position=[0.3, 9.0])
        )

        assert module._last_positions == {"joint1": 0.3, "joint2": 0.2}
        assert "missing" in module._warned_unmatched
        assert logged_urdfs
        assert "package://" not in logged_urdfs[0].read_text()
        assert any(path == "world/test_xarm7/transforms" for path, _ in logged)
        assert any(path == "world/debug/end_effector" for path, _ in logged)
    finally:
        module.stop()


def test_debug_pose_logging_uses_distinct_transform_and_marker_entities(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    logged: list[tuple[str, Any]] = []
    monkeypatch.setattr(rr, "log", lambda path, archetype: logged.append((path, archetype)))

    module = RerunUrdfRobotVisualizer.__new__(RerunUrdfRobotVisualizer)
    module.log_pose(
        PoseStamped(position=[1.0, 2.0, 3.0], orientation=[0.0, 0.0, 0.0, 1.0]),
        "world/debug/desired_controller",
        [255, 120, 180],
    )

    assert [path for path, _ in logged] == [
        "world/debug/desired_controller",
        "world/debug/desired_controller/marker",
    ]
