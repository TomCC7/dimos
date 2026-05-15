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

"""`PolicyNode` DimOS module.

Connects multi-camera images, the latest robot joint state, a task
description, and the teleop `Buttons` stream to a configured
`PolicyBackend`. Runs inference at `PolicyNodeConfig.policy_rate` on its
own thread (kept off the `ControlCoordinator` tick loop) and publishes
joint position commands as `JointState` on `joint_command`.

Teleop preempts: when any button in `teleop_engage_buttons` goes high,
publication is suspended and `backend.reset()` is called. On disengage,
publication resumes from a fresh `select_action()` against the current
observation; pre-engage buffered actions are never replayed.
"""

from __future__ import annotations

from collections.abc import Mapping
import threading
import time
from typing import TYPE_CHECKING, Any

from dimos.core.core import rpc
from dimos.core.module import Module
from dimos.core.stream import In, Out

# Importing the backends package registers built-in backends ("test",
# "lerobot") on the shared registry. Without this import, fresh sessions
# would only see backends registered by the caller.
import dimos.manipulation.policy.backends  # noqa: F401
from dimos.manipulation.policy.command import (
    JointPositionCommand,
    NoOpCommand,
    PolicyCommand,
)
from dimos.manipulation.policy.config import ALLOWED_CAMERA_SLOTS, CommandMode, PolicyNodeConfig
from dimos.manipulation.policy.observation import PolicyObservation
from dimos.manipulation.policy.registry import create_backend
from dimos.msgs.sensor_msgs.Image import Image
from dimos.msgs.sensor_msgs.JointState import JointState
from dimos.teleop.quest.quest_types import Buttons
from dimos.utils.logging_config import setup_logger

if TYPE_CHECKING:
    from collections.abc import Callable

    from dimos.manipulation.policy.backend import PolicyBackend

    _ImageHandler = Callable[[Image], None]

logger = setup_logger()


# Slot names on the node that may be connected to camera streams. Mirrored
# from `PolicyNodeConfig.ALLOWED_CAMERA_SLOTS` for runtime use; keep the
# `In[Image]` annotations on `PolicyNode` in sync if you change this list.
_IMAGE_SLOT_NAMES: tuple[str, ...] = ALLOWED_CAMERA_SLOTS


