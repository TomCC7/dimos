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

"""Viser URDF visualization-only simulation module."""

from __future__ import annotations

from pathlib import Path
import re
import tempfile
from typing import Any

import numpy as np
import pinocchio
from pydantic import Field

from dimos.core.core import rpc
from dimos.core.module import Module, ModuleConfig
from dimos.core.stream import In
from dimos.msgs.geometry_msgs.PoseStamped import PoseStamped
from dimos.msgs.sensor_msgs.JointState import JointState
from dimos.utils.logging_config import setup_logger

logger = setup_logger()

_ENTITY_PATH_SAFE_CHARS = re.compile(r"[^A-Za-z0-9_.-]+")


class ViserUrdfSimModuleConfig(ModuleConfig):
    """Configuration for ``ViserUrdfSimModule``."""

    urdf_path: str | Path
    server_host: str | None = None
    server_port: int | None = None
    server_label: str | None = None
    server_verbose: bool | None = None
    root_node_name: str = "/robot"
    desired_controller_frame: str = "/debug/desired_controller"
    desired_target_frame: str = "/debug/desired_target"
    end_effector_frame_path: str = "/debug/desired_end_effector"
    debug_pose_axis_length: float = 0.15
    route_debug_poses_by_frame_id: bool = False
    end_effector_frame: str = ""
    load_meshes: bool = True
    load_collision_meshes: bool = False
    package_paths: dict[str, str | Path] = Field(default_factory=dict)


def normalize_joint_name(joint_name: str) -> str:
    """Map DimOS joint names such as ``arm/joint1`` to URDF names."""
    return joint_name.rsplit("/", maxsplit=1)[-1]


