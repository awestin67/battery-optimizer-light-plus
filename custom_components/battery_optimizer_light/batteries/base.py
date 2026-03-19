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

from abc import ABC, abstractmethod

class BatteryApi(ABC):
    """Gemensamt gränssnitt för alla batterityper i Optimizer Light."""

    @abstractmethod
    async def get_current_soc(self) -> float | None:
        """Hämtar aktuell SoC (State of Charge)."""
        pass

    @abstractmethod
    async def apply_action(self, action: str, target_kw: float = 0.0):
        """
        Verkställer ett beslut från molnet eller lokalt.
        action: 'CHARGE', 'DISCHARGE', 'HOLD', 'IDLE'
        target_kw: Måleffekt i kW (t.ex. 5.0 för 5000W).
        """
        pass

    # --- Bekvämlighetsmetoder för PeakGuard och Tjänster ---
    # Du behöver inte skriva över dessa i dina batteriklasser,
    # de dirigerar automatiskt vidare till apply_action!
    async def force_charge(self, power_w: int):
        await self.apply_action("CHARGE", power_w / 1000.0)

    async def force_discharge(self, power_w: int):
        await self.apply_action("DISCHARGE", power_w / 1000.0)

    async def hold(self):
        await self.apply_action("HOLD", 0.0)

    async def set_auto_mode(self):
        await self.apply_action("IDLE", 0.0)