class PolicyNode(Module):
    """Streams perception → policy → coordinator-native commands.

    Inputs:
        image, image_aux1, image_aux2: Camera image slots. Each slot maps
            via `PolicyNodeConfig.camera_sources` to a key in the
            `PolicyObservation.images` dict the backend receives.
        joint_state: Latest robot joint state.
        task_description: Plain text task. Falls back to
            `PolicyNodeConfig.default_task` when no value has arrived.
        buttons: Teleop button state used to detect engage/disengage and
            preempt the policy.

    Output:
        joint_command: `JointState` whose `name`/`position` are wired to
            `ControlCoordinator.joint_command`.
    """

    config: PolicyNodeConfig

    image: In[Image]
    image_aux1: In[Image]
    image_aux2: In[Image]
    joint_state: In[JointState]
    task_description: In[str]
    buttons: In[Buttons]

    joint_command: Out[JointState]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

        self._latest_lock = threading.Lock()
        self._latest_images: dict[str, Image] = {}
        self._latest_joint_state: JointState | None = None
        self._latest_joint_state_ts: float = 0.0
        self._latest_task: str | None = None
        self._latest_buttons: Buttons | None = None

        self._engage_lock = threading.Lock()
        self._engaged: bool = False
        self._engage_pending_reset: bool = False

        self._backend: PolicyBackend | None = None
        self._backend_lock = threading.Lock()

        self._inference_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._unsub: list[Any] = []

    # ── lifecycle ─────────────────────────────────────────────────────────

    @rpc
    def start(self) -> None:
        super().start()
        with self._backend_lock:
            self._backend = create_backend(self.config.backend, **self.config.backend_config)
            self._backend.initialize()

        self._subscribe_inputs()

        self._stop_event.clear()
        thread = threading.Thread(
            target=self._inference_loop,
            name=f"policy-node[{self.config.backend}]",
            daemon=True,
        )
        self._inference_thread = thread
        thread.start()
        logger.info(
            f"PolicyNode started: backend={self.config.backend} rate={self.config.policy_rate}Hz"
        )

    @rpc
    def stop(self) -> None:
        self._stop_event.set()
        for unsub in self._unsub:
            try:
                unsub()
            except Exception:
                logger.exception("PolicyNode: error unsubscribing input")
        self._unsub = []

        thread = self._inference_thread
        self._inference_thread = None
        if thread is not None and thread.is_alive():
            thread.join(timeout=2.0)

        with self._backend_lock:
            backend = self._backend
            self._backend = None
        if backend is not None:
            try:
                backend.close()
            except Exception:
                logger.exception("PolicyNode: backend.close() raised")

        super().stop()
        logger.info("PolicyNode stopped")

    # ── input subscription ────────────────────────────────────────────────

    def _subscribe_inputs(self) -> None:
        for slot in _IMAGE_SLOT_NAMES:
            if slot not in self.config.camera_sources:
                continue
            stream: In[Image] = getattr(self, slot)
            cam_key = self.config.camera_sources[slot]
            try:
                self._unsub.append(stream.subscribe(self._make_image_handler(cam_key)))
            except Exception:
                logger.warning(f"PolicyNode: could not subscribe to image slot '{slot}'")

        try:
            self._unsub.append(self.joint_state.subscribe(self._on_joint_state))
        except Exception:
            logger.warning("PolicyNode: could not subscribe to joint_state")

        try:
            self._unsub.append(self.task_description.subscribe(self._on_task_description))
        except Exception:
            logger.debug("PolicyNode: task_description not connected")

        try:
            self._unsub.append(self.buttons.subscribe(self._on_buttons))
        except Exception:
            logger.debug("PolicyNode: buttons not connected (no teleop preempt)")

    def _make_image_handler(self, camera_key: str) -> _ImageHandler:
        def _handle(msg: Image) -> None:
            self._on_image(camera_key, msg)

        return _handle

    # ── handlers (also called directly from unit tests) ───────────────────

    def _on_image(self, camera_key: str, msg: Image) -> None:
        with self._latest_lock:
            self._latest_images[camera_key] = msg

    def _on_joint_state(self, msg: JointState) -> None:
        with self._latest_lock:
            self._latest_joint_state = msg
            self._latest_joint_state_ts = time.time()

    def _on_task_description(self, msg: str) -> None:
        with self._latest_lock:
            self._latest_task = msg

    def _on_buttons(self, msg: Buttons) -> None:
        with self._latest_lock:
            self._latest_buttons = msg
        engaged_now = self._is_engaged(msg)
        with self._engage_lock:
            was_engaged = self._engaged
            self._engaged = engaged_now
            if engaged_now and not was_engaged:
                self._engage_pending_reset = True

        if engaged_now and not was_engaged:
            self._reset_backend("teleop engaged")

    def _is_engaged(self, buttons: Buttons) -> bool:
        for field in self.config.teleop_engage_buttons:
            if getattr(buttons, field, False):
                return True
        return False

    # ── observation assembly ──────────────────────────────────────────────

    def assemble_observation(self) -> PolicyObservation:
        """Snapshot the latest inputs into a `PolicyObservation`.

        Public so blueprint examples and tests can build observations
        directly without going through the inference thread.
        """
        with self._latest_lock:
            images = dict(self._latest_images)
            joint_state = self._latest_joint_state
            task = self._latest_task
            joint_ts = self._latest_joint_state_ts
        if task is None:
            task = self.config.default_task
        return PolicyObservation(
            images=images,
            joint_state=joint_state,
            task=task,
            timestamp=joint_ts,
        )

    # ── inference loop ────────────────────────────────────────────────────

    def _inference_loop(self) -> None:
        rate = max(0.1, float(self.config.policy_rate))
        period = 1.0 / rate

        while not self._stop_event.is_set():
            t0 = time.monotonic()
            try:
                self._tick_once()
            except Exception:
                logger.exception("PolicyNode: tick_once raised")
            elapsed = time.monotonic() - t0
            sleep = period - elapsed
            if sleep > 0:
                # Use Event.wait so stop() can interrupt the sleep promptly.
                self._stop_event.wait(timeout=sleep)

    def _tick_once(self) -> PolicyCommand | None:
        """Run a single inference step.

        Returns the command produced (`PolicyCommand`) for testing, or
        `None` if the step was skipped (preempted, missing inputs, or
        backend not yet initialized).
        """
        with self._engage_lock:
            if self._engaged:
                return None

        backend = self._backend
        if backend is None:
            return None

        observation = self.assemble_observation()
        if observation.joint_state is None:
            return None

        if self.config.observation_max_age > 0.0:
            age = time.time() - observation.timestamp
            if age > self.config.observation_max_age:
                logger.warning(
                    f"PolicyNode: skipping tick, joint_state age {age:.3f}s exceeds "
                    f"observation_max_age {self.config.observation_max_age:.3f}s"
                )
                return None

        try:
            command = backend.select_action(observation)
        except Exception:
            logger.exception("PolicyNode: backend.select_action raised")
            return None

        self._publish_if_valid(command)
        return command

    # ── command validation + publishing ───────────────────────────────────

    def _publish_if_valid(self, command: PolicyCommand) -> None:
        if isinstance(command, NoOpCommand):
            if command.reason:
                logger.debug(f"PolicyNode: backend no-op ({command.reason})")
            return

        if isinstance(command, JointPositionCommand):
            if "joint_position" not in self.config.enabled_command_modes:
                logger.warning(
                    "PolicyNode: backend returned joint_position but the command mode "
                    "is not enabled in PolicyNodeConfig.enabled_command_modes"
                )
                return
            joint_state = self._joint_position_command_to_joint_state(command)
            if joint_state is None:
                return
            self.joint_command.publish(joint_state)
            return

        logger.warning(
            f"PolicyNode: unsupported PolicyCommand kind '{getattr(command, 'kind', '?')}'"
        )

    def _joint_position_command_to_joint_state(
        self, command: JointPositionCommand
    ) -> JointState | None:
        try:
            mapped_names = [self._map_joint_name(n) for n in command.joint_names]
        except KeyError as exc:
            logger.warning(f"PolicyNode: rejecting command with unmapped joint {exc}")
            return None

        configured = list(self.config.joint_names)
        if configured:
            if list(mapped_names) != configured:
                logger.warning(
                    "PolicyNode: rejecting command — backend joints do not match "
                    f"PolicyNodeConfig.joint_names\n  backend: {list(mapped_names)}\n  "
                    f"configured: {configured}"
                )
                return None

        return JointState(
            name=list(mapped_names),
            position=list(command.positions),
            frame_id=self.frame_id,
        )

    def _map_joint_name(self, name: str) -> str:
        return self.config.joint_name_map.get(name, name)

    # ── teleop preempt support ────────────────────────────────────────────

    def _reset_backend(self, reason: str) -> None:
        backend = self._backend
        if backend is None:
            return
        try:
            backend.reset()
            logger.info(f"PolicyNode: backend.reset() called ({reason})")
        except Exception:
            logger.exception("PolicyNode: backend.reset() raised")

    # ── test/inspection helpers ───────────────────────────────────────────

    def latest(self) -> Mapping[str, Any]:
        """Snapshot of the latest cached inputs (for tests/diagnostics)."""
        with self._latest_lock:
            return {
                "images": dict(self._latest_images),
                "joint_state": self._latest_joint_state,
                "task": self._latest_task,
                "buttons": self._latest_buttons,
            }

    def is_engaged(self) -> bool:
        """Return whether teleop is currently treated as engaged."""
        with self._engage_lock:
            return self._engaged


__all__ = ["CommandMode", "PolicyNode", "PolicyNodeConfig"]
