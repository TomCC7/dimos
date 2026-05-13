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

"""Pure desired-output Pink IK modules for visualization."""

from __future__ import annotations

from pathlib import Path
import time
from typing import Any, Literal

from pydantic import Field

from dimos.control.task import CoordinatorState, JointStateSnapshot
from dimos.control.tasks.pink_teleop_task import (
    OpenArmBimanualIKTask,
    OpenArmBimanualIKTaskConfig,
    XArm7IKTask,
    XArm7IKTaskConfig,
)
from dimos.core.core import rpc
from dimos.core.module import Module, ModuleConfig
from dimos.core.stream import In, Out
from dimos.msgs.geometry_msgs.PoseStamped import PoseStamped
from dimos.msgs.sensor_msgs.JointState import JointState
from dimos.robot.catalog.openarm import OPENARM_V10_BIMANUAL_FK_MODEL
from dimos.robot.catalog.ufactory import XARM7_FK_MODEL
from dimos.teleop.quest.quest_types import Buttons


class XArm7PinkIkDesiredStateConfig(ModuleConfig):
    """Configuration for the XArm7 Pink desired-joint visualization path."""

    task_name: str = "teleop_xarm"
    joint_names: list[str] = Field(default_factory=lambda: [f"arm/joint{i}" for i in range(1, 8)])
    model_path: str | Path = XARM7_FK_MODEL
    hand: Literal["left", "right"] = "right"
    end_effector_frame: str = "link7"
    solver: str | None = None
    damping: float = 1e-12
    num_solver_iterations: int = 1
    amplify_factor: float = 1.0
    position_cost: float = 1.0
    orientation_cost: float = 1.0
    lm_damping: float = 1.0
    gain: float = 1.0
    posture_cost: float = 0.0
    posture_default_weight: float = 1.0
    posture_joint_weights: dict[str, float] = Field(default_factory=dict)
    posture_reference: dict[str, float] = Field(default_factory=dict)
    posture_lm_damping: float = 0.0
    posture_gain: float = 1.0
    max_joint_delta_deg: float = 5.0
    timeout: float = 0.5


class XArm7PinkIkDesiredState(Module):
    """Publish Pink IK desired joint positions directly as ``JointState``."""

    config: XArm7PinkIkDesiredStateConfig

    cartesian_command: In[PoseStamped]
    buttons: In[Buttons]

    desired_joint_state: Out[JointState]
    desired_controller_pose: Out[PoseStamped]
    desired_target_pose: Out[PoseStamped]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._task = XArm7IKTask(
            self.config.task_name,
            XArm7IKTaskConfig(
                joint_names=self.config.joint_names,
                model_path=self.config.model_path,
                timeout=self.config.timeout,
                max_joint_delta_deg=self.config.max_joint_delta_deg,
                hand=self.config.hand,
                solver=self.config.solver,
                damping=self.config.damping,
                num_solver_iterations=self.config.num_solver_iterations,
                amplify_factor=self.config.amplify_factor,
                end_effector_frame=self.config.end_effector_frame,
                position_cost=self.config.position_cost,
                orientation_cost=self.config.orientation_cost,
                lm_damping=self.config.lm_damping,
                gain=self.config.gain,
                posture_cost=self.config.posture_cost,
                posture_default_weight=self.config.posture_default_weight,
                posture_joint_weights=self.config.posture_joint_weights,
                posture_reference=self.config.posture_reference,
                posture_lm_damping=self.config.posture_lm_damping,
                posture_gain=self.config.posture_gain,
            ),
        )
        self._positions = {name: 0.0 for name in self.config.joint_names}
        self._last_t = time.perf_counter()

    @rpc
    def start(self) -> None:
        self._task.start()
        super().start()

    @rpc
    def stop(self) -> None:
        self._task.stop()
        super().stop()

    async def handle_cartesian_command(self, msg: PoseStamped) -> None:
        if msg.frame_id and msg.frame_id != self.config.task_name:
            return

        t_now = time.perf_counter()
        dt = max(t_now - self._last_t, 1e-9)
        self._last_t = t_now

        self._task.on_cartesian_command(msg, t_now=t_now)
        self.desired_controller_pose.publish(msg)
        self.desired_target_pose.publish(msg)

        output = self._task.compute(
            CoordinatorState(
                joints=JointStateSnapshot(
                    joint_positions=dict(self._positions),
                    timestamp=time.time(),
                ),
                t_now=t_now,
                dt=dt,
            )
        )
        if output is None or output.positions is None:
            return

        for name, position in zip(output.joint_names, output.positions, strict=False):
            if name in self._positions:
                self._positions[name] = float(position)

        names = list(self._positions.keys())
        self.desired_joint_state.publish(
            JointState(
                frame_id=self.config.task_name,
                name=names,
                position=[self._positions[name] for name in names],
            )
        )

    async def handle_buttons(self, msg: Buttons) -> None:
        self._task.on_buttons(msg)


