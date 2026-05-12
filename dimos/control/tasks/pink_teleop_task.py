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

"""Pink-backed teleoperation IK control tasks.

These tasks preserve the passive ControlCoordinator contract while using Pink
to solve differential IK from Quest controller pose deltas.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import threading
from typing import TYPE_CHECKING, Any, Literal, cast

import numpy as np
import pink
from pink import solve_ik
from pink.tasks import FrameTask
import pinocchio
import qpsolvers

from dimos.control.task import (
    BaseControlTask,
    ControlMode,
    CoordinatorState,
    JointCommandOutput,
    ResourceClaim,
)
from dimos.manipulation.planning.kinematics.pinocchio_ik import check_joint_delta, pose_to_se3
from dimos.robot.catalog.ufactory import XARM7_FK_MODEL
from dimos.utils.logging_config import setup_logger

if TYPE_CHECKING:
    from numpy.typing import NDArray

    from dimos.msgs.geometry_msgs.Pose import Pose
    from dimos.msgs.geometry_msgs.PoseStamped import PoseStamped
    from dimos.teleop.quest.quest_types import Buttons

logger = setup_logger()


def _load_pinocchio_model(model_path: str | Path) -> pinocchio.Model:
    path = Path(str(model_path))
    if not path.exists():
        raise FileNotFoundError(f"Model file not found: {path}")
    if path.suffix == ".xml":
        return pinocchio.buildModelFromMJCF(str(path))
    return pinocchio.buildModelFromUrdf(str(path))


def _default_solver() -> str:
    if "daqp" in qpsolvers.available_solvers:
        return "daqp"
    if not qpsolvers.available_solvers:
        raise RuntimeError("Pink IK requires at least one qpsolvers backend")
    return str(qpsolvers.available_solvers[0])


def _model_joint_names(model: pinocchio.Model) -> list[str]:
    return [str(name) for name in model.names[1:]]


def _unqualified_joint_name(joint_name: str) -> str:
    return joint_name.rsplit("/", maxsplit=1)[-1]


@dataclass
class PinkIKTaskConfig:
    """Configuration shared by Pink teleop IK tasks."""

    joint_names: list[str]
    model_path: str | Path
    priority: int = 10
    timeout: float = 0.5
    max_joint_delta_deg: float = 5.0
    hand: Literal["left", "right"] | None = "right"
    solver: str | None = None
    damping: float = 1e-12
    end_effector_frame: str = ""
    position_cost: float = 1.0
    orientation_cost: float = 1.0
    lm_damping: float = 1.0
    gain: float = 1.0
    gripper_joint: str | None = None
    gripper_open_pos: float = 0.0
    gripper_closed_pos: float = 0.0


class BasePinkIKTask(BaseControlTask):
    """Base control task for Pink-backed teleoperation IK."""

    def __init__(self, name: str, config: PinkIKTaskConfig) -> None:
        if not config.joint_names:
            raise ValueError(f"{type(self).__name__} '{name}' requires at least one joint")
        if config.hand not in ("left", "right"):
            raise ValueError(f"{type(self).__name__} '{name}' requires hand='left' or 'right'")

        self._name = name
        self._config = config
        self._joint_names = frozenset(config.joint_names)
        self._joint_names_list = list(config.joint_names)
        self._solver = config.solver or _default_solver()

        self._model = _load_pinocchio_model(config.model_path)
        self._data = self._model.createData()
        self._validate_model()

        q0 = pinocchio.neutral(self._model)
        self._configuration = pink.Configuration(self._model, self._data, q0)
        self._frame_tasks = self._create_frame_tasks()
        self._pink_tasks = [*self._frame_tasks, *self._create_extra_tasks()]

        self._lock = threading.Lock()
        self._target_pose: Pose | PoseStamped | None = None
        self._last_update_time = 0.0
        self._active = False
        self._initial_ee_pose: pinocchio.SE3 | None = None
        self._prev_primary = False
        self._gripper_target = config.gripper_open_pos
        self._logged_first_target = False
        self._logged_first_output = False

    @property
    def name(self) -> str:
        """Unique task identifier."""
        return self._name

    def claim(self) -> ResourceClaim:
        """Declare resource requirements for coordinator arbitration."""
        joints = self._joint_names
        if self._config.gripper_joint:
            joints = joints | frozenset([self._config.gripper_joint])
        return ResourceClaim(
            joints=joints, priority=self._config.priority, mode=ControlMode.SERVO_POSITION
        )

    def is_active(self) -> bool:
        """Return true when a live controller target can produce IK output."""
        with self._lock:
            return self._active and self._target_pose is not None

    def start(self) -> None:
        """Activate the task so incoming targets can be consumed."""
        with self._lock:
            self._active = True
        logger.info(f"{type(self).__name__} {self._name} started")

    def stop(self) -> None:
        """Deactivate the task and clear captured target state."""
        with self._lock:
            self._active = False
            self._target_pose = None
            self._initial_ee_pose = None
        logger.info(f"{type(self).__name__} {self._name} stopped")

    def compute(self, state: CoordinatorState) -> JointCommandOutput | None:
        """Run one Pink differential IK tick and return joint positions."""
        raw_pose = self._get_live_target(state.t_now)
        if raw_pose is None:
            return None

        q_current = self._get_current_joints(state)
        if q_current is None:
            logger.debug(
                f"{type(self).__name__} {self._name}: missing joint state for IK warm-start"
            )
            return None

        self._configuration.update(q_current)
        if not self._ensure_initial_ee_pose(q_current):
            return None

        with self._lock:
            initial_ee_pose = self._initial_ee_pose
        if initial_ee_pose is None:
            return None

        delta_se3 = pose_to_se3(raw_pose)
        target_pose = pinocchio.SE3(
            delta_se3.rotation @ initial_ee_pose.rotation,
            initial_ee_pose.translation + delta_se3.translation,
        )
        self._update_frame_targets(target_pose)

        dt = max(state.dt, 1e-9)
        try:
            velocity = solve_ik(
                self._configuration,
                self._pink_tasks,
                dt,
                solver=self._solver,
                damping=self._config.damping,
            )
        except Exception as exc:
            logger.warning(f"{type(self).__name__} {self._name}: Pink IK failed: {exc}")
            return None

        q_solution = np.asarray(self._configuration.integrate(velocity, dt), dtype=float)
        if not check_joint_delta(q_solution, q_current, self._config.max_joint_delta_deg):
            logger.warning(
                f"{type(self).__name__} {self._name}: joint delta exceeds "
                f"{self._config.max_joint_delta_deg}°, rejecting solution"
            )
            return None

        joint_names = list(self._joint_names_list)
        positions = q_solution.flatten().tolist()
        if self._config.gripper_joint:
            with self._lock:
                gripper_pos = self._gripper_target
            joint_names.append(self._config.gripper_joint)
            positions.append(gripper_pos)

        if not self._logged_first_output:
            logger.info(
                f"{type(self).__name__} {self._name}: Pink IK output active "
                f"for {len(self._joint_names_list)} joints using solver={self._solver}"
            )
            self._logged_first_output = True

        return JointCommandOutput(
            joint_names=joint_names,
            positions=positions,
            mode=ControlMode.SERVO_POSITION,
        )

    def on_cartesian_command(self, pose: Pose | PoseStamped, t_now: float) -> bool:
        """Store the latest robot-frame controller delta pose."""
        with self._lock:
            self._target_pose = pose
            self._last_update_time = t_now
            self._active = True
        if not self._logged_first_target:
            logger.info(f"{type(self).__name__} {self._name}: received first cartesian target")
            self._logged_first_target = True
        return True

    def on_buttons(self, msg: Buttons) -> bool:
        """Press-and-hold engage with optional gripper trigger mapping."""
        is_left = self._config.hand == "left"
        primary = msg.left_primary if is_left else msg.right_primary

        if primary and not self._prev_primary:
            logger.info(f"{type(self).__name__} {self._name}: engage")
            with self._lock:
                self._initial_ee_pose = None
        elif not primary and self._prev_primary:
            logger.info(f"{type(self).__name__} {self._name}: disengage")
            with self._lock:
                self._target_pose = None
                self._initial_ee_pose = None
                self._active = False
        self._prev_primary = primary

        if self._config.gripper_joint:
            trigger = msg.left_trigger_analog if is_left else msg.right_trigger_analog
            self.on_gripper_trigger(trigger)
        return True

    def on_gripper_trigger(self, value: float, _t_now: float = 0.0) -> bool:
        """Map analog trigger value to configured gripper position."""
        if not self._config.gripper_joint:
            return False
        clamped = max(0.0, min(1.0, value))
        position = (
            self._config.gripper_open_pos
            + (self._config.gripper_closed_pos - self._config.gripper_open_pos) * clamped
        )
        with self._lock:
            self._gripper_target = position
        return True

    def on_preempted(self, by_task: str, joints: frozenset[str]) -> None:
        """Clear active target state when a higher-priority task preempts us."""
        if joints & self.claim().joints:
            logger.warning(
                f"{type(self).__name__} {self._name} preempted by {by_task} on joints {joints}"
            )
            with self._lock:
                self._target_pose = None
                self._initial_ee_pose = None
                self._active = False

    def _get_live_target(self, t_now: float) -> Pose | PoseStamped | None:
        with self._lock:
            if not self._active or self._target_pose is None:
                return None
            if self._config.timeout > 0:
                time_since_update = t_now - self._last_update_time
                if time_since_update > self._config.timeout:
                    logger.warning(
                        f"{type(self).__name__} {self._name} timed out "
                        f"(no update for {time_since_update:.3f}s)"
                    )
                    self._target_pose = None
                    self._initial_ee_pose = None
                    self._active = False
                    return None
            return self._target_pose

    def _get_current_joints(self, state: CoordinatorState) -> NDArray[np.floating[Any]] | None:
        positions = []
        for joint_name in self._joint_names_list:
            position = state.joints.get_position(joint_name)
            if position is None:
                return None
            positions.append(position)
        return np.array(positions, dtype=float)

    def _ensure_initial_ee_pose(self, q_current: NDArray[np.floating[Any]]) -> bool:
        with self._lock:
            if self._initial_ee_pose is not None:
                return True
        initial_pose = self._capture_end_effector_pose(q_current)
        with self._lock:
            self._initial_ee_pose = initial_pose
        return True

    def _capture_end_effector_pose(self, _q_current: NDArray[np.floating[Any]]) -> pinocchio.SE3:
        return self._configuration.get_transform_frame_to_world(self._primary_frame_name()).copy()

    def _primary_frame_name(self) -> str:
        if not self._frame_tasks:
            raise RuntimeError(f"{type(self).__name__} {self._name} has no frame tasks")
        return cast("str", self._frame_tasks[0].frame)

    def _validate_model(self) -> None:
        if self._model.nq != len(self._joint_names_list):
            raise ValueError(
                f"{type(self).__name__} '{self._name}' model DOF ({self._model.nq}) "
                f"does not match joint count ({len(self._joint_names_list)})"
            )

    def _create_frame_tasks(self) -> list[FrameTask]:
        raise NotImplementedError

    def _create_extra_tasks(self) -> list[Any]:
        return []

    def _update_frame_targets(self, target_pose: pinocchio.SE3) -> None:
        self._frame_tasks[0].set_target(target_pose)


@dataclass
class XArm7IKTaskConfig(PinkIKTaskConfig):
    """XArm7-specific Pink teleop IK configuration."""

    model_path: str | Path = XARM7_FK_MODEL
    end_effector_frame: str = "link7"
    hand: Literal["left", "right"] | None = "right"


class XArm7IKTask(BasePinkIKTask):
    """Pink teleop IK task for the existing right-controller XArm7 route."""

    _config: XArm7IKTaskConfig

    def __init__(self, name: str, config: XArm7IKTaskConfig) -> None:
        super().__init__(name, config)

    def _validate_model(self) -> None:
        super()._validate_model()
        configured = [_unqualified_joint_name(name) for name in self._joint_names_list]
        model_joints = _model_joint_names(self._model)
        if configured != model_joints:
            raise ValueError(
                f"XArm7IKTask '{self._name}' joint names {configured} do not match "
                f"model joints {model_joints}"
            )
        if not self._model.existFrame(self._config.end_effector_frame):
            raise ValueError(
                f"XArm7IKTask '{self._name}' model has no frame '{self._config.end_effector_frame}'"
            )

    def _create_frame_tasks(self) -> list[FrameTask]:
        return [
            FrameTask(
                self._config.end_effector_frame,
                position_cost=self._config.position_cost,
                orientation_cost=self._config.orientation_cost,
                lm_damping=self._config.lm_damping,
                gain=self._config.gain,
            )
        ]


__all__ = [
    "BasePinkIKTask",
    "PinkIKTaskConfig",
    "XArm7IKTask",
    "XArm7IKTaskConfig",
]
