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

"""Tests for Pink-backed teleop IK control tasks."""

from __future__ import annotations

import numpy as np
from pink.tasks import FrameTask
import pytest

from dimos.control.coordinator import ControlCoordinator, ControlCoordinatorConfig, TaskConfig
from dimos.control.task import ControlMode, CoordinatorState, JointStateSnapshot
from dimos.control.tasks import pink_teleop_task
from dimos.control.tasks.pink_teleop_task import (
    BasePinkIKTask,
    OpenArmBimanualIKTask,
    OpenArmBimanualIKTaskConfig,
    SingleFramePinkIKTask,
    WeightedPostureTask,
    XArm7IKTask,
    XArm7IKTaskConfig,
)
from dimos.msgs.geometry_msgs.PoseStamped import PoseStamped
from dimos.robot.catalog.openarm import OPENARM_V10_BIMANUAL_FK_MODEL
from dimos.robot.catalog.ufactory import XARM7_FK_MODEL

XARM7_JOINTS = [f"arm/joint{i}" for i in range(1, 8)]
OPENARM_JOINTS = [
    *[f"openarm_left_joint{i}" for i in range(1, 8)],
    *[f"openarm_right_joint{i}" for i in range(1, 8)],
]


def _state(*, t_now: float = 1.0, dt: float = 0.01) -> CoordinatorState:
    return CoordinatorState(
        joints=JointStateSnapshot(joint_positions={name: 0.0 for name in XARM7_JOINTS}),
        t_now=t_now,
        dt=dt,
    )


def _task(
    *,
    timeout: float = 0.5,
    max_joint_delta_deg: float = 5.0,
    gripper_joint: str | None = None,
    posture_cost: float = 0.0,
    posture_default_weight: float = 1.0,
    posture_joint_weights: dict[str, float] | None = None,
    posture_reference: dict[str, float] | None = None,
    posture_lm_damping: float = 0.0,
    posture_gain: float = 1.0,
    gain: float = 1.0,
) -> XArm7IKTask:
    config = XArm7IKTaskConfig(
        joint_names=XARM7_JOINTS,
        model_path=XARM7_FK_MODEL,
        timeout=timeout,
        max_joint_delta_deg=max_joint_delta_deg,
        gripper_joint=gripper_joint,
        gain=gain,
        posture_cost=posture_cost,
        posture_default_weight=posture_default_weight,
        posture_joint_weights=posture_joint_weights or {},
        posture_reference=posture_reference or {},
        posture_lm_damping=posture_lm_damping,
        posture_gain=posture_gain,
    )
    return XArm7IKTask("teleop_xarm", config)


def test_missing_joint_state_returns_no_command() -> None:
    task = _task()
    task.on_cartesian_command(PoseStamped(frame_id="teleop_xarm"), t_now=1.0)
    state = CoordinatorState(
        joints=JointStateSnapshot(joint_positions={name: 0.0 for name in XARM7_JOINTS[:-1]}),
        t_now=1.0,
        dt=0.01,
    )

    assert task.compute(state) is None


def test_timeout_clears_active_target_state() -> None:
    task = _task(timeout=0.1)
    task.on_cartesian_command(PoseStamped(frame_id="teleop_xarm"), t_now=1.0)

    assert task.compute(_state(t_now=1.2)) is None
    assert not task.is_active()


def test_timeout_clears_active_target_state_before_joint_extraction() -> None:
    task = _task(timeout=0.1)
    task.on_cartesian_command(PoseStamped(frame_id="teleop_xarm"), t_now=1.0)
    state = CoordinatorState(
        joints=JointStateSnapshot(joint_positions={name: 0.0 for name in XARM7_JOINTS[:-1]}),
        t_now=1.2,
        dt=0.01,
    )

    assert task.compute(state) is None
    assert not task.is_active()


def test_inactive_state_returns_no_command() -> None:
    task = _task()

    assert task.compute(_state()) is None


def test_single_target_state_lives_in_single_frame_layer() -> None:
    assert issubclass(XArm7IKTask, SingleFramePinkIKTask)
    assert not hasattr(BasePinkIKTask, "_get_live_target")
    assert not hasattr(BasePinkIKTask, "_single_frame_task")
    assert not hasattr(BasePinkIKTask, "_primary_frame_name")


