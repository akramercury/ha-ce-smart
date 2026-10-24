"""Constants for the CE Smart (Local) integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "ce_smart"

# Setup mode selected in the config flow.
CONF_MODE: Final = "mode"
MODE_LOCAL: Final = "local"
MODE_CLOUD: Final = "cloud"

# Cloud (Tuya OpenAPI) config keys
CONF_ACCESS_ID: Final = "access_id"
CONF_ACCESS_SECRET: Final = "access_secret"
CONF_REGION: Final = "region"

# Tuya OpenAPI data-centre endpoints the user can pick in the cloud flow.
CLOUD_ENDPOINTS: Final = {
    "us": "https://openapi.tuyaus.com",
    "eu": "https://openapi.tuyaeu.com",
    "cn": "https://openapi.tuyacn.com",
    "in": "https://openapi.tuyain.com",
}
DEFAULT_REGION: Final = "us"

# Config entry / data keys
CONF_DEVICE_ID: Final = "device_id"
CONF_LOCAL_KEY: Final = "local_key"
CONF_HOST: Final = "host"
CONF_PROTOCOL_VERSION: Final = "protocol_version"
CONF_DEVICE_TYPE: Final = "device_type"
CONF_NAME: Final = "name"

# Options keys
CONF_SCAN_INTERVAL: Final = "scan_interval"
CONF_DPS: Final = "dps"  # list of per-DP mapping dicts
CONF_DP_ID: Final = "dp_id"
CONF_DP_KIND: Final = "dp_kind"  # switch | sensor | light-skip
CONF_DP_NAME: Final = "dp_name"
CONF_DP_UNIT: Final = "dp_unit"
CONF_DP_SCALE: Final = "dp_scale"
CONF_DP_DEVICE_CLASS: Final = "dp_device_class"

# Device types offered in the config flow
DEVICE_TYPE_SWITCH: Final = "switch"
DEVICE_TYPE_PLUG: Final = "plug"
DEVICE_TYPE_LIGHT: Final = "light"
DEVICE_TYPE_GENERIC: Final = "generic"

DEVICE_TYPES: Final = [
    DEVICE_TYPE_SWITCH,
    DEVICE_TYPE_PLUG,
    DEVICE_TYPE_LIGHT,
    DEVICE_TYPE_GENERIC,
]

# tinytuya supported protocol versions
PROTOCOL_VERSIONS: Final = ["3.1", "3.2", "3.3", "3.4", "3.5"]
DEFAULT_PROTOCOL_VERSION: Final = "3.3"

DEFAULT_SCAN_INTERVAL: Final = 30  # seconds
MIN_SCAN_INTERVAL: Final = 5

# Platforms this integration can set up
PLATFORMS: Final = ["switch", "sensor", "light"]

MANUFACTURER: Final = "Commercial Electric (CE Smart)"

# Classic Tuya energy-plug datapoint map (category cz). CE Smart metering plugs
# expose: add_ele (17 -> cumulative energy, 0.01 kWh), cur_current (18 -> mA),
# cur_power (19 -> 0.1 W) and cur_voltage (20 -> 0.1 V).
ENERGY_DP_ENERGY: Final = "17"
ENERGY_DP_CURRENT: Final = "18"
ENERGY_DP_POWER: Final = "19"
ENERGY_DP_VOLTAGE: Final = "20"

# Some CE Smart metering plugs use a different, lower DP layout for the same
# four readings instead of the classic 17-20. Local setup auto-detects which
# layout a device actually reports by checking the numeric DP ids currently
# present in its status, highest-confidence match first.
#
# name -> ordered list of (unit, scale, device_class, state_class, dp_id) to
# try, most common layout first.
ENERGY_DP_CANDIDATES: Final = {
    "energy": [("17", 0.01), ("2", 0.01)],
    "current": [("18", 1), ("5", 1)],
    "power": [("19", 0.1), ("4", 0.1)],
    "voltage": [("20", 0.1), ("6", 0.1)],
}

# DPs that are the primary on/off switch, in priority order.
SWITCH_DP_CANDIDATES: Final = ["1", "20", "switch_1", "switch"]

# ---------------------------------------------------------------------------
# Cloud status CODE maps. The Tuya cloud reports datapoints by string "code",
# not by the numeric id used on the LAN. (code -> name/unit/scale/class/stateclass)
# ---------------------------------------------------------------------------

# Energy-related cloud codes with HA metadata.
# tuple: (name, unit, scale, device_class, state_class)
CLOUD_ENERGY_CODES: Final = {
    "add_ele": ("Energy", "kWh", 0.01, "energy", "total_increasing"),
    "cur_power": ("Power", "W", 0.1, "power", "measurement"),
    "cur_current": ("Current", "mA", 1, "current", "measurement"),
    "cur_voltage": ("Voltage", "V", 0.1, "voltage", "measurement"),
}

# Codes treated as the on/off relay (booleans). Priority order for the primary.
CLOUD_SWITCH_CODES: Final = ["switch", "switch_1", "switch_2", "switch_3", "switch_4"]

# Light control codes (v2 + legacy) used by the cloud light entity.
CLOUD_LIGHT_CODES: Final = {
    "switch": ["switch_led", "switch_led_1", "led_switch"],
    "mode": ["work_mode"],
    "bright": ["bright_value_v2", "bright_value"],
    "temp": ["temp_value_v2", "temp_value"],
    "colour": ["colour_data_v2", "colour_data"],
}
