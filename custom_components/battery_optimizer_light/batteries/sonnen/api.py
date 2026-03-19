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


"""API-klient för Sonnen Batteri."""
import logging
import aiohttp

API_STATUS = "/api/v2/status"
API_CONFIG = "/api/v2/configurations"

_LOGGER = logging.getLogger(__name__)

class SonnenAPI:
    """Klass för att kommunicera med Sonnen API V2."""

    def __init__(self, host, port, token, session: aiohttp.ClientSession):
        self._host = host.replace("http://", "").replace("https://", "").rstrip("/")
        self._port = port
        self._token = token
        self._session = session
        self._base_url = f"http://{self._host}:{port}"
        self._headers = {
            "Auth-Token": self._token,
            "Content-Type": "application/json"
        }

    async def async_get_status(self):
        """Hämtar status."""
        url = f"{self._base_url}{API_STATUS}"
        try:
            async with self._session.get(url, headers=self._headers) as response:
                response.raise_for_status()
                return await response.json()
        except Exception as e:
            _LOGGER.debug("Kunde inte hämta data från Sonnen: %s", e)
            raise

    async def async_set_operating_mode(self, mode: int):
        """Sätter driftläge."""
        url = f"{self._base_url}{API_CONFIG}"
        payload = {"EM_OperatingMode": str(mode)}

        try:
            async with self._session.put(url, json=payload, headers=self._headers) as response:
                response.raise_for_status()
                return True
        except Exception as e:
            _LOGGER.error("Fel vid ändring av driftläge: %s", e)
            return False

    async def async_charge(self, power: int):
        """Skicka laddningskommando."""
        url = f"{self._base_url}/api/v2/setpoint/charge/{power}"
        try:
            async with self._session.post(url, json={}, headers=self._headers) as response:
                response.raise_for_status()
                return True
        except Exception as e:
            _LOGGER.error("Fel vid skickande av laddningskommando: %s", e)
            return False

    async def async_discharge(self, power: int):
        """Skicka urladdningskommando."""
        url = f"{self._base_url}/api/v2/setpoint/discharge/{power}"
        try:
            async with self._session.post(url, json={}, headers=self._headers) as response:
                response.raise_for_status()
                return True
        except Exception as e:
            _LOGGER.error("Fel vid skickande av urladdningskommando: %s", e)
            return False
