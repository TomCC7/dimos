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

from dataclasses import dataclass, field
from pathlib import Path
import threading
from typing import TYPE_CHECKING, Any, Literal

import numpy as np
import pink
from pink import solve_ik
from pink.tasks import FrameTask, PostureTask as PinkPostureTask
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
from dimos.msgs.geometry_msgs.PoseStamped import PoseStamped
from dimos.robot.catalog.openarm import OPENARM_V10_BIMANUAL_FK_MODEL
from dimos.robot.catalog.ufactory import XARM7_FK_MODEL
from dimos.utils.logging_config import setup_logger

if TYPE_CHECKING:
    from numpy.typing import NDArray

    from dimos.msgs.geometry_msgs.Pose import Pose
    from dimos.teleop.quest.quest_types import Buttons

    class _PostureTaskBase:
        target_q: NDArray[np.floating[Any]] | None

        def __init__(self, cost: float, lm_damping: float = 0.0, gain: float = 1.0) -> None: ...

        def set_target(self, target_q: NDArray[np.floating[Any]]) -> None: ...

        def compute_error(self, configuration: pink.Configuration) -> NDArray[np.floating[Any]]: ...

        def compute_jacobian(
            self, configuration: pink.Configuration
        ) -> NDArray[np.floating[Any]]: ...

else:
    _PostureTaskBase = PinkPostureTask

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


def _require_finite(name: str, value: float) -> None:
    if not np.isfinite(value):
        raise ValueError(f"{name} must be finite")


def _require_non_negative(name: str, value: float) -> None:
    _require_finite(name, value)
    if value < 0.0:
        raise ValueError(f"{name} must be non-negative")


def _require_unit_interval(name: str, value: float) -> None:
    _require_finite(name, value)
    if value < 0.0 or value > 1.0:
        raise ValueError(f"{name} must be in [0, 1]")


class WeightedPostureTask(_PostureTaskBase):
    """Pink posture task with per-joint residual and Jacobian weights."""

    def __init__(
        self,
        cost: float,
        weights: NDArray[np.floating[Any]],
        lm_damping: float = 0.0,
        gain: float = 1.0,
    ) -> None:
        super().__init__(cost=cost, lm_damping=lm_damping, gain=gain)
        self.weights = np.asarray(weights, dtype=float)
        if self.weights.ndim != 1:
            raise ValueError("posture weights must be a one-dimensional vector")
        if not np.isfinite(self.weights).all():
            raise ValueError("posture weights must be finite")
        if (self.weights < 0.0).any():
            raise ValueError("posture weights must be non-negative")

    def compute_error(self, configuration: pink.Configuration) -> NDArray[np.floating[Any]]:
        error = np.asarray(super().compute_error(configuration), dtype=float)
        weighted_error: NDArray[np.floating[Any]] = self.weights * error
        return weighted_error

    def compute_jacobian(self, configuration: pink.Configuration) -> NDArray[np.floating[Any]]:
        jacobian = np.asarray(super().compute_jacobian(configuration), dtype=float)
        weighted_jacobian: NDArray[np.floating[Any]] = self.weights[:, np.newaxis] * jacobian
        return weighted_jacobian


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
    num_solver_iterations: int = 1
    amplify_factor: float = 1.0
    end_effector_frame: str = ""
    position_cost: float = 1.0
    orientation_cost: float = 1.0
    lm_damping: float = 1.0
    gain: float = 1.0
    gripper_joint: str | None = None
    gripper_open_pos: float = 0.0
    gripper_closed_pos: float = 0.0
    posture_cost: float = 0.0
    posture_default_weight: float = 1.0
    posture_joint_weights: dict[str, float] = field(default_factory=dict)
    posture_reference: dict[str, float] = field(default_factory=dict)
    posture_lm_damping: float = 0.0
    posture_gain: float = 1.0


