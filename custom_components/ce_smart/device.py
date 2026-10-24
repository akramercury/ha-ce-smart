"""Thin wrapper around the (blocking) tinytuya device API.

All tinytuya calls block on network I/O, so every public method here is
synchronous and is expected to be invoked from an executor thread via the
coordinator. A single persistent socket is reused for the lifetime of the
config entry.
"""

from __future__ import annotations

import logging
from typing import Any

import tinytuya

from .const import DEVICE_TYPE_LIGHT

_LOGGER = logging.getLogger(__name__)


class CeSmartDeviceError(Exception):
    """Raised when the device returns an error or cannot be reached."""


class CeSmartDevice:
    """Wrap a tinytuya device with HA-friendly helpers."""

    def __init__(
        self,
        device_id: str,
        host: str,
        local_key: str,
        protocol_version: str,
        device_type: str,
    ) -> None:
        """Create the underlying tinytuya device object."""
        self.device_id = device_id
        self.host = host
        self._device_type = device_type

        cls = (
            tinytuya.BulbDevice
            if device_type == DEVICE_TYPE_LIGHT
            else tinytuya.OutletDevice
        )
        self._device = cls(
            dev_id=device_id,
            address=host,
            local_key=local_key,
            version=float(protocol_version),
            persist=True,
        )
        # Fail fast rather than hanging forever on an unreachable host.
        self._device.set_socketTimeout(7)
        self._device.set_socketRetryLimit(1)

    # -- low level -----------------------------------------------------------

    @staticmethod
    def _raise_on_error(payload: Any) -> dict[str, Any]:
        """Normalise a tinytuya response and raise on an error payload."""
        if not isinstance(payload, dict):
            raise CeSmartDeviceError(f"Unexpected response: {payload!r}")
        if "Error" in payload or "Err" in payload:
            raise CeSmartDeviceError(
                payload.get("Error") or f"Device error code {payload.get('Err')}"
            )
        return payload

    # -- status --------------------------------------------------------------

    def status(self) -> dict[str, Any]:
        """Return the current datapoint map {dp_id: value}."""
        payload = self._raise_on_error(self._device.status())
        return dict(payload.get("dps") or {})

    def detect_available_dps(self) -> dict[str, Any]:
        """Probe the device for all datapoints it will report."""
        try:
            return dict(self._device.detect_available_dps() or {})
        except Exception as err:  # noqa: BLE001 - tinytuya raises bare exceptions
            raise CeSmartDeviceError(str(err)) from err

    # -- control -------------------------------------------------------------

    def set_dp(self, dp_id: str | int, value: Any) -> dict[str, Any]:
        """Set a single datapoint and return the resulting dps map."""
        payload = self._raise_on_error(self._device.set_value(dp_id, value))
        return dict(payload.get("dps") or {})

    def set_multiple_dps(self, values: dict[str, Any]) -> dict[str, Any]:
        """Set several datapoints in one command."""
        payload = self._raise_on_error(self._device.set_multiple_values(values))
        return dict(payload.get("dps") or {})

    # -- lifecycle -----------------------------------------------------------

    def close(self) -> None:
        """Close the persistent socket."""
        try:
            self._device.close()
        except Exception:  # noqa: BLE001 - closing must never raise
            _LOGGER.debug("Error while closing device %s", self.device_id, exc_info=True)