def test_unsafe_joint_delta_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    task = _task(max_joint_delta_deg=1.0)
    task.on_cartesian_command(PoseStamped(frame_id="teleop_xarm"), t_now=1.0)

    def large_velocity(*_args: object, **_kwargs: object) -> np.ndarray:
        return np.ones(7) * 100.0

    monkeypatch.setattr(pink_teleop_task, "solve_ik", large_velocity)

    assert task.compute(_state(t_now=1.0, dt=0.1)) is None


def test_weighted_posture_task_weights_error_and_jacobian() -> None:
    task = _task(posture_cost=0.2, posture_default_weight=2.0)
    posture_task = task._posture_task
    assert isinstance(posture_task, WeightedPostureTask)

    task._configuration.update(np.zeros(7, dtype=float))
    posture_task.set_target(np.ones(7, dtype=float))

    error = posture_task.compute_error(task._configuration)
    jacobian = posture_task.compute_jacobian(task._configuration)

    assert np.allclose(error, np.full(7, -2.0))
    assert np.allclose(jacobian, np.eye(7) * 2.0)


def test_posture_disabled_keeps_frame_task_only() -> None:
    task = _task(posture_cost=0.0)

    assert task._posture_task is None
    assert len(task._pink_tasks) == 1


def test_posture_enabled_preserves_frame_task_in_solve(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task = _task(posture_cost=0.2)
    task.on_cartesian_command(PoseStamped(frame_id="teleop_xarm"), t_now=1.0)
    solve_tasks: list[object] = []

    def capture_tasks(
        _configuration: object, tasks: list[object], *_args: object, **_kwargs: object
    ) -> np.ndarray:
        solve_tasks.extend(tasks)
        return np.zeros(7, dtype=float)

    monkeypatch.setattr(pink_teleop_task, "solve_ik", capture_tasks)

    assert task.compute(_state(t_now=1.0, dt=0.1)) is not None
    assert task._frame_tasks[0] in solve_tasks
    assert task._posture_task in solve_tasks


def test_pink_ik_uses_single_official_solve_and_integrate_step(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task = _task()
    task.on_cartesian_command(PoseStamped(frame_id="teleop_xarm"), t_now=1.0)
    calls: list[float] = []

    def constant_velocity(
        _configuration: object,
        _tasks: list[object],
        dt: float,
        **_kwargs: object,
    ) -> np.ndarray:
        calls.append(dt)
        return np.ones(7, dtype=float) * 0.1

    monkeypatch.setattr(pink_teleop_task, "solve_ik", constant_velocity)

    output = task.compute(_state(t_now=1.0, dt=0.1))

    assert output is not None
    assert calls == [0.1]
    assert output.positions is not None
    assert np.allclose(output.positions, np.full(7, 0.01))


def test_posture_reference_changes_observable_ik_output() -> None:
    state = _state(t_now=1.0, dt=0.01)
    frame_only = _task(max_joint_delta_deg=180.0)
    frame_only.on_cartesian_command(PoseStamped(frame_id="teleop_xarm"), t_now=1.0)

    posture = _task(
        max_joint_delta_deg=180.0,
        posture_cost=0.1,
        posture_reference={"arm/joint3": 0.5},
    )
    posture.on_cartesian_command(PoseStamped(frame_id="teleop_xarm"), t_now=1.0)

    frame_only_output = frame_only.compute(state)
    posture_output = posture.compute(state)

    assert frame_only_output is not None
    assert posture_output is not None
    assert frame_only_output.positions is not None
    assert posture_output.positions is not None
    assert not np.allclose(frame_only_output.positions, posture_output.positions)


def test_posture_weight_and_reference_map_by_joint_name() -> None:
    task = _task(
        posture_cost=0.2,
        posture_default_weight=0.5,
        posture_joint_weights={"arm/joint2": 3.0, "joint4": 4.0},
        posture_reference={"arm/joint3": 1.25, "joint5": -0.5},
    )

    assert task._posture_task is not None
    assert np.allclose(task._posture_task.weights, [0.5, 3.0, 0.5, 4.0, 0.5, 0.5, 0.5])

    q_current = np.arange(7, dtype=float)
    assert task._update_extra_task_targets(q_current)

    assert task._posture_task.target_q is not None
    assert np.allclose(task._posture_task.target_q, [0.0, 1.0, 1.25, 3.0, -0.5, 5.0, 6.0])


def test_posture_target_refreshes_from_current_joint_state() -> None:
    task = _task(posture_cost=0.2, posture_reference={"arm/joint3": 1.25})
    assert task._posture_task is not None

    first = np.zeros(7, dtype=float)
    second = np.arange(7, dtype=float) * 0.1

    assert task._update_extra_task_targets(first)
    assert task._posture_task.target_q is not None
    assert np.allclose(task._posture_task.target_q, [0.0, 0.0, 1.25, 0.0, 0.0, 0.0, 0.0])

    assert task._update_extra_task_targets(second)
    assert task._posture_task.target_q is not None
    assert np.allclose(task._posture_task.target_q, [0.0, 0.1, 1.25, 0.3, 0.4, 0.5, 0.6])


def test_posture_reference_rejects_unknown_joint_name() -> None:
    with pytest.raises(ValueError, match="posture joint"):
        _task(posture_cost=0.2, posture_reference={"missing_joint": 0.0})


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("posture_cost", -0.1, "posture_cost"),
        ("posture_default_weight", -1.0, "posture_default_weight"),
        ("posture_lm_damping", float("nan"), "posture_lm_damping"),
        ("posture_gain", float("inf"), "posture_gain"),
        ("posture_gain", 1.1, "posture_gain"),
        ("gain", 1.1, "gain"),
        ("max_joint_delta_deg", float("inf"), "max_joint_delta_deg"),
        ("timeout", -1.0, "timeout"),
    ],
)
def test_invalid_numeric_config_is_rejected(field: str, value: float, match: str) -> None:
    with pytest.raises(ValueError, match=match):
        if field == "posture_cost":
            _task(posture_cost=value)
        elif field == "posture_default_weight":
            _task(posture_default_weight=value)
        elif field == "posture_lm_damping":
            _task(posture_lm_damping=value)
        elif field == "posture_gain":
            _task(posture_gain=value)
        elif field == "gain":
            _task(gain=value)
        elif field == "max_joint_delta_deg":
            _task(max_joint_delta_deg=value)
        elif field == "timeout":
            _task(timeout=value)
        else:
            raise AssertionError(f"Unhandled field: {field}")


