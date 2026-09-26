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
import asyncio
import logging
import aiohttp

API_STATUS = "/api/v2/status"
API_CONFIG = "/api/v2/configurations"
API_SITE_CONFIG = "/api/v2/site/configurations"
API_SITE_LIMITS = "/api/v2/site/limits"
API_SITE_SETPOINT = "/api/v2/site/setpoint"
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
        self._last_em_usoc: str | None = None
        self._last_operating_mode: str | None = None
        self.site_limits_supported: bool = True
        self._site_limits_em2_logged: bool = False

    async def async_get_status(self):
        """Hämtar status och konfiguration."""
        url = f"{self._base_url}{API_STATUS}"
        config_url = f"{self._base_url}{API_CONFIG}"
        try:
            async with self._session.get(url, headers=self._headers) as response:
                response.raise_for_status()
                status_data = await response.json()

            # Hämta även konfiguration för att få EM_USOC (Backup-reserv), EM_OperatingMode och DE_Software
            try:
                async with self._session.get(config_url, headers=self._headers) as conf_response:
                    if conf_response.status == 200:
                        conf_data = await conf_response.json(content_type=None)
                        if isinstance(conf_data, dict):
                            if "EM_USOC" in conf_data:
                                status_data["EM_USOC"] = conf_data["EM_USOC"]
                                self._last_em_usoc = str(conf_data["EM_USOC"])
                            if "EM_OperatingMode" in conf_data:
                                status_data["EM_OperatingMode"] = str(conf_data["EM_OperatingMode"])
                                self._last_operating_mode = str(conf_data["EM_OperatingMode"])
                            if "DE_Software" in conf_data:
                                status_data["DE_Software"] = conf_data["DE_Software"]
            except Exception as conf_e:
                _LOGGER.debug("Kunde inte hämta konfiguration från Sonnen: %s", conf_e)

            return status_data
        except Exception as e:
            _LOGGER.debug("Kunde inte hämta data från Sonnen: %s", e)
            raise

    async def async_set_operating_mode(self, mode: int) -> bool:
        """Sätter driftläge via /api/v2/site/configurations (med fallback till /api/v2/configurations)."""
        mode_str = str(mode)
        headers_json = {"Auth-Token": self._token, "Content-Type": "application/json"}
        headers_form = {"Auth-Token": self._token}

        # 1. Prova först det officiella EMS Site Configurations API:et (application/json)
        site_config_url = f"{self._base_url}{API_SITE_CONFIG}"
        site_payloads = []
        if self._last_em_usoc is not None:
            site_payloads.append({"EM_OperatingMode": mode_str, "EM_USOC": self._last_em_usoc})
        site_payloads.append({"EM_OperatingMode": mode_str})

        for payload in site_payloads:
            try:
                async with self._session.put(
                    site_config_url, json=payload, headers=headers_json, timeout=aiohttp.ClientTimeout(total=5)
                ) as resp:
                    resp_text = ""
                    try:
                        resp_text = await resp.text()
                    except Exception:
                        pass
                    if resp.status in (200, 204):
                        _LOGGER.info(
                            "Sonnen satte driftläge %s via %s: %s (payload: %s)",
                            mode,
                            API_SITE_CONFIG,
                            resp_text,
                            payload,
                        )
                        self._last_operating_mode = mode_str
                        return True
                    _LOGGER.debug(
                        "Sonnen PUT %s returnerade status %s: %s (payload: %s), provar nästa",
                        API_SITE_CONFIG,
                        resp.status,
                        resp_text,
                        payload,
                    )
            except Exception as e:
                _LOGGER.debug("Kunde inte sätta driftläge via %s: %s (payload: %s)", API_SITE_CONFIG, e, payload)

        # 2. Fallback: Prova legacy /api/v2/configurations med application/x-www-form-urlencoded
        config_url = f"{self._base_url}{API_CONFIG}"
        form_data = {"EM_OperatingMode": mode_str}
        try:
            async with self._session.put(
                config_url, data=form_data, headers=headers_form, timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                resp_text = ""
                try:
                    resp_text = await resp.text()
                except Exception:
                    pass
                if resp.status in (200, 204):
                    _LOGGER.info(
                        "Sonnen satte driftläge %s via form-encoded %s: status %s, body: '%s'",
                        mode,
                        API_CONFIG,
                        resp.status,
                        resp_text,
                    )
                    self._last_operating_mode = mode_str
                    return True
                _LOGGER.warning(
                    "Sonnen PUT form-encoded %s returnerade status %s: %s",
                    API_CONFIG,
                    resp.status,
                    resp_text,
                )
        except Exception as e:
            _LOGGER.warning("Kunde inte sätta driftläge via form-encoded %s: %s", API_CONFIG, e)

        # 3. Fallback: Prova legacy /api/v2/configurations med JSON (om äldre firmware kräver JSON)
        try:
            async with self._session.put(
                config_url,
                json={"EM_OperatingMode": mode_str},
                headers=headers_json,
                timeout=aiohttp.ClientTimeout(total=5),
            ) as resp:
                resp_text = ""
                try:
                    resp_text = await resp.text()
                except Exception:
                    pass
                if resp.status in (200, 204):
                    _LOGGER.info(
                        "Sonnen satte driftläge %s via JSON %s: status %s, body: '%s'",
                        mode,
                        API_CONFIG,
                        resp.status,
                        resp_text,
                    )
                    self._last_operating_mode = mode_str
                    return True
        except Exception as e:
            _LOGGER.debug("Kunde inte sätta driftläge via JSON %s: %s", API_CONFIG, e)

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
        """Hämtar firmware-version från DE_Software eller configurations."""
        url = f"{self._base_url}{API_CONFIG_SOFTWARE}"
        try:
            async with self._session.get(url, headers=self._headers, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    try:
                        data = await resp.json(content_type=None)
                        if isinstance(data, dict) and "DE_Software" in data:
                            return str(data["DE_Software"]).strip()
                        elif isinstance(data, (str, int, float)):
                            return str(data).strip()
                    except Exception:
                        text = (await resp.text()).strip().strip('"')
                        if text:
                            return text
                else:
                    _LOGGER.info(
                        "Sonnen GET %s returnerade status %s, provar fallback till %s",
                        API_CONFIG_SOFTWARE,
                        resp.status,
                        API_CONFIG,
                    )
        except Exception as e:
            _LOGGER.info(
                "Kunde inte nå %s: %s (provar fallback till %s)",
                API_CONFIG_SOFTWARE,
                e,
                API_CONFIG,
            )

        # Fallback: hämta från full konfiguration /api/v2/configurations
        conf_url = f"{self._base_url}{API_CONFIG}"
        try:
            async with self._session.get(
                conf_url, headers=self._headers, timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status == 200:
                    conf_data = await resp.json(content_type=None)
                    if isinstance(conf_data, dict) and "DE_Software" in conf_data:
                        return str(conf_data["DE_Software"]).strip()
                else:
                    _LOGGER.warning(
                        "Sonnen GET %s returnerade status %s: %s",
                        API_CONFIG,
                        resp.status,
                        await resp.text(),
                    )
        except Exception as e:
            _LOGGER.warning("Kunde inte hämta konfiguration från %s: %s", API_CONFIG, e)

        return None

    async def async_set_site_limits(self, limits: dict) -> bool:
        """Sätter site power limits via PUT /api/v2/site/limits."""
        if not self.site_limits_supported:
            return False

        url = f"{self._base_url}{API_SITE_LIMITS}"
        try:
            limit_keys = {
                "p_gcp_max_import_limit",
                "p_gcp_max_export_limit",
                "p_bess_inv_max_export_limit",
                "p_bess_inv_max_import_limit",
                "i_bess_storage_max_charge_limit",
                "i_bess_storage_max_discharge_limit",
            }
            # Rensa bort None-värden och casta numeriska limits till int (<int32>) enligt Sonnens Swagger-schema
            payload = {}
            for k, v in limits.items():
                if k in limit_keys:
                    if v is not None:
                        try:
                            payload[k] = round(float(v))
                        except (ValueError, TypeError):
                            payload[k] = v
                elif k == "duration":
                    payload[k] = str(v)

            # Säkerställ sekundformat (PT600S för 10 minuter) då Sonnens Swagger kräver PT...S
            if "duration" not in payload or payload.get("duration") in ("PT90S", "PT10M"):
                payload["duration"] = "PT600S"

            # Sonnen Swagger specificerar: "At least one limit must be specified."
            # Om inga specifika gränser anges returnerar Sonnen 400 Bad Request.
            if not any(k in payload for k in limit_keys):
                _LOGGER.debug(
                    "Inga specifika site limits i payloaden (%s), hoppar över anrop till PutSiteLimits",
                    limits,
                )
                return True

            async with self._session.put(
                url, json=payload, headers=self._headers, timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status in (200, 204):
                    _LOGGER.info(
                        "Sonnen satte Site Limits via %s: %s (status %s)",
                        API_SITE_LIMITS,
                        payload,
                        resp.status,
                    )
                    return True
                try:
                    resp_text = await resp.text()
                except Exception:
                    resp_text = ""

                # Om Sonnen svarar att EM2 krävs: sätt Mode 2, vänta och prova en retry
                if "EM2" in resp_text:
                    if not self._site_limits_em2_logged:
                        _LOGGER.info(
                            "Sonnen meddelar att Site Limits kräver EM2. Försöker säkerställa Mode 2 och provar igen..."
                        )
                    mode_set = await self.async_set_operating_mode(2)
                    if not mode_set:
                        if not self._site_limits_em2_logged:
                            _LOGGER.warning(
                                "Kunde inte sätta Sonnen i Mode 2 (EM2). "
                                "Avaktiverar Site Limits och växlar till standardstyrning."
                            )
                            self._site_limits_em2_logged = True
                        self.site_limits_supported = False
                        return False

                    await asyncio.sleep(0.5)

                    async with self._session.put(
                        url, json=payload, headers=self._headers, timeout=aiohttp.ClientTimeout(total=5)
                    ) as retry_resp:
                        if retry_resp.status in (200, 204):
                            _LOGGER.info("Sonnen PutSiteLimits lyckades efter växling till Mode 2!")
                            return True
                        try:
                            retry_text = await retry_resp.text()
                        except Exception:
                            retry_text = ""

                        if not self._site_limits_em2_logged:
                            _LOGGER.info(
                                "Sonnen tillåter inte dynamisk styrning via Site Limits (%s: %s). "
                                "Växlar automatiskt till beprövad standard Sonnen-styrning (Manual Mode setpoints).",
                                retry_resp.status,
                                retry_text.strip(),
                            )
                            self._site_limits_em2_logged = True
                        self.site_limits_supported = False
                        return False

                _LOGGER.warning(
                    "Sonnen PutSiteLimits returnerade status %s: %s (payload: %s)",
                    resp.status,
                    resp_text,
                    payload,
                )

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
