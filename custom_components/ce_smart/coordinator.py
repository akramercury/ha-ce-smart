"""DataUpdateCoordinator for CE Smart devices."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_DEVICE_ID,
    CONF_DEVICE_TYPE,
    CONF_HOST,
    CONF_LOCAL_KEY,
    CONF_PROTOCOL_VERSION,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MANUFACTURER,
)
from .device import CeSmartDevice, CeSmartDeviceError

_LOGGER = logging.getLogger(__name__)


class CeSmartDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Poll a single CE Smart device and share its datapoint state."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialise the coordinator from a config entry."""
        self.entry = entry
        self.device_id: str = entry.data[CONF_DEVICE_ID]
        self.device_type: str = entry.data[CONF_DEVICE_TYPE]
        self.host: str = entry.data[CONF_HOST]

        scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

        self._device = CeSmartDevice(
            device_id=entry.data[CONF_DEVICE_ID],
            host=entry.data[CONF_HOST],
            local_key=entry.data[CONF_LOCAL_KEY],
            protocol_version=entry.data[CONF_PROTOCOL_VERSION],
            device_type=entry.data[CONF_DEVICE_TYPE],
        )

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} {self.device_id}",
            update_interval=timedelta(seconds=scan_interval),
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Return registry info shared by every entity of this device."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.device_id)},
            manufacturer=MANUFACTURER,
            name=self.entry.title,
            model=self.device_type.capitalize(),
            configuration_url="https://github.com/akramercury/ha-ce-smart",
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch the latest datapoint map from the device."""
        try:
            return await self.hass.async_add_executor_job(self._device.status)
        except CeSmartDeviceError as err:
            raise UpdateFailed(f"Error communicating with {self.host}: {err}") from err

    async def async_set_dp(self, dp_id: str | int, value: Any) -> None:
        """Write a datapoint, then refresh so entities reflect the result."""
        try:
            dps = await self.hass.async_add_executor_job(
                self._device.set_dp, dp_id, value
            )
        except CeSmartDeviceError as err:
            raise UpdateFailed(f"Error writing to {self.host}: {err}") from err
        # Optimistically merge the returned dps and notify listeners.
        merged = {**(self.data or {}), **dps}
        self.async_set_updated_data(merged)

    async def async_set_multiple_dps(self, values: dict[str, Any]) -> None:
        """Write several datapoints in one command."""
        try:
            dps = await self.hass.async_add_executor_job(
                self._device.set_multiple_dps, values
            )
        except CeSmartDeviceError as err:
            raise UpdateFailed(f"Error writing to {self.host}: {err}") from err
        merged = {**(self.data or {}), **dps}
        self.async_set_updated_data(merged)

    async def async_detect_dps(self) -> dict[str, Any]:
        """Return all datapoints the device reports (used by the config flow)."""
        return await self.hass.async_add_executor_job(self._device.detect_available_dps)

    async def async_shutdown_device(self) -> None:
        """Close the persistent socket on unload."""
        await self.hass.async_add_executor_job(self._device.close)