def test_invalid_posture_weight_is_rejected() -> None:
    with pytest.raises(ValueError, match="posture_joint_weights"):
        _task(posture_cost=0.2, posture_joint_weights={"arm/joint2": float("nan")})


def test_out_of_limit_posture_reference_is_rejected() -> None:
    with pytest.raises(ValueError, match="outside model limits"):
        _task(posture_cost=0.2, posture_reference={"arm/joint2": 1000.0})


def test_posture_enabled_solver_failure_returns_no_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task = _task(posture_cost=0.2)
    task.on_cartesian_command(PoseStamped(frame_id="teleop_xarm"), t_now=1.0)

    def fail_solve(*_args: object, **_kwargs: object) -> np.ndarray:
        raise RuntimeError("solver failed")

    monkeypatch.setattr(pink_teleop_task, "solve_ik", fail_solve)

    assert task.compute(_state(t_now=1.0, dt=0.1)) is None


def test_posture_enabled_unsafe_joint_delta_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task = _task(posture_cost=0.2, max_joint_delta_deg=1.0)
    task.on_cartesian_command(PoseStamped(frame_id="teleop_xarm"), t_now=1.0)

    def large_velocity(*_args: object, **_kwargs: object) -> np.ndarray:
        return np.ones(7) * 100.0

    monkeypatch.setattr(pink_teleop_task, "solve_ik", large_velocity)

    assert task.compute(_state(t_now=1.0, dt=0.1)) is None


def test_non_finite_ik_output_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    task = _task(posture_cost=0.2)
    task.on_cartesian_command(PoseStamped(frame_id="teleop_xarm"), t_now=1.0)

    def non_finite_velocity(*_args: object, **_kwargs: object) -> np.ndarray:
        return np.full(7, np.nan)

    monkeypatch.setattr(pink_teleop_task, "solve_ik", non_finite_velocity)

    assert task.compute(_state(t_now=1.0, dt=0.1)) is None


def test_xarm7_task_claims_arm_and_gripper() -> None:
    task = _task(gripper_joint="arm/gripper")

    claim = task.claim()

    assert claim.mode == ControlMode.SERVO_POSITION
    assert claim.joints == frozenset([*XARM7_JOINTS, "arm/gripper"])


