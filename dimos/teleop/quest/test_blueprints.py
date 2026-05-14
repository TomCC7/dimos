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

from collections.abc import Iterator
from contextlib import contextmanager
import importlib
import sys
from types import ModuleType

from dimos.control.coordinator import ControlCoordinator
from dimos.core.global_config import global_config
from dimos.manipulation.manipulation_module import ManipulationModule
from dimos.msgs.geometry_msgs.PoseStamped import PoseStamped
from dimos.msgs.sensor_msgs.Image import Image
from dimos.msgs.sensor_msgs.JointState import JointState
from dimos.teleop.quest.quest_types import Buttons

_BLUEPRINT_MODULES = (
    "dimos.teleop.quest.blueprints",
    "dimos.control.blueprints.teleop",
)


@contextmanager
def _teleop_blueprints(
    *,
    simulation: bool,
    xarm7_ip: str | None,
    can_port: str | None = "can0",
) -> Iterator[tuple[ModuleType, ModuleType]]:
    original_simulation = global_config.simulation
    original_simulation_backend = global_config.simulation_backend
    original_xarm7_ip = global_config.xarm7_ip
    original_can_port = global_config.can_port
    original_modules = {name: sys.modules.get(name) for name in _BLUEPRINT_MODULES}

    try:
        global_config.update(
            simulation=simulation,
            simulation_backend="mujoco",
            xarm7_ip=xarm7_ip,
            can_port=can_port,
        )
        for name in _BLUEPRINT_MODULES:
            sys.modules.pop(name, None)
        control_blueprints = importlib.import_module("dimos.control.blueprints.teleop")
        quest_blueprints = importlib.import_module("dimos.teleop.quest.blueprints")
        yield control_blueprints, quest_blueprints
    finally:
        global_config.update(
            simulation=original_simulation,
            simulation_backend=original_simulation_backend,
            xarm7_ip=original_xarm7_ip,
            can_port=original_can_port,
        )
        for name in _BLUEPRINT_MODULES:
            sys.modules.pop(name, None)
            if original_modules[name] is not None:
                sys.modules[name] = original_modules[name]


def _module_names(blueprint: object) -> set[str]:
    return {atom.module.__name__ for atom in blueprint.blueprints}


def _xarm7_adapter_type(control_blueprints: ModuleType) -> str:
    atom = next(
        atom
        for atom in control_blueprints.coordinator_teleop_xarm7.blueprints
        if atom.module is ControlCoordinator
    )
    return atom.kwargs["hardware"][0].adapter_type


def _piper_adapter_type(control_blueprints: ModuleType) -> str:
    atom = next(
        atom
        for atom in control_blueprints.coordinator_teleop_piper.blueprints
        if atom.module is ControlCoordinator
    )
    return atom.kwargs["hardware"][0].adapter_type


def _piper_task_configs(control_blueprints: ModuleType) -> list[object]:
    atom = next(
        atom
        for atom in control_blueprints.coordinator_teleop_piper.blueprints
        if atom.module is ControlCoordinator
    )
    return list(atom.kwargs["tasks"])


def _piper_manipulation_robot_configs(quest_blueprints: ModuleType) -> list[object]:
    atom = next(
        atom
        for atom in quest_blueprints.teleop_quest_piper.blueprints
        if atom.module is ManipulationModule
    )
    return list(atom.kwargs["robots"])


def test_no_ip_xarm7_teleop_uses_mock_and_manipulation_preview() -> None:
    with _teleop_blueprints(simulation=False, xarm7_ip=None) as (
        control_blueprints,
        quest_blueprints,
    ):
        assert control_blueprints.is_xarm7_mock_preview is True
        assert _xarm7_adapter_type(control_blueprints) == "mock"
        assert "ManipulationModule" in _module_names(quest_blueprints.teleop_quest_xarm7)
        assert (
            quest_blueprints.teleop_quest_xarm7.transport_map[
                ("joint_state", JointState)
            ].topic.topic
            == "/coordinator/joint_state"
        )


def test_no_can_piper_teleop_uses_mock_and_manipulation_preview() -> None:
    with _teleop_blueprints(simulation=False, xarm7_ip="192.168.1.10", can_port=None) as (
        control_blueprints,
        quest_blueprints,
    ):
        assert control_blueprints.is_piper_mock_preview is True
        assert _piper_adapter_type(control_blueprints) == "mock"
        assert "ManipulationModule" in _module_names(quest_blueprints.teleop_quest_piper)
        assert [(task.type, task.name) for task in _piper_task_configs(control_blueprints)] == [
            ("single_arm_pink_ik", "teleop_piper"),
            ("trajectory", "traj_arm"),
        ]
        piper_task = next(
            task for task in _piper_task_configs(control_blueprints) if task.name == "teleop_piper"
        )
        assert piper_task.gripper_open_pos == 0.08
        assert piper_task.gripper_closed_pos == 0.0
        assert (
            _piper_manipulation_robot_configs(quest_blueprints)[0].coordinator_task_name
            == "traj_arm"
        )
        assert (
            quest_blueprints.teleop_quest_piper.transport_map[
                ("joint_state", JointState)
            ].topic.topic
            == "/coordinator/joint_state"
        )


