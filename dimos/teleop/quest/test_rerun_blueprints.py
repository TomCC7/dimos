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

from dimos.teleop.quest.blueprints import teleop_quest_xarm7_rerun


def test_teleop_quest_xarm7_rerun_blueprint_is_defined() -> None:
    names = {blueprint.module.__name__ for blueprint in teleop_quest_xarm7_rerun.active_blueprints}

    assert "ArmTeleopModule" in names
    assert "XArm7PinkIkDesiredState" in names
    assert "RerunUrdfRobotVisualizer" in names
