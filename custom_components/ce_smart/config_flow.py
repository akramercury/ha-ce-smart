"""Config and options flow for CE Smart (Local & Cloud)."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .cloud import CeSmartCloudApi, CeSmartCloudError
from .const import (
    CLOUD_ENDPOINTS,
    CONF_ACCESS_ID,
    CONF_ACCESS_SECRET,
    CONF_DEVICE_ID,
    CONF_DEVICE_TYPE,
    CONF_HOST,
    CONF_LOCAL_KEY,
    CONF_MODE,
    CONF_NAME,
    CONF_PROTOCOL_VERSION,
    CONF_REGION,
    CONF_SCAN_INTERVAL,
    DEFAULT_PROTOCOL_VERSION,
    DEFAULT_REGION,
    DEFAULT_SCAN_INTERVAL,
    DEVICE_TYPE_GENERIC,
    DEVICE_TYPES,
    DOMAIN,
    MIN_SCAN_INTERVAL,
    MODE_CLOUD,
    MODE_LOCAL,
    PROTOCOL_VERSIONS,
)
from .device import CeSmartDevice, CeSmartDeviceError

_LOGGER = logging.getLogger(__name__)


def _local_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    """Build the local setup form schema."""
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Required(
                CONF_NAME, default=defaults.get(CONF_NAME, "CE Smart Device")
            ): str,
            vol.Required(CONF_DEVICE_ID, default=defaults.get(CONF_DEVICE_ID, "")): str,
            vol.Required(CONF_LOCAL_KEY, default=defaults.get(CONF_LOCAL_KEY, "")): str,
            vol.Required(CONF_HOST, default=defaults.get(CONF_HOST, "")): str,
            vol.Required(
                CONF_PROTOCOL_VERSION,
                default=defaults.get(CONF_PROTOCOL_VERSION, DEFAULT_PROTOCOL_VERSION),
            ): SelectSelector(
                SelectSelectorConfig(
                    options=PROTOCOL_VERSIONS, mode=SelectSelectorMode.DROPDOWN
                )
            ),
            vol.Required(
                CONF_DEVICE_TYPE,
                default=defaults.get(CONF_DEVICE_TYPE, DEVICE_TYPE_GENERIC),
            ): SelectSelector(
                SelectSelectorConfig(
                    options=DEVICE_TYPES,
                    mode=SelectSelectorMode.DROPDOWN,
                    translation_key="device_type",
                )
            ),
        }
    )


def _cloud_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    """Build the cloud setup form schema."""
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Required(
                CONF_REGION, default=defaults.get(CONF_REGION, DEFAULT_REGION)
            ): SelectSelector(
                SelectSelectorConfig(
                    options=list(CLOUD_ENDPOINTS.keys()),
                    mode=SelectSelectorMode.DROPDOWN,
                    translation_key="region",
                )
            ),
            vol.Required(
                CONF_ACCESS_ID, default=defaults.get(CONF_ACCESS_ID, "")
            ): str,
            vol.Required(
                CONF_ACCESS_SECRET, default=defaults.get(CONF_ACCESS_SECRET, "")
            ): str,
        }
    )


async def _validate_local(hass, data: dict[str, Any]) -> None:
    """Reach the device and read its state. Raise CeSmartDeviceError on failure."""
    device = CeSmartDevice(
        device_id=data[CONF_DEVICE_ID],
        host=data[CONF_HOST],
        local_key=data[CONF_LOCAL_KEY],
        protocol_version=data[CONF_PROTOCOL_VERSION],
        device_type=data[CONF_DEVICE_TYPE],
    )

    def _check() -> None:
        try:
            device.status()
        finally:
            device.close()

    await hass.async_add_executor_job(_check)


async def _validate_cloud(hass, data: dict[str, Any]) -> int:
    """Connect to the Tuya project and return the number of devices found."""
    api = CeSmartCloudApi(
        region=data[CONF_REGION],
        access_id=data[CONF_ACCESS_ID],
        access_secret=data[CONF_ACCESS_SECRET],
    )

    def _check() -> int:
        api.connect()
        return len(api.list_devices())

    return await hass.async_add_executor_job(_check)


class CeSmartConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the UI setup flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Offer a choice between cloud and local setup."""
        return self.async_show_menu(
            step_id="user", menu_options=[MODE_CLOUD, MODE_LOCAL]
        )

    async def async_step_local(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Set up a single device over the LAN."""
        errors: dict[str, str] = {}

        if user_input is not None:
            device_id = user_input[CONF_DEVICE_ID].strip()
            user_input[CONF_DEVICE_ID] = device_id
            user_input[CONF_LOCAL_KEY] = user_input[CONF_LOCAL_KEY].strip()
            user_input[CONF_HOST] = user_input[CONF_HOST].strip()

            await self.async_set_unique_id(device_id)
            self._abort_if_unique_id_configured()

            try:
                await _validate_local(self.hass, user_input)
            except CeSmartDeviceError as err:
                _LOGGER.warning("CE Smart local validation failed: %s", err)
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error validating CE Smart device")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data={
                        CONF_MODE: MODE_LOCAL,
                        CONF_NAME: user_input[CONF_NAME],
                        CONF_DEVICE_ID: device_id,
                        CONF_LOCAL_KEY: user_input[CONF_LOCAL_KEY],
                        CONF_HOST: user_input[CONF_HOST],
                        CONF_PROTOCOL_VERSION: user_input[CONF_PROTOCOL_VERSION],
                        CONF_DEVICE_TYPE: user_input[CONF_DEVICE_TYPE],
                    },
                )

        return self.async_show_form(
            step_id="local", data_schema=_local_schema(user_input), errors=errors
        )

    async def async_step_cloud(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Set up a Tuya IoT project and import all linked devices."""
        errors: dict[str, str] = {}

        if user_input is not None:
            access_id = user_input[CONF_ACCESS_ID].strip()
            user_input[CONF_ACCESS_ID] = access_id
            user_input[CONF_ACCESS_SECRET] = user_input[CONF_ACCESS_SECRET].strip()

            await self.async_set_unique_id(f"cloud_{access_id}")
            self._abort_if_unique_id_configured()

            try:
                count = await _validate_cloud(self.hass, user_input)
            except CeSmartCloudError as err:
                _LOGGER.warning("CE Smart cloud validation failed: %s", err)
                errors["base"] = "cloud_auth"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error validating Tuya cloud project")
                errors["base"] = "unknown"
            else:
                if count == 0:
                    errors["base"] = "no_devices"
                else:
                    return self.async_create_entry(
                        title="CE Smart Cloud",
                        data={
                            CONF_MODE: MODE_CLOUD,
                            CONF_REGION: user_input[CONF_REGION],
                            CONF_ACCESS_ID: access_id,
                            CONF_ACCESS_SECRET: user_input[CONF_ACCESS_SECRET],
                        },
                    )

        return self.async_show_form(
            step_id="cloud", data_schema=_cloud_schema(user_input), errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> CeSmartOptionsFlow:
        """Return the options flow handler."""
        return CeSmartOptionsFlow()


class CeSmartOptionsFlow(OptionsFlow):
    """Handle runtime options (polling interval)."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        current = self.config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )
        schema = vol.Schema(
            {
                vol.Required(CONF_SCAN_INTERVAL, default=current): NumberSelector(
                    NumberSelectorConfig(
                        min=MIN_SCAN_INTERVAL,
                        max=600,
                        step=1,
                        unit_of_measurement="s",
                        mode=NumberSelectorMode.BOX,
                    )
                ),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
