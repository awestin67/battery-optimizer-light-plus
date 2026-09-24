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
API_SITE_LIMITS = "/api/v2/site/limits"
API_CONFIG_SOFTWARE = "/api/v2/configurations/DE_Software"

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
        """Hämtar status och konfiguration."""
        url = f"{self._base_url}{API_STATUS}"
        config_url = f"{self._base_url}{API_CONFIG}"
        try:
            async with self._session.get(url, headers=self._headers) as response:
                response.raise_for_status()
                status_data = await response.json()

            # Hämta även konfiguration för att få EM_USOC (Backup-reserv)
            try:
                async with self._session.get(config_url, headers=self._headers) as conf_response:
                    if conf_response.status == 200:
                        conf_data = await conf_response.json()
                        if "EM_USOC" in conf_data:
                            status_data["EM_USOC"] = conf_data["EM_USOC"]
            except Exception as conf_e:
                _LOGGER.debug("Kunde inte hämta konfiguration (EM_USOC) från Sonnen: %s", conf_e)

            return status_data
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

    async def async_get_software_version(self) -> str | None:
        """Hämtar firmware-version från DE_Software."""
        url = f"{self._base_url}{API_CONFIG_SOFTWARE}"
        try:
            async with self._session.get(url, headers=self._headers, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if isinstance(data, dict):
                        return data.get("DE_Software")
                    elif isinstance(data, str):
                        return data
        except Exception as e:
            _LOGGER.debug("Kunde inte hämta DE_Software från Sonnen: %s", e)
        return None

    async def async_set_site_limits(self, limits: dict) -> bool:
        """Sätter site power limits via PUT /api/v2/site/limits."""
        url = f"{self._base_url}{API_SITE_LIMITS}"
        try:
            # Rensa bort eventuella None-värden
            payload = {k: v for k, v in limits.items() if v is not None}
            # Säkerställ längre duration än koordinators 5 minuter (standard PT10M)
            if "duration" not in payload or payload.get("duration") == "PT90S":
                payload["duration"] = "PT10M"

            async with self._session.put(
                url, json=payload, headers=self._headers, timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status in (200, 204):
                    return True
                _LOGGER.warning("Sonnen PutSiteLimits returnerade status %s: %s", resp.status, await resp.text())
                return False
        except Exception as e:
            _LOGGER.error("Fel vid anrop till Sonnen PutSiteLimits: %s", e)
            return False

    async def async_get_site_limits(self) -> dict | None:
        """Hämtar aktiva site limits via GET /api/v2/site/limits."""
        url = f"{self._base_url}{API_SITE_LIMITS}"
        try:
            async with self._session.get(url, headers=self._headers, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    return await resp.json()
        except Exception as e:
            _LOGGER.debug("Kunde inte hämta aktiva site limits från Sonnen: %s", e)
        return None