class OpenArmBimanualPinkIkDesiredStateConfig(ModuleConfig):
    """Configuration for the unified OpenArm bimanual Pink visualization path."""

    task_name: str = "teleop_openarm"
    left_task_name: str = "teleop_openarm_left"
    right_task_name: str = "teleop_openarm_right"
    joint_names: list[str] = Field(
        default_factory=lambda: [
            *[f"openarm_left_joint{i}" for i in range(1, 8)],
            *[f"openarm_right_joint{i}" for i in range(1, 8)],
        ]
    )
    model_path: str | Path = OPENARM_V10_BIMANUAL_FK_MODEL
    left_end_effector_frame: str = "openarm_left_link7"
    right_end_effector_frame: str = "openarm_right_link7"
    solver: str | None = None
    damping: float = 1e-12
    num_solver_iterations: int = 1
    amplify_factor: float = 1.0
    position_cost: float = 1.0
    orientation_cost: float = 1.0
    lm_damping: float = 1.0
    gain: float = 1.0
    max_joint_delta_deg: float = 5.0
    timeout: float = 0.5


class OpenArmBimanualPinkIkDesiredState(Module):
    """Publish unified OpenArm Pink IK desired joint positions as ``JointState``."""

    config: OpenArmBimanualPinkIkDesiredStateConfig

    cartesian_command: In[PoseStamped]

    desired_joint_state: Out[JointState]
    desired_controller_pose: Out[PoseStamped]
    desired_target_pose: Out[PoseStamped]
    end_effector_pose: Out[PoseStamped]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._task = OpenArmBimanualIKTask(
            self.config.task_name,
            OpenArmBimanualIKTaskConfig(
                joint_names=self.config.joint_names,
                model_path=self.config.model_path,
                timeout=self.config.timeout,
                max_joint_delta_deg=self.config.max_joint_delta_deg,
                solver=self.config.solver,
                damping=self.config.damping,
                num_solver_iterations=self.config.num_solver_iterations,
                amplify_factor=self.config.amplify_factor,
                left_task_name=self.config.left_task_name,
                right_task_name=self.config.right_task_name,
                left_end_effector_frame=self.config.left_end_effector_frame,
                right_end_effector_frame=self.config.right_end_effector_frame,
                position_cost=self.config.position_cost,
                orientation_cost=self.config.orientation_cost,
                lm_damping=self.config.lm_damping,
                gain=self.config.gain,
            ),
        )
        self._positions = {name: 0.0 for name in self.config.joint_names}
        self._last_t = time.perf_counter()

    @rpc
    def start(self) -> None:
        self._task.start()
        super().start()

    @rpc
    def stop(self) -> None:
        self._task.stop()
        super().stop()

    async def handle_cartesian_command(self, msg: PoseStamped) -> None:
        t_now = time.perf_counter()
        dt = max(t_now - self._last_t, 1e-9)
        self._last_t = t_now

        if not self._task.on_cartesian_command(msg, t_now=t_now):
            return

        self.desired_controller_pose.publish(msg)
        self.desired_target_pose.publish(msg)

        output = self._task.compute(
            CoordinatorState(
                joints=JointStateSnapshot(
                    joint_positions=dict(self._positions),
                    timestamp=time.time(),
                ),
                t_now=t_now,
                dt=dt,
            )
        )
        if output is None or output.positions is None:
            return

        for name, position in zip(output.joint_names, output.positions, strict=False):
            if name in self._positions:
                self._positions[name] = float(position)

        names = list(self._positions.keys())
        self.desired_joint_state.publish(
            JointState(
                frame_id=self.config.task_name,
                name=names,
                position=[self._positions[name] for name in names],
            )
        )
        solved_pose = self._task.end_effector_pose(msg.frame_id)
        if solved_pose is not None:
            self.end_effector_pose.publish(solved_pose)


__all__ = [
    "OpenArmBimanualPinkIkDesiredState",
    "OpenArmBimanualPinkIkDesiredStateConfig",
    "XArm7PinkIkDesiredState",
    "XArm7PinkIkDesiredStateConfig",
]
