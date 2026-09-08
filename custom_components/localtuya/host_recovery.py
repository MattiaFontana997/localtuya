"""Safe automatic recovery for Tuya devices whose LAN address changed.

The helpers in this module validate a newly discovered host with the device's
existing LocalTuya credentials before changing persistent configuration. This
prevents an unauthenticated discovery packet from silently replacing a working
host address.
"""

from __future__ import annotations

import asyncio
import copy
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any

from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_DEVICES,
    CONF_FRIENDLY_NAME,
    CONF_HOST,
)

from .const import ATTR_UPDATED_AT, CONF_PRODUCT_KEY
from .repair_issues import async_sync_host_recovery_issue

_LOGGER = logging.getLogger(__name__)


class HostRecoveryOutcome(str, Enum):
    """Privacy-safe result of one discovered-host recovery attempt."""

    UNCHANGED = "unchanged"
    UPDATED = "updated"
    METADATA_UPDATED = "metadata_updated"
    INVALID_ADDRESS = "invalid_address"
    DEVICE_NOT_CONFIGURED = "device_not_configured"
    VALIDATION_FAILED = "validation_failed"
    STALE = "stale"


@dataclass(slots=True, frozen=True)
class HostRecoveryResult:
    """Result of a host recovery attempt without device/network identifiers."""

    outcome: HostRecoveryOutcome
    validation_error_type: str | None = None

    @property
    def applied(self) -> bool:
        """Return whether persistent configuration was changed."""
        return self.outcome in {
            HostRecoveryOutcome.UPDATED,
            HostRecoveryOutcome.METADATA_UPDATED,
        }

    def as_dict(self) -> dict[str, Any]:
        """Return a privacy-safe diagnostic representation."""
        return {
            "outcome": self.outcome.value,
            "applied": self.applied,
            "validation_error_type": self.validation_error_type,
        }


HostValidator = Callable[[Any, dict[str, Any]], Awaitable[Any]]


def _sync_repair_issue(
    hass,
    device_id: str,
    device_name: str | None,
    result: HostRecoveryResult,
) -> None:
    """Best-effort sync with Home Assistant Repairs.

    Repair-registry availability must never prevent a validated host update.
    Only the exception class is logged so a lower-level message cannot expose
    device credentials or network identifiers.
    """
    try:
        async_sync_host_recovery_issue(
            hass,
            device_id=device_id,
            device_name=device_name,
            outcome=result.outcome,
        )
    except Exception as ex:  # noqa: BLE001 - repair UI is non-critical.
        _LOGGER.debug(
            "Unable to synchronize LocalTuya repair issue: %s",
            type(ex).__name__,
        )


async def async_recover_discovered_host(
    hass,
    config_entry,
    device_id: str,
    candidate_host: str,
    *,
    validator: HostValidator,
    product_key: str | None = None,
) -> HostRecoveryResult:
    """Validate and persist a newly discovered host for a configured device.

    The candidate host is never saved until ``validator`` has successfully
    authenticated and completed the normal LocalTuya LAN validation path.
    Validation exceptions are reduced to their class name so diagnostics never
    retain local keys, device IDs, IP addresses, tokens, or exception messages.

    After awaiting validation, the config entry is read again. If another
    update has already moved the device to a different host, this result is
    treated as stale and is not allowed to overwrite the newer configuration.
    """
    if not isinstance(candidate_host, str) or not candidate_host.strip():
        return HostRecoveryResult(HostRecoveryOutcome.INVALID_ADDRESS)

    candidate_host = candidate_host.strip()

    devices = config_entry.data.get(CONF_DEVICES, {})
    if not isinstance(devices, dict):
        return HostRecoveryResult(HostRecoveryOutcome.DEVICE_NOT_CONFIGURED)

    current = devices.get(device_id)
    if not isinstance(current, dict):
        return HostRecoveryResult(HostRecoveryOutcome.DEVICE_NOT_CONFIGURED)

    device_name = current.get(CONF_FRIENDLY_NAME)
    original_host = str(current.get(CONF_HOST) or "").strip()
    product_changed = (
        product_key is not None
        and current.get(CONF_PRODUCT_KEY) != product_key
    )

    if candidate_host == original_host:
        if not product_changed:
            result = HostRecoveryResult(HostRecoveryOutcome.UNCHANGED)
            _sync_repair_issue(hass, device_id, device_name, result)
            return result

        new_data = copy.deepcopy(dict(config_entry.data))
        latest = new_data.get(CONF_DEVICES, {}).get(device_id)
        if not isinstance(latest, dict):
            return HostRecoveryResult(HostRecoveryOutcome.DEVICE_NOT_CONFIGURED)

        latest[CONF_PRODUCT_KEY] = product_key
        new_data[ATTR_UPDATED_AT] = str(int(time.time() * 1000))
        hass.config_entries.async_update_entry(config_entry, data=new_data)
        result = HostRecoveryResult(HostRecoveryOutcome.METADATA_UPDATED)
        _sync_repair_issue(hass, device_id, device_name, result)
        return result

    probe_data = copy.deepcopy(current)
    probe_data[CONF_DEVICE_ID] = device_id
    probe_data[CONF_HOST] = candidate_host

    try:
        await validator(hass, probe_data)
    except asyncio.CancelledError:
        raise
    except Exception as ex:  # noqa: BLE001 - classification is deliberate.
        result = HostRecoveryResult(
            HostRecoveryOutcome.VALIDATION_FAILED,
            validation_error_type=type(ex).__name__,
        )
        _sync_repair_issue(hass, device_id, device_name, result)
        return result

    # Re-read after the await so a slow validation can never clobber a newer
    # config-entry update that happened while the probe was in flight.
    fresh_devices = config_entry.data.get(CONF_DEVICES, {})
    fresh = fresh_devices.get(device_id) if isinstance(fresh_devices, dict) else None
    if not isinstance(fresh, dict):
        return HostRecoveryResult(HostRecoveryOutcome.DEVICE_NOT_CONFIGURED)

    fresh_host = str(fresh.get(CONF_HOST) or "").strip()
    if fresh_host not in {original_host, candidate_host}:
        return HostRecoveryResult(HostRecoveryOutcome.STALE)

    product_changed = (
        product_key is not None
        and fresh.get(CONF_PRODUCT_KEY) != product_key
    )

    if fresh_host == candidate_host and not product_changed:
        result = HostRecoveryResult(HostRecoveryOutcome.UNCHANGED)
        _sync_repair_issue(hass, device_id, device_name, result)
        return result

    new_data = copy.deepcopy(dict(config_entry.data))
    latest = new_data[CONF_DEVICES][device_id]
    latest[CONF_HOST] = candidate_host

    if product_key is not None:
        latest[CONF_PRODUCT_KEY] = product_key

    new_data[ATTR_UPDATED_AT] = str(int(time.time() * 1000))
    hass.config_entries.async_update_entry(config_entry, data=new_data)

    result = HostRecoveryResult(HostRecoveryOutcome.UPDATED)
    _sync_repair_issue(hass, device_id, device_name, result)
    return result
