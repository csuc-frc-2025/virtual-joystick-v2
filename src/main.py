# Copyright (c) farm-ng, inc. Amiga Development Kit License, Version 0.1
from __future__ import annotations

import argparse
import asyncio
import os
import logging
from pathlib import Path
from typing import Literal

from amiga_package import ops

from virtual_joystick.joystick import VirtualJoystickWidget

# import internal libs
from farm_ng.core.event_client import EventClient
from farm_ng.core.event_service_pb2 import EventServiceConfig
from farm_ng.core.event_service_pb2 import EventServiceConfigList
from farm_ng.core.event_service_pb2 import SubscribeRequest
from farm_ng.core.events_file_reader import proto_from_json_file
from farm_ng.core.uri_pb2 import Uri

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

from turbojpeg import TurboJPEG
from kornia_rs import ImageDecoder

logger = logging.getLogger("amiga.apps.camera")


class KivyVirtualJoystick(App):
    """Base class for the main Kivy app."""
    amiga_state = StringProperty("???")
    amiga_speed = StringProperty("???")
    amiga_rate = StringProperty("???")

    STREAM_NAMES = ["rgb", "disparity", "left", "right"]


    def __init__(self, service_config: EventServiceConfig, stream_every_n: int) -> None:
        super().__init__()

        self.counter: int = 0

        self.service_config = service_config
        self.stream_every_n = stream_every_n

        self.async_tasks: list[asyncio.Task] = []

        self.image_decoder = ImageDecoder()
        self.view_name = 'rgb'

        print(EventServiceConfigList)

        # self.image_decoder = TurboJPEG('/mnt/managed_home/farm-ng-user-oliverfuchs/virtual-joystick-kivy/venv/lib/python3.8/site-packages/turbojpeg.py')

    def build(self):
        return Builder.load_file("res/main.kv")

    def on_exit_btn(self) -> None:
        """Kills the running kivy application."""
        App.get_running_app().stop()
    
    def update_view(self, view_name: str):
        print(view_name)
        self.view_name = view_name

    async def app_func(self):
        async def run_wrapper() -> None:
            # we don't actually need to set asyncio as the lib because it is
            # the default, but it doesn't hurt to be explicit
            await self.async_run(async_lib="asyncio")
            for task in self.async_tasks:
                task.cancel()

        # Camera task
        print(self.view_name)
        self.async_tasks: list[asyncio.Task] = [       
            asyncio.create_task(self.stream_camera(view_name))
            for view_name in self.STREAM_NAMES
        ]

        return await asyncio.gather(run_wrapper(), *self.async_tasks)

    async def stream_camera(
        self, view_name: Literal["rgb", "disparity", "left", "right"] = "rgb"
    ) -> None:
        """Subscribes to the camera service and populates the tabbed panel with all 4 image streams."""
        while self.root is None:
            await asyncio.sleep(0.01)
        print("how often does this happen")
        async for _, message in EventClient(self.service_config).subscribe(
            SubscribeRequest(
                uri=Uri(path=f"/{view_name}"), every_n=self.stream_every_n
            ),
            decode=True,
        ):
            print("can you read this: " + self.view_name)
            print(f"/{view_name}")
            
            try:
                img = self.image_decoder.decode(message.image_data)
            except Exception as e:
                logger.exception(f"Error decoding image: {e}")
                continue

            # create the opengl texture and set it to the image
            texture = Texture.create(size=(img.shape[1], img.shape[0]), icolorfmt="rgb")
            texture.flip_vertical()
            texture.blit_buffer(
                bytes(img.data),
                colorfmt="rgb",
                bufferfmt="ubyte",
                mipmap_generation=False,
            )
            self.root.ids[view_name].texture = texture

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
    parser.add_argument(
        "--service-config", type=Path, default="/opt/farmng/config.json"
    )
    parser.add_argument("--camera-name", type=str, default="oak1")
    parser.add_argument(
        "--stream-every-n", type=int, default=1, help="Streaming frequency"
    )
    args = parser.parse_args()

    service_config_list: EventServiceConfigList = proto_from_json_file(
        args.service_config, EventServiceConfigList()
    )

    oak_service_config = find_config_by_name(service_config_list, args.camera_name)
    # print(oak_service_config)
    if oak_service_config is None:
        raise RuntimeError(f"Could not find service config for {args.camera_name}")

    loop = asyncio.get_event_loop()

    try:
        loop.run_until_complete(KivyVirtualJoystick(oak_service_config, args.stream_every_n).app_func())
    except asyncio.CancelledError:
        pass
    loop.close()
