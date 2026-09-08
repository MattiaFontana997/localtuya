"""Runtime helpers for privacy-safe LocalTuya device health snapshots."""

from __future__ import annotations

import asyncio
import copy
from typing import Any

from homeassistant.const import CONF_DEVICE_ID
from homeassistant.core import HomeAssistant

from .config_flow import async_device_preflight
from .const import DOMAIN, TUYA_DEVICES

DEVICE_HEALTH_PROBE_TIMEOUT = 10.0


async def async_build_device_health_snapshot(
    hass: HomeAssistant,
    device_id: str,
    device_config: dict[str, Any],
    *,
    timeout: float = DEVICE_HEALTH_PROBE_TIMEOUT,
) -> dict[str, Any]:
    """Return a bounded device-health snapshot safe for diagnostics/services.

    Device identifiers, local keys, network addresses, raw datapoint values and
    exception messages are deliberately excluded from the returned structure.
    The supplied device configuration is copied before the private Device ID is
    attached for the protocol probe.
    """
    domain_data = hass.data.get(DOMAIN, {})
    runtime_devices = domain_data.get(TUYA_DEVICES, {})
    runtime_device = (
        runtime_devices.get(device_id)
        if isinstance(runtime_devices, dict)
        else None
    )

    result: dict[str, Any] = {
        "runtime_present": runtime_device is not None,
        "runtime_connected": (
            bool(getattr(runtime_device, "connected", False))
            if runtime_device is not None
            else None
        ),
        "preflight": None,
    }

    probe_data = copy.deepcopy(device_config)
    probe_data[CONF_DEVICE_ID] = device_id

    try:
        async with asyncio.timeout(timeout):
            report = await async_device_preflight(
                hass,
                probe_data,
            )
    except TimeoutError:
        result["probe_error_type"] = "TimeoutError"
        return result
    except Exception as ex:  # noqa: BLE001 - health reporting must fail closed.
        # Only the class name is safe. Exception messages from protocol/network
        # libraries can contain private addresses, IDs or credentials.
        result["probe_error_type"] = type(ex).__name__
        return result

    result["preflight"] = report.as_dict()
    return result
