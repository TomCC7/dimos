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

"""Smoke tests for Quest Rerun teleop blueprints."""

from __future__ import annotations

from dimos.teleop.quest.blueprints import teleop_quest_openarm_rerun, teleop_quest_xarm7_rerun

LCM_MAX_CHANNEL_LENGTH = 63


def test_teleop_quest_xarm7_rerun_blueprint_is_defined() -> None:
    names = {blueprint.module.__name__ for blueprint in teleop_quest_xarm7_rerun.active_blueprints}

    assert "ArmTeleopModule" in names
    assert "XArm7PinkIkDesiredState" in names
    assert "RerunUrdfRobotVisualizer" in names


def test_teleop_quest_xarm7_rerun_uses_weighted_posture_costs() -> None:
    desired_state = next(
        blueprint
        for blueprint in teleop_quest_xarm7_rerun.active_blueprints
        if blueprint.module.__name__ == "XArm7PinkIkDesiredState"
    )

    assert desired_state.kwargs["position_cost"] == 8.0
    assert desired_state.kwargs["orientation_cost"] == 2.0
    assert desired_state.kwargs["lm_damping"] == 3.0
    assert desired_state.kwargs["posture_cost"] == 0.01
    assert desired_state.kwargs["posture_lm_damping"] == 1.0


def test_teleop_quest_openarm_rerun_blueprint_is_defined() -> None:
    names = {
        blueprint.module.__name__ for blueprint in teleop_quest_openarm_rerun.active_blueprints
    }

    assert "ArmTeleopModule" in names
    assert "OpenArmBimanualPinkIkDesiredState" in names
    assert "RerunUrdfRobotVisualizer" in names


def test_teleop_quest_openarm_rerun_lcm_channels_fit_lcm_limit() -> None:
    channels = [str(transport.topic) for transport in teleop_quest_openarm_rerun.transport_map.values()]

    assert all(len(channel) <= LCM_MAX_CHANNEL_LENGTH for channel in channels)