class BasePinkIKTask(BaseControlTask):
    """Base control task for Pink-backed teleoperation IK."""

    def __init__(self, name: str, config: PinkIKTaskConfig) -> None:
        if not config.joint_names:
            raise ValueError(f"{type(self).__name__} '{name}' requires at least one joint")
        if config.hand is not None and config.hand not in ("left", "right"):
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
        self._active = False
        self._gripper_target = config.gripper_open_pos
        self._logged_first_output = False
        self._last_solution: NDArray[np.floating[Any]] | None = None

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
        """Return true when this task should be considered for compute."""
        with self._lock:
            return self._active

    def start(self) -> None:
        """Activate the task so incoming targets can be consumed."""
        with self._lock:
            self._active = True
        logger.info(f"{type(self).__name__} {self._name} started")

    def stop(self) -> None:
        """Deactivate the task and clear captured target state."""
        with self._lock:
            self._active = False
            self._clear_target_state()
        logger.info(f"{type(self).__name__} {self._name} stopped")

    def compute(self, state: CoordinatorState) -> JointCommandOutput | None:
        """Run one Pink differential IK tick and return joint positions."""
        if not self._prepare_compute(state):
            return None

        q_current = self._get_current_joints(state)
        if q_current is None:
            logger.debug(
                f"{type(self).__name__} {self._name}: missing joint state for IK warm-start"
            )
            return None

        self._configuration.update(q_current)
        if not self._update_frame_targets(state, q_current):
            return None
        if not self._update_extra_task_targets(q_current):
            return None

        dt = max(state.dt, 1e-9)
        q_solution = self._solve_ik_refined(dt)
        if q_solution is None:
            return None

        if not check_joint_delta(q_solution, q_current, self._config.max_joint_delta_deg):
            logger.warning(
                f"{type(self).__name__} {self._name}: joint delta exceeds "
                f"{self._config.max_joint_delta_deg}°, rejecting solution"
            )
            return None
        self._last_solution = q_solution

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

    def _solve_ik_refined(self, dt: float) -> NDArray[np.floating[Any]] | None:
        q_solution: NDArray[np.floating[Any]] | None = None
        solver_dt = dt / self._config.num_solver_iterations
        integration_dt = solver_dt * self._config.amplify_factor
        for _ in range(self._config.num_solver_iterations):
            try:
                velocity = solve_ik(
                    self._configuration,
                    self._pink_tasks,
                    solver_dt,
                    solver=self._solver,
                    damping=self._config.damping,
                )
            except Exception as exc:
                logger.warning(f"{type(self).__name__} {self._name}: Pink IK failed: {exc}")
                return None

            velocity_array = np.asarray(velocity, dtype=float)
            if not np.isfinite(velocity_array).all():
                logger.warning(
                    f"{type(self).__name__} {self._name}: Pink IK returned non-finite velocity"
                )
                return None
            q_solution = np.asarray(
                self._configuration.integrate(velocity_array, integration_dt), dtype=float
            )
            if not np.isfinite(q_solution).all():
                logger.warning(
                    f"{type(self).__name__} {self._name}: Pink IK returned non-finite output"
                )
                return None
            self._configuration.update(q_solution)

        return q_solution

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
                self._active = False
                self._clear_target_state()

    def _get_current_joints(self, state: CoordinatorState) -> NDArray[np.floating[Any]] | None:
        positions = []
        for joint_name in self._joint_names_list:
            position = state.joints.get_position(joint_name)
            if position is None:
                return None
            positions.append(position)
        return np.array(positions, dtype=float)

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

    def _update_extra_task_targets(self, _q_current: NDArray[np.floating[Any]]) -> bool:
        return True

    def _clear_target_state(self) -> None:
        """Clear concrete target state while holding ``self._lock``."""

    def _prepare_compute(self, _state: CoordinatorState) -> bool:
        return True

    def _update_frame_targets(
        self, state: CoordinatorState, q_current: NDArray[np.floating[Any]]
    ) -> bool:
        raise NotImplementedError


