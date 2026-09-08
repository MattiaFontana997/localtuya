"""Helpers backing the LocalTuya device-health service."""

from __future__ import annotations

import copy

from homeassistant.const import CONF_DEVICES
from homeassistant.core import HomeAssistant

from .common import async_config_entry_by_device_id
from .health_runtime import async_build_device_health_snapshot


class DeviceHealthTargetNotFound(Exception):
    """Raised when a requested LocalTuya device is not configured."""


async def async_check_configured_device_health(
    hass: HomeAssistant,
    device_id: str,
) -> dict:
    """Run a privacy-safe health check for one configured LocalTuya device."""
    entry = async_config_entry_by_device_id(
        hass,
        device_id,
    )

    if entry is None:
        raise DeviceHealthTargetNotFound

    devices = entry.data.get(CONF_DEVICES, {})
    device_config = (
        devices.get(device_id)
        if isinstance(devices, dict)
        else None
    )

    if not isinstance(device_config, dict):
        raise DeviceHealthTargetNotFound

    return await async_build_device_health_snapshot(
        hass,
        device_id,
        copy.deepcopy(device_config),
    )
