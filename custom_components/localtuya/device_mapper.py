"""Generic Tuya Cloud metadata to LocalTuya entity mapper."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from typing import Any

from homeassistant.components.sensor import CONF_STATE_CLASS
from homeassistant.const import (
    CONF_BRIGHTNESS,
    CONF_COLOR_TEMP,
    CONF_DEVICE_CLASS,
    CONF_FRIENDLY_NAME,
    CONF_ID,
    CONF_PLATFORM,
    CONF_TEMPERATURE_UNIT,
    CONF_UNIT_OF_MEASUREMENT,
)

from .const import (
    CONF_BRIGHTNESS_LOWER,
    CONF_BRIGHTNESS_UPPER,
    CONF_COLOR,
    CONF_COLOR_MODE,
    CONF_CURRENT_TEMPERATURE_DP,
    CONF_PRECISION,
    CONF_PRESET_DP,
    CONF_PRESET_SET,
    CONF_SCALING,
    CONF_TARGET_PRECISION,
    CONF_TARGET_TEMPERATURE_DP,
    CONF_TEMPERATURE_STEP,
    CONF_TEMP_MAX,
    CONF_TEMP_MIN,
)


class MappingConfidence(str, Enum):
    """Confidence assigned to an automatically mapped entity."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass(frozen=True, slots=True)
class DpMetadata:
    """Normalized metadata for one Tuya datapoint."""

    id: int
    code: str
    type_name: str
    values: dict[str, Any]
    readable: bool
    writable: bool


@dataclass(frozen=True, slots=True)
class EntityCandidate:
    """One entity proposed by the generic mapper."""

    platform: str
    primary_dp: int
    confidence: MappingConfidence
    config: dict[str, Any]
    matched_codes: tuple[str, ...]
    referenced_dps: tuple[int, ...] = ()


_LIGHT_POWER_CODES = (
    "switch_led",
    "switch_led_1",
)

_LIGHT_BRIGHTNESS_CODES = (
    "bright_value_v2",
    "bright_value",
)

_LIGHT_TEMPERATURE_CODES = (
    "temp_value_v2",
    "temp_value",
)

_LIGHT_MODE_CODES = (
    "work_mode",
)

# LocalTuya's current light implementation expects the older encoded
# string representation for the color DP. Tuya colour_data_v2 is often
# structured JSON, so it must not be mapped automatically yet.
_LIGHT_COLOR_CODES = (
    "colour_data",
    "color_data",
)

_THERMOSTAT_CATEGORIES = {
    "wk",
}

_THERMOSTAT_POWER_CODES = (
    "switch",
)

_THERMOSTAT_TARGET_TEMP_CODES = (
    "temp_set",
)

_THERMOSTAT_CURRENT_TEMP_CODES = (
    "temp_current",
)

_THERMOSTAT_PRESET_CODES = (
    "mode",
)

THERMOSTAT_PRESET_AUTO_MANUAL_HOLIDAY = (
    "auto/manual/holiday"
)

_SENSOR_RULES = {
    "cur_voltage": (
        "Voltage",
        "voltage",
        "V",
    ),
    "voltage": (
        "Voltage",
        "voltage",
        "V",
    ),
    "cur_current": (
        "Current",
        "current",
        "A",
    ),
    "current": (
        "Current",
        "current",
        "A",
    ),
    "cur_power": (
        "Power",
        "power",
        "W",
    ),
    "power": (
        "Power",
        "power",
        "W",
    ),
    "temp_current": (
        "Temperature",
        "temperature",
        "°C",
    ),
}


def _parse_values(value: Any) -> dict[str, Any]:
    """Normalize Tuya values metadata to a dictionary."""
    if isinstance(value, dict):
        return dict(value)

    if not isinstance(value, str) or not value:
        return {}

    try:
        parsed = json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}

    return parsed if isinstance(parsed, dict) else {}


def _coerce_dp_id(value: Any) -> int | None:
    """Convert a possible Tuya DP identifier to int."""
    if isinstance(value, bool):
        return None

    try:
        dp_id = int(value)
    except (TypeError, ValueError):
        return None

    if not 0 < dp_id < 10000:
        return None

    return dp_id


def _normalized_code(value: Any) -> str:
    """Normalize a Tuya function code."""
    if not isinstance(value, str):
        return ""

    return value.strip().lower()


def _normalized_type(value: Any) -> str:
    """Normalize a Tuya datatype."""
    if not isinstance(value, str):
        return ""

    return value.strip().lower()


