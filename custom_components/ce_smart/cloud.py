"""Tuya OpenAPI cloud wrapper and coordinator for CE Smart.

Cloud mode talks to the Tuya OpenAPI using the user's *own* IoT project
credentials (access id + secret) with an app account linked on the Tuya
portal. All HTTP is done by the blocking tuya-iot-py-sdk, so calls are run in
an executor from the coordinator.
"""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from tuya_iot import TuyaOpenAPI

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CLOUD_ENDPOINTS,
    CONF_ACCESS_ID,
    CONF_ACCESS_SECRET,
    CONF_REGION,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

DEVICES_PATH = "/v1.0/iot-01/associated-users/devices"


class CeSmartCloudError(Exception):
    """Raised on any cloud authentication or request failure."""


class CeSmartCloudApi:
    """Blocking wrapper around TuyaOpenAPI. Call from an executor only."""

    def __init__(self, region: str, access_id: str, access_secret: str) -> None:
        """Store credentials and build the (unconnected) OpenAPI client."""
        endpoint = CLOUD_ENDPOINTS.get(region, CLOUD_ENDPOINTS["us"])
        self._api = TuyaOpenAPI(endpoint, access_id, access_secret)

    def connect(self) -> None:
        """Obtain an access token; raise on failure."""
        try:
            resp = self._api.connect()
        except Exception as err:  # noqa: BLE001 - sdk raises bare exceptions
            raise CeSmartCloudError(f"Connection error: {err}") from err
        if not isinstance(resp, dict) or not resp.get("success", False):
            msg = (resp or {}).get("msg", "authentication failed") if isinstance(resp, dict) else "authentication failed"
            raise CeSmartCloudError(msg)

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        try:
            resp = self._api.get(path, params or {})
        except Exception as err:  # noqa: BLE001
            raise CeSmartCloudError(str(err)) from err
        if not isinstance(resp, dict) or not resp.get("success", False):
            raise CeSmartCloudError((resp or {}).get("msg", "request failed"))
        return resp.get("result")

    def list_devices(self) -> dict[str, dict[str, Any]]:
        """Return {device_id: {info..., 'status': {code: value}}}."""
        result = self._get(DEVICES_PATH, {"size": 100})
        if isinstance(result, dict):
            raw = result.get("devices", [])
        elif isinstance(result, list):
            raw = result
        else:
            raw = []

        devices: dict[str, dict[str, Any]] = {}
        for dev in raw:
            dev_id = dev.get("id")
            if not dev_id:
                continue
            status = {
                item["code"]: item["value"]
                for item in dev.get("status", [])
                if "code" in item and "value" in item
            }
            devices[dev_id] = {
                "id": dev_id,
                "name": dev.get("name") or dev.get("product_name") or dev_id,
                "category": dev.get("category", ""),
                "product_name": dev.get("product_name", ""),
                "online": bool(dev.get("online", True)),
                "status": status,
            }
        return devices

    def send_commands(self, device_id: str, commands: list[dict[str, Any]]) -> None:
        """Send one or more {code, value} commands to a device."""
        try:
            resp = self._api.post(
                f"/v1.0/devices/{device_id}/commands", {"commands": commands}
            )
        except Exception as err:  # noqa: BLE001
            raise CeSmartCloudError(str(err)) from err
        if not isinstance(resp, dict) or not resp.get("success", False):
            raise CeSmartCloudError((resp or {}).get("msg", "command failed"))


class CeSmartCloudCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """Poll all devices linked to the Tuya project in one request."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Build the cloud API client from the entry credentials."""
        self.entry = entry
        self._api = CeSmartCloudApi(
            region=entry.data[CONF_REGION],
            access_id=entry.data[CONF_ACCESS_ID],
            access_secret=entry.data[CONF_ACCESS_SECRET],
        )
        self._connected = False

        scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} cloud",
            update_interval=timedelta(seconds=max(scan_interval, 10)),
        )

    async def _async_ensure_connected(self) -> None:
        if not self._connected:
            await self.hass.async_add_executor_job(self._api.connect)
            self._connected = True

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        try:
            await self._async_ensure_connected()
            return await self.hass.async_add_executor_job(self._api.list_devices)
        except CeSmartCloudError as err:
            # Token may have expired; force a reconnect on the next cycle.
            self._connected = False
            raise UpdateFailed(f"Tuya cloud error: {err}") from err

    async def async_send_commands(
        self, device_id: str, commands: list[dict[str, Any]]
    ) -> None:
        """Send commands then refresh so entities reflect the new state."""
        try:
            await self._async_ensure_connected()
            await self.hass.async_add_executor_job(
                self._api.send_commands, device_id, commands
            )
        except CeSmartCloudError as err:
            self._connected = False
            raise UpdateFailed(f"Tuya cloud command error: {err}") from err
        await self.async_request_refresh()

    def device_status(self, device_id: str) -> dict[str, Any]:
        """Current {code: value} map for one device."""
        data = self.data or {}
        dev = data.get(device_id) or {}
        return dev.get("status", {})
