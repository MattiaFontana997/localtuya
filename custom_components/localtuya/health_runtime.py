"""Runtime helpers for privacy-safe LocalTuya device health snapshots."""

from __future__ import annotations

import asyncio
import copy
from typing import Any

from homeassistant.const import CONF_DEVICE_ID, CONF_FRIENDLY_NAME
from homeassistant.core import HomeAssistant

from .const import CONF_PROTOCOL_VERSION, DOMAIN, TUYA_DEVICES
from .device_health import DeviceHealthFailure, DeviceHealthReport, DeviceHealthStage
from .device_probe import async_device_preflight
from .repair_issues import async_sync_device_health_issue

DEVICE_HEALTH_PROBE_TIMEOUT = 10.0


def _failure_report(device_config: dict[str, Any]) -> DeviceHealthReport:
    """Return a safe generic probe-failure report for bounded runtime errors."""
    return DeviceHealthReport(
        requested_protocol=str(device_config.get(CONF_PROTOCOL_VERSION, "auto")),
        stage=DeviceHealthStage.PROTOCOL,
        failure=DeviceHealthFailure.PROBE_ERROR,
    )


async def async_build_device_health_snapshot(
    hass: HomeAssistant,
    device_id: str,
    device_config: dict[str, Any],
    *,
    timeout: float = DEVICE_HEALTH_PROBE_TIMEOUT,
) -> dict[str, Any]:
    """Return a bounded health snapshot and keep Repairs in sync.

    Device identifiers, local keys, network addresses, raw datapoint values and
    exception messages are deliberately excluded from the returned structure and
    from Repair issue data.
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
    device_name = str(
        device_config.get(CONF_FRIENDLY_NAME) or "LocalTuya device"
    )

    try:
        async with asyncio.timeout(timeout):
            report = await async_device_preflight(hass, probe_data)
    except TimeoutError:
        report = _failure_report(device_config)
        result["probe_error_type"] = "TimeoutError"
    except Exception as ex:  # noqa: BLE001 - health reporting must fail closed.
        report = _failure_report(device_config)
        result["probe_error_type"] = type(ex).__name__

    async_sync_device_health_issue(
        hass,
        device_id=device_id,
        device_name=device_name,
        report=report,
    )
    result["preflight"] = report.as_dict()
    return result
