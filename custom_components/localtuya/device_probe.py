"""Low-level LAN protocol preflight for LocalTuya devices.

This module contains the reusable network probe used by onboarding, diagnostics,
health services and repairs. It deliberately has no config-flow or UI imports so
runtime health checks do not depend on Home Assistant flow implementation code.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.const import CONF_DEVICE_ID, CONF_HOST
from homeassistant.core import HomeAssistant

from .common import pytuya
from .const import (
    CONF_ENABLE_DEBUG,
    CONF_LOCAL_KEY,
    CONF_PROTOCOL_VERSION,
    CONF_RESET_DPIDS,
)
from .device_health import (
    DeviceHealthFailure,
    DeviceHealthReport,
    DeviceHealthStage,
    async_run_device_preflight,
)

_LOGGER = logging.getLogger(__name__)

PROTOCOL_AUTO = "auto"
SUPPORTED_PROTOCOL_VERSIONS = (
    "3.5",
    "3.4",
    "3.3",
    "3.2",
    "3.1",
)
PROTOCOL_OPTIONS = (
    PROTOCOL_AUTO,
    *SUPPORTED_PROTOCOL_VERSIONS,
)
PROTOCOL_PROBE_TIMEOUT = 8.0


async def _async_probe_protocol(
    data: dict[str, Any],
    protocol_version: str,
    reset_ids: list[int],
) -> dict[Any, Any]:
    """Probe one Tuya LAN protocol and return detected datapoints."""
    interface = None

    try:
        async with asyncio.timeout(PROTOCOL_PROBE_TIMEOUT):
            interface = await pytuya.connect(
                data[CONF_HOST],
                data[CONF_DEVICE_ID],
                data[CONF_LOCAL_KEY],
                float(protocol_version),
                data.get(CONF_ENABLE_DEBUG, False),
            )

            try:
                detected_dps = await interface.detect_available_dps()
            except Exception as ex:
                if protocol_version == "3.3" and reset_ids:
                    _LOGGER.debug(
                        "Initial DPS detection failed using protocol %s (%s); "
                        "trying reset IDs %s",
                        protocol_version,
                        type(ex).__name__,
                        reset_ids,
                    )
                    await interface.reset(reset_ids)
                    detected_dps = await interface.detect_available_dps()
                else:
                    raise

            return detected_dps or {}
    finally:
        if interface is not None:
            try:
                await interface.close()
            except Exception as ex:  # noqa: BLE001 - cleanup must not mask probe result.
                _LOGGER.debug(
                    "Error closing protocol %s probe: %s",
                    protocol_version,
                    type(ex).__name__,
                )


def reset_ids_from_data(data: dict[str, Any]) -> list[int]:
    """Parse optional reset DPIDs without retaining other device data."""
    reset_ids_value = data.get(CONF_RESET_DPIDS)
    if not reset_ids_value:
        return []
    if not isinstance(reset_ids_value, str):
        raise ValueError("reset DPIDs must be a comma-separated string")

    return [
        int(value.strip())
        for value in reset_ids_value.split(",")
        if value.strip()
    ]


async def async_device_preflight(
    hass: HomeAssistant | None,
    data: dict[str, Any],
) -> DeviceHealthReport:
    """Run a structured, privacy-safe LAN/protocol/DPS preflight."""
    del hass

    requested_protocol = data.get(
        CONF_PROTOCOL_VERSION,
        PROTOCOL_AUTO,
    )

    try:
        reset_ids = reset_ids_from_data(data)
    except (TypeError, ValueError):
        report = DeviceHealthReport(
            requested_protocol=str(requested_protocol),
            stage=DeviceHealthStage.CONFIGURATION,
            failure=DeviceHealthFailure.INVALID_CONFIGURATION,
        )
        _LOGGER.debug("LocalTuya preflight result: %s", report.as_dict())
        return report

    async def probe(protocol_version: str):
        return await _async_probe_protocol(
            data,
            protocol_version,
            reset_ids,
        )

    report = await async_run_device_preflight(
        requested_protocol=str(requested_protocol),
        supported_protocols=SUPPORTED_PROTOCOL_VERSIONS,
        probe=probe,
        auto_protocol=PROTOCOL_AUTO,
        auth_or_protocol_error_types=(
            pytuya.DecodeError,
            ValueError,
        ),
    )

    _LOGGER.debug("LocalTuya preflight result: %s", report.as_dict())
    return report
