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
import pytest

from dimos.control.coordinator import ControlCoordinator, ControlCoordinatorConfig, TaskConfig
from dimos.control.task import ControlMode, CoordinatorState, JointStateSnapshot
from dimos.control.tasks import pink_teleop_task
from dimos.control.tasks.pink_teleop_task import XArm7IKTask, XArm7IKTaskConfig
from dimos.msgs.geometry_msgs.PoseStamped import PoseStamped
from dimos.robot.catalog.ufactory import XARM7_FK_MODEL

XARM7_JOINTS = [f"arm/joint{i}" for i in range(1, 8)]


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
) -> XArm7IKTask:
    config = XArm7IKTaskConfig(
        joint_names=XARM7_JOINTS,
        model_path=XARM7_FK_MODEL,
        timeout=timeout,
        max_joint_delta_deg=max_joint_delta_deg,
        gripper_joint=gripper_joint,
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


def test_inactive_state_returns_no_command() -> None:
    task = _task()

    assert task.compute(_state()) is None


def test_unsafe_joint_delta_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    task = _task(max_joint_delta_deg=1.0)
    task.on_cartesian_command(PoseStamped(frame_id="teleop_xarm"), t_now=1.0)

    def large_velocity(*_args: object, **_kwargs: object) -> np.ndarray:
        return np.ones(7) * 100.0

    monkeypatch.setattr(pink_teleop_task, "solve_ik", large_velocity)

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
