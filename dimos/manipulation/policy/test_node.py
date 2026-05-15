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

"""Unit tests for `PolicyNode`.

These tests exercise observation assembly, command validation, the
joint-state publish path, and the teleop-takeover behavior. We drive the
internal `_on_*` handlers and `_tick_once()` directly rather than going
through the LCM-backed transport so the tests stay fast and hermetic.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pytest

from dimos.manipulation.policy import (
    JointPositionCommand,
    NoOpCommand,
    PolicyNode,
    PolicyNodeConfig,
    PolicyObservation,
    register_backend,
)
from dimos.msgs.sensor_msgs.Image import Image, ImageFormat
from dimos.msgs.sensor_msgs.JointState import JointState
from dimos.teleop.quest.quest_types import Buttons


def _img(seed: int = 0) -> Image:
    arr = np.full((4, 4, 3), seed, dtype=np.uint8)
    return Image(data=arr, format=ImageFormat.RGB)


class _RecordingBackend:
    """Test backend that records every call and emits a fixed command."""

    def __init__(
        self,
        joint_names: Sequence[str],
        positions: Sequence[float] | None = None,
    ) -> None:
        self.joint_names = tuple(joint_names)
        self._positions = tuple(positions or [0.0] * len(joint_names))
        self.observations: list[PolicyObservation] = []
        self.init_calls = 0
        self.reset_calls = 0
        self.close_calls = 0
        self._next_command: JointPositionCommand | NoOpCommand | None = None

    def initialize(self) -> None:
        self.init_calls += 1

    def select_action(self, observation: PolicyObservation) -> JointPositionCommand | NoOpCommand:
        self.observations.append(observation)
        if self._next_command is not None:
            cmd = self._next_command
            return cmd
        return JointPositionCommand(joint_names=self.joint_names, positions=self._positions)

    def queue(self, command: JointPositionCommand | NoOpCommand) -> None:
        self._next_command = command

    def reset(self) -> None:
        self.reset_calls += 1
        self._next_command = None  # mirror "drop buffered chunk"

    def close(self) -> None:
        self.close_calls += 1


@pytest.fixture
def node_factory(request):
    """Create PolicyNode + injected backend pairs and clean each up on teardown."""
    created: list[PolicyNode] = []

    def _make(*, backend_name: str, **config_overrides) -> tuple[PolicyNode, _RecordingBackend]:
        backend = _RecordingBackend(
            joint_names=config_overrides.pop("backend_joint_names", ("j1", "j2")),
            positions=config_overrides.pop("backend_positions", (0.1, 0.2)),
        )
        register_backend(backend_name, lambda **_: backend)

        cfg_kwargs = dict(
            backend=backend_name,
            policy_rate=200.0,
            joint_names=["j1", "j2"],
            camera_sources={"image": "main"},
        )
        cfg_kwargs.update(config_overrides)

        node = PolicyNode(**cfg_kwargs)
        node._backend = backend
        created.append(node)
        return node, backend

    yield _make

    for n in created:
        try:
            n._close_module()
        except Exception:
            pass


# ── 6.3 observation assembly ──────────────────────────────────────────────


def test_observation_assembly_with_multi_camera_inputs(node_factory):
    node, _ = node_factory(
        backend_name="__test_assembly__",
        camera_sources={"image": "main", "image_aux1": "wrist"},
    )
    node._on_image("main", _img(seed=1))
    node._on_image("wrist", _img(seed=2))
    node._on_joint_state(JointState(name=["j1", "j2"], position=[0.1, 0.2]))
    node._on_task_description("pick up the cube")

    obs = node.assemble_observation()
    assert sorted(obs.images.keys()) == ["main", "wrist"]
    assert obs.joint_state is not None
    assert obs.joint_state.name == ["j1", "j2"]
    assert obs.task == "pick up the cube"


def test_default_task_used_when_no_task_input_arrived(node_factory):
    node, _ = node_factory(
        backend_name="__test_default_task__",
        default_task="open the drawer",
    )
    obs = node.assemble_observation()
    assert obs.task == "open the drawer"


# ── 6.4 command validation + JointState.position publishing ───────────────


def test_publishes_joint_state_with_matching_positions(node_factory):
    node, backend = node_factory(
        backend_name="__test_publish__",
        backend_positions=(0.4, 0.5),
    )

    published: list[JointState] = []
    node.joint_command.subscribe(published.append)

    node._on_joint_state(JointState(name=["j1", "j2"], position=[0.0, 0.0]))
    cmd = node._tick_once()
    assert isinstance(cmd, JointPositionCommand)

    assert len(published) == 1
    msg = published[0]
    assert msg.name == ["j1", "j2"]
    assert msg.position == [0.4, 0.5]


def test_rejects_command_with_unmatched_joint_names(node_factory):
    node, backend = node_factory(backend_name="__test_unmatched__")
    backend.joint_names = ("foreign_j",)
    backend._positions = (1.0,)

    published: list[JointState] = []
    node.joint_command.subscribe(published.append)

    node._on_joint_state(JointState(name=["j1"], position=[0.0]))
    node._tick_once()
    assert published == []  # rejected


def test_rejects_command_when_command_mode_disabled(node_factory):
    node, _ = node_factory(
        backend_name="__test_disabled_mode__",
        enabled_command_modes=[],
    )

    published: list[JointState] = []
    node.joint_command.subscribe(published.append)

    node._on_joint_state(JointState(name=["j1", "j2"], position=[0.0, 0.0]))
    node._tick_once()
    assert published == []


def test_noop_command_does_not_publish(node_factory):
    node, backend = node_factory(backend_name="__test_noop__")
    backend.queue(NoOpCommand(reason="explicit no-op"))

    published: list[JointState] = []
    node.joint_command.subscribe(published.append)

    node._on_joint_state(JointState(name=["j1", "j2"], position=[0.0, 0.0]))
    node._tick_once()
    assert published == []


def test_skips_step_when_no_joint_state_yet(node_factory):
    node, backend = node_factory(backend_name="__test_no_js__")
    cmd = node._tick_once()
    assert cmd is None
    assert backend.observations == []


def test_joint_name_map_is_applied_before_validation(node_factory):
    node, backend = node_factory(
        backend_name="__test_map__",
        joint_name_map={"raw1": "j1", "raw2": "j2"},
    )
    backend.joint_names = ("raw1", "raw2")
    backend._positions = (0.1, 0.2)

    published: list[JointState] = []
    node.joint_command.subscribe(published.append)

    node._on_joint_state(JointState(name=["j1", "j2"], position=[0.0, 0.0]))
    node._tick_once()
    assert len(published) == 1
    assert published[0].name == ["j1", "j2"]


# ── 6.6 teleop takeover ───────────────────────────────────────────────────


def test_engage_button_suspends_publication_and_resets_backend(node_factory):
    node, backend = node_factory(backend_name="__test_engage__")

    published: list[JointState] = []
    node.joint_command.subscribe(published.append)

    node._on_joint_state(JointState(name=["j1", "j2"], position=[0.0, 0.0]))
    node._tick_once()
    assert len(published) == 1
    pre_resets = backend.reset_calls

    # Engage event: simulate the right-primary button going high.
    btns = Buttons()
    btns.right_primary = True
    node._on_buttons(btns)
    assert backend.reset_calls == pre_resets + 1
    assert node.is_engaged() is True

    cmd = node._tick_once()
    assert cmd is None
    assert len(published) == 1  # no new publication while engaged


def test_disengage_resumes_publication_with_fresh_select_action(node_factory):
    node, backend = node_factory(backend_name="__test_disengage__")

    published: list[JointState] = []
    node.joint_command.subscribe(published.append)

    node._on_joint_state(JointState(name=["j1", "j2"], position=[0.0, 0.0]))

    # Pre-engage: simulate the backend buffering a stale chunk that would
    # be replayed at the next select_action call if `reset()` did not run.
    backend.queue(JointPositionCommand(joint_names=("j1", "j2"), positions=(9.9, 9.9)))

    # Engage event triggers backend.reset() → buffered chunk dropped.
    btns_engaged = Buttons()
    btns_engaged.right_primary = True
    node._on_buttons(btns_engaged)
    assert backend.reset_calls == 1

    # During engagement, no commands are published.
    node._tick_once()
    assert published == []

    # Disengage and run one tick: the next select_action call must return
    # a fresh command computed from the current observation, not the
    # pre-engage buffered (9.9, 9.9) chunk.
    btns_idle = Buttons()
    node._on_buttons(btns_idle)
    assert node.is_engaged() is False

    obs_count_before = len(backend.observations)
    node._tick_once()
    assert len(backend.observations) == obs_count_before + 1
    assert len(published) == 1
    assert published[0].position == [0.1, 0.2]  # default, not the 9.9 stale


def test_engage_then_repeated_engage_only_resets_once_per_edge(node_factory):
    node, backend = node_factory(backend_name="__test_edge__")

    btns_engaged = Buttons()
    btns_engaged.right_primary = True

    pre = backend.reset_calls
    node._on_buttons(btns_engaged)
    node._on_buttons(btns_engaged)  # held
    node._on_buttons(btns_engaged)  # held
    assert backend.reset_calls == pre + 1


# ── config validation ────────────────────────────────────────────────────


def test_unknown_camera_slot_in_config_raises():
    with pytest.raises(Exception, match="image slot"):
        PolicyNodeConfig(
            backend="test",
            joint_names=["j1"],
            camera_sources={"not_a_real_slot": "main"},
        )


def test_unsupported_command_mode_raises():
    with pytest.raises(Exception, match="enabled_command_modes|joint_position"):
        PolicyNodeConfig(
            backend="test",
            joint_names=["j1"],
            enabled_command_modes=["cartesian"],
        )