class SingleFramePinkIKTask(BasePinkIKTask):
    """Pink teleop IK base for concrete tasks with one controlled frame target."""

    def __init__(self, name: str, config: PinkIKTaskConfig) -> None:
        super().__init__(name, config)
        self._target_pose: Pose | PoseStamped | None = None
        self._last_update_time = 0.0
        self._initial_ee_pose: pinocchio.SE3 | None = None
        self._prev_primary = False
        self._logged_first_target = False

    def is_active(self) -> bool:
        """Return true when a live single-frame target can produce IK output."""
        with self._lock:
            return self._active and self._target_pose is not None

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
                self._active = False
                self._clear_target_state()
        self._prev_primary = primary

        if self._config.gripper_joint:
            trigger = msg.left_trigger_analog if is_left else msg.right_trigger_analog
            self.on_gripper_trigger(trigger)
        return True

    def _prepare_compute(self, state: CoordinatorState) -> bool:
        return self._get_live_target(state.t_now) is not None

    def _update_frame_targets(
        self, state: CoordinatorState, q_current: NDArray[np.floating[Any]]
    ) -> bool:
        raw_pose = self._get_live_target(state.t_now)
        if raw_pose is None:
            return False
        if not self._ensure_initial_ee_pose(q_current):
            return False

        with self._lock:
            initial_ee_pose = self._initial_ee_pose
        if initial_ee_pose is None:
            return False

        delta_se3 = pose_to_se3(raw_pose)
        target_pose = pinocchio.SE3(
            delta_se3.rotation @ initial_ee_pose.rotation,
            initial_ee_pose.translation + delta_se3.translation,
        )
        self._single_frame_task().set_target(target_pose)
        return True

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
                    self._active = False
                    self._clear_target_state()
                    return None
            return self._target_pose

    def _ensure_initial_ee_pose(self, q_current: NDArray[np.floating[Any]]) -> bool:
        with self._lock:
            if self._initial_ee_pose is not None:
                return True
        initial_pose = self._capture_end_effector_pose(q_current)
        with self._lock:
            self._initial_ee_pose = initial_pose
        return True

    def _capture_end_effector_pose(self, _q_current: NDArray[np.floating[Any]]) -> pinocchio.SE3:
        return self._configuration.get_transform_frame_to_world(self._single_frame_name()).copy()

    def _single_frame_name(self) -> str:
        return str(self._single_frame_task().frame)

    def _single_frame_task(self) -> FrameTask:
        if len(self._frame_tasks) != 1:
            raise RuntimeError(
                f"{type(self).__name__} {self._name} requires exactly one frame task"
            )
        return self._frame_tasks[0]

    def _clear_target_state(self) -> None:
        self._target_pose = None
        self._initial_ee_pose = None


@dataclass
class XArm7IKTaskConfig(PinkIKTaskConfig):
    """XArm7-specific Pink teleop IK configuration."""

    model_path: str | Path = XARM7_FK_MODEL
    end_effector_frame: str = "link7"
    hand: Literal["left", "right"] | None = "right"