def _metadata_from_entry(
    dp_id: int,
    entry: dict[str, Any],
    *,
    readable: bool,
    writable: bool,
) -> DpMetadata:
    """Create normalized metadata from one Cloud/mapping entry."""
    values = _parse_values(entry.get("values"))

    if not values:
        values = _parse_values(entry.get("raw_values"))

    return DpMetadata(
        id=dp_id,
        code=_normalized_code(entry.get("code")),
        type_name=_normalized_type(entry.get("type")),
        values=values,
        readable=readable,
        writable=writable,
    )


def _merge_metadata(
    current: DpMetadata | None,
    incoming: DpMetadata,
) -> DpMetadata:
    """Merge metadata about the same Tuya DP."""
    if current is None:
        return incoming

    return DpMetadata(
        id=current.id,
        code=incoming.code or current.code,
        type_name=incoming.type_name or current.type_name,
        values=incoming.values or current.values,
        readable=current.readable or incoming.readable,
        writable=current.writable or incoming.writable,
    )


def normalize_device_metadata(
    device: dict[str, Any] | None = None,
    specification: dict[str, Any] | None = None,
) -> dict[int, DpMetadata]:
    """Normalize TinyTuya mapping and Tuya Cloud specification formats.

    ``device["mapping"]`` is the mapping format commonly returned by
    TinyTuya/device scans.

    Tuya Cloud device specifications expose ``functions`` and ``status``.
    The two sources are merged by DP id.
    """
    normalized: dict[int, DpMetadata] = {}

    device = device or {}
    specification = specification or {}

    mapping = device.get("mapping")

    if isinstance(mapping, dict):
        for raw_dp_id, raw_entry in mapping.items():
            if not isinstance(raw_entry, dict):
                continue

            dp_id = _coerce_dp_id(raw_dp_id)

            if dp_id is None:
                dp_id = _coerce_dp_id(
                    raw_entry.get("dp_id")
                    or raw_entry.get("id")
                )

            if dp_id is None:
                continue

            metadata = _metadata_from_entry(
                dp_id,
                raw_entry,
                readable=True,
                writable=True,
            )

            normalized[dp_id] = _merge_metadata(
                normalized.get(dp_id),
                metadata,
            )

    cloud_collections = (
        ("functions", False, True),
        ("status", True, False),
    )

    for collection_name, readable, writable in cloud_collections:
        collection = specification.get(collection_name)

        if not isinstance(collection, list):
            continue

        for raw_entry in collection:
            if not isinstance(raw_entry, dict):
                continue

            dp_id = _coerce_dp_id(
                raw_entry.get("dp_id")
                or raw_entry.get("id")
            )

            if dp_id is None:
                continue

            metadata = _metadata_from_entry(
                dp_id,
                raw_entry,
                readable=readable,
                writable=writable,
            )

            normalized[dp_id] = _merge_metadata(
                normalized.get(dp_id),
                metadata,
            )

    return dict(sorted(normalized.items()))


def _find_by_codes(
    metadata: dict[int, DpMetadata],
    codes: tuple[str, ...],
) -> DpMetadata | None:
    """Return the first DP matching the preferred code order."""
    by_code = {
        dp.code: dp
        for dp in metadata.values()
        if dp.code
    }

    for code in codes:
        if code in by_code:
            return by_code[code]

    return None


def _numeric_value(
    metadata: DpMetadata | None,
    key: str,
) -> float | None:
    """Read a numeric property from DP metadata."""
    if metadata is None:
        return None

    value = metadata.values.get(key)

    if isinstance(value, bool):
        return None

    if isinstance(value, (int, float)):
        return float(value)

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _integer_range(
    metadata: DpMetadata | None,
) -> tuple[int, int] | None:
    """Return min/max metadata when usable."""
    minimum = _numeric_value(metadata, "min")
    maximum = _numeric_value(metadata, "max")

    if minimum is None or maximum is None:
        return None

    minimum = int(minimum)
    maximum = int(maximum)

    if maximum <= minimum:
        return None

    return minimum, maximum


def _device_name(
    device: dict[str, Any],
    fallback: str,
) -> str:
    """Return the best available friendly device name."""
    for key in (
        "name",
        "product_name",
        "model",
    ):
        value = device.get(key)

        if isinstance(value, str) and value.strip():
            return value.strip()

    return fallback


