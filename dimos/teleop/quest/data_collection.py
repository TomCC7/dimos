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

from datetime import datetime, timezone

from pydantic import Field
from reactivex.disposable import Disposable

from dimos.core.core import rpc
from dimos.core.module import Module, ModuleConfig
from dimos.core.stream import In
from dimos.msgs.sensor_msgs.Image import Image
from dimos.msgs.sensor_msgs.JointState import JointState
from dimos.utils.testing.replay import TimedSensorStorage


def default_recording_name() -> str:
    timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"piper_data_collection/{timestamp}"


class PiperDataRecorderConfig(ModuleConfig):
    recording_name: str = Field(default_factory=default_recording_name)
    camera_stream_name: str = "observation.images.usb"
    state_stream_name: str = "observation.state"
    action_stream_name: str = "action"


class PiperDataRecorder(Module):
    config: PiperDataRecorderConfig

    color_image: In[Image]
    joint_state: In[JointState]
    desired_joint_action: In[JointState]

    @rpc
    def start(self) -> None:
        super().start()

        camera_store = TimedSensorStorage(
            f"{self.config.recording_name}/{self.config.camera_stream_name}"
        )
        state_store = TimedSensorStorage(
            f"{self.config.recording_name}/{self.config.state_stream_name}"
        )
        action_store = TimedSensorStorage(
            f"{self.config.recording_name}/{self.config.action_stream_name}"
        )

        self.register_disposable(Disposable(self.color_image.subscribe(camera_store.save)))
        self.register_disposable(Disposable(self.joint_state.subscribe(state_store.save)))
        self.register_disposable(Disposable(self.desired_joint_action.subscribe(action_store.save)))


__all__ = ["PiperDataRecorder", "PiperDataRecorderConfig", "default_recording_name"]
