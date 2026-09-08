"""Home Assistant Repairs integration for LocalTuya reliability failures."""

from __future__ import annotations

import hashlib

from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN

_HOST_RECOVERY_ISSUE_PREFIX = "host_recovery_"
_RECOVERED_OUTCOMES = {
    "unchanged",
    "updated",
    "metadata_updated",
}


def host_recovery_issue_id(device_id: str) -> str:
    """Return a stable issue ID without exposing the Tuya device identifier."""
    digest = hashlib.sha256(str(device_id).encode("utf-8")).hexdigest()[:16]
    return f"{_HOST_RECOVERY_ISSUE_PREFIX}{digest}"


def async_clear_host_recovery_issue(hass, device_id: str) -> None:
    """Remove a previously reported host recovery issue for one device."""
    ir.async_delete_issue(
        hass,
        DOMAIN,
        host_recovery_issue_id(device_id),
    )


def _outcome_value(outcome) -> str:
    """Normalize an enum/string outcome without importing recovery internals."""
    value = getattr(outcome, "value", outcome)
    return str(value)


def async_sync_host_recovery_issue(
    hass,
    *,
    device_id: str,
    device_name: str | None,
    outcome,
) -> None:
    """Create or clear a privacy-safe repair issue from a recovery outcome.

    Only the user-assigned/friendly device name is shown. The issue ID is a
    one-way digest and the issue stores no Tuya Device ID, local key, IP address,
    QR authorization material, exception message, or raw datapoint value.
    """
    issue_id = host_recovery_issue_id(device_id)
    normalized = _outcome_value(outcome)

    if normalized in _RECOVERED_OUTCOMES:
        ir.async_delete_issue(hass, DOMAIN, issue_id)
        return

    if normalized != "validation_failed":
        return

    name = str(device_name or "LocalTuya device").strip() or "LocalTuya device"

    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        is_fixable=True,
        is_persistent=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key="host_recovery_failed",
        translation_placeholders={
            "device_name": name,
        },
    )