def _build_light_candidate(
    device: dict[str, Any],
    metadata: dict[int, DpMetadata],
) -> EntityCandidate | None:
    """Build a generic Tuya light candidate."""
    power = _find_by_codes(
        metadata,
        _LIGHT_POWER_CODES,
    )

    if power is None:
        return None

    # switch_led is strong semantic evidence that this is a light.
    if power.type_name not in ("", "boolean", "bool"):
        return None

    brightness = _find_by_codes(
        metadata,
        _LIGHT_BRIGHTNESS_CODES,
    )

    color_temp = _find_by_codes(
        metadata,
        _LIGHT_TEMPERATURE_CODES,
    )

    work_mode = _find_by_codes(
        metadata,
        _LIGHT_MODE_CODES,
    )

    color = _find_by_codes(
        metadata,
        _LIGHT_COLOR_CODES,
    )

    config: dict[str, Any] = {
        CONF_ID: power.id,
        CONF_FRIENDLY_NAME: _device_name(
            device,
            "Tuya Light",
        ),
        CONF_PLATFORM: "light",
    }

    matched_codes = [power.code]

    brightness_range = _integer_range(brightness)

    if brightness is not None:
        config[CONF_BRIGHTNESS] = brightness.id
        matched_codes.append(brightness.code)

        if brightness_range is not None:
            config[CONF_BRIGHTNESS_LOWER] = (
                brightness_range[0]
            )
            config[CONF_BRIGHTNESS_UPPER] = (
                brightness_range[1]
            )

    if color_temp is not None:
        temperature_range = _integer_range(color_temp)

        # Current LocalTuya light code uses brightness_upper as the
        # raw color-temperature maximum. Auto-map temperature only
        # where the metadata confirms the ranges are compatible.
        brightness_max = (
            brightness_range[1]
            if brightness_range is not None
            else 1000
        )

        temperature_max = (
            temperature_range[1]
            if temperature_range is not None
            else brightness_max
        )

        if temperature_max == brightness_max:
            config[CONF_COLOR_TEMP] = color_temp.id
            matched_codes.append(color_temp.code)

    if work_mode is not None:
        modes = work_mode.values.get("range", [])

        if (
            not modes
            or (
                isinstance(modes, list)
                and "white" in modes
            )
        ):
            config[CONF_COLOR_MODE] = work_mode.id
            matched_codes.append(work_mode.code)

    if (
        color is not None
        and color.type_name in ("", "string", "raw")
    ):
        config[CONF_COLOR] = color.id
        matched_codes.append(color.code)

    referenced_dps = [power.id]

    for dp in (
        brightness,
        color_temp,
        work_mode,
        color,
    ):
        if (
            dp is not None
            and dp.id in config.values()
            and dp.id not in referenced_dps
        ):
            referenced_dps.append(dp.id)

    return EntityCandidate(
        platform="light",
        primary_dp=power.id,
        confidence=MappingConfidence.HIGH,
        config=config,
        matched_codes=tuple(matched_codes),
        referenced_dps=tuple(referenced_dps),
    )


