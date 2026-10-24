"""Sensor platform for CE Smart (Local).

Numeric datapoints that are not the on/off relay become sensors. The classic
Tuya energy-plug datapoints (power/current/voltage) are given the right unit,
scale, device class and state class automatically; anything else is exposed
as a plain numeric sensor.
"""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import (
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import CeSmartConfigEntry
from .cloud import CeSmartCloudCoordinator
from .cloud_entity import CeSmartCloudEntity
from .const import (
    CLOUD_ENERGY_CODES,
    DEVICE_TYPE_LIGHT,
    ENERGY_DP_CURRENT,
    ENERGY_DP_ENERGY,
    ENERGY_DP_POWER,
    ENERGY_DP_VOLTAGE,
)
from .coordinator import CeSmartDataUpdateCoordinator
from .entity import CeSmartEntity

# Map the cloud metadata's string device/state classes to HA enums.
_DEVICE_CLASS = {
    "energy": SensorDeviceClass.ENERGY,
    "power": SensorDeviceClass.POWER,
    "current": SensorDeviceClass.CURRENT,
    "voltage": SensorDeviceClass.VOLTAGE,
}
_STATE_CLASS = {
    "measurement": SensorStateClass.MEASUREMENT,
    "total_increasing": SensorStateClass.TOTAL_INCREASING,
}

# Cloud light control codes that should not become sensors.
_CLOUD_LIGHT_CODES = {
    "switch_led",
    "work_mode",
    "bright_value",
    "bright_value_v2",
    "temp_value",
    "temp_value_v2",
    "colour_data",
    "colour_data_v2",
}

# dp_id -> (name, unit, scale, device_class, state_class)
_ENERGY_MAP = {
    ENERGY_DP_ENERGY: (
        "Energy",
        UnitOfEnergy.KILO_WATT_HOUR,
        0.01,
        SensorDeviceClass.ENERGY,
        SensorStateClass.TOTAL_INCREASING,
    ),
    ENERGY_DP_CURRENT: (
        "Current",
        UnitOfElectricCurrent.MILLIAMPERE,
        1,
        SensorDeviceClass.CURRENT,
        SensorStateClass.MEASUREMENT,
    ),
    ENERGY_DP_POWER: (
        "Power",
        UnitOfPower.WATT,
        0.1,
        SensorDeviceClass.POWER,
        SensorStateClass.MEASUREMENT,
    ),
    ENERGY_DP_VOLTAGE: (
        "Voltage",
        UnitOfElectricPotential.VOLT,
        0.1,
        SensorDeviceClass.VOLTAGE,
        SensorStateClass.MEASUREMENT,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CeSmartConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create sensors for numeric datapoints."""
    coordinator = entry.runtime_data

    if isinstance(coordinator, CeSmartCloudCoordinator):
        _setup_cloud(coordinator, async_add_entities)
        return

    data = coordinator.data or {}

    entities: list[CeSmartSensor] = []
    for dp_id, value in data.items():
        # Skip booleans (switches) and, for lights, the control datapoints.
        if isinstance(value, bool):
            continue
        if coordinator.device_type == DEVICE_TYPE_LIGHT and dp_id in {
            "20",
            "21",
            "22",
            "23",
            "24",
            "25",
            "26",
        }:
            continue
        if isinstance(value, (int, float)):
            entities.append(CeSmartSensor(coordinator, dp_id))

    async_add_entities(entities)


def _setup_cloud(
    coordinator: CeSmartCloudCoordinator,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Build sensors for numeric cloud codes across all devices."""
    entities: list[CeSmartCloudSensor] = []
    for device_id, dev in (coordinator.data or {}).items():
        for code, value in dev.get("status", {}).items():
            if isinstance(value, bool) or code in _CLOUD_LIGHT_CODES:
                continue
            if isinstance(value, (int, float)):
                entities.append(CeSmartCloudSensor(coordinator, device_id, code))
    async_add_entities(entities)


class CeSmartSensor(CeSmartEntity, SensorEntity):
    """A numeric datapoint exposed as a sensor."""

    def __init__(
        self, coordinator: CeSmartDataUpdateCoordinator, dp_id: str
    ) -> None:
        """Apply energy-plug defaults when the datapoint is a known one."""
        super().__init__(coordinator, dp_id)
        self._scale: float = 1

        if dp_id in _ENERGY_MAP:
            name, unit, scale, device_class, state_class = _ENERGY_MAP[dp_id]
            self._attr_name = name
            self._attr_native_unit_of_measurement = unit
            self._scale = scale
            self._attr_device_class = device_class
            self._attr_state_class = state_class
        else:
            self._attr_name = f"DP {dp_id}"
            self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> float | int | None:
        """Return the scaled datapoint value."""
        value = self._dp_value()
        if value is None or not isinstance(value, (int, float)):
            return None
        if self._scale != 1:
            return round(value * self._scale, 3)
        return value


class CeSmartCloudSensor(CeSmartCloudEntity, SensorEntity):
    """A numeric cloud datapoint exposed as a sensor."""

    def __init__(
        self,
        coordinator: CeSmartCloudCoordinator,
        device_id: str,
        code: str,
    ) -> None:
        """Apply energy metadata for known codes, else a plain sensor."""
        super().__init__(coordinator, device_id, code)
        self._scale: float = 1

        if code in CLOUD_ENERGY_CODES:
            name, unit, scale, device_class, state_class = CLOUD_ENERGY_CODES[code]
            self._attr_name = name
            self._attr_native_unit_of_measurement = unit
            self._scale = scale
            self._attr_device_class = _DEVICE_CLASS.get(device_class)
            self._attr_state_class = _STATE_CLASS.get(state_class)
        else:
            self._attr_name = code.replace("_", " ").title()
            self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> float | int | None:
        """Return the scaled datapoint value."""
        value = self._value()
        if value is None or not isinstance(value, (int, float)):
            return None
        if self._scale != 1:
            return round(value * self._scale, 3)
        return value
