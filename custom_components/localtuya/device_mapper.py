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
    CONF_COMMANDS_SET,
    CONF_CURRENT_POSITION_DP,
    CONF_CURRENT_TEMPERATURE_DP,
    CONF_FAN_DIRECTION,
    CONF_FAN_DIRECTION_FWD,
    CONF_FAN_DIRECTION_REV,
    CONF_FAN_DPS_TYPE,
    CONF_FAN_ORDERED_LIST,
    CONF_FAN_OSCILLATING_CONTROL,
    CONF_FAN_SPEED_CONTROL,
    CONF_FAN_SPEED_MAX,
    CONF_FAN_SPEED_MIN,
    CONF_MAX_VALUE,
    CONF_MIN_VALUE,
    CONF_OPTIONS,
    CONF_PASSIVE_ENTITY,
    CONF_POSITIONING_MODE,
    CONF_PRECISION,
    CONF_PRESET_DP,
    CONF_PRESET_SET,
    CONF_RESTORE_ON_RECONNECT,
    CONF_SCALING,
    CONF_SET_POSITION_DP,
    CONF_STATE_OFF,
    CONF_STATE_ON,
    CONF_STEPSIZE_VALUE,
    CONF_TARGET_PRECISION,
    CONF_TARGET_TEMPERATURE_DP,
    CONF_TEMPERATURE_STEP,
    CONF_TEMP_MAX,
    CONF_TEMP_MIN,
)

from .product_overrides import get_product_entity_overrides


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

_COVER_CATEGORIES = {
    "cl",
    "clkg",
}

_COVER_CONTROL_CODES = (
    "control",
    "control_2",
)

_COVER_REQUIRED_COMMANDS = {
    "open",
    "stop",
    "close",
}

_COVER_COMMANDS_OPEN_CLOSE_STOP = (
    "open_close_stop"
)

_COVER_POSITION_MODE = "position"


_FAN_CATEGORIES = {
    "fs",
    "fsd",
}

_FAN_POWER_CODES = {
    "fs": (
        "switch",
    ),
    "fsd": (
        "fan_switch",
    ),
}

_FAN_SPEED_CODES = {
    "fs": (
        "fan_speed_percent",
        "fan_speed",
    ),
    "fsd": (
        "fan_speed",
        "fan_speed_percent",
    ),
}

_FAN_OSCILLATION_CODES = (
    "switch_horizontal",
    "switch_vertical",
)

_FAN_DIRECTION_CODES = (
    "fan_direction",
)


# These codes have specialized semantics and must not fall
# through to the generic switch mapper.
_GENERIC_SWITCH_BLOCKLIST = {
    *_LIGHT_POWER_CODES,
    *_FAN_OSCILLATION_CODES,
}


_BINARY_SENSOR_RULES = {
    # Contact/opening sensors
    "doorcontact_state": (
        "Door",
        "door",
    ),
    "door_contact": (
        "Door",
        "door",
    ),
    "contact_state": (
        "Opening",
        "opening",
    ),

    # Motion / occupancy
    "pir": (
        "Motion",
        "motion",
    ),
    "pir_state": (
        "Motion",
        "motion",
    ),
    "motion": (
        "Motion",
        "motion",
    ),
    "motion_state": (
        "Motion",
        "motion",
    ),
    "presence": (
        "Occupancy",
        "occupancy",
    ),
    "presence_state": (
        "Occupancy",
        "occupancy",
    ),
    "occupancy": (
        "Occupancy",
        "occupancy",
    ),

    # Safety sensors
    "water_sensor_state": (
        "Moisture",
        "moisture",
    ),
    "water_leak": (
        "Moisture",
        "moisture",
    ),
    "smoke_sensor_state": (
        "Smoke",
        "smoke",
    ),
    "smoke_alarm": (
        "Smoke",
        "smoke",
    ),
    "gas_sensor_state": (
        "Gas",
        "gas",
    ),
    "gas_alarm": (
        "Gas",
        "gas",
    ),

    # Security / maintenance
    "tamper": (
        "Tamper",
        "tamper",
    ),
    "tamper_alarm": (
        "Tamper",
        "tamper",
    ),
    "battery_low": (
        "Battery Low",
        "battery",
    ),
    "low_battery": (
        "Battery Low",
        "battery",
    ),
}


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


