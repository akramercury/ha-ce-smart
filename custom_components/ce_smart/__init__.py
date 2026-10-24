"""The CE Smart (Local) integration.

Two setup modes share this component:

* **Local** - control a single device over the LAN with its local key.
* **Cloud** - import every device linked to a Tuya IoT project and control
  them through the Tuya OpenAPI.

Local control needs no cloud at runtime; cloud control needs no per-device key
or static IP. The user picks the mode in the config flow.
"""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .cloud import CeSmartCloudCoordinator
from .const import CONF_MODE, MODE_CLOUD, PLATFORMS
from .coordinator import CeSmartDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

type CeSmartCoordinator = CeSmartDataUpdateCoordinator | CeSmartCloudCoordinator
type CeSmartConfigEntry = ConfigEntry[CeSmartCoordinator]

_PLATFORMS: list[Platform] = [Platform(p) for p in PLATFORMS]


async def async_setup_entry(hass: HomeAssistant, entry: CeSmartConfigEntry) -> bool:
    """Set up CE Smart from a config entry."""
    if entry.data.get(CONF_MODE) == MODE_CLOUD:
        coordinator: CeSmartCoordinator = CeSmartCloudCoordinator(hass, entry)
    else:
        coordinator = CeSmartDataUpdateCoordinator(hass, entry)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: CeSmartConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
    if unload_ok:
        coordinator = entry.runtime_data
        if isinstance(coordinator, CeSmartDataUpdateCoordinator):
            await coordinator.async_shutdown_device()
    return unload_ok


async def _async_update_listener(
    hass: HomeAssistant, entry: CeSmartConfigEntry
) -> None:
    """Reload the entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)
