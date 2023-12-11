# Copyright (c) farm-ng, inc.
#
# Licensed under the Amiga Development Kit License (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://github.com/farm-ng/amiga-dev-kit/blob/main/LICENSE
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import os
from math import sqrt
from typing import Tuple

from virtual_joystick.utils import Vec2

# Must come before kivy imports
os.environ["KIVY_NO_ARGS"] = "1"

from kivy.clock import Clock  # noqa: E402
from kivy.input.providers.mouse import MouseMotionEvent  # noqa: E402
from kivy.lang.builder import Builder  # noqa: E402
from kivy.uix.widget import Widget  # noqa: E402


class VirtualJoystickWidget(Widget):
    def __init__(self, **kwargs) -> None:
        super(VirtualJoystickWidget, self).__init__(**kwargs)

        self.joystick_pose: Vec2 = Vec2()

        # Schedule the drawing of the joystick at 30 hz
        Clock.schedule_interval(self.draw_joystick, 1 / 30)

        # Build the .kv file for this VirtualJoystickWidget
        # This is so it is included when your app imports the VirtualJoystickWidget
        Builder.load_file(os.path.join(os.path.dirname(__file__), "res/joystick.kv"))

    def on_touch_down(self, touch: MouseMotionEvent) -> None:
        """Overwrite kivy method that handles initial press with mouse click or touchscreen.

        NOTE: This is called regardless of whether this is the touched widget.
        """
        # Check if touch is in this widget using kivy ``collide_point`` method
        if not self.collide_point(*touch.pos):
            return

        self.update_joystick_pose(touch)

    def on_touch_move(self, touch: MouseMotionEvent) -> None:
        """Overwrite kivy method that handles when press is held and dragged with mouse click or touchscreen.

        NOTE: This is called regardless of whether this is the touched widget.
        """
        # Check if touch is in this widget using kivy ``collide_point`` method
        if not self.collide_point(*touch.pos):
            return

        self.update_joystick_pose(touch)

    def on_touch_up(self, touch: MouseMotionEvent) -> None:
        """Overwrite kivy method that handles release of press with mouse click or touchscreen.

        NOTE: This is called regardless of whether this is the touched widget.
        """
        # Reset joystick pose, regardless of where touch_up occurs
        self.joystick_pose = Vec2()

    def update_joystick_pose(self, touch: MouseMotionEvent) -> None:
        assert self.collide_point(*touch.pos), "Only pass touches "

        res: Tuple[float, float] = self.relative_cord_in_widget(touch)

        # Clip to unit circle
        div: float = max(1.0, sqrt(res[0] ** 2 + res[1] ** 2))
        self.joystick_pose = Vec2(x=res[0] / div, y=res[1] / div)

    def relative_cord_in_widget(self, touch: MouseMotionEvent) -> Tuple[float, float]:
        """Returns the coordinates of the touch on the scale IFF it occurs within the bounds of the widget."""

        # Range to put the values on
        scale: Tuple[float, float] = (-1.0, 1.0)

        # Map coord onto scale range
        return (
            scale[0] + (touch.x - self.pos[0]) * (scale[1] - scale[0]) / (self.width),
            scale[0] + (touch.y - self.pos[1]) * (scale[1] - scale[0]) / (self.height),
        )

    def draw_joystick(self, dt: float = 0.0):
        """Update the drawn pose of the joystick, in pixel coords."""
        self.joystick_position_x = (
            self.center_x
            + 0.5 * self.joystick_pose.x * (self.width - self.joystick_diameter)
            - self.joystick_diameter // 2
        )

        self.joystick_position_y = (
            self.center_y
            + 0.5 * self.joystick_pose.y * (self.height - self.joystick_diameter)
            - self.joystick_diameter // 2
        )
