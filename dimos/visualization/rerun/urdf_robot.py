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

"""Rerun URDF robot visualization helpers and modules."""

from __future__ import annotations

from pathlib import Path
import re
import tempfile
from typing import TYPE_CHECKING, Any

import numpy as np
import pinocchio
from pydantic import Field
import rerun as rr

from dimos.core.core import rpc
from dimos.core.module import Module, ModuleConfig
from dimos.core.stream import In
from dimos.msgs.geometry_msgs.PoseStamped import PoseStamped
from dimos.msgs.sensor_msgs.JointState import JointState
from dimos.utils.logging_config import setup_logger
from dimos.visualization.rerun.constants import RERUN_GRPC_PORT
from dimos.visualization.rerun.init import rerun_init

if TYPE_CHECKING:
    from collections.abc import Iterable

    from numpy.typing import NDArray
    from rerun.urdf import UrdfJoint, UrdfTree

logger = setup_logger()


class RerunUrdfRobotVisualizerConfig(ModuleConfig):
    """Configuration for ``RerunUrdfRobotVisualizer``."""

    urdf_path: str | Path
    entity_path_prefix: str = "world/robot"
    frame_prefix: str = ""
    joint_name_prefixes: list[str] = Field(default_factory=lambda: ["arm/"])
    desired_controller_entity_path: str = "world/debug/desired_controller"
    desired_target_entity_path: str = "world/debug/desired_target"
    end_effector_entity_path: str = "world/debug/end_effector"
    debug_pose_axis_length: float = 0.15
    end_effector_frame: str = ""
    connect_url: str | None = None
    memory_limit: str = "25%"
    package_paths: dict[str, str | Path] = Field(default_factory=dict)


def normalize_joint_name(joint_name: str, prefixes: Iterable[str]) -> str:
    """Map DimOS joint names such as ``arm/joint1`` to URDF names."""
    for prefix in prefixes:
        if joint_name.startswith(prefix):
            return joint_name[len(prefix) :]
    return joint_name.rsplit("/", maxsplit=1)[-1]