def _enum_options(
    dp: DpMetadata | None,
) -> list[str]:
    """Return normalized non-empty enum options."""
    if dp is None:
        return []

    raw_options = dp.values.get(
        "range"
    )

    if not isinstance(
        raw_options,
        list,
    ):
        return []

    return [
        str(value).strip()
        for value in raw_options
        if str(value).strip()
    ]


def _is_percentage_dp(
    dp: DpMetadata | None,
    *,
    require_readable: bool = False,
    require_writable: bool = False,
) -> bool:
    """Return whether a DP is an unscaled 0..100 percentage."""
    if dp is None:
        return False

    if (
        require_readable
        and not dp.readable
    ):
        return False

    if (
        require_writable
        and not dp.writable
    ):
        return False

    if dp.type_name not in {
        "",
        "integer",
        "value",
        "float",
        "double",
    }:
        return False

    factor = _tuya_scale_factor(
        dp
    )

    if factor != 1.0:
        return False

    minimum = _numeric_value(
        dp,
        "min",
    )
    maximum = _numeric_value(
        dp,
        "max",
    )

    return (
        minimum == 0
        and maximum == 100
    )


def _build_cover_candidates(
    device: dict[str, Any],
    metadata: dict[int, DpMetadata],
    consumed_dps: set[int],
) -> list[EntityCandidate]:
    """Build standard Tuya curtain/cover candidates."""
    category = str(
        device.get("category") or ""
    ).strip().lower()

    if category not in _COVER_CATEGORIES:
        return []

    candidates: list[EntityCandidate] = []

    device_name = _device_name(
        device,
        "Tuya Cover",
    )

    for control_code in _COVER_CONTROL_CODES:
        control = _find_by_codes(
            metadata,
            (control_code,),
        )

        if (
            control is None
            or control.id in consumed_dps
            or not control.writable
            or control.type_name != "enum"
        ):
            continue

        command_values = {
            option.lower()
            for option in _enum_options(
                control
            )
        }

        if not (
            _COVER_REQUIRED_COMMANDS
            .issubset(command_values)
        ):
            continue

        suffix = (
            ""
            if control_code == "control"
            else control_code.removeprefix(
                "control"
            )
        )

        set_position = _find_by_codes(
            metadata,
            (
                f"percent_control{suffix}",
            ),
        )

        if (
            set_position is not None
            and (
                set_position.id
                in consumed_dps
                or not _is_percentage_dp(
                    set_position,
                    require_writable=True,
                )
            )
        ):
            set_position = None

        current_position = _find_by_codes(
            metadata,
            (
                f"percent_state{suffix}",
            ),
        )

        if (
            current_position is not None
            and (
                current_position.id
                in consumed_dps
                or not _is_percentage_dp(
                    current_position,
                    require_readable=True,
                )
            )
        ):
            current_position = None

        # Some curtain profiles report percent_control itself,
        # so it can safely serve as current position when
        # percent_state is absent.
        if (
            current_position is None
            and set_position is not None
            and set_position.readable
        ):
            current_position = (
                set_position
            )

        friendly_name = device_name

        if suffix:
            friendly_name = (
                f"{device_name} Cover "
                f"{suffix.lstrip('_')}"
            )

        config: dict[str, Any] = {
            CONF_ID: control.id,
            CONF_FRIENDLY_NAME:
                friendly_name,
            CONF_PLATFORM: "cover",
            CONF_COMMANDS_SET:
                _COVER_COMMANDS_OPEN_CLOSE_STOP,
        }

        matched_codes = [
            control.code
        ]

        referenced_dps = [
            control.id
        ]

        # Only enable HA position support when both a writable
        # target and readable position are available.
        if (
            set_position is not None
            and current_position
            is not None
        ):
            config[
                CONF_POSITIONING_MODE
            ] = _COVER_POSITION_MODE

            config[
                CONF_SET_POSITION_DP
            ] = set_position.id

            config[
                CONF_CURRENT_POSITION_DP
            ] = current_position.id

            for dp in (
                set_position,
                current_position,
            ):
                if dp.code not in matched_codes:
                    matched_codes.append(
                        dp.code
                    )

                if dp.id not in referenced_dps:
                    referenced_dps.append(
                        dp.id
                    )

        candidates.append(
            EntityCandidate(
                platform="cover",
                primary_dp=control.id,
                confidence=MappingConfidence.HIGH,
                config=config,
                matched_codes=tuple(
                    matched_codes
                ),
                referenced_dps=tuple(
                    referenced_dps
                ),
            )
        )

    return candidates


