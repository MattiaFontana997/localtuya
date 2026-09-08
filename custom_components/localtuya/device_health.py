"""Privacy-safe device health model for LocalTuya LAN preflight checks.

This module intentionally contains no Home Assistant flow/UI code. It provides
one small, deterministic model that can be reused by onboarding, repairs and
diagnostics without ever storing device credentials or exception messages.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class DeviceHealthStage(str, Enum):
    """Furthest meaningful stage reached by a device preflight."""

    CONFIGURATION = "configuration"
    LAN = "lan"
    PROTOCOL = "protocol"
    DATAPOINTS = "datapoints"
    READY = "ready"


class DeviceHealthFailure(str, Enum):
    """Privacy-safe reason why a device preflight did not complete."""

    INVALID_CONFIGURATION = "invalid_configuration"
    HOST_UNREACHABLE = "host_unreachable"
    AUTH_OR_PROTOCOL = "auth_or_protocol"
    PROTOCOL_NOT_DETECTED = "protocol_not_detected"
    EMPTY_DPS = "empty_dps"
    PROBE_ERROR = "probe_error"


class DeviceHealthAction(str, Enum):
    """User-facing recovery action suitable for diagnostics and Repairs."""

    REVIEW_CONFIGURATION = "review_configuration"
    REDISCOVER_HOST = "rediscover_host"
    VERIFY_CREDENTIALS_OR_PROTOCOL = "verify_credentials_or_protocol"
    SELECT_PROTOCOL = "select_protocol"
    REVIEW_DATAPOINTS = "review_datapoints"
    RETRY = "retry"


class ProtocolProbeOutcome(str, Enum):
    """Result of one protocol-version attempt."""

    SUCCESS = "success"
    HOST_UNREACHABLE = "host_unreachable"
    AUTH_OR_PROTOCOL = "auth_or_protocol"
    NO_DPS = "no_dps"
    ERROR = "error"


_FAILURE_ACTIONS = {
    DeviceHealthFailure.INVALID_CONFIGURATION:
        DeviceHealthAction.REVIEW_CONFIGURATION,
    DeviceHealthFailure.HOST_UNREACHABLE:
        DeviceHealthAction.REDISCOVER_HOST,
    DeviceHealthFailure.AUTH_OR_PROTOCOL:
        DeviceHealthAction.VERIFY_CREDENTIALS_OR_PROTOCOL,
    DeviceHealthFailure.PROTOCOL_NOT_DETECTED:
        DeviceHealthAction.SELECT_PROTOCOL,
    DeviceHealthFailure.EMPTY_DPS:
        DeviceHealthAction.REVIEW_DATAPOINTS,
    DeviceHealthFailure.PROBE_ERROR:
        DeviceHealthAction.RETRY,
}


@dataclass(slots=True, frozen=True)
class ProtocolProbeHealth:
    """Safe summary of a single protocol probe.

    ``error_type`` contains only the exception class name. Exception text is
    deliberately discarded because lower-level networking/protocol libraries
    can include device identifiers or credentials in their messages.
    """

    protocol: str
    outcome: ProtocolProbeOutcome
    dps_count: int = 0
    error_type: str | None = None

    def as_dict(self) -> dict[str, Any]:
        """Return a serialization safe for diagnostics."""
        return {
            "protocol": self.protocol,
            "outcome": self.outcome.value,
            "dps_count": self.dps_count,
            "error_type": self.error_type,
        }


@dataclass(slots=True)
class DeviceHealthReport:
    """Structured result of a complete LocalTuya LAN preflight.

    Raw datapoint values are retained only for the caller that needs to finish
    configuration. They are excluded from ``repr`` and from ``as_dict()``.
    The report never receives/stores host, Device ID, local_key, account data or
    QR authorization material.
    """

    requested_protocol: str
    stage: DeviceHealthStage
    attempts: list[ProtocolProbeHealth] = field(default_factory=list)
    resolved_protocol: str | None = None
    failure: DeviceHealthFailure | None = None
    detected_dps: dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def ok(self) -> bool:
        """Return whether the device completed local validation."""
        return self.stage is DeviceHealthStage.READY and self.failure is None

    @property
    def dp_ids(self) -> list[int]:
        """Return sorted numeric datapoint IDs without exposing values."""
        result: set[int] = set()
        for raw_id in self.detected_dps:
            try:
                result.add(int(raw_id))
            except (TypeError, ValueError):
                continue
        return sorted(result)

    @property
    def recommended_action(self) -> DeviceHealthAction | None:
        """Return the stable recovery action associated with this failure."""
        if self.failure is None:
            return None
        return _FAILURE_ACTIONS.get(self.failure, DeviceHealthAction.RETRY)

    @property
    def repair_key(self) -> str | None:
        """Return a stable translation/repair key without device identifiers."""
        action = self.recommended_action
        return f"device_health_{action.value}" if action is not None else None

    def as_dict(self) -> dict[str, Any]:
        """Return a privacy-safe diagnostic representation."""
        action = self.recommended_action
        return {
            "ok": self.ok,
            "stage": self.stage.value,
            "failure": self.failure.value if self.failure else None,
            "recommended_action": action.value if action else None,
            "repair_key": self.repair_key,
            "requested_protocol": self.requested_protocol,
            "resolved_protocol": self.resolved_protocol,
            "dps_count": len(self.detected_dps),
            "dp_ids": self.dp_ids,
            "attempts": [attempt.as_dict() for attempt in self.attempts],
        }


ProbeCallback = Callable[[str], Awaitable[Mapping[Any, Any] | None]]


async def async_run_device_preflight(
    *,
    requested_protocol: str,
    supported_protocols: Sequence[str],
    probe: ProbeCallback,
    auto_protocol: str = "auto",
    network_error_types: tuple[type[BaseException], ...] = (
        ConnectionRefusedError,
        ConnectionResetError,
        OSError,
        TimeoutError,
    ),
    auth_or_protocol_error_types: tuple[type[BaseException], ...] = (),
) -> DeviceHealthReport:
    """Probe a device and return a structured health report.

    Protocol auto-detection deliberately tries incompatible versions, so a
    decryption/authentication-looking failure on one attempt is *not* treated
    as definitive invalid credentials. We record it as ``auth_or_protocol``
    and decide only after every candidate protocol has been attempted.
    """
    requested = str(requested_protocol or auto_protocol)
    supported = tuple(str(version) for version in supported_protocols)

    if requested != auto_protocol and requested not in supported:
        return DeviceHealthReport(
            requested_protocol=requested,
            stage=DeviceHealthStage.CONFIGURATION,
            failure=DeviceHealthFailure.INVALID_CONFIGURATION,
        )

    protocols = supported if requested == auto_protocol else (requested,)
    attempts: list[ProtocolProbeHealth] = []

    for protocol in protocols:
        try:
            raw_dps = await probe(protocol)
        except Exception as ex:  # noqa: BLE001 - classification is the purpose here.
            if isinstance(ex, network_error_types):
                outcome = ProtocolProbeOutcome.HOST_UNREACHABLE
            elif auth_or_protocol_error_types and isinstance(
                ex,
                auth_or_protocol_error_types,
            ):
                outcome = ProtocolProbeOutcome.AUTH_OR_PROTOCOL
            else:
                outcome = ProtocolProbeOutcome.ERROR

            attempts.append(
                ProtocolProbeHealth(
                    protocol=protocol,
                    outcome=outcome,
                    error_type=type(ex).__name__,
                )
            )
            continue

        dps = dict(raw_dps or {})
        if not dps:
            attempts.append(
                ProtocolProbeHealth(
                    protocol=protocol,
                    outcome=ProtocolProbeOutcome.NO_DPS,
                )
            )
            continue

        attempts.append(
            ProtocolProbeHealth(
                protocol=protocol,
                outcome=ProtocolProbeOutcome.SUCCESS,
                dps_count=len(dps),
            )
        )
        return DeviceHealthReport(
            requested_protocol=requested,
            resolved_protocol=protocol,
            stage=DeviceHealthStage.READY,
            attempts=attempts,
            detected_dps=dps,
        )

    outcomes = {attempt.outcome for attempt in attempts}

    if attempts and outcomes == {ProtocolProbeOutcome.HOST_UNREACHABLE}:
        stage = DeviceHealthStage.LAN
        failure = DeviceHealthFailure.HOST_UNREACHABLE
    elif ProtocolProbeOutcome.NO_DPS in outcomes:
        # At least one protocol completed far enough to query datapoints.
        stage = DeviceHealthStage.DATAPOINTS
        failure = DeviceHealthFailure.EMPTY_DPS
    elif ProtocolProbeOutcome.AUTH_OR_PROTOCOL in outcomes:
        stage = DeviceHealthStage.PROTOCOL
        failure = DeviceHealthFailure.AUTH_OR_PROTOCOL
    elif ProtocolProbeOutcome.ERROR in outcomes:
        stage = DeviceHealthStage.PROTOCOL
        failure = DeviceHealthFailure.PROBE_ERROR
    else:
        stage = DeviceHealthStage.PROTOCOL
        failure = DeviceHealthFailure.PROTOCOL_NOT_DETECTED

    return DeviceHealthReport(
        requested_protocol=requested,
        stage=stage,
        attempts=attempts,
        failure=failure,
    )