class ViserUrdfSimModule(Module):
    """Display desired robot state in Viser without physics or hardware feedback."""

    config: ViserUrdfSimModuleConfig

    desired_joint_state: In[JointState]
    desired_controller_pose: In[PoseStamped]
    desired_target_pose: In[PoseStamped]
    end_effector_pose: In[PoseStamped]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._server: Any | None = None
        self._viser_urdf: Any | None = None
        self._joint_order: list[str] = []
        self._positions: dict[str, float] = {}
        self._warned_unmatched: set[str] = set()
        self._pin_model: pinocchio.Model | None = None
        self._pin_data: pinocchio.Data | None = None
        self._q: np.ndarray[Any, np.dtype[np.float64]] | None = None
        self._pin_joint_indices: dict[str, int] = {}
        self._resolved_urdf_dir: tempfile.TemporaryDirectory[str] | None = None

    @rpc
    def start(self) -> None:
        self._load_urdf()
        super().start()

    @rpc
    def stop(self) -> None:
        super().stop()
        if self._server is not None and hasattr(self._server, "stop"):
            self._server.stop()
        self._server = None
        self._viser_urdf = None
        if self._resolved_urdf_dir is not None:
            self._resolved_urdf_dir.cleanup()
            self._resolved_urdf_dir = None

    async def handle_desired_joint_state(self, msg: JointState) -> None:
        self.update_desired_joint_state(msg)

    async def handle_desired_controller_pose(self, msg: PoseStamped) -> None:
        self.log_pose(msg, self._debug_frame_path(self.config.desired_controller_frame, msg))

    async def handle_desired_target_pose(self, msg: PoseStamped) -> None:
        self.log_pose(msg, self._debug_frame_path(self.config.desired_target_frame, msg))

    async def handle_end_effector_pose(self, msg: PoseStamped) -> None:
        self.log_pose(msg, self._debug_frame_path(self.config.end_effector_frame_path, msg))

    def _load_urdf(self) -> None:
        path = Path(str(self.config.urdf_path)).expanduser()
        if not path.is_file():
            raise FileNotFoundError(f"Viser URDF simulator path does not exist: {path}")

        server_host = self.config.server_host or self.config.g.listen_host
        server_port = self.config.server_port or self.config.g.viser_port
        server_label = self.config.server_label or self.config.g.viser_label
        server_verbose = (
            self.config.server_verbose
            if self.config.server_verbose is not None
            else self.config.g.viser_verbose
        )
        self._server = _create_viser_server(
            server_host,
            server_port,
            server_label,
            server_verbose,
        )
        logger.info(
            "Viser URDF simulator started",
            host=server_host,
            port=server_port,
            label=server_label,
        )
        if hasattr(self._server.scene, "set_up_direction"):
            self._server.scene.set_up_direction("+z")

        viser_path = self._write_viser_loadable_urdf(path)
        self._viser_urdf = _create_viser_urdf(
            self._server,
            viser_path,
            self.config.root_node_name,
            self.config.load_meshes,
            self.config.load_collision_meshes,
        )
        limits = self._viser_urdf.get_actuated_joint_limits()
        self._joint_order = list(limits.keys())
        self._positions = {joint_name: 0.0 for joint_name in self._joint_order}
        self._update_viser_cfg()

        if self.config.end_effector_frame:
            self._pin_model = pinocchio.buildModelFromUrdf(str(path))
            self._pin_data = self._pin_model.createData()
            self._q = pinocchio.neutral(self._pin_model)
            self._pin_joint_indices = {
                str(self._pin_model.names[i]): self._pin_model.idx_qs[i]
                for i in range(1, self._pin_model.njoints)
            }
            if not self._pin_model.existFrame(self.config.end_effector_frame):
                raise ValueError(
                    f"End-effector frame {self.config.end_effector_frame!r} not found in {path}"
                )

    def _write_viser_loadable_urdf(self, path: Path) -> Path:
        package_paths = self._default_package_paths(path) | {
            name: Path(str(package_path)).resolve()
            for name, package_path in self.config.package_paths.items()
        }
        text = path.read_text()
        resolved = _resolve_package_uris(text, package_paths)
        if resolved == text:
            return path

        if self._resolved_urdf_dir is not None:
            self._resolved_urdf_dir.cleanup()
        self._resolved_urdf_dir = tempfile.TemporaryDirectory(prefix="dimos-viser-urdf-")
        resolved_path = Path(self._resolved_urdf_dir.name) / path.name
        resolved_path.write_text(resolved)
        return resolved_path

    def _default_package_paths(self, path: Path) -> dict[str, Path]:
        package_xml = next(path.parent.glob("package.xml"), None)
        search_dir = path.parent
        while package_xml is None and search_dir != search_dir.parent:
            search_dir = search_dir.parent
            package_xml = next(search_dir.glob("package.xml"), None)
        if package_xml is None:
            return {}
        name_match = re.search(r"<name>([^<]+)</name>", package_xml.read_text())
        if name_match is None:
            return {}
        return {name_match.group(1): package_xml.parent.resolve()}

    def update_desired_joint_state(self, msg: JointState) -> None:
        for raw_name, position in zip(msg.name, msg.position, strict=False):
            joint_name = normalize_joint_name(raw_name)
            if joint_name not in self._positions:
                if joint_name not in self._warned_unmatched:
                    logger.warning(f"Viser URDF simulator ignoring unmatched joint {raw_name!r}")
                    self._warned_unmatched.add(joint_name)
                continue

            value = float(position)
            self._positions[joint_name] = value
            self._set_pin_joint(joint_name, value)

        self._update_viser_cfg()
        self._log_computed_end_effector_pose()

    def _update_viser_cfg(self) -> None:
        if self._viser_urdf is None:
            return
        self._viser_urdf.update_cfg(
            np.asarray([self._positions[joint_name] for joint_name in self._joint_order])
        )

    def log_pose(self, pose: PoseStamped, frame_path: str) -> None:
        if self._server is None:
            return
        self._server.scene.add_frame(
            frame_path,
            position=(
                float(pose.position.x),
                float(pose.position.y),
                float(pose.position.z),
            ),
            wxyz=(
                float(pose.orientation.w),
                float(pose.orientation.x),
                float(pose.orientation.y),
                float(pose.orientation.z),
            ),
            axes_length=self.config.debug_pose_axis_length,
        )

    def _debug_frame_path(self, base_path: str, pose: PoseStamped) -> str:
        if not self.config.route_debug_poses_by_frame_id or not pose.frame_id:
            return base_path
        safe_frame_id = _ENTITY_PATH_SAFE_CHARS.sub("_", pose.frame_id).strip("_")
        if not safe_frame_id:
            return base_path
        return f"{base_path}/{safe_frame_id}"

    def _set_pin_joint(self, joint_name: str, position: float) -> None:
        if self._q is None:
            return
        idx = self._pin_joint_indices.get(joint_name)
        if idx is None:
            return
        self._q[idx] = position

    def _log_computed_end_effector_pose(self) -> None:
        if (
            not self.config.end_effector_frame
            or self._pin_model is None
            or self._pin_data is None
            or self._q is None
        ):
            return

        pinocchio.framesForwardKinematics(self._pin_model, self._pin_data, self._q)
        frame_id = self._pin_model.getFrameId(self.config.end_effector_frame)
        placement = self._pin_data.oMf[frame_id]
        quat = pinocchio.Quaternion(placement.rotation).coeffs()
        self.log_pose(
            PoseStamped(
                position=placement.translation.tolist(),
                orientation=[float(quat[0]), float(quat[1]), float(quat[2]), float(quat[3])],
                frame_id=self.config.end_effector_frame,
            ),
            self.config.end_effector_frame_path,
        )


def _create_viser_server(host: str, port: int, label: str, verbose: bool) -> Any:
    import viser

    return viser.ViserServer(host=host, port=port, label=label, verbose=verbose)


def _create_viser_urdf(
    server: Any,
    urdf_path: Path,
    root_node_name: str,
    load_meshes: bool,
    load_collision_meshes: bool,
) -> Any:
    from viser.extras import ViserUrdf

    return ViserUrdf(
        server,
        urdf_or_path=urdf_path,
        root_node_name=root_node_name,
        load_meshes=load_meshes,
        load_collision_meshes=load_collision_meshes,
    )


def _resolve_package_uris(text: str, package_paths: dict[str, Path]) -> str:
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    pattern = re.compile(r"package://([^/]+)/([^\"'<>\s)]+)")

    def replace(match: re.Match[str]) -> str:
        package_name = match.group(1)
        relative_path = match.group(2)
        package_path = package_paths.get(package_name)
        if package_path is None:
            return match.group(0)
        resolved_package_path = package_path.resolve()
        resolved_path = (package_path / relative_path).resolve()
        if not resolved_path.is_relative_to(resolved_package_path):
            logger.warning(f"Viser URDF package URI escapes package root: {match.group(0)}")
            return match.group(0)
        if not resolved_path.exists():
            logger.warning(f"Viser URDF package URI target not found: {match.group(0)}")
            return match.group(0)
        return str(resolved_path)

    return pattern.sub(replace, text)


__all__ = [
    "ViserUrdfSimModule",
    "ViserUrdfSimModuleConfig",
    "normalize_joint_name",
]
