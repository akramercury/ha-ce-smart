"""Light platform for CE Smart (Local).

Supports CE Smart / Tuya Wi-Fi bulbs. On/off, brightness, colour temperature
and colour are mapped from the standard Tuya lighting datapoints. Both the
legacy (DP 1-5) and v2 (DP 20-24) datapoint sets are detected automatically.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_HS_COLOR,
    ColorMode,
    LightEntity,
)
import json

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import CeSmartConfigEntry
from .cloud import CeSmartCloudCoordinator
from .cloud_entity import CeSmartCloudEntity
from .const import DEVICE_TYPE_LIGHT
from .coordinator import CeSmartDataUpdateCoordinator
from .entity import CeSmartEntity

# Tuya bulb colour-temperature endpoints.
MIN_KELVIN = 2700
MAX_KELVIN = 6500

# Legacy and v2 datapoint layouts.
_DP_SETS = {
    "v2": {
        "switch": "20",
        "mode": "21",
        "bright": "22",
        "temp": "23",
        "colour": "24",
        "bright_max": 1000,
    },
    "legacy": {
        "switch": "1",
        "mode": "2",
        "bright": "3",
        "temp": "4",
        "colour": "5",
        "bright_max": 255,
    },
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CeSmartConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create one light entity when the device is configured as a light."""
    coordinator = entry.runtime_data

    if isinstance(coordinator, CeSmartCloudCoordinator):
        _setup_cloud(coordinator, async_add_entities)
        return

    if coordinator.device_type != DEVICE_TYPE_LIGHT:
        return

    data = coordinator.data or {}
    if _DP_SETS["v2"]["switch"] in data:
        dpset = _DP_SETS["v2"]
    elif _DP_SETS["legacy"]["switch"] in data:
        dpset = _DP_SETS["legacy"]
    else:
        # Fall back to v2 layout; the switch DP will simply be absent until seen.
        dpset = _DP_SETS["v2"]

    async_add_entities([CeSmartLight(coordinator, dpset)])


# Cloud light control codes (v2 preferred, legacy fallback).
_CLOUD_CODES = {
    "switch": ["switch_led", "switch_led_1", "led_switch"],
    "mode": ["work_mode"],
    "bright": ["bright_value_v2", "bright_value"],
    "temp": ["temp_value_v2", "temp_value"],
    "colour": ["colour_data_v2", "colour_data"],
}


def _first_present(status: dict, codes: list[str]) -> str | None:
    """Return the first code in the priority list that the device reports."""
    for code in codes:
        if code in status:
            return code
    return None


