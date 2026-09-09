"""Home Assistant Repairs integration for LocalTuya reliability failures."""

from __future__ import annotations

import hashlib

from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN

_HOST_RECOVERY_ISSUE_PREFIX = "host_recovery_"
_HEALTH_ISSUE_PREFIX = "device_health_"
_RECOVERED_OUTCOMES = {"unchanged", "updated", "metadata_updated"}

HEALTH_FAILURE_TRANSLATIONS = {
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


def device_health_issue_id(device_id: str, failure: str) -> str:
    """Return a stable issue ID for one health failure category."""
    safe_failure = str(failure).strip().lower().replace(" ", "_")
    return f"{_HEALTH_ISSUE_PREFIX}{safe_failure}_{_stable_digest(device_id)}"


def async_clear_host_recovery_issue(hass, device_id: str) -> None:
    """Remove a previously reported host recovery issue."""
    ir.async_delete_issue(hass, DOMAIN, host_recovery_issue_id(device_id))


def async_clear_device_health_issues(hass, device_id: str) -> None:
    """Remove every known health issue for a device."""
    for failure in HEALTH_FAILURE_TRANSLATIONS:
        ir.async_delete_issue(hass, DOMAIN, device_health_issue_id(device_id, failure))


def _outcome_value(outcome) -> str:
    return str(getattr(outcome, "value", outcome))


def async_sync_host_recovery_issue(
    hass,
    *,
    device_id: str,
    device_name: str | None,
    outcome,
) -> None:
    """Create or clear a privacy-safe host-recovery issue."""
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
    """Keep exactly one fixable health issue in sync with a preflight report."""
    if bool(getattr(report, "ok", False)):
        async_clear_device_health_issues(hass, device_id)
        return

    failure = getattr(report, "failure", None)
    failure_value = str(getattr(failure, "value", failure) or "")
    translation_key = HEALTH_FAILURE_TRANSLATIONS.get(failure_value)
    if not translation_key:
        return

    async_clear_device_health_issues(hass, device_id)
    name = str(device_name or "LocalTuya device").strip() or "LocalTuya device"
    ir.async_create_issue(
        hass,
        DOMAIN,
        device_health_issue_id(device_id, failure_value),
        is_fixable=True,
        is_persistent=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key=translation_key,
        translation_placeholders={"device_name": name},
    )
