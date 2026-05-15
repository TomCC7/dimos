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

"""Deterministic sinusoidal `PolicyBackend` for wiring/integration tests.

`TestPolicy` requires no model files, no GPU, and no third-party
robot-learning packages. It produces joint position commands that follow
``center + amplitude * sin(2π · frequency · t + phase)`` per joint.

The backend's "time" is the wall-clock elapsed since the most recent
`reset()` (or `initialize()`), so calling `reset()` deterministically
restarts the trajectory from phase 0.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import math
import time

from dimos.manipulation.policy.command import JointPositionCommand, PolicyCommand
from dimos.manipulation.policy.observation import PolicyObservation


class TestPolicy:
    """Sinusoidal joint position backend used for tests and dry runs.

    Args:
        joint_names: Joint names to emit positions for, in order.
        amplitude: Per-joint amplitude (radians or meters depending on
            joint type). Scalar broadcasts to every joint.
        frequency: Per-joint sinusoid frequency in Hz. Scalar broadcasts.
        phase: Per-joint phase offset in radians. Scalar broadcasts.
        center: Optional per-joint center value. ``None`` is treated as
            ``0.0`` for every joint. A scalar broadcasts.
    """

    # Tell pytest this is not a test class despite the `Test` prefix.
    __test__ = False

    def __init__(
        self,
        *,
        joint_names: Sequence[str],
        amplitude: float | Sequence[float] = 0.1,
        frequency: float | Sequence[float] = 0.5,
        phase: float | Sequence[float] = 0.0,
        center: float | Sequence[float] | None = None,
    ) -> None:
        if not joint_names:
            raise ValueError("TestPolicy requires at least one joint name")

        self._joint_names: tuple[str, ...] = tuple(joint_names)
        n = len(self._joint_names)
        self._amplitude: tuple[float, ...] = self._broadcast(amplitude, n, "amplitude")
        self._frequency: tuple[float, ...] = self._broadcast(frequency, n, "frequency")
        self._phase: tuple[float, ...] = self._broadcast(phase, n, "phase")
        center_seq: float | Sequence[float] = 0.0 if center is None else center
        self._center: tuple[float, ...] = self._broadcast(center_seq, n, "center")

        self._t0: float = time.monotonic()

    @staticmethod
    def _broadcast(value: float | Sequence[float], n: int, name: str) -> tuple[float, ...]:
        if isinstance(value, (int, float)):
            return tuple(float(value) for _ in range(n))
        seq = tuple(float(v) for v in value)
        if len(seq) != n:
            raise ValueError(
                f"TestPolicy.{name}: expected scalar or length-{n} sequence, got length {len(seq)}"
            )
        return seq

    @property
    def joint_names(self) -> tuple[str, ...]:
        return self._joint_names

    def initialize(self) -> None:
        """Reset the phase clock so the first inference starts at t=0."""
        self._t0 = time.monotonic()

    def select_action(self, observation: PolicyObservation) -> PolicyCommand:
        del observation  # TestPolicy is open-loop on purpose.
        return JointPositionCommand(
            joint_names=self._joint_names,
            positions=self._sample_at(time.monotonic() - self._t0),
        )

    def _sample_at(self, t: float) -> tuple[float, ...]:
        two_pi = 2.0 * math.pi
        return tuple(
            c + a * math.sin(two_pi * f * t + p)
            for c, a, f, p in zip(
                self._center, self._amplitude, self._frequency, self._phase, strict=True
            )
        )

    # Exposed for unit tests so behavior can be checked deterministically
    # without sleeping.
    def sample_at(self, t: float) -> Mapping[str, float]:
        """Return the position each joint would take at time `t` (seconds
        since the last `reset()` / `initialize()`)."""
        return dict(zip(self._joint_names, self._sample_at(t), strict=True))

    def reset(self) -> None:
        """Restart the sinusoid phase clock from zero."""
        self._t0 = time.monotonic()

    def close(self) -> None:
        """No-op — `TestPolicy` holds no external resources."""


__all__ = ["TestPolicy"]