def _build_fan_candidate(
    device: dict[str, Any],
    metadata: dict[int, DpMetadata],
    consumed_dps: set[int],
) -> EntityCandidate | None:
    """Build a standard Tuya fan candidate."""
    category = str(
        device.get("category") or ""
    ).strip().lower()

    if category not in _FAN_CATEGORIES:
        return None

    power = _find_by_codes(
        metadata,
        _FAN_POWER_CODES[
            category
        ],
    )

    if (
        power is None
        or power.id in consumed_dps
        or not power.writable
        or power.type_name not in {
            "",
            "boolean",
            "bool",
        }
    ):
        return None

    config: dict[str, Any] = {
        CONF_ID: power.id,
        CONF_FRIENDLY_NAME:
            _device_name(
                device,
                "Tuya Fan",
            ),
        CONF_PLATFORM: "fan",
    }

    matched_codes = [
        power.code
    ]

    referenced_dps = [
        power.id
    ]

    # --------------------------------------------------------
    # Speed
    # --------------------------------------------------------

    speed = _find_by_codes(
        metadata,
        _FAN_SPEED_CODES[
            category
        ],
    )

    if (
        speed is not None
        and speed.id
        not in consumed_dps
        and speed.writable
    ):
        if speed.type_name in {
            "integer",
            "value",
        }:
            speed_range = _integer_range(
                speed
            )

            if (
                _tuya_scale_factor(speed)
                == 1.0
                and speed_range
                is not None
                and speed_range[0] >= 1
            ):
                config[
                    CONF_FAN_SPEED_CONTROL
                ] = speed.id

                config[
                    CONF_FAN_SPEED_MIN
                ] = speed_range[0]

                config[
                    CONF_FAN_SPEED_MAX
                ] = speed_range[1]

                config[
                    CONF_FAN_DPS_TYPE
                ] = "int"

        elif speed.type_name == "enum":
            options = _enum_options(
                speed
            )

            if (
                len(options) > 1
                and not any(
                    "," in option
                    for option in options
                )
            ):
                config[
                    CONF_FAN_SPEED_CONTROL
                ] = speed.id

                config[
                    CONF_FAN_ORDERED_LIST
                ] = ",".join(
                    options
                )

                config[
                    CONF_FAN_DPS_TYPE
                ] = "str"

        if (
            config.get(
                CONF_FAN_SPEED_CONTROL
            )
            == speed.id
        ):
            matched_codes.append(
                speed.code
            )
            referenced_dps.append(
                speed.id
            )

    # --------------------------------------------------------
    # Oscillation
    # LocalTuya currently supports one oscillation DP.
    # Prefer horizontal, then vertical.
    # --------------------------------------------------------

    for oscillation_code in (
        _FAN_OSCILLATION_CODES
    ):
        oscillation = _find_by_codes(
            metadata,
            (oscillation_code,),
        )

        if (
            oscillation is None
            or oscillation.id
            in consumed_dps
            or not oscillation.writable
            or oscillation.type_name
            not in {
                "",
                "boolean",
                "bool",
            }
        ):
            continue

        config[
            CONF_FAN_OSCILLATING_CONTROL
        ] = oscillation.id

        matched_codes.append(
            oscillation.code
        )

        referenced_dps.append(
            oscillation.id
        )

        break

    # --------------------------------------------------------
    # Direction
    # --------------------------------------------------------

    direction = _find_by_codes(
        metadata,
        _FAN_DIRECTION_CODES,
    )

    if (
        direction is not None
        and direction.id
        not in consumed_dps
        and direction.writable
        and direction.type_name
        == "enum"
    ):
        raw_options = _enum_options(
            direction
        )

        option_map = {
            option.lower(): option
            for option in raw_options
        }

        if {
            "forward",
            "reverse",
        }.issubset(option_map):
            config[
                CONF_FAN_DIRECTION
            ] = direction.id

            config[
                CONF_FAN_DIRECTION_FWD
            ] = option_map[
                "forward"
            ]

            config[
                CONF_FAN_DIRECTION_REV
            ] = option_map[
                "reverse"
            ]

            matched_codes.append(
                direction.code
            )

            referenced_dps.append(
                direction.id
            )

    return EntityCandidate(
        platform="fan",
        primary_dp=power.id,
        confidence=MappingConfidence.HIGH,
        config=config,
        matched_codes=tuple(
            matched_codes
        ),
        referenced_dps=tuple(
            referenced_dps
        ),
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

        # A switch must be writable. Status-only boolean DPS
        # must never become controllable entities.
        if not dp.writable:
            continue

        if dp.code in _GENERIC_SWITCH_BLOCKLIST:
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


def _build_binary_sensor_candidates(
    device: dict[str, Any],
    metadata: dict[int, DpMetadata],
    consumed_dps: set[int],
) -> list[EntityCandidate]:
    """Build high-confidence read-only boolean sensors."""
    candidates: list[EntityCandidate] = []

    device_name = _device_name(
        device,
        "Tuya Device",
    )

    for dp in metadata.values():
        if dp.id in consumed_dps:
            continue

        # Automatic binary sensors must come from status-only
        # metadata. A writable Boolean belongs to some control
        # surface and must not be exposed as a sensor.
        if (
            not dp.readable
            or dp.writable
        ):
            continue

        if dp.type_name not in (
            "",
            "boolean",
            "bool",
        ):
            continue

        rule = _BINARY_SENSOR_RULES.get(
            dp.code
        )

        if rule is None:
            continue

        label, device_class = rule

        candidates.append(
            EntityCandidate(
                platform="binary_sensor",
                primary_dp=dp.id,
                confidence=MappingConfidence.HIGH,
                config={
                    CONF_ID: dp.id,
                    CONF_FRIENDLY_NAME: (
                        f"{device_name} {label}"
                    ),
                    CONF_PLATFORM: "binary_sensor",
                    CONF_STATE_ON: "True",
                    CONF_STATE_OFF: "False",
                    CONF_DEVICE_CLASS:
                        device_class,
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


def _generic_dp_label(
    code: str,
) -> str:
    """Create a readable fallback label from a Tuya code."""
    label = (
        code.replace("_", " ")
        .strip()
        .title()
    )

    return label or "Value"


def _build_number_candidates(
    device: dict[str, Any],
    metadata: dict[int, DpMetadata],
    consumed_dps: set[int],
) -> list[EntityCandidate]:
    """Build medium-confidence writable numeric candidates."""
    candidates: list[EntityCandidate] = []

    device_name = _device_name(
        device,
        "Tuya Device",
    )

    numeric_types = {
        "integer",
        "value",
        "float",
        "double",
    }

    for dp in metadata.values():
        if dp.id in consumed_dps:
            continue

        if not dp.writable:
            continue

        if dp.type_name not in numeric_types:
            continue

        factor = _tuya_scale_factor(dp)

        if factor is None:
            continue

        raw_min = _numeric_value(
            dp,
            "min",
        )
        raw_max = _numeric_value(
            dp,
            "max",
        )
        raw_step = _numeric_value(
            dp,
            "step",
        )

        if (
            raw_min is None
            or raw_max is None
            or raw_step is None
            or raw_max <= raw_min
            or raw_step <= 0
        ):
            continue

        config: dict[str, Any] = {
            CONF_ID: dp.id,
            CONF_FRIENDLY_NAME: (
                f"{device_name} "
                f"{_generic_dp_label(dp.code)}"
            ),
            CONF_PLATFORM: "number",
            CONF_MIN_VALUE: round(
                raw_min * factor,
                6,
            ),
            CONF_MAX_VALUE: round(
                raw_max * factor,
                6,
            ),
            CONF_STEPSIZE_VALUE: round(
                raw_step * factor,
                6,
            ),
            CONF_RESTORE_ON_RECONNECT: False,
            CONF_PASSIVE_ENTITY: False,
        }

        if factor != 1.0:
            config[
                CONF_SCALING
            ] = factor

        unit = _normalize_unit(
            dp.values.get("unit"),
            "",
        )

        if unit:
            config[
                CONF_UNIT_OF_MEASUREMENT
            ] = unit

        candidates.append(
            EntityCandidate(
                platform="number",
                primary_dp=dp.id,
                confidence=MappingConfidence.MEDIUM,
                config=config,
                matched_codes=(dp.code,),
                referenced_dps=(dp.id,),
            )
        )

    return candidates


def _build_select_candidates(
    device: dict[str, Any],
    metadata: dict[int, DpMetadata],
    consumed_dps: set[int],
) -> list[EntityCandidate]:
    """Build medium-confidence writable enum candidates."""
    candidates: list[EntityCandidate] = []

    device_name = _device_name(
        device,
        "Tuya Device",
    )

    for dp in metadata.values():
        if dp.id in consumed_dps:
            continue

        if not dp.writable:
            continue

        if dp.type_name != "enum":
            continue

        raw_options = dp.values.get(
            "range"
        )

        if not isinstance(
            raw_options,
            list,
        ):
            continue

        options = [
            str(value).strip()
            for value in raw_options
            if str(value).strip()
        ]

        if len(options) < 2:
            continue

        # LocalTuya select stores raw options separated by ';'.
        if any(
            ";" in option
            for option in options
        ):
            continue

        candidates.append(
            EntityCandidate(
                platform="select",
                primary_dp=dp.id,
                confidence=MappingConfidence.MEDIUM,
                config={
                    CONF_ID: dp.id,
                    CONF_FRIENDLY_NAME: (
                        f"{device_name} "
                        f"{_generic_dp_label(dp.code)}"
                    ),
                    CONF_PLATFORM: "select",
                    CONF_OPTIONS: ";".join(
                        options
                    ),
                    CONF_RESTORE_ON_RECONNECT: False,
                    CONF_PASSIVE_ENTITY: False,
                },
                matched_codes=(dp.code,),
                referenced_dps=(dp.id,),
            )
        )

    return candidates


def _apply_product_overrides(
    device: dict[str, Any],
    candidates: list[EntityCandidate],
    available_dps: set[int] | None,
) -> list[EntityCandidate]:
    """Apply verified product extensions to generic candidates.

    Undocumented product DPS are only enabled when the LAN probe has
    independently confirmed that those DPS exist on this device.
    """
    if available_dps is None:
        return candidates

    overrides = get_product_entity_overrides(
        device
    )

    if not overrides:
        return candidates

    result = list(candidates)

    for override in overrides:
        if not set(
            override.required_dps
        ).issubset(available_dps):
            continue

        for index, candidate in enumerate(
            result
        ):
            if (
                candidate.platform
                != override.platform
                or candidate.primary_dp
                != override.primary_dp
            ):
                continue

            config = dict(
                candidate.config
            )

            config.update(
                dict(
                    override.config_updates
                )
            )

            referenced_dps = list(
                candidate.referenced_dps
                or (
                    candidate.primary_dp,
                )
            )

            for dp_id in override.required_dps:
                if dp_id not in referenced_dps:
                    referenced_dps.append(
                        dp_id
                    )

            result[index] = EntityCandidate(
                platform=candidate.platform,
                primary_dp=candidate.primary_dp,
                confidence=candidate.confidence,
                config=config,
                matched_codes=(
                    candidate.matched_codes
                ),
                referenced_dps=tuple(
                    referenced_dps
                ),
            )

            break

    return result


def build_entity_candidates(
    device: dict[str, Any] | None = None,
    specification: dict[str, Any] | None = None,
    *,
    available_dps: set[int] | None = None,
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

    cover_candidates = (
        _build_cover_candidates(
            device,
            metadata,
            consumed_dps,
        )
    )

    candidates.extend(
        cover_candidates
    )

    for candidate in cover_candidates:
        consumed_dps.update(
            candidate.referenced_dps
            or (candidate.primary_dp,)
        )

    fan = _build_fan_candidate(
        device,
        metadata,
        consumed_dps,
    )

    if fan is not None:
        candidates.append(
            fan
        )

        consumed_dps.update(
            fan.referenced_dps
            or (fan.primary_dp,)
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

    binary_sensor_candidates = (
        _build_binary_sensor_candidates(
            device,
            metadata,
            consumed_dps,
        )
    )

    candidates.extend(
        binary_sensor_candidates
    )

    for candidate in binary_sensor_candidates:
        consumed_dps.update(
            candidate.referenced_dps
            or (candidate.primary_dp,)
        )

    sensor_candidates = (
        _build_sensor_candidates(
            device,
            metadata,
            consumed_dps,
        )
    )

    candidates.extend(
        sensor_candidates
    )

    for candidate in sensor_candidates:
        consumed_dps.update(
            candidate.referenced_dps
            or (candidate.primary_dp,)
        )

    number_candidates = (
        _build_number_candidates(
            device,
            metadata,
            consumed_dps,
        )
    )

    candidates.extend(
        number_candidates
    )

    for candidate in number_candidates:
        consumed_dps.update(
            candidate.referenced_dps
            or (candidate.primary_dp,)
        )

    select_candidates = (
        _build_select_candidates(
            device,
            metadata,
            consumed_dps,
        )
    )

    candidates.extend(
        select_candidates
    )

    candidates = _apply_product_overrides(
        device,
        candidates,
        available_dps,
    )

    return sorted(
        candidates,
        key=lambda candidate: (
            candidate.platform,
            candidate.primary_dp,
        ),
    )

