"""Base entity for cloud-mode CE Smart devices."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .cloud import CeSmartCloudCoordinator
from .const import DOMAIN, MANUFACTURER


class CeSmartCloudEntity(CoordinatorEntity[CeSmartCloudCoordinator]):
    """One datapoint 'code' of one cloud device."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: CeSmartCloudCoordinator,
        device_id: str,
        code: str,
    ) -> None:
        """Bind to a device id and status code."""
        super().__init__(coordinator)
        self._device_id = device_id
        self._code = code
        self._attr_unique_id = f"{device_id}_{code}"

    @property
    def _device(self) -> dict[str, Any]:
        return (self.coordinator.data or {}).get(self._device_id, {})

    @property
    def _status(self) -> dict[str, Any]:
        return self._device.get("status", {})

    def _value(self) -> Any:
        return self._status.get(self._code)

    @property
    def device_info(self) -> DeviceInfo:
        """Group all of a device's entities under one registry device."""
        dev = self._device
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            manufacturer=MANUFACTURER,
            name=dev.get("name", self._device_id),
            model=dev.get("product_name") or dev.get("category") or "CE Smart",
            configuration_url="https://github.com/akramercury/ha-ce-smart",
        )

    @property
    def available(self) -> bool:
        """Available when the poll succeeded, device is online and code present."""
        return (
            super().available
            and bool(self._device)
            and self._device.get("online", True)
            and self._code in self._status
        )
