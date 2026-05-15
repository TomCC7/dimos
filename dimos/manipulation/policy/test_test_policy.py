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

"""Unit tests for the deterministic `TestPolicy` backend."""

from __future__ import annotations

import math

import pytest

from dimos.manipulation.policy import TestPolicy, create_backend
from dimos.manipulation.policy.command import JointPositionCommand
from dimos.manipulation.policy.observation import PolicyObservation


def test_sample_at_zero_is_center_for_zero_phase():
    policy = TestPolicy(joint_names=["j1", "j2"], amplitude=0.5, frequency=1.0, phase=0.0)
    sample = policy.sample_at(0.0)
    assert sample == {"j1": 0.0, "j2": 0.0}


def test_sample_at_quarter_period_hits_amplitude():
    policy = TestPolicy(joint_names=["j"], amplitude=0.7, frequency=1.0, phase=0.0)
    sample = policy.sample_at(0.25)
    assert sample["j"] == pytest.approx(0.7, abs=1e-9)


def test_per_joint_amplitude_and_phase_broadcast():
    policy = TestPolicy(
        joint_names=["a", "b", "c"],
        amplitude=[0.1, 0.2, 0.3],
        frequency=1.0,
        phase=[0.0, math.pi / 2.0, math.pi],
    )
    s = policy.sample_at(0.0)
    # phase=π/2 → sin = 1, phase=π → sin = 0
    assert s["a"] == pytest.approx(0.0, abs=1e-9)
    assert s["b"] == pytest.approx(0.2, abs=1e-9)
    assert s["c"] == pytest.approx(0.0, abs=1e-9)


def test_center_offsets_each_joint():
    policy = TestPolicy(
        joint_names=["a", "b"],
        amplitude=0.0,
        frequency=1.0,
        center=[0.4, -0.2],
    )
    s = policy.sample_at(0.123)
    assert s == {"a": 0.4, "b": -0.2}


def test_select_action_returns_joint_position_command():
    policy = TestPolicy(joint_names=["j1", "j2"], amplitude=0.1, frequency=1.0)
    policy.initialize()
    cmd = policy.select_action(PolicyObservation())
    assert isinstance(cmd, JointPositionCommand)
    assert cmd.joint_names == ("j1", "j2")
    assert len(cmd.positions) == 2


def test_reset_restarts_phase_clock_without_error():
    policy = TestPolicy(joint_names=["j"], amplitude=1.0, frequency=2.0)
    policy.initialize()
    # Multiple resets must succeed and remain idempotent.
    policy.reset()
    policy.reset()
    cmd = policy.select_action(PolicyObservation())
    assert isinstance(cmd, JointPositionCommand)


def test_test_policy_uses_registry_path():
    backend = create_backend("test", joint_names=["a", "b"], amplitude=0.3, frequency=0.5)
    backend.initialize()
    cmd = backend.select_action(PolicyObservation())
    assert isinstance(cmd, JointPositionCommand)
    assert cmd.joint_names == ("a", "b")


def test_amplitude_length_mismatch_raises():
    with pytest.raises(ValueError, match="amplitude"):
        TestPolicy(joint_names=["j1", "j2"], amplitude=[0.1, 0.2, 0.3])


def test_zero_joint_names_rejected():
    with pytest.raises(ValueError, match="at least one joint"):
        TestPolicy(joint_names=[])
