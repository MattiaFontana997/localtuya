"""Home Assistant Repairs integration for LocalTuya reliability failures."""

from __future__ import annotations

import hashlib

from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN

_HOST_RECOVERY_ISSUE_PREFIX = "host_recovery_"
_HEALTH_ISSUE_PREFIX = "device_health_"
_RECOVERED_OUTCOMES = {
    "unchanged",
    "updated",
    "metadata_updated",
}

_HEALTH_TRANSLATIONS = {
    "host_unreachable": "device_health_host_unreachable",
    "auth_or_protocol": "device_health_auth_or_protocol",
    "protocol_not_detected": "device_health_protocol_not_detected",
    "empty_dps": "device_health_empty_dps",
    "invalid_configuration": "device_health_invalid_configuration",
    "probe_error": "device_health_probe_error",
}


def _stable_digest(device_id: str) -> str:
    """Hash private Tuya identifiers before using them in issue IDs."""
    return hashlib.sha256(str(device_id).encode("utf-8")).hexdigest()[:16]


def host_recovery_issue_id(device_id: str) -> str:
    """Return a stable issue ID without exposing the Tuya device identifier."""
    return f"{_HOST_RECOVERY_ISSUE_PREFIX}{_stable_digest(device_id)}"


def device_health_issue_id(device_id: str) -> str:
    """Return the stable device-health issue ID for a configured device."""
    return f"{_HEALTH_ISSUE_PREFIX}{_stable_digest(device_id)}"


def async_clear_host_recovery_issue(hass, device_id: str) -> None:
    """Remove a previously reported host recovery issue for one device."""
    ir.async_delete_issue(
        hass,
        DOMAIN,
        host_recovery_issue_id(device_id),
    )


def async_clear_device_health_issue(hass, device_id: str) -> None:
    """Remove a previously reported health issue for one device."""
    ir.async_delete_issue(hass, DOMAIN, device_health_issue_id(device_id))


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
    """Create or clear a privacy-safe repair issue from a recovery outcome."""
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
        translation_placeholders={"device_name": name},
    )


def async_sync_device_health_issue(
    hass,
    *,
    device_id: str,
    device_name: str | None,
    report,
) -> None:
    """Create/clear a fixable issue for structured device-health failures.

    The issue stores only a friendly name and a stable failure category. It does
    not expose the Tuya Device ID, host, local key, datapoint values, cloud
    credentials or exception messages.
    """
    issue_id = device_health_issue_id(device_id)
    ok = bool(getattr(report, "ok", False))
    if ok:
        ir.async_delete_issue(hass, DOMAIN, issue_id)
        return

    failure = getattr(report, "failure", None)
    failure_value = getattr(failure, "value", failure)
    failure_value = str(failure_value or "")
    translation_key = _HEALTH_TRANSLATIONS.get(failure_value)
    if not translation_key:
        return

    name = str(device_name or "LocalTuya device").strip() or "LocalTuya device"
    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        is_fixable=True,
        is_persistent=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key=translation_key,
        translation_placeholders={"device_name": name},
    )
