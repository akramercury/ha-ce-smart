"""Switch platform for CE Smart (Local).

Every boolean datapoint the device reports becomes a switch. For plain
switches and plugs this is the relay(s); generic devices expose whatever
booleans they have.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import CeSmartConfigEntry
from .cloud import CeSmartCloudCoordinator
from .cloud_entity import CeSmartCloudEntity
from .const import DEVICE_TYPE_LIGHT
from .coordinator import CeSmartDataUpdateCoordinator
from .entity import CeSmartEntity

# Cloud light codes to skip when building switches (they belong to the light).
_LIGHT_SWITCH_CODES = {"switch_led", "switch_led_1", "led_switch"}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CeSmartConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create a switch for each boolean datapoint."""
    coordinator = entry.runtime_data

    if isinstance(coordinator, CeSmartCloudCoordinator):
        _setup_cloud(coordinator, async_add_entities)
        return

    # A device configured as a light is controlled by the light platform.
    if coordinator.device_type == DEVICE_TYPE_LIGHT:
        return

    data = coordinator.data or {}
    bool_dps = [dp for dp, val in data.items() if isinstance(val, bool)]

    entities = [
        CeSmartSwitch(coordinator, dp, single=len(bool_dps) == 1) for dp in bool_dps
    ]
    async_add_entities(entities)


def _setup_cloud(
    coordinator: CeSmartCloudCoordinator,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Build a switch for every boolean 'switch*' code across all devices."""
    entities: list[CeSmartCloudSwitch] = []
    for device_id, dev in (coordinator.data or {}).items():
        for code, value in dev.get("status", {}).items():
            if not isinstance(value, bool):
                continue
            if code in _LIGHT_SWITCH_CODES:
                continue
            # Only treat switch-like codes as switches; other booleans could be
            # read-only flags, but exposing them as switches is harmless and
            # matches how most local-Tuya tools behave.
            entities.append(CeSmartCloudSwitch(coordinator, device_id, code))
    async_add_entities(entities)


class CeSmartSwitch(CeSmartEntity, SwitchEntity):
    """A single boolean datapoint exposed as a switch."""

    def __init__(
        self,
        coordinator: CeSmartDataUpdateCoordinator,
        dp_id: str,
        single: bool,
    ) -> None:
        """Set up naming: a lone relay carries the device name only."""
        super().__init__(coordinator, dp_id)
        if single:
            # One relay -> entity takes the device's own name.
            self._attr_name = None
        else:
            self._attr_name = f"Switch {dp_id}"

    @property
    def is_on(self) -> bool | None:
        """Return the relay state."""
        value = self._dp_value()
        if value is None:
            return None
        return bool(value)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the relay on."""
        await self.coordinator.async_set_dp(self._dp_id, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the relay off."""
        await self.coordinator.async_set_dp(self._dp_id, False)


class CeSmartCloudSwitch(CeSmartCloudEntity, SwitchEntity):
    """A boolean cloud datapoint exposed as a switch."""

    def __init__(
        self,
        coordinator: CeSmartCloudCoordinator,
        device_id: str,
        code: str,
    ) -> None:
        """Name multi-gang relays by their code, lone relays by the device."""
        super().__init__(coordinator, device_id, code)
        if code in ("switch", "switch_1"):
            self._attr_name = None
        else:
            self._attr_name = code.replace("_", " ").title()

    @property
    def is_on(self) -> bool | None:
        """Return the relay state."""
        value = self._value()
        return None if value is None else bool(value)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the relay on."""
        await self.coordinator.async_send_commands(
            self._device_id, [{"code": self._code, "value": True}]
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the relay off."""
        await self.coordinator.async_send_commands(
            self._device_id, [{"code": self._code, "value": False}]
        )
