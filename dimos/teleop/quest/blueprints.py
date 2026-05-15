#!/usr/bin/env python3
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

"""Teleop blueprints for testing and deployment.

Single sim/real blueprints — pass `--simulation` to run inside MuJoCo, omit for
real hardware. The underlying coordinator blueprints branch on
`global_config.simulation`.
"""

import math

from dimos.control.blueprints.teleop import (
    coordinator_teleop_dual,
    coordinator_teleop_piper,
    coordinator_teleop_piper_with_policy,
    coordinator_teleop_xarm6,
    coordinator_teleop_xarm7,
    is_xarm7_mock_preview,
    piper_policy_joint_names,
    piper_policy_overlapping_teleop_tasks,
    piper_teleop_robot_model_config,
    xarm7_teleop_robot_model_config,
)
from dimos.core.coordination.blueprints import autoconnect
from dimos.core.transport import LCMTransport
from dimos.hardware.sensors.camera.module import CameraModule
from dimos.manipulation.manipulation_module import ManipulationModule
from dimos.manipulation.policy import (
    PolicyNode,
    RolloutToggle,
    policy_engage_buttons,
)
from dimos.msgs.geometry_msgs.PoseStamped import PoseStamped
from dimos.msgs.sensor_msgs.Image import Image
from dimos.msgs.sensor_msgs.JointState import JointState
from dimos.teleop.quest.data_collection_vis import piper_data_collection_rerun_config
from dimos.teleop.quest.episode_boundary import EpisodeBoundary
from dimos.teleop.quest.quest_extensions import ArmTeleopModule
from dimos.teleop.quest.quest_types import Buttons
from dimos.visualization.rerun.recorder import RerunDataRecorder
from dimos.visualization.vis_module import vis_module

# Arm teleop with press-and-hold engage (has rerun viz)
teleop_quest_rerun = autoconnect(
    ArmTeleopModule.blueprint(),
    vis_module("rerun"),
).transports(
    {
        ("left_controller_output", PoseStamped): LCMTransport("/teleop/left_delta", PoseStamped),
        ("right_controller_output", PoseStamped): LCMTransport("/teleop/right_delta", PoseStamped),
        ("buttons", Buttons): LCMTransport("/teleop/buttons", Buttons),
    }
)


# XArm7 teleop (mock Meshcat preview by default, real with IP, MuJoCo with --simulation):
# right controller -> xarm7.
teleop_quest_xarm7 = autoconnect(
    ArmTeleopModule.blueprint(task_names={"right": "teleop_xarm"}),
    coordinator_teleop_xarm7,
    *(
        (
            ManipulationModule.blueprint(
                robots=[xarm7_teleop_robot_model_config()],
                enable_viz=True,
            ),
        )
        if is_xarm7_mock_preview
        else ()
    ),
).transports(
    {
        ("joint_state", JointState): LCMTransport("/coordinator/joint_state", JointState),
        ("right_controller_output", PoseStamped): LCMTransport(
            "/coordinator/cartesian_command", PoseStamped
        ),
        ("buttons", Buttons): LCMTransport("/teleop/buttons", Buttons),
    }
)


# Piper teleop (ManipulationModule viz on hardware/mock, MuJoCo with --simulation):
# right controller -> piper arm.
teleop_quest_piper = autoconnect(
    ArmTeleopModule.blueprint(task_names={"right": "teleop_piper"}),
    coordinator_teleop_piper,
    ManipulationModule.blueprint(
        robots=[piper_teleop_robot_model_config()],
        enable_viz=True,
    ),
).transports(
    {
        ("joint_state", JointState): LCMTransport("/coordinator/joint_state", JointState),
        ("right_controller_output", PoseStamped): LCMTransport(
            "/coordinator/cartesian_command", PoseStamped
        ),
        ("buttons", Buttons): LCMTransport("/teleop/buttons", Buttons),
    }
)

# Piper teleop data collection: right controller -> piper arm, with USB camera
# observation plus measured state / desired action streams. A live Rerun viewer
# and a standalone on-disk `.rrd` recorder are wired as independent sinks that
# share a single `piper_data_collection_rerun_config()` instance — guaranteeing
# the viewer and the recorder cannot drift at wiring time. Rolling over to the
# next episode within a session is operator-driven via `EpisodeBoundary`
# (right-controller A by default), which calls `recorder.rotate_recording()`.
_data_collection_rerun_config = piper_data_collection_rerun_config()
# Subset of `_data_collection_rerun_config` accepted by RerunBridgeModule.Config.
_DATA_COLLECTION_BRIDGE_KEYS = (
    "visual_override",
    "entity_prefix",
    "topic_to_entity",
    "blueprint",
)
# Subset of `_data_collection_rerun_config` accepted by RerunDataRecorderConfig.
_DATA_COLLECTION_RECORDER_KEYS = (
    "visual_override",
    "entity_prefix",
    "topic_to_entity",
    "record_path_factory",
    "recording_id_factory",
    "episode_metadata",
)
teleop_quest_piper_data_collection = autoconnect(
    ArmTeleopModule.blueprint(task_names={"right": "teleop_piper"}),
    coordinator_teleop_piper,
    CameraModule.blueprint(),
    RerunDataRecorder.blueprint(
        **{k: _data_collection_rerun_config[k] for k in _DATA_COLLECTION_RECORDER_KEYS}
    ),
    EpisodeBoundary.blueprint(),
    ManipulationModule.blueprint(
        robots=[piper_teleop_robot_model_config()],
        enable_viz=True,
    ),
    vis_module(
        "rerun",
        rerun_config={k: _data_collection_rerun_config[k] for k in _DATA_COLLECTION_BRIDGE_KEYS},
    ),
).transports(
    {
        ("joint_state", JointState): LCMTransport("/coordinator/joint_state", JointState),
        ("desired_joint_action", JointState): LCMTransport(
            "/coordinator/desired_joint_action", JointState
        ),
        ("right_controller_output", PoseStamped): LCMTransport(
            "/coordinator/cartesian_command", PoseStamped
        ),
        ("buttons", Buttons): LCMTransport("/teleop/buttons", Buttons),
        ("color_image", Image): LCMTransport("/piper_data_collection/color_image", Image),
    }
)

