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

from __future__ import annotations

from typing import Any

from dimos.teleop.quest import data_collection
from dimos.teleop.quest.data_collection import PiperDataRecorder


def test_piper_data_recorder_uses_stable_storage_paths(monkeypatch: Any) -> None:
    storage_names: list[str] = []
    subscribed_streams: list[str] = []

    class FakeStorage:
        def __init__(self, name: str) -> None:
            storage_names.append(name)

        def save(self, *_args: object) -> None:
            pass

    def subscribe_for(name: str):  # type: ignore[no-untyped-def]
        def subscribe(_cb: object) -> None:
            subscribed_streams.append(name)

        return subscribe

    monkeypatch.setattr(data_collection, "TimedSensorStorage", FakeStorage)

    recorder = PiperDataRecorder(recording_name="session")
    recorder.color_image.subscribe = subscribe_for("color_image")  # type: ignore[method-assign]
    recorder.joint_state.subscribe = subscribe_for("joint_state")  # type: ignore[method-assign]
    recorder.desired_joint_action.subscribe = subscribe_for("desired_joint_action")  # type: ignore[method-assign]

    recorder.start()
    recorder.stop()

    assert storage_names == [
        "session/observation.images.usb",
        "session/observation.state",
        "session/action",
    ]
    assert subscribed_streams == ["color_image", "joint_state", "desired_joint_action"]
