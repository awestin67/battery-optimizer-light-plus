# Battery Optimizer Light
# Copyright (C) 2026 @awestin67
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

from homeassistant.const import STATE_UNKNOWN, STATE_UNAVAILABLE
from .base import BatteryApi

class GenericBattery(BatteryApi):
    def __init__(self, hass, soc_entity):
        self.hass = hass
        self.soc_entity = soc_entity

    async def get_current_soc(self) -> float | None:
        if not self.soc_entity:
            return None
        state = self.hass.states.get(self.soc_entity)
        if state and state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            try:
                return float(state.state)
            except ValueError:
                return None
        return None

    async def apply_action(self, action: str, target_kw: float = 0.0):
        pass # Gör ingenting lokalt för Generic
