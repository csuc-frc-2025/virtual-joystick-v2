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


class Vec2:
    """Simple container for keeping joystick coords in x & y terms.

    Defaults to a centered joystick (0,0). Clips values to range [-1.0, 1.0], as with the Amiga joystick.
    """

    def __init__(self, x: float = 0.0, y: float = 0.0) -> None:
        self.x: float = min(max(-1.0, x), 1.0)
        self.y: float = min(max(-1.0, y), 1.0)

    def __str__(self) -> str:
        return f"({self.x:0.2f}, {self.y:0.2f})"
