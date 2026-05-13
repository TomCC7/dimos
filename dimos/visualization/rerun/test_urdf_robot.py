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
from dimos.robot.catalog.openarm import OPENARM_V10_BIMANUAL_FK_MODEL
from dimos.robot.catalog.ufactory import XARM7_FK_MODEL
from dimos.visualization.rerun import urdf_robot
from dimos.visualization.rerun.urdf_robot import (
    RerunUrdfRobotVisualizer,
    RerunUrdfRobotVisualizerConfig,
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
    assert normalize_joint_name("arm/joint1") == "joint1"
    assert normalize_joint_name("left_arm/joint1") == "joint1"
    assert normalize_joint_name("openarm_left_joint1") == "openarm_left_joint1"
    assert normalize_joint_name("joint3") == "joint3"


def test_package_uris_resolve_to_absolute_mesh_paths() -> None:
    package_path = Path(str(XARM7_FK_MODEL)).parents[2]
    text = 'filename="package://xarm_description/meshes/xarm7/visual/link1.stl"'

    resolved = _resolve_package_uris(text, {"xarm_description": package_path})

    assert "package://" not in resolved
    assert str(package_path / "meshes/xarm7/visual/link1.stl") in resolved


def test_package_uri_resolution_ignores_commented_mesh_templates() -> None:
    package_path = Path(str(OPENARM_V10_BIMANUAL_FK_MODEL)).parents[2]
    text = Path(str(OPENARM_V10_BIMANUAL_FK_MODEL)).read_text()

    resolved = _resolve_package_uris(text, {"openarm_description": package_path})

    assert "${arm_type}" not in resolved
    assert "${name}" not in resolved
    assert "package://" not in resolved
    assert str(package_path / "meshes/arm/v10/visual/link0.dae") in resolved


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


def test_urdf_load_logs_initial_joint_transforms(monkeypatch: pytest.MonkeyPatch) -> None:
    logged: list[tuple[str, Any]] = []

    monkeypatch.setattr(urdf_robot, "rerun_init", lambda *args, **kwargs: None)
    monkeypatch.setattr(rr, "log_file_from_path", lambda *args, **kwargs: None)
    monkeypatch.setattr(rr, "log", lambda path, archetype: logged.append((path, archetype)))

    module = RerunUrdfRobotVisualizer(
        urdf_path=OPENARM_V10_BIMANUAL_FK_MODEL,
        entity_path_prefix="world/openarm_desired",
    )
    try:
        module._load_urdf()

        assert len(module._joint_lookup) == 14
        assert sum(path == "world/openarm_desired/transforms" for path, _ in logged) >= 14
    finally:
        module.stop()


def test_debug_pose_logging_uses_distinct_transform_and_marker_entities(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    logged: list[tuple[str, Any]] = []
    monkeypatch.setattr(rr, "log", lambda path, archetype: logged.append((path, archetype)))

    module = RerunUrdfRobotVisualizer.__new__(RerunUrdfRobotVisualizer)
    module.config = RerunUrdfRobotVisualizerConfig(urdf_path=XARM7_FK_MODEL)
    module.log_pose(
        PoseStamped(position=[1.0, 2.0, 3.0], orientation=[0.0, 0.0, 0.0, 1.0]),
        "world/debug/desired_controller",
        [255, 120, 180],
    )

    assert [path for path, _ in logged] == [
        "world/debug/desired_controller",
        "world/debug/desired_controller",
        "world/debug/desired_controller/marker",
    ]
    assert logged[2][1].positions.as_arrow_array().to_pylist() == [[0.0, 0.0, 0.0]]


def test_debug_pose_entity_path_can_route_by_frame_id() -> None:
    module = RerunUrdfRobotVisualizer.__new__(RerunUrdfRobotVisualizer)
    module.config = RerunUrdfRobotVisualizerConfig(
        urdf_path=XARM7_FK_MODEL,
        route_debug_poses_by_frame_id=True,
    )

    path = module._debug_entity_path(
        "world/debug/openarm/desired_target",
        PoseStamped(frame_id="teleop_openarm_left"),
    )

    assert path == "world/debug/openarm/desired_target/teleop_openarm_left"


def test_debug_pose_entity_path_sanitizes_frame_id() -> None:
    module = RerunUrdfRobotVisualizer.__new__(RerunUrdfRobotVisualizer)
    module.config = RerunUrdfRobotVisualizerConfig(
        urdf_path=XARM7_FK_MODEL,
        route_debug_poses_by_frame_id=True,
    )

    path = module._debug_entity_path(
        "world/debug/openarm/desired_target",
        PoseStamped(frame_id="../../bad path"),
    )

    assert path == "world/debug/openarm/desired_target/.._.._bad_path"


def test_package_uri_resolution_rejects_paths_outside_package(tmp_path: Path) -> None:
    package_path = tmp_path / "pkg"
    package_path.mkdir()
    outside = tmp_path / "outside.stl"
    outside.write_text("mesh")
    text = 'filename="package://pkg/../outside.stl"'

    resolved = _resolve_package_uris(text, {"pkg": package_path})

    assert resolved == text