class XArm7IKTask(SingleFramePinkIKTask):
    """Pink teleop IK task for the existing right-controller XArm7 route."""

    _config: XArm7IKTaskConfig

    def __init__(self, name: str, config: XArm7IKTaskConfig) -> None:
        self._posture_task: WeightedPostureTask | None = None
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
        self._validate_numeric_config()
        self._validate_posture_config()

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

    def _create_extra_tasks(self) -> list[Any]:
        if self._config.posture_cost <= 0.0:
            return []

        self._posture_task = WeightedPostureTask(
            cost=self._config.posture_cost,
            weights=self._posture_weights(),
            lm_damping=self._config.posture_lm_damping,
            gain=self._config.posture_gain,
        )
        return [self._posture_task]

    def _update_extra_task_targets(self, q_current: NDArray[np.floating[Any]]) -> bool:
        if self._posture_task is None:
            return True

        target = np.asarray(q_current, dtype=float).copy()
        for joint_name, position in self._config.posture_reference.items():
            target[self._posture_joint_index(joint_name)] = position
        self._posture_task.set_target(target)
        return True

    def _clear_target_state(self) -> None:
        super()._clear_target_state()

    def _posture_weights(self) -> NDArray[np.floating[Any]]:
        weights = np.full(self._model.nv, self._config.posture_default_weight, dtype=float)
        for joint_name, weight in self._config.posture_joint_weights.items():
            weights[self._posture_joint_index(joint_name)] = weight
        return weights

    def _validate_posture_joint_names(self) -> None:
        for joint_name in [
            *self._config.posture_joint_weights.keys(),
            *self._config.posture_reference.keys(),
        ]:
            self._posture_joint_index(joint_name)

    def _validate_numeric_config(self) -> None:
        _require_non_negative("damping", self._config.damping)
        _require_finite("amplify_factor", self._config.amplify_factor)
        if self._config.amplify_factor <= 0.0:
            raise ValueError("amplify_factor must be positive")
        if self._config.num_solver_iterations < 1:
            raise ValueError("num_solver_iterations must be positive")
        _require_non_negative("position_cost", self._config.position_cost)
        _require_non_negative("orientation_cost", self._config.orientation_cost)
        _require_non_negative("lm_damping", self._config.lm_damping)
        _require_unit_interval("gain", self._config.gain)
        _require_finite("timeout", self._config.timeout)
        if self._config.timeout < 0.0:
            raise ValueError("timeout must be non-negative")
        _require_finite("max_joint_delta_deg", self._config.max_joint_delta_deg)
        if self._config.max_joint_delta_deg <= 0.0:
            raise ValueError("max_joint_delta_deg must be positive")

    def _validate_posture_config(self) -> None:
        _require_non_negative("posture_cost", self._config.posture_cost)
        _require_non_negative("posture_default_weight", self._config.posture_default_weight)
        _require_non_negative("posture_lm_damping", self._config.posture_lm_damping)
        _require_unit_interval("posture_gain", self._config.posture_gain)
        self._validate_posture_joint_names()
        for joint_name, weight in self._config.posture_joint_weights.items():
            _require_non_negative(f"posture_joint_weights[{joint_name!r}]", weight)
        for joint_name, position in self._config.posture_reference.items():
            _require_finite(f"posture_reference[{joint_name!r}]", position)
            index = self._posture_joint_index(joint_name)
            lower = float(self._model.lowerPositionLimit[index])
            upper = float(self._model.upperPositionLimit[index])
            if position < lower or position > upper:
                raise ValueError(
                    f"posture_reference[{joint_name!r}]={position} is outside "
                    f"model limits [{lower}, {upper}]"
                )

    def _posture_joint_index(self, joint_name: str) -> int:
        names = {
            configured_name: index for index, configured_name in enumerate(self._joint_names_list)
        }
        names.update(
            {
                _unqualified_joint_name(configured_name): index
                for index, configured_name in enumerate(self._joint_names_list)
            }
        )
        if joint_name not in names:
            raise ValueError(
                f"XArm7IKTask '{self._name}' posture joint '{joint_name}' is not in "
                f"configured joints {self._joint_names_list}"
            )
        return names[joint_name]


@dataclass
class OpenArmBimanualIKTaskConfig(PinkIKTaskConfig):
    """OpenArm whole-robot Pink teleop IK configuration."""

    joint_names: list[str] = field(
        default_factory=lambda: [
            *[f"openarm_left_joint{i}" for i in range(1, 8)],
            *[f"openarm_right_joint{i}" for i in range(1, 8)],
        ]
    )
    model_path: str | Path = OPENARM_V10_BIMANUAL_FK_MODEL
    hand: Literal["left", "right"] | None = None
    left_task_name: str = "teleop_openarm_left"
    right_task_name: str = "teleop_openarm_right"
    left_end_effector_frame: str = "openarm_left_link7"
    right_end_effector_frame: str = "openarm_right_link7"