# Piper teleop + policy deployment (no data collection): right controller -> piper
# arm via Pink IK; a low-priority servo task on the same joints accepts policy
# joint commands. The PolicyNode is gated by `RolloutToggle` (left_secondary by
# default) and preempted by `right_primary` (teleop engage). The `TestPolicy`
# backend with amplitude=0 emits constant-position commands so the first wiring
# run is a no-motion shakedown — change `backend` / `backend_config` to swap in
# a LeRobot model.
_piper_policy_joints = piper_policy_joint_names()
_piper_policy_engage_buttons = policy_engage_buttons(
    _piper_policy_joints, piper_policy_overlapping_teleop_tasks()
)

teleop_quest_piper_policy = (
    autoconnect(
        ArmTeleopModule.blueprint(task_names={"right": "teleop_piper"}),
        coordinator_teleop_piper_with_policy,
        CameraModule.blueprint(),
        PolicyNode.blueprint(
            backend="test",
            backend_config={
                "joint_names": _piper_policy_joints,
                # 6 arm joints get a visible ~8.5° (0.15 rad) swing; the
                # gripper (last entry) stays small to avoid slamming.
                "amplitude": [0.15, 0.15, 0.15, 0.15, 0.15, 0.15, 0.01],
                "frequency": 0.3,
                # Staggered phases produce a wave across joints so the motion
                # is visually distinct rather than synchronized.
                "phase": [
                    0.0,
                    math.pi / 6,
                    math.pi / 3,
                    math.pi / 2,
                    2 * math.pi / 3,
                    5 * math.pi / 6,
                    0.0,
                ],
            },
            policy_rate=10.0,
            joint_names=_piper_policy_joints,
            camera_sources={"image": "main"},
            teleop_engage_buttons=_piper_policy_engage_buttons,
            default_task="run policy",
        ),
        RolloutToggle.blueprint(),
        ManipulationModule.blueprint(
            robots=[piper_teleop_robot_model_config()],
            enable_viz=True,
        ),
    )
    .remappings(
        [
            # CameraModule publishes `color_image`; PolicyNode listens on `image`.
            (PolicyNode, "image", "color_image"),
        ],
    )
    .transports(
        {
            ("joint_state", JointState): LCMTransport("/coordinator/joint_state", JointState),
            ("right_controller_output", PoseStamped): LCMTransport(
                "/coordinator/cartesian_command", PoseStamped
            ),
            ("buttons", Buttons): LCMTransport("/teleop/buttons", Buttons),
            ("color_image", Image): LCMTransport("/piper_policy/color_image", Image),
            ("joint_command", JointState): LCMTransport("/coordinator/joint_command", JointState),
        }
    )
)


# XArm6 teleop (sim with --simulation, real otherwise): right controller -> xarm6
teleop_quest_xarm6 = autoconnect(
    ArmTeleopModule.blueprint(task_names={"right": "teleop_xarm"}),
    coordinator_teleop_xarm6,
).transports(
    {
        ("right_controller_output", PoseStamped): LCMTransport(
            "/coordinator/cartesian_command", PoseStamped
        ),
        ("buttons", Buttons): LCMTransport("/teleop/buttons", Buttons),
    }
)


# Dual arm teleop: right -> piper, left -> xarm6 (TeleopIK, real-only)
teleop_quest_dual = autoconnect(
    ArmTeleopModule.blueprint(task_names={"right": "teleop_piper", "left": "teleop_xarm"}),
    coordinator_teleop_dual,
).transports(
    {
        ("right_controller_output", PoseStamped): LCMTransport(
            "/coordinator/cartesian_command", PoseStamped
        ),
        ("left_controller_output", PoseStamped): LCMTransport(
            "/coordinator/cartesian_command", PoseStamped
        ),
        ("buttons", Buttons): LCMTransport("/teleop/buttons", Buttons),
    }
)


__all__ = [
    "teleop_quest_dual",
    "teleop_quest_piper",
    "teleop_quest_piper_data_collection",
    "teleop_quest_piper_policy",
    "teleop_quest_rerun",
    "teleop_quest_xarm6",
    "teleop_quest_xarm7",
]