def test_xarm7_construction_rejects_mismatched_joint_names() -> None:
    with pytest.raises(ValueError, match="joint names"):
        XArm7IKTask(
            "teleop_xarm",
            XArm7IKTaskConfig(
                joint_names=[f"arm/bad{i}" for i in range(1, 8)],
                model_path=XARM7_FK_MODEL,
            ),
        )


def test_xarm7_construction_rejects_missing_end_effector_frame() -> None:
    with pytest.raises(ValueError, match="no frame"):
        XArm7IKTask(
            "teleop_xarm",
            XArm7IKTaskConfig(
                joint_names=XARM7_JOINTS,
                model_path=XARM7_FK_MODEL,
                end_effector_frame="missing_frame",
            ),
        )


def test_openarm_bimanual_task_accepts_left_and_right_target_slots() -> None:
    task = OpenArmBimanualIKTask(
        "teleop_openarm",
        OpenArmBimanualIKTaskConfig(
            joint_names=OPENARM_JOINTS,
            model_path=OPENARM_V10_BIMANUAL_FK_MODEL,
        ),
    )

    assert task.target_task_names == ("teleop_openarm_left", "teleop_openarm_right")
    assert task.on_cartesian_command(
        PoseStamped(frame_id="teleop_openarm_left"),
        t_now=1.0,
    )
    assert task.on_cartesian_command(
        PoseStamped(frame_id="teleop_openarm_right"),
        t_now=1.0,
    )
    assert not task.on_cartesian_command(PoseStamped(frame_id="teleop_xarm"), t_now=1.0)


def test_openarm_bimanual_task_solves_with_one_live_target() -> None:
    task = OpenArmBimanualIKTask(
        "teleop_openarm",
        OpenArmBimanualIKTaskConfig(
            joint_names=OPENARM_JOINTS,
            model_path=OPENARM_V10_BIMANUAL_FK_MODEL,
        ),
    )
    task.on_cartesian_command(PoseStamped(frame_id="teleop_openarm_left"), t_now=1.0)

    output = task.compute(
        CoordinatorState(
            joints=JointStateSnapshot(joint_positions={name: 0.0 for name in OPENARM_JOINTS}),
            t_now=1.0,
            dt=0.01,
        )
    )

    assert output is not None
    assert output.joint_names == OPENARM_JOINTS