class OpenArmBimanualIKTask(BasePinkIKTask):
    """Unified Pink IK task for bimanual OpenArm teleoperation."""

    _config: OpenArmBimanualIKTaskConfig

    def __init__(self, name: str, config: OpenArmBimanualIKTaskConfig) -> None:
        self._target_poses: dict[str, Pose | PoseStamped] = {}
        self._last_update_times: dict[str, float] = {}
        self._initial_ee_poses: dict[str, pinocchio.SE3] = {}
        self._logged_target_names: set[str] = set()
        super().__init__(name, config)

    @property
    def target_task_names(self) -> tuple[str, str]:
        """Quest task names accepted by this unified IK task."""
        return (self._config.left_task_name, self._config.right_task_name)

    def is_active(self) -> bool:
        """Return true when at least one live bimanual target can produce IK output."""
        with self._lock:
            return self._active and bool(self._target_poses)

    def on_cartesian_command(self, pose: Pose | PoseStamped, t_now: float) -> bool:
        """Store the latest controller delta pose for one OpenArm target slot."""
        frame_id = getattr(pose, "frame_id", "")
        if frame_id not in self.target_task_names:
            return False

        with self._lock:
            self._target_poses[frame_id] = pose
            self._last_update_times[frame_id] = t_now
            self._active = True
        if frame_id not in self._logged_target_names:
            logger.info(f"{type(self).__name__} {self._name}: received first {frame_id} target")
            self._logged_target_names.add(frame_id)
        return True

    def _prepare_compute(self, state: CoordinatorState) -> bool:
        return bool(self._live_targets(state.t_now))

    def _update_frame_targets(
        self, state: CoordinatorState, q_current: NDArray[np.floating[Any]]
    ) -> bool:
        live_targets = self._live_targets(state.t_now)
        if not live_targets:
            return False

        live_frame_names = {self._frame_name_for_task(task_name) for task_name in live_targets}
        for frame_task in self._frame_tasks:
            if str(frame_task.frame) not in live_frame_names:
                frame_task.set_target_from_configuration(self._configuration)

        for task_name, raw_pose in live_targets.items():
            frame_name = self._frame_name_for_task(task_name)
            if not self._ensure_initial_ee_pose(frame_name, q_current):
                return False
            initial_ee_pose = self._initial_ee_poses.get(frame_name)
            if initial_ee_pose is None:
                return False
            delta_se3 = pose_to_se3(raw_pose)
            target_pose = pinocchio.SE3(
                delta_se3.rotation @ initial_ee_pose.rotation,
                initial_ee_pose.translation + delta_se3.translation,
            )
            self._frame_task_for_frame(frame_name).set_target(target_pose)
        return True

    def _validate_model(self) -> None:
        super()._validate_model()
        configured = list(self._joint_names_list)
        model_joints = _model_joint_names(self._model)
        if configured != model_joints:
            raise ValueError(
                f"OpenArmBimanualIKTask '{self._name}' joint names {configured} do not match "
                f"model joints {model_joints}"
            )
        for frame_name in (
            self._config.left_end_effector_frame,
            self._config.right_end_effector_frame,
        ):
            if not self._model.existFrame(frame_name):
                raise ValueError(
                    f"OpenArmBimanualIKTask '{self._name}' model has no frame '{frame_name}'"
                )
        self._validate_numeric_config()

    def _create_frame_tasks(self) -> list[FrameTask]:
        return [
            FrameTask(
                self._config.left_end_effector_frame,
                position_cost=self._config.position_cost,
                orientation_cost=self._config.orientation_cost,
                lm_damping=self._config.lm_damping,
                gain=self._config.gain,
            ),
            FrameTask(
                self._config.right_end_effector_frame,
                position_cost=self._config.position_cost,
                orientation_cost=self._config.orientation_cost,
                lm_damping=self._config.lm_damping,
                gain=self._config.gain,
            ),
        ]

    def _clear_target_state(self) -> None:
        self._target_poses.clear()
        self._last_update_times.clear()
        self._initial_ee_poses.clear()

    def _live_targets(self, t_now: float) -> dict[str, Pose | PoseStamped]:
        with self._lock:
            stale = [
                task_name
                for task_name, last_update in self._last_update_times.items()
                if self._config.timeout > 0 and t_now - last_update > self._config.timeout
            ]
            for task_name in stale:
                logger.warning(f"{type(self).__name__} {self._name} target {task_name} timed out")
                self._target_poses.pop(task_name, None)
                self._last_update_times.pop(task_name, None)
                self._initial_ee_poses.pop(self._frame_name_for_task(task_name), None)
            if not self._target_poses:
                self._active = False
            return dict(self._target_poses)

    def _ensure_initial_ee_pose(
        self, frame_name: str, q_current: NDArray[np.floating[Any]]
    ) -> bool:
        if frame_name in self._initial_ee_poses:
            return True
        self._configuration.update(q_current)
        self._initial_ee_poses[frame_name] = self._configuration.get_transform_frame_to_world(
            frame_name
        ).copy()
        return True

    def _frame_name_for_task(self, task_name: str) -> str:
        if task_name == self._config.left_task_name:
            return self._config.left_end_effector_frame
        if task_name == self._config.right_task_name:
            return self._config.right_end_effector_frame
        raise ValueError(f"Unknown OpenArm target task name: {task_name}")

    def _frame_task_for_frame(self, frame_name: str) -> FrameTask:
        for frame_task in self._frame_tasks:
            if str(frame_task.frame) == frame_name:
                return frame_task
        raise ValueError(f"OpenArm frame task not found for frame: {frame_name}")

    def end_effector_pose(self, task_name: str) -> PoseStamped | None:
        """Return the last solved end-effector pose for a left/right OpenArm target."""
        if self._last_solution is None:
            return None
        frame_name = self._frame_name_for_task(task_name)
        self._configuration.update(self._last_solution)
        placement = self._configuration.get_transform_frame_to_world(frame_name)
        quat = pinocchio.Quaternion(placement.rotation).coeffs()
        return PoseStamped(
            position=placement.translation.tolist(),
            orientation=[float(quat[0]), float(quat[1]), float(quat[2]), float(quat[3])],
            frame_id=task_name,
        )

    def _validate_numeric_config(self) -> None:
        _require_non_negative("damping", self._config.damping)
        _require_finite("amplify_factor", self._config.amplify_factor)
        if self._config.amplify_factor <= 0.0:
            raise ValueError("amplify_factor must be positive")
        if self._config.num_solver_iterations < 1:
            raise ValueError("num_solver_iterations must be positive")
        _require_non_negative("position_cost", self._config.position_cost)
        _require_non_negative("orientation_cost", self._config.orientation_cost)
        _require_non_negative("lm_damping", self._config.lm_damping)
        _require_unit_interval("gain", self._config.gain)
        _require_finite("timeout", self._config.timeout)
        if self._config.timeout < 0.0:
            raise ValueError("timeout must be non-negative")
        _require_finite("max_joint_delta_deg", self._config.max_joint_delta_deg)
        if self._config.max_joint_delta_deg <= 0.0:
            raise ValueError("max_joint_delta_deg must be positive")


__all__ = [
    "BasePinkIKTask",
    "OpenArmBimanualIKTask",
    "OpenArmBimanualIKTaskConfig",
    "PinkIKTaskConfig",
    "SingleFramePinkIKTask",
    "WeightedPostureTask",
    "XArm7IKTask",
    "XArm7IKTaskConfig",
]
