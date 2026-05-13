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

from pathlib import Path
from typing import Any

import pytest

from dimos.core.global_config import global_config
from dimos.msgs.geometry_msgs.PoseStamped import PoseStamped
from dimos.msgs.sensor_msgs.JointState import JointState
from dimos.robot.catalog.ufactory import XARM7_FK_MODEL
from dimos.simulation.engines import viser_urdf_sim_module
from dimos.simulation.engines.viser_urdf_sim_module import (
    ViserUrdfSimModule,
    normalize_joint_name,
)


class _FakeScene:
    def __init__(self) -> None:
        self.frames: list[tuple[str, dict[str, Any]]] = []
        self.up_direction: str | None = None

    def set_up_direction(self, direction: str) -> None:
        self.up_direction = direction

    def add_frame(self, name: str, **kwargs: Any) -> None:
        self.frames.append((name, kwargs))


class _FakeServer:
    def __init__(self, host: str, port: int, label: str, verbose: bool = False) -> None:
        self.host = host
        self.port = port
        self.label = label
        self.verbose = verbose
        self.scene = _FakeScene()
        self.stopped = False

    def stop(self) -> None:
        self.stopped = True


class _FakeViserUrdf:
    def __init__(self) -> None:
        self.configs: list[list[float]] = []

    def get_actuated_joint_limits(self) -> dict[str, tuple[float, float]]:
        return {"joint1": (-1.0, 1.0), "joint2": (-1.0, 1.0)}

    def update_cfg(self, cfg: list[float]) -> None:
        self.configs.append(list(cfg))


def _avoid_numpy_thread_start(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(viser_urdf_sim_module.np, "asarray", lambda values: list(values))


def test_normalize_joint_name_supports_dimos_prefixes() -> None:
    assert normalize_joint_name("arm/joint1") == "joint1"
    assert normalize_joint_name("left_arm/joint1") == "joint1"
    assert normalize_joint_name("openarm_left_joint1") == "openarm_left_joint1"


def test_viser_urdf_sim_uses_listen_host_and_loads_urdf(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    servers: list[_FakeServer] = []
    fake_urdf = _FakeViserUrdf()
    _avoid_numpy_thread_start(monkeypatch)
    original_host = global_config.listen_host
    original_port = global_config.viser_port
    original_label = global_config.viser_label
    original_verbose = global_config.viser_verbose
    global_config.update(
        listen_host="0.0.0.0",
        viser_port=8099,
        viser_label="Test Viser",
        viser_verbose=False,
    )

    def create_server(host: str, port: int, label: str, verbose: bool) -> _FakeServer:
        server = _FakeServer(host, port, label, verbose)
        servers.append(server)
        return server

    monkeypatch.setattr(viser_urdf_sim_module, "_create_viser_server", create_server)
    monkeypatch.setattr(
        viser_urdf_sim_module,
        "_create_viser_urdf",
        lambda *args, **kwargs: fake_urdf,
    )

    try:
        module = ViserUrdfSimModule(urdf_path=XARM7_FK_MODEL)
        module._load_urdf()

        assert servers[0].host == "0.0.0.0"
        assert servers[0].port == 8099
        assert servers[0].label == "Test Viser"
        assert servers[0].verbose is False
        assert servers[0].scene.up_direction == "+z"
        assert fake_urdf.configs[-1] == [0.0, 0.0]
    finally:
        if "module" in locals():
            module.stop()
        global_config.update(
            listen_host=original_host,
            viser_port=original_port,
            viser_label=original_label,
            viser_verbose=original_verbose,
        )


def test_desired_joint_state_updates_named_joints_and_preserves_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_urdf = _FakeViserUrdf()
    _avoid_numpy_thread_start(monkeypatch)
    monkeypatch.setattr(
        viser_urdf_sim_module,
        "_create_viser_server",
        lambda host, port, label, verbose: _FakeServer(host, port, label, verbose),
    )
    monkeypatch.setattr(
        viser_urdf_sim_module,
        "_create_viser_urdf",
        lambda *args, **kwargs: fake_urdf,
    )
    module = ViserUrdfSimModule(urdf_path=XARM7_FK_MODEL)
    try:
        module._load_urdf()

        module.update_desired_joint_state(
            JointState(name=["arm/joint1", "arm/joint2"], position=[0.1, 0.2])
        )
        module.update_desired_joint_state(
            JointState(name=["arm/joint1", "arm/missing"], position=[0.3, 9.0])
        )

        assert module._positions == {"joint1": 0.3, "joint2": 0.2}
        assert "missing" in module._warned_unmatched
        assert fake_urdf.configs[-1] == [0.3, 0.2]
    finally:
        module.stop()


def test_debug_pose_logs_distinct_viser_frame() -> None:
    server = _FakeServer("127.0.0.1", 8080, "test")
    module = ViserUrdfSimModule(urdf_path=XARM7_FK_MODEL)
    module._server = server

    module.log_pose(
        PoseStamped(position=[1.0, 2.0, 3.0], orientation=[0.0, 0.0, 0.0, 1.0]),
        "/debug/test",
    )

    assert server.scene.frames == [
        (
            "/debug/test",
            {
                "position": (1.0, 2.0, 3.0),
                "wxyz": (1.0, 0.0, 0.0, 0.0),
                "axes_length": 0.15,
            },
        )
    ]
    module.stop()


def test_invalid_urdf_path_fails_clearly() -> None:
    module = ViserUrdfSimModule(urdf_path=Path("/tmp/dimos-missing-robot.urdf"))

    try:
        with pytest.raises(FileNotFoundError, match="Viser URDF simulator path does not exist"):
            module._load_urdf()
    finally:
        module.stop()