class RerunUrdfRobotVisualizer(Module):
    """Load a URDF in Rerun and update its joint transforms from ``JointState``."""

    config: RerunUrdfRobotVisualizerConfig

    joint_state: In[JointState]
    desired_controller_pose: In[PoseStamped]
    desired_target_pose: In[PoseStamped]
    end_effector_pose: In[PoseStamped]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._urdf_tree: UrdfTree | None = None
        self._joint_lookup: dict[str, UrdfJoint] = {}
        self._last_positions: dict[str, float] = {}
        self._warned_unmatched: set[str] = set()
        self._pin_model: pinocchio.Model | None = None
        self._pin_data: pinocchio.Data | None = None
        self._q: NDArray[np.float64] | None = None
        self._pin_joint_indices: dict[str, int] = {}
        self._resolved_urdf_dir: tempfile.TemporaryDirectory[str] | None = None

    @rpc
    def start(self) -> None:
        self._load_urdf()
        super().start()

    @rpc
    def stop(self) -> None:
        super().stop()
        if self._resolved_urdf_dir is not None:
            self._resolved_urdf_dir.cleanup()
            self._resolved_urdf_dir = None

    async def handle_joint_state(self, msg: JointState) -> None:
        self.update_joint_state(msg)

    async def handle_desired_controller_pose(self, msg: PoseStamped) -> None:
        self.log_pose(msg, self.config.desired_controller_entity_path, [255, 120, 180])

    async def handle_desired_target_pose(self, msg: PoseStamped) -> None:
        self.log_pose(msg, self.config.desired_target_entity_path, [80, 180, 255])

    async def handle_end_effector_pose(self, msg: PoseStamped) -> None:
        self.log_pose(msg, self.config.end_effector_entity_path, [80, 255, 120])

    def _load_urdf(self) -> None:
        path = Path(str(self.config.urdf_path)).expanduser()
        if not path.is_file():
            raise FileNotFoundError(f"Rerun URDF robot visualizer path does not exist: {path}")

        connect_url = self.config.connect_url
        if connect_url is None:
            connect_url = f"rerun+http://{self.config.g.listen_host}:{RERUN_GRPC_PORT}/proxy"
        rerun_init(
            start_grpc=True,
            grpc_config={"connect_url": connect_url, "server_memory_limit": self.config.memory_limit},
        )
        rerun_path = self._write_rerun_loadable_urdf(path)
        rr.log_file_from_path(rerun_path, entity_path_prefix=self.config.entity_path_prefix, static=True)

        import rerun.urdf as rr_urdf

        self._urdf_tree = rr_urdf.UrdfTree.from_file_path(
            rerun_path, entity_path_prefix=self.config.entity_path_prefix
        )
        self._joint_lookup = {
            joint.name: joint
            for joint in self._urdf_tree.joints()
            if joint.joint_type in ("revolute", "continuous")
        }

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

    def _write_rerun_loadable_urdf(self, path: Path) -> Path:
        """Return a URDF path whose ``package://`` mesh URIs are absolute paths."""
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
        self._resolved_urdf_dir = tempfile.TemporaryDirectory(prefix="dimos-rerun-urdf-")
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

    def update_joint_state(self, msg: JointState) -> None:
        """Log joint transforms for the named positions present in ``msg``."""
        for raw_name, position in zip(msg.name, msg.position, strict=False):
            joint_name = normalize_joint_name(raw_name, self.config.joint_name_prefixes)
            joint = self._joint_lookup.get(joint_name)
            if joint is None:
                if joint_name not in self._warned_unmatched:
                    logger.warning(f"Rerun URDF visualizer ignoring unmatched joint {raw_name!r}")
                    self._warned_unmatched.add(joint_name)
                continue

            value = float(position)
            self._last_positions[joint_name] = value
            rr.log(self._transform_entity_path, joint.compute_transform(value))
            self._set_pin_joint(joint_name, value)

        self._log_computed_end_effector_pose()

    def log_pose(self, pose: PoseStamped, entity_path: str, color: list[int]) -> None:
        """Log a debug pose as a transform plus a colored point marker."""
        translation = [float(pose.position.x), float(pose.position.y), float(pose.position.z)]
        quaternion = [
            float(pose.orientation.x),
            float(pose.orientation.y),
            float(pose.orientation.z),
            float(pose.orientation.w),
        ]
        rr.log(
            entity_path,
            rr.Transform3D(translation=translation, quaternion=rr.Quaternion(xyzw=quaternion)),
        )
        rr.log(entity_path, rr.TransformAxes3D(self.config.debug_pose_axis_length))
        rr.log(
            f"{entity_path}/marker",
            rr.Points3D([[0.0, 0.0, 0.0]], radii=[0.025], colors=[color], labels=[entity_path.rsplit('/', 1)[-1]]),
        )

    @property
    def _transform_entity_path(self) -> str:
        return f"{self.config.entity_path_prefix}/transforms"

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
        pose = PoseStamped(
            position=placement.translation.tolist(),
            orientation=[float(quat[0]), float(quat[1]), float(quat[2]), float(quat[3])],
            frame_id=self.config.end_effector_frame,
        )
        self.log_pose(pose, self.config.end_effector_entity_path, [80, 255, 120])


__all__ = [
    "RerunUrdfRobotVisualizer",
    "RerunUrdfRobotVisualizerConfig",
    "normalize_joint_name",
]


def _resolve_package_uris(text: str, package_paths: dict[str, Path]) -> str:
    pattern = re.compile(r"package://([^/]+)/([^\"'<>\s)]+)")

    def replace(match: re.Match[str]) -> str:
        package_name = match.group(1)
        relative_path = match.group(2)
        package_path = package_paths.get(package_name)
        if package_path is None:
            return match.group(0)
        resolved_path = package_path / relative_path
        if not resolved_path.exists():
            logger.warning(f"Rerun URDF package URI target not found: {resolved_path}")
            return match.group(0)
        return str(resolved_path)

    return pattern.sub(replace, text)
