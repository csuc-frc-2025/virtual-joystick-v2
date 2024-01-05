# Copyright (c) farm-ng, inc. Amiga Development Kit License, Version 0.1
from __future__ import annotations

import argparse
import asyncio
import logging
import os
from pathlib import Path
from typing import Literal

from farm_ng.canbus.canbus_pb2 import Twist2d
from farm_ng.canbus.packet import AmigaControlState
from farm_ng.canbus.packet import AmigaTpdo1
from farm_ng.core.event_client import EventClient
from farm_ng.core.event_service_pb2 import EventServiceConfig
from farm_ng.core.event_service_pb2 import EventServiceConfigList
from farm_ng.core.event_service_pb2 import SubscribeRequest
from farm_ng.core.events_file_reader import payload_to_protobuf
from farm_ng.core.events_file_reader import proto_from_json_file
from farm_ng.core.uri_pb2 import Uri
from turbojpeg import TurboJPEG

from virtual_joystick.joystick import VirtualJoystickWidget

# import internal libs

# Must come before kivy imports
os.environ["KIVY_NO_ARGS"] = "1"

# gui configs must go before any other kivy import
from kivy.config import Config  # noreorder # noqa: E402

Config.set("graphics", "resizable", False)
Config.set("graphics", "width", "1280")
Config.set("graphics", "height", "800")
Config.set("graphics", "fullscreen", "false")
Config.set("input", "mouse", "mouse,disable_on_activity")
Config.set("kivy", "keyboard_mode", "systemanddock")

# kivy imports
from kivy.app import App  # noqa: E402
from kivy.graphics.texture import Texture  # noqa: E402
from kivy.lang.builder import Builder  # noqa: E402
from kivy.properties import StringProperty  # noqa: E402


logger = logging.getLogger("amiga.apps.camera")

MAX_LINEAR_VELOCITY_MPS = 0.5
MAX_ANGULAR_VELOCITY_RPS = 0.5
VELOCITY_INCREMENT = 0.05


class KivyVirtualJoystick(App):
    """Base class for the main Kivy app."""

    amiga_state = StringProperty("???")
    amiga_speed = StringProperty("???")
    amiga_rate = StringProperty("???")

    STREAM_NAMES = ["rgb", "disparity", "left", "right"]

    def __init__(
        self,
        service_config: EventServiceConfig,
    ) -> None:
        super().__init__()

        self.counter: int = 0

        self.service_config = service_config

        self.async_tasks: list[asyncio.Task] = []

        self.image_decoder = TurboJPEG()

        self.view_name = "rgb"

        self.max_speed: float = 1.0
        self.max_angular_rate: float = 1.0

    def build(self):
        return Builder.load_file("res/main.kv")

    def on_exit_btn(self) -> None:
        """Kills the running kivy application."""
        for task in self.tasks:
            task.cancel()
        App.get_running_app().stop()

    def update_view(self, view_name: str):
        self.view_name = view_name

    async def app_func(self):

        async def run_wrapper() -> None:
            # we don't actually need to set asyncio as the lib because it is
            # the default, but it doesn't hurt to be explicit
            await self.async_run(async_lib="asyncio")
            for task in self.async_tasks:
                task.cancel()

        config_list = proto_from_json_file(
            self.service_config, EventServiceConfigList()
        )

        oak0_client: EventClient | None = None
        canbus_client: EventClient | None = None


        for config in config_list.configs:
            if config.name == "oak0":
                oak0_client = EventClient(config)
            elif config.name == "canbus":
                canbus_client = EventClient(config)


        # Confirm that EventClients were created for all required services
        if None in [oak0_client,canbus_client]:
            raise RuntimeError(
                f"No {config} service config in {self.service_config}"
            )

        # Camera task
        self.tasks: list[asyncio.Task] = [
            asyncio.create_task(self.stream_camera(oak0_client, view_name))
            for view_name in self.STREAM_NAMES
        ]

        self.tasks.append(asyncio.create_task(self.pose_generator(canbus_client)))

        return await asyncio.gather(run_wrapper(),*self.tasks)

    async def stream_camera(
        self,
        oak_client: EventClient,
        view_name: Literal["rgb", "disparity", "left", "right"] = "rgb",
    ) -> None:

        """Subscribes to the camera service and populates the tabbed panel with all 4 image streams."""
        while self.root is None:
            await asyncio.sleep(0.01)

        rate = oak_client.config.subscriptions[0].every_n

        async for event, payload in oak_client.subscribe(
            SubscribeRequest(
                uri=Uri(path=f"/{view_name}"), every_n=rate
            ),
            decode=False,
        ):
            if view_name == self.view_name:
                message = payload_to_protobuf(event, payload)
                try:
                    img = self.image_decoder.decode(message.image_data)
                except Exception as e:
                    logger.exception(f"Error decoding image: {e}")
                    continue

                # create the opengl texture and set it to the image
                texture = Texture.create(
                    size=(img.shape[1], img.shape[0]), icolorfmt="rgb"
                )
                texture.flip_vertical()
                texture.blit_buffer(
                    bytes(img.data),
                    colorfmt="rgb",
                    bufferfmt="ubyte",
                    mipmap_generation=False,
                )
                self.root.ids[view_name].texture = texture

    async def pose_generator(self, canbus_client: EventClient, period: float = 0.02):
        """The pose generator yields an AmigaRpdo1 (auto control command) for the canbus client to send on the bus
        at the specified period (recommended 50hz) based on the onscreen joystick position."""
        while self.root is None:
            await asyncio.sleep(0.01)

        twist = Twist2d()
        
        joystick: VirtualJoystickWidget = self.root.ids["joystick"]

        rate = canbus_client.config.subscriptions[0].every_n

        async for event, payload in canbus_client.subscribe(
            SubscribeRequest(uri=Uri(path="/state"), every_n=rate),
            decode=False,
        ):
            message = payload_to_protobuf(event, payload)
            tpdo1 = AmigaTpdo1.from_proto(message.amiga_tpdo1)

            twist.linear_velocity_x = self.max_speed * joystick.joystick_pose.y
            twist.angular_velocity = self.max_angular_rate * -joystick.joystick_pose.x

            self.amiga_state = tpdo1.state.name
            self.amiga_speed = "{:.4f}".format(twist.linear_velocity_x)
            self.amiga_rate = "{:.4f}".format(twist.angular_velocity)

            await canbus_client.request_reply("/twist", twist)
            await asyncio.sleep(period)


def find_config_by_name(
    service_configs: EventServiceConfigList, name: str
) -> EventServiceConfig | None:
    """Utility function to find a service config by name.

    Args:
        service_configs: List of service configs
        name: Name of the service to find
    """
    for config in service_configs.configs:
        if config.name == name:
            return config
    return None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="template-app")

    # Add additional command line arguments here
    parser.add_argument("--service-config", type=Path, default="service_config.json")

    args = parser.parse_args()

    loop = asyncio.get_event_loop()

    try:
        loop.run_until_complete(KivyVirtualJoystick(args.service_config).app_func())
    except asyncio.CancelledError:
        pass
    loop.close()