def _setup_cloud(
    coordinator: CeSmartCloudCoordinator,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Build a light for every device that reports a bulb switch code."""
    entities: list[CeSmartCloudLight] = []
    for device_id, dev in (coordinator.data or {}).items():
        status = dev.get("status", {})
        switch_code = _first_present(status, _CLOUD_CODES["switch"])
        if switch_code is None:
            continue
        codes = {
            "switch": switch_code,
            "mode": _first_present(status, _CLOUD_CODES["mode"]),
            "bright": _first_present(status, _CLOUD_CODES["bright"]),
            "temp": _first_present(status, _CLOUD_CODES["temp"]),
            "colour": _first_present(status, _CLOUD_CODES["colour"]),
        }
        entities.append(CeSmartCloudLight(coordinator, device_id, codes))
    async_add_entities(entities)


class CeSmartLight(CeSmartEntity, LightEntity):
    """A CE Smart Wi-Fi bulb."""

    _attr_name = None  # the bulb takes the device's own name
    _attr_min_color_temp_kelvin = MIN_KELVIN
    _attr_max_color_temp_kelvin = MAX_KELVIN

    def __init__(
        self, coordinator: CeSmartDataUpdateCoordinator, dpset: dict[str, Any]
    ) -> None:
        """Determine supported colour modes from the datapoints present."""
        super().__init__(coordinator, dpset["switch"])
        self._dp = dpset
        data = coordinator.data or {}

        modes: set[ColorMode] = set()
        if dpset["colour"] in data:
            modes.add(ColorMode.HS)
        if dpset["temp"] in data:
            modes.add(ColorMode.COLOR_TEMP)
        if not modes:
            if dpset["bright"] in data:
                modes.add(ColorMode.BRIGHTNESS)
            else:
                modes.add(ColorMode.ONOFF)

        self._attr_supported_color_modes = modes

    # -- helpers -------------------------------------------------------------

    def _get(self, key: str):
        data = self.coordinator.data or {}
        return data.get(self._dp[key])

    # -- state ---------------------------------------------------------------

    @property
    def is_on(self) -> bool | None:
        """Return whether the bulb is on."""
        value = self._get("switch")
        return None if value is None else bool(value)

    @property
    def brightness(self) -> int | None:
        """Return brightness scaled to 0-255."""
        raw = self._get("bright")
        if raw is None or not isinstance(raw, (int, float)):
            return None
        bright_max = self._dp["bright_max"]
        return max(0, min(255, round(raw / bright_max * 255)))

    @property
    def color_mode(self) -> ColorMode | None:
        """Report the active colour mode based on the device's work mode."""
        modes = self._attr_supported_color_modes or set()
        mode = self._get("mode")
        if mode == "colour" and ColorMode.HS in modes:
            return ColorMode.HS
        if ColorMode.COLOR_TEMP in modes:
            return ColorMode.COLOR_TEMP
        if ColorMode.HS in modes:
            return ColorMode.HS
        if ColorMode.BRIGHTNESS in modes:
            return ColorMode.BRIGHTNESS
        return ColorMode.ONOFF

    @property
    def color_temp_kelvin(self) -> int | None:
        """Return colour temperature in Kelvin."""
        raw = self._get("temp")
        if raw is None or not isinstance(raw, (int, float)):
            return None
        # Tuya temp: 0 = warm (min K), 1000 = cool (max K).
        frac = raw / 1000
        return round(MIN_KELVIN + frac * (MAX_KELVIN - MIN_KELVIN))

    @property
    def hs_color(self) -> tuple[float, float] | None:
        """Return hue/saturation decoded from the Tuya colour datapoint."""
        raw = self._get("colour")
        if not isinstance(raw, str) or len(raw) < 12:
            return None
        try:
            hue = int(raw[0:4], 16)
            sat = int(raw[4:8], 16)
        except ValueError:
            return None
        return (float(hue % 360), max(0.0, min(100.0, sat / 10)))

    # -- commands ------------------------------------------------------------

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on and apply any brightness/colour attributes."""
        updates: dict[str, Any] = {self._dp["switch"]: True}

        if ATTR_HS_COLOR in kwargs and self._dp["colour"] in (
            self.coordinator.data or {}
        ):
            hue, sat = kwargs[ATTR_HS_COLOR]
            value = kwargs.get(ATTR_BRIGHTNESS)
            v = round((value or self.brightness or 255) / 255 * 1000)
            colour = f"{int(hue) % 360:04x}{round(sat * 10):04x}{v:04x}"
            updates[self._dp["colour"]] = colour
            updates[self._dp["mode"]] = "colour"

        elif ATTR_COLOR_TEMP_KELVIN in kwargs and self._dp["temp"] in (
            self.coordinator.data or {}
        ):
            kelvin = kwargs[ATTR_COLOR_TEMP_KELVIN]
            frac = (kelvin - MIN_KELVIN) / (MAX_KELVIN - MIN_KELVIN)
            updates[self._dp["temp"]] = max(0, min(1000, round(frac * 1000)))
            updates[self._dp["mode"]] = "white"

        if ATTR_BRIGHTNESS in kwargs and self._dp["bright"] in (
            self.coordinator.data or {}
        ):
            bright_max = self._dp["bright_max"]
            scaled = round(kwargs[ATTR_BRIGHTNESS] / 255 * bright_max)
            # Tuya bulbs reject 0 brightness; clamp to a small minimum.
            minimum = 10 if bright_max == 1000 else 25
            updates[self._dp["bright"]] = max(minimum, scaled)

        if len(updates) == 1:
            await self.coordinator.async_set_dp(self._dp["switch"], True)
        else:
            await self.coordinator.async_set_multiple_dps(updates)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the bulb off."""
        await self.coordinator.async_set_dp(self._dp["switch"], False)


class CeSmartCloudLight(CeSmartCloudEntity, LightEntity):
    """A CE Smart Wi-Fi bulb controlled through the Tuya cloud."""

    _attr_name = None
    _attr_min_color_temp_kelvin = MIN_KELVIN
    _attr_max_color_temp_kelvin = MAX_KELVIN

    def __init__(
        self,
        coordinator: CeSmartCloudCoordinator,
        device_id: str,
        codes: dict[str, str | None],
    ) -> None:
        """Determine colour support from the codes the device reports."""
        super().__init__(coordinator, device_id, codes["switch"])
        self._codes = codes
        # v2 datapoints use a 0-1000 range; legacy bright_value uses 0-255.
        self._bright_max = 1000 if (codes["bright"] or "").endswith("_v2") else 255

        modes: set[ColorMode] = set()
        if codes["colour"]:
            modes.add(ColorMode.HS)
        if codes["temp"]:
            modes.add(ColorMode.COLOR_TEMP)
        if not modes:
            modes.add(ColorMode.BRIGHTNESS if codes["bright"] else ColorMode.ONOFF)
        self._attr_supported_color_modes = modes

    def _code_value(self, key: str):
        code = self._codes.get(key)
        if not code:
            return None
        return self._status.get(code)

    @property
    def is_on(self) -> bool | None:
        """Return whether the bulb is on."""
        value = self._value()
        return None if value is None else bool(value)

    @property
    def brightness(self) -> int | None:
        """Return brightness scaled to 0-255."""
        raw = self._code_value("bright")
        if not isinstance(raw, (int, float)):
            return None
        return max(0, min(255, round(raw / self._bright_max * 255)))

    @property
    def color_mode(self) -> ColorMode | None:
        """Report the active colour mode from the device's work mode."""
        modes = self._attr_supported_color_modes or set()
        if self._code_value("mode") == "colour" and ColorMode.HS in modes:
            return ColorMode.HS
        if ColorMode.COLOR_TEMP in modes:
            return ColorMode.COLOR_TEMP
        if ColorMode.HS in modes:
            return ColorMode.HS
        if ColorMode.BRIGHTNESS in modes:
            return ColorMode.BRIGHTNESS
        return ColorMode.ONOFF

    @property
    def color_temp_kelvin(self) -> int | None:
        """Return colour temperature in Kelvin."""
        raw = self._code_value("temp")
        if not isinstance(raw, (int, float)):
            return None
        return round(MIN_KELVIN + (raw / 1000) * (MAX_KELVIN - MIN_KELVIN))

    @property
    def hs_color(self) -> tuple[float, float] | None:
        """Return hue/saturation from the cloud colour datapoint (JSON)."""
        raw = self._code_value("colour")
        if not isinstance(raw, str) or not raw:
            return None
        try:
            data = json.loads(raw)
            hue = float(data.get("h", 0))
            sat = float(data.get("s", 0))
        except (ValueError, TypeError, AttributeError):
            return None
        # v2 saturation is 0-1000; legacy is 0-255.
        sat_pct = sat / 10 if sat > 100 else sat / 2.55
        return (hue % 360, max(0.0, min(100.0, sat_pct)))

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on and apply brightness/colour attributes."""
        commands: list[dict[str, Any]] = [{"code": self._codes["switch"], "value": True}]

        if ATTR_HS_COLOR in kwargs and self._codes["colour"]:
            hue, sat = kwargs[ATTR_HS_COLOR]
            bright = kwargs.get(ATTR_BRIGHTNESS, self.brightness or 255)
            v = round(bright / 255 * self._bright_max)
            s = round(sat * 10) if self._bright_max == 1000 else round(sat * 2.55)
            colour = json.dumps({"h": int(hue) % 360, "s": s, "v": v})
            commands.append({"code": self._codes["colour"], "value": colour})
            if self._codes["mode"]:
                commands.append({"code": self._codes["mode"], "value": "colour"})

        elif ATTR_COLOR_TEMP_KELVIN in kwargs and self._codes["temp"]:
            kelvin = kwargs[ATTR_COLOR_TEMP_KELVIN]
            frac = (kelvin - MIN_KELVIN) / (MAX_KELVIN - MIN_KELVIN)
            commands.append(
                {"code": self._codes["temp"], "value": max(0, min(1000, round(frac * 1000)))}
            )
            if self._codes["mode"]:
                commands.append({"code": self._codes["mode"], "value": "white"})

        if ATTR_BRIGHTNESS in kwargs and self._codes["bright"]:
            scaled = round(kwargs[ATTR_BRIGHTNESS] / 255 * self._bright_max)
            minimum = 10 if self._bright_max == 1000 else 25
            commands.append(
                {"code": self._codes["bright"], "value": max(minimum, scaled)}
            )

        await self.coordinator.async_send_commands(self._device_id, commands)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the bulb off."""
        await self.coordinator.async_send_commands(
            self._device_id, [{"code": self._codes["switch"], "value": False}]
        )