def _build_climate_candidate(
    device: dict[str, Any],
    metadata: dict[int, DpMetadata],
) -> EntityCandidate | None:
    """Build a high-confidence thermostat candidate."""
    category = str(
        device.get("category") or ""
    ).strip().lower()

    if category not in _THERMOSTAT_CATEGORIES:
        return None

    power = _find_by_codes(
        metadata,
        _THERMOSTAT_POWER_CODES,
    )

    target_temperature = _find_by_codes(
        metadata,
        _THERMOSTAT_TARGET_TEMP_CODES,
    )

    current_temperature = _find_by_codes(
        metadata,
        _THERMOSTAT_CURRENT_TEMP_CODES,
    )

    # For HIGH confidence require the canonical thermostat
    # trio plus the power DP.
    if (
        power is None
        or target_temperature is None
        or current_temperature is None
    ):
        return None

    if power.type_name not in (
        "",
        "boolean",
        "bool",
    ):
        return None

    numeric_types = {
        "",
        "integer",
        "value",
        "float",
        "double",
    }

    if (
        target_temperature.type_name
        not in numeric_types
        or current_temperature.type_name
        not in numeric_types
    ):
        return None

    target_factor = _tuya_scale_factor(
        target_temperature
    )

    current_factor = _tuya_scale_factor(
        current_temperature
    )

    # Scale is required for automatic climate configuration.
    # Guessing temperature scaling would be unsafe.
    if (
        target_factor is None
        or current_factor is None
    ):
        return None

    config: dict[str, Any] = {
        CONF_ID: power.id,
        CONF_FRIENDLY_NAME: _device_name(
            device,
            "Tuya Thermostat",
        ),
        CONF_PLATFORM: "climate",
        CONF_TARGET_TEMPERATURE_DP:
            target_temperature.id,
        CONF_CURRENT_TEMPERATURE_DP:
            current_temperature.id,
        CONF_TARGET_PRECISION:
            target_factor,
        CONF_PRECISION:
            current_factor,
    }

    matched_codes = [
        power.code,
        target_temperature.code,
        current_temperature.code,
    ]

    referenced_dps = [
        power.id,
        target_temperature.id,
        current_temperature.id,
    ]

    unit = (
        target_temperature.values.get("unit")
        or current_temperature.values.get("unit")
    )

    normalized_unit = str(
        unit or ""
    ).strip().lower()

    if normalized_unit in {
        "℃",
        "°c",
        "c",
        "celsius",
    }:
        config[
            CONF_TEMPERATURE_UNIT
        ] = "celsius"

    elif normalized_unit in {
        "℉",
        "°f",
        "f",
        "fahrenheit",
    }:
        config[
            CONF_TEMPERATURE_UNIT
        ] = "fahrenheit"

    raw_min = _numeric_value(
        target_temperature,
        "min",
    )

    raw_max = _numeric_value(
        target_temperature,
        "max",
    )

    if (
        raw_min is not None
        and raw_max is not None
        and raw_max > raw_min
    ):
        config[CONF_TEMP_MIN] = round(
            raw_min * target_factor,
            4,
        )

        config[CONF_TEMP_MAX] = round(
            raw_max * target_factor,
            4,
        )

    raw_step = _numeric_value(
        target_temperature,
        "step",
    )

    if raw_step is not None and raw_step > 0:
        real_step = round(
            raw_step * target_factor,
            4,
        )

        # Current LocalTuya climate config flow supports
        # these standard HA increments.
        if real_step in {
            0.1,
            0.5,
            1.0,
        }:
            config[
                CONF_TEMPERATURE_STEP
            ] = real_step

    preset = _find_by_codes(
        metadata,
        _THERMOSTAT_PRESET_CODES,
    )

    if preset is not None:
        raw_range = preset.values.get(
            "range",
            [],
        )

        if isinstance(raw_range, list):
            preset_values = {
                str(value).strip().lower()
                for value in raw_range
            }

            if preset_values == {
                "auto",
                "manual",
                "holiday",
            }:
                config[
                    CONF_PRESET_DP
                ] = preset.id

                config[
                    CONF_PRESET_SET
                ] = (
                    THERMOSTAT_PRESET_AUTO_MANUAL_HOLIDAY
                )

                matched_codes.append(
                    preset.code
                )

                referenced_dps.append(
                    preset.id
                )

    # Do not infer CONF_HVAC_MODE_DP from generic "mode".
    # Some thermostats, including the real test device, expose
    # their actual HVAC mode only through undocumented LAN DPS.
    return EntityCandidate(
        platform="climate",
        primary_dp=power.id,
        confidence=MappingConfidence.HIGH,
        config=config,
        matched_codes=tuple(matched_codes),
        referenced_dps=tuple(referenced_dps),
    )


def _build_switch_candidates(
    device: dict[str, Any],
    metadata: dict[int, DpMetadata],
    consumed_dps: set[int],
) -> list[EntityCandidate]:
    """Build generic switch candidates."""
    candidates: list[EntityCandidate] = []

    device_name = _device_name(
        device,
        "Tuya Device",
    )

    for dp in metadata.values():
        if dp.id in consumed_dps:
            continue

        if dp.code == "switch_led":
            continue

        if not (
            dp.code == "switch"
            or dp.code.startswith("switch_")
        ):
            continue

        if dp.type_name not in ("", "boolean", "bool"):
            continue

        suffix = ""

        if dp.code.startswith("switch_"):
            suffix = (
                dp.code.removeprefix("switch_")
                .replace("_", " ")
                .strip()
            )

        friendly_name = device_name

        if suffix and suffix != "1":
            friendly_name = (
                f"{device_name} Switch {suffix.title()}"
            )

        candidates.append(
            EntityCandidate(
                platform="switch",
                primary_dp=dp.id,
                confidence=MappingConfidence.HIGH,
                config={
                    CONF_ID: dp.id,
                    CONF_FRIENDLY_NAME: friendly_name,
                    CONF_PLATFORM: "switch",
                },
                matched_codes=(dp.code,),
                referenced_dps=(dp.id,),
            )
        )

    return candidates


