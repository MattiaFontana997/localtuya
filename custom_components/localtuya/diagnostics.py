"""Diagnostics support for LocalTuya."""

from __future__ import annotations

import copy
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET, CONF_DEVICES
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.redact import async_redact_data

from .const import CONF_LOCAL_KEY, CONF_USER_ID, DATA_CLOUD, DOMAIN

CLOUD_DEVICES = "cloud_devices"
DEVICE_CONFIG = "device_config"
DEVICE_CLOUD_INFO = "device_cloud_info"

TO_REDACT = {
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_USER_ID,
    CONF_LOCAL_KEY,
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    tuya_api = hass.data[DOMAIN][DATA_CLOUD]

    data = copy.deepcopy(dict(entry.data))
    data[CLOUD_DEVICES] = copy.deepcopy(tuya_api.device_list)

    return async_redact_data(data, TO_REDACT)


async def async_get_device_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry, device: DeviceEntry
) -> dict[str, Any]:
    """Return diagnostics for a device entry."""
    dev_id = list(device.identifiers)[0][1].split("_")[-1]

    data: dict[str, Any] = {
        DEVICE_CONFIG: copy.deepcopy(entry.data[CONF_DEVICES][dev_id]),
    }

    tuya_api = hass.data[DOMAIN][DATA_CLOUD]

    if dev_id in tuya_api.device_list:
        data[DEVICE_CLOUD_INFO] = copy.deepcopy(tuya_api.device_list[dev_id])

    return async_redact_data(data, TO_REDACT)