def test_openarm_bimanual_task_solves_both_frame_tasks_together(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task = OpenArmBimanualIKTask(
        "teleop_openarm",
        OpenArmBimanualIKTaskConfig(
            joint_names=OPENARM_JOINTS,
            model_path=OPENARM_V10_BIMANUAL_FK_MODEL,
        ),
    )
    seen_frames: list[str] = []

    def zero_velocity(
        _configuration: object, tasks: list[FrameTask], *_args: object, **_kwargs: object
    ) -> np.ndarray:
        seen_frames.extend(str(frame_task.frame) for frame_task in tasks)
        return np.zeros(len(OPENARM_JOINTS), dtype=float)

    monkeypatch.setattr(pink_teleop_task, "solve_ik", zero_velocity)
    task.on_cartesian_command(PoseStamped(frame_id="teleop_openarm_left"), t_now=1.0)
    task.on_cartesian_command(PoseStamped(frame_id="teleop_openarm_right"), t_now=1.0)

    output = task.compute(
        CoordinatorState(
            joints=JointStateSnapshot(joint_positions={name: 0.0 for name in OPENARM_JOINTS}),
            t_now=1.0,
            dt=0.01,
        )
    )

    assert output is not None
    assert seen_frames == ["openarm_left_link7", "openarm_right_link7"]


def test_openarm_bimanual_task_preserves_target_slots_on_alternating_updates() -> None:
    task = OpenArmBimanualIKTask(
        "teleop_openarm",
        OpenArmBimanualIKTaskConfig(
            joint_names=OPENARM_JOINTS,
            model_path=OPENARM_V10_BIMANUAL_FK_MODEL,
        ),
    )
    first_right = PoseStamped(frame_id="teleop_openarm_right", position=[0.1, 0.0, 0.0])
    next_left = PoseStamped(frame_id="teleop_openarm_left", position=[0.0, 0.1, 0.0])

    task.on_cartesian_command(PoseStamped(frame_id="teleop_openarm_left"), t_now=1.0)
    task.on_cartesian_command(first_right, t_now=1.1)
    task.on_cartesian_command(next_left, t_now=1.2)

    assert task._target_poses["teleop_openarm_left"] is next_left
    assert task._target_poses["teleop_openarm_right"] is first_right


def test_openarm_bimanual_task_rejects_mismatched_joint_names() -> None:
    with pytest.raises(ValueError, match="joint names"):
        OpenArmBimanualIKTask(
            "teleop_openarm",
            OpenArmBimanualIKTaskConfig(
                joint_names=[f"bad_joint{i}" for i in range(14)],
                model_path=OPENARM_V10_BIMANUAL_FK_MODEL,
            ),
        )


def test_openarm_bimanual_task_rejects_missing_end_effector_frame() -> None:
    with pytest.raises(ValueError, match="no frame"):
        OpenArmBimanualIKTask(
            "teleop_openarm",
            OpenArmBimanualIKTaskConfig(
                joint_names=OPENARM_JOINTS,
                model_path=OPENARM_V10_BIMANUAL_FK_MODEL,
                left_end_effector_frame="missing_frame",
            ),
        )


def test_right_controller_pose_activates_without_left_controller_data() -> None:
    task = _task()

    assert task.on_cartesian_command(PoseStamped(frame_id="teleop_xarm"), t_now=1.0)
    assert task.is_active()


def test_coordinator_creates_xarm7_pink_task_with_teleop_route_key() -> None:
    coordinator = ControlCoordinator.__new__(ControlCoordinator)

    task = coordinator._create_task_from_config(
        TaskConfig(
            name="teleop_xarm",
            type="xarm7_pink_ik",
            joint_names=XARM7_JOINTS,
            model_path=XARM7_FK_MODEL,
            hand="right",
            pink_end_effector_frame="link7",
        )
    )

    assert isinstance(task, XArm7IKTask)
    assert task.name == "teleop_xarm"


def test_coordinator_passes_xarm7_pink_posture_config() -> None:
    coordinator = ControlCoordinator.__new__(ControlCoordinator)

    task = coordinator._create_task_from_config(
        TaskConfig(
            name="teleop_xarm",
            type="xarm7_pink_ik",
            joint_names=XARM7_JOINTS,
            model_path=XARM7_FK_MODEL,
            hand="right",
            pink_end_effector_frame="link7",
            pink_posture_cost=0.3,
            pink_posture_default_weight=0.25,
            pink_posture_joint_weights={"arm/joint2": 2.0},
            pink_posture_reference={"arm/joint3": 0.75},
            pink_posture_lm_damping=0.1,
            pink_posture_gain=0.9,
        )
    )

    assert isinstance(task, XArm7IKTask)
    assert task._config.posture_cost == 0.3
    assert task._config.posture_default_weight == 0.25
    assert task._config.posture_joint_weights == {"arm/joint2": 2.0}
    assert task._config.posture_reference == {"arm/joint3": 0.75}
    assert task._config.posture_lm_damping == 0.1
    assert task._config.posture_gain == 0.9


def test_coordinator_creates_openarm_bimanual_task_with_default_joints() -> None:
    coordinator = ControlCoordinator.__new__(ControlCoordinator)

    task = coordinator._create_task_from_config(
        TaskConfig(
            name="teleop_openarm",
            type="openarm_bimanual_pink_ik",
            model_path=OPENARM_V10_BIMANUAL_FK_MODEL,
        )
    )

    assert isinstance(task, OpenArmBimanualIKTask)
    assert task._config.joint_names == OPENARM_JOINTS


def test_xarm7_pink_task_requests_cartesian_and_button_subscriptions() -> None:
    coordinator = ControlCoordinator.__new__(ControlCoordinator)
    coordinator.config = ControlCoordinatorConfig(
        tasks=[
            TaskConfig(
                name="teleop_xarm",
                type="xarm7_pink_ik",
                joint_names=XARM7_JOINTS,
                model_path=XARM7_FK_MODEL,
                hand="right",
                pink_end_effector_frame="link7",
            )
        ]
    )

    assert coordinator._has_cartesian_target_task()
    assert coordinator._has_teleop_task()