def _tuya_scale_factor(
    dp: DpMetadata,
) -> float | None:
    """Return the numeric multiplier represented by Tuya scale."""
    scale = dp.values.get("scale")

    if isinstance(scale, bool):
        return None

    try:
        scale = int(scale)
    except (TypeError, ValueError):
        return None

    if not 0 <= scale <= 10:
        return None

    return 10 ** (-scale)


def _tuya_scaling(
    dp: DpMetadata,
) -> float | None:
    """Translate Tuya decimal scale metadata into LocalTuya scaling."""
    factor = _tuya_scale_factor(dp)

    if factor is None or factor == 1.0:
        return None

    return factor


def _normalize_unit(unit: Any, fallback: str) -> str:
    """Normalize common Tuya unit strings."""
    if not isinstance(unit, str) or not unit.strip():
        return fallback

    unit = unit.strip()

    aliases = {
        "℃": "°C",
        "°c": "°C",
        "℉": "°F",
        "°f": "°F",
    }

    return aliases.get(
        unit.lower(),
        aliases.get(unit, unit),
    )


def _build_sensor_candidates(
    device: dict[str, Any],
    metadata: dict[int, DpMetadata],
    consumed_dps: set[int],
) -> list[EntityCandidate]:
    """Build high-confidence measurement sensor candidates."""
    candidates: list[EntityCandidate] = []

    device_name = _device_name(
        device,
        "Tuya Device",
    )

    for dp in metadata.values():
        if dp.id in consumed_dps:
            continue

        rule = _SENSOR_RULES.get(dp.code)

        if rule is None:
            continue

        if dp.type_name not in (
            "",
            "integer",
            "value",
            "float",
            "double",
        ):
            continue

        label, device_class, fallback_unit = rule

        config: dict[str, Any] = {
            CONF_ID: dp.id,
            CONF_FRIENDLY_NAME: (
                f"{device_name} {label}"
            ),
            CONF_PLATFORM: "sensor",
            CONF_DEVICE_CLASS: device_class,
            CONF_STATE_CLASS: "measurement",
            CONF_UNIT_OF_MEASUREMENT: _normalize_unit(
                dp.values.get("unit"),
                fallback_unit,
            ),
        }

        scaling = _tuya_scaling(dp)

        if scaling is not None:
            config[CONF_SCALING] = scaling

        candidates.append(
            EntityCandidate(
                platform="sensor",
                primary_dp=dp.id,
                confidence=MappingConfidence.HIGH,
                config=config,
                matched_codes=(dp.code,),
                referenced_dps=(dp.id,),
            )
        )

    return candidates


def build_entity_candidates(
    device: dict[str, Any] | None = None,
    specification: dict[str, Any] | None = None,
) -> list[EntityCandidate]:
    """Build generic LocalTuya entity candidates from Tuya metadata."""
    device = device or {}

    metadata = normalize_device_metadata(
        device,
        specification,
    )

    candidates: list[EntityCandidate] = []
    consumed_dps: set[int] = set()

    climate = _build_climate_candidate(
        device,
        metadata,
    )

    if climate is not None:
        candidates.append(climate)

        consumed_dps.update(
            climate.referenced_dps
            or (climate.primary_dp,)
        )

    light = _build_light_candidate(
        device,
        metadata,
    )

    if (
        light is not None
        and light.primary_dp
        not in consumed_dps
    ):
        candidates.append(light)

        consumed_dps.update(
            light.referenced_dps
            or (light.primary_dp,)
        )

    candidates.extend(
        _build_switch_candidates(
            device,
            metadata,
            consumed_dps,
        )
    )

    # Switch candidates consume only their own primary DP.
    for candidate in candidates:
        if candidate.platform == "switch":
            consumed_dps.update(
                candidate.referenced_dps
                or (candidate.primary_dp,)
            )

    candidates.extend(
        _build_sensor_candidates(
            device,
            metadata,
            consumed_dps,
        )
    )

    return sorted(
        candidates,
        key=lambda candidate: (
            candidate.platform,
            candidate.primary_dp,
        ),
    )

