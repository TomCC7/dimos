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

Single sim/real blueprints — pass `--simulation` to run inside MuJoCo, omit for real
hardware. The underlying coordinator blueprints branch on `global_config.simulation`.
"""

from dimos.control.blueprints.teleop import (
    coordinator_teleop_dual,
    coordinator_teleop_piper,
    coordinator_teleop_xarm6,
    coordinator_teleop_xarm7,
)
from dimos.control.pink_ik_visualization import (
    OpenArmBimanualPinkIkDesiredState,
    XArm7PinkIkDesiredState,
)
from dimos.core.coordination.blueprints import autoconnect
from dimos.core.transport import LCMTransport
from dimos.msgs.geometry_msgs.PoseStamped import PoseStamped
from dimos.msgs.sensor_msgs.JointState import JointState
from dimos.robot.catalog.openarm import OPENARM_V10_BIMANUAL_FK_MODEL
from dimos.robot.catalog.ufactory import XARM7_FK_MODEL
from dimos.teleop.quest.quest_extensions import ArmTeleopModule
from dimos.teleop.quest.quest_types import Buttons
from dimos.visualization.rerun.urdf_robot import RerunUrdfRobotVisualizer
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


# XArm7 teleop (sim with --simulation, real otherwise): right controller -> xarm7
teleop_quest_xarm7 = autoconnect(
    ArmTeleopModule.blueprint(task_names={"right": "teleop_xarm"}),
    coordinator_teleop_xarm7,
).transports(
    {
        ("right_controller_output", PoseStamped): LCMTransport(
            "/coordinator/cartesian_command", PoseStamped
        ),
        ("buttons", Buttons): LCMTransport("/teleop/buttons", Buttons),
    }
)


# XArm7 teleop Rerun debug path: right controller -> Pink IK desired joints -> URDF robot.
teleop_quest_xarm7_rerun = autoconnect(
    ArmTeleopModule.blueprint(task_names={"right": "teleop_xarm"}),
    XArm7PinkIkDesiredState.blueprint(
        position_cost=8.0,
        orientation_cost=2.0,
        lm_damping=3.0,
        posture_cost=0.01,
        posture_lm_damping=1.0,
    ),
    RerunUrdfRobotVisualizer.blueprint(
        urdf_path=XARM7_FK_MODEL,
        entity_path_prefix="world/xarm7_desired",
        end_effector_frame="link7",
        desired_controller_entity_path="world/debug/xarm7/desired_controller",
        desired_target_entity_path="world/debug/xarm7/desired_target",
        end_effector_entity_path="world/debug/xarm7/desired_end_effector",
    ),
    vis_module("rerun"),
).transports(
    {
        ("right_controller_output", PoseStamped): LCMTransport(
            "/coordinator/cartesian_command", PoseStamped
        ),
        ("cartesian_command", PoseStamped): LCMTransport(
            "/coordinator/cartesian_command", PoseStamped
        ),
        ("buttons", Buttons): LCMTransport("/teleop/buttons", Buttons),
        ("desired_joint_state", JointState): LCMTransport(
            "/teleop/xarm7/desired_joint_state", JointState
        ),
        ("joint_state", JointState): LCMTransport("/teleop/xarm7/desired_joint_state", JointState),
    }
)


# OpenArm bimanual teleop Rerun debug path: left/right controllers -> one Pink IK solve.
teleop_quest_openarm_rerun = autoconnect(
    ArmTeleopModule.blueprint(
        task_names={"left": "teleop_openarm_left", "right": "teleop_openarm_right"}
    ),
    OpenArmBimanualPinkIkDesiredState.blueprint(),
    RerunUrdfRobotVisualizer.blueprint(
        urdf_path=OPENARM_V10_BIMANUAL_FK_MODEL,
        entity_path_prefix="world/openarm_desired",
        desired_controller_entity_path="world/debug/openarm/desired_controller",
        desired_target_entity_path="world/debug/openarm/desired_target",
        end_effector_entity_path="world/debug/openarm/desired_end_effector",
        route_debug_poses_by_frame_id=True,
    ),
    vis_module("rerun"),
).transports(
    {
        ("left_controller_output", PoseStamped): LCMTransport("/teleop/openarm/cmd", PoseStamped),
        ("right_controller_output", PoseStamped): LCMTransport("/teleop/openarm/cmd", PoseStamped),
        ("cartesian_command", PoseStamped): LCMTransport("/teleop/openarm/cmd", PoseStamped),
        ("desired_controller_pose", PoseStamped): LCMTransport(
            "/teleop/openarm/ctrl", PoseStamped
        ),
        ("desired_target_pose", PoseStamped): LCMTransport(
            "/teleop/openarm/tgt", PoseStamped
        ),
        ("end_effector_pose", PoseStamped): LCMTransport("/teleop/openarm/ee", PoseStamped),
        ("buttons", Buttons): LCMTransport("/teleop/buttons", Buttons),
        ("desired_joint_state", JointState): LCMTransport("/teleop/openarm/joints", JointState),
        ("joint_state", JointState): LCMTransport("/teleop/openarm/joints", JointState),
    }
)


# Piper teleop (sim with --simulation, real otherwise): left controller -> piper arm
teleop_quest_piper = autoconnect(
    ArmTeleopModule.blueprint(task_names={"left": "teleop_piper"}),
    coordinator_teleop_piper,
).transports(
    {
        ("left_controller_output", PoseStamped): LCMTransport(
            "/coordinator/cartesian_command", PoseStamped
        ),
        ("buttons", Buttons): LCMTransport("/teleop/buttons", Buttons),
    }
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
    "teleop_quest_openarm_rerun",
    "teleop_quest_piper",
    "teleop_quest_rerun",
    "teleop_quest_xarm6",
    "teleop_quest_xarm7",
    "teleop_quest_xarm7_rerun",
]