def test_piper_data_collection_blueprint_routes_recorded_streams() -> None:
    with _teleop_blueprints(simulation=False, xarm7_ip="192.168.1.10", can_port=None) as (
        _control_blueprints,
        quest_blueprints,
    ):
        names = _module_names(quest_blueprints.teleop_quest_piper_data_collection)
        assert "ArmTeleopModule" in names
        assert "ControlCoordinator" in names
        assert "CameraModule" in names
        assert "PiperDataRecorder" in names
        assert (
            quest_blueprints.teleop_quest_piper_data_collection.transport_map[
                ("joint_state", JointState)
            ].topic.topic
            == "/coordinator/joint_state"
        )
        assert (
            quest_blueprints.teleop_quest_piper_data_collection.transport_map[
                ("desired_joint_action", JointState)
            ].topic.topic
            == "/coordinator/desired_joint_action"
        )
        assert (
            quest_blueprints.teleop_quest_piper_data_collection.transport_map[
                ("right_controller_output", PoseStamped)
            ].topic.topic
            == "/coordinator/cartesian_command"
        )
        assert (
            quest_blueprints.teleop_quest_piper_data_collection.transport_map[
                ("buttons", Buttons)
            ].topic.topic
            == "/teleop/buttons"
        )
        assert (
            quest_blueprints.teleop_quest_piper_data_collection.transport_map[
                ("color_image", Image)
            ].topic.topic
            == "/piper_data_collection/color_image"
        )


def test_piper_data_collection_blueprint_includes_rerun_vis_sink() -> None:
    """Data collection blueprint exposes the recorded streams to a Rerun vis sink.

    Verifies the blueprint contains a RerunBridgeModule atom in addition to the
    existing recording stack, and that the topics for the pre-existing
    transport_map entries are unchanged (visualization is a passive sink).
    """
    with _teleop_blueprints(simulation=False, xarm7_ip="192.168.1.10", can_port=None) as (
        _control_blueprints,
        quest_blueprints,
    ):
        bp = quest_blueprints.teleop_quest_piper_data_collection
        names = _module_names(bp)
        assert "RerunBridgeModule" in names, names
        # The recording stack must still be there alongside the new vis sink.
        for required in ("CameraModule", "PiperDataRecorder", "ControlCoordinator"):
            assert required in names, (required, names)

        # Topics for the pre-existing transport_map entries are unchanged.
        expected_topics = {
            ("joint_state", JointState): "/coordinator/joint_state",
            ("desired_joint_action", JointState): "/coordinator/desired_joint_action",
            ("right_controller_output", PoseStamped): "/coordinator/cartesian_command",
            ("buttons", Buttons): "/teleop/buttons",
            ("color_image", Image): "/piper_data_collection/color_image",
        }
        for key, topic in expected_topics.items():
            assert bp.transport_map[key].topic.topic == topic, key


def test_real_can_piper_teleop_uses_hardware_with_manipulation_preview() -> None:
    with _teleop_blueprints(simulation=False, xarm7_ip="192.168.1.10", can_port="can0") as (
        control_blueprints,
        quest_blueprints,
    ):
        assert control_blueprints.is_piper_mock_preview is False
        assert _piper_adapter_type(control_blueprints) == "piper"
        assert "ManipulationModule" in _module_names(quest_blueprints.teleop_quest_piper)


def test_simulation_piper_teleop_uses_mujoco_with_manipulation_preview() -> None:
    with _teleop_blueprints(simulation=True, xarm7_ip="192.168.1.10", can_port=None) as (
        control_blueprints,
        quest_blueprints,
    ):
        assert control_blueprints.is_piper_mock_preview is False
        assert _piper_adapter_type(control_blueprints) == "sim_mujoco"
        assert "MujocoSimModule" in _module_names(control_blueprints.coordinator_teleop_piper)
        assert "ManipulationModule" in _module_names(quest_blueprints.teleop_quest_piper)


def test_real_ip_xarm7_teleop_uses_hardware_without_manipulation_preview() -> None:
    with _teleop_blueprints(simulation=False, xarm7_ip="192.168.1.10") as (
        control_blueprints,
        quest_blueprints,
    ):
        assert control_blueprints.is_xarm7_mock_preview is False
        assert _xarm7_adapter_type(control_blueprints) == "xarm"
        assert "ManipulationModule" not in _module_names(quest_blueprints.teleop_quest_xarm7)


def test_simulation_xarm7_teleop_uses_mujoco_without_manipulation_preview() -> None:
    with _teleop_blueprints(simulation=True, xarm7_ip=None) as (
        control_blueprints,
        quest_blueprints,
    ):
        assert control_blueprints.is_xarm7_mock_preview is False
        assert _xarm7_adapter_type(control_blueprints) == "sim_mujoco"
        assert "MujocoSimModule" in _module_names(control_blueprints.coordinator_teleop_xarm7)
        assert "ManipulationModule" not in _module_names(quest_blueprints.teleop_quest_xarm7)
