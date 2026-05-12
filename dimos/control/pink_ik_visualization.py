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
from dimos.control.tasks.pink_teleop_task import XArm7IKTask, XArm7IKTaskConfig
from dimos.core.core import rpc
from dimos.core.module import Module, ModuleConfig
from dimos.core.stream import In, Out
from dimos.msgs.geometry_msgs.PoseStamped import PoseStamped
from dimos.msgs.sensor_msgs.JointState import JointState
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
    position_cost: float = 1.0
    orientation_cost: float = 1.0
    lm_damping: float = 1.0
    gain: float = 1.0
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
                end_effector_frame=self.config.end_effector_frame,
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


__all__ = ["XArm7PinkIkDesiredState", "XArm7PinkIkDesiredStateConfig"]
