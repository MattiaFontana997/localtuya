"""Platform to present any Tuya DP as a binary sensor."""

import logging
from functools import partial
from typing import Any

import voluptuous as vol
from homeassistant.components.binary_sensor import (
    DEVICE_CLASSES_SCHEMA,
    DOMAIN,
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import CONF_DEVICE_CLASS

from .common import LocalTuyaEntity, async_setup_entry
from .const import CONF_STATE_OFF, CONF_STATE_ON

_LOGGER = logging.getLogger(__name__)

CONF_BINARY_SENSOR_MAPPING = "binary_sensor_mapping"
CONF_BINARY_SENSOR_BITFIELD = "binary_sensor_bitfield"
_MAX_BINARY_SENSOR_MAPPING_RULES = 32


def _valid_mapping_scalar(value: Any) -> bool:
    return isinstance(value, (str, int, bool)) or value is None


def validate_binary_sensor_mapping(
    value: Any, *, bitfield: bool = False
) -> list[dict[str, Any]] | None:
    """Validate bounded catalog-provided binary sensor mapping rules."""
    if not isinstance(bitfield, bool):
        return None
    if (
        not isinstance(value, list)
        or not value
        or len(value) > _MAX_BINARY_SENSOR_MAPPING_RULES
    ):
        return None

    normalized: list[dict[str, Any]] = []
    for raw_rule in value:
        if not isinstance(raw_rule, dict) or set(raw_rule) - {"dps_val", "value"}:
            return None
        if "value" not in raw_rule or not isinstance(raw_rule["value"], bool):
            return None

        rule = {"value": raw_rule["value"]}
        if "dps_val" in raw_rule:
            expected = raw_rule["dps_val"]
            if bitfield:
                if expected is not None and (
                    isinstance(expected, bool)
                    or not isinstance(expected, int)
                    or expected < 0
                ):
                    return None
            elif not _valid_mapping_scalar(expected):
                return None
            rule["dps_val"] = expected
        normalized.append(rule)
    return normalized


def _mapping_rule_matches(expected: Any, actual: Any, *, bitfield: bool) -> bool:
    """Mirror Tuya Local exact/bitfield rule matching semantics."""
    if bitfield and expected:
        try:
            return (int(actual) & int(expected)) != 0
        except (TypeError, ValueError):
            return False
    return str(actual) == str(expected)


def evaluate_binary_sensor_mapping(
    raw_state: Any,
    mapping: Any,
    *,
    bitfield: bool = False,
) -> bool | None:
    """Map one raw state using ordered exact/bitfield rules and a catch-all."""
    rules = validate_binary_sensor_mapping(mapping, bitfield=bitfield)
    if rules is None:
        return None

    default: bool | None = None
    for rule in rules:
        if "dps_val" not in rule:
            default = rule["value"]
            continue
        if _mapping_rule_matches(rule["dps_val"], raw_state, bitfield=bitfield):
            return rule["value"]
    return default


def flow_schema(dps):
    """Return schema used in config flow."""
    return {
        vol.Required(CONF_STATE_ON, default="True"): str,
        vol.Required(CONF_STATE_OFF, default="False"): str,
        vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
    }


class LocaltuyaBinarySensor(LocalTuyaEntity, BinarySensorEntity):
    """Representation of a Tuya binary sensor."""

    def __init__(
        self,
        device,
        config_entry,
        sensorid,
        **kwargs,
    ):
        """Initialize the Tuya binary sensor."""
        super().__init__(device, config_entry, sensorid, _LOGGER, **kwargs)

        self._attr_is_on = None
        self._binary_mapping_supplied = CONF_BINARY_SENSOR_MAPPING in self._config
        self._binary_mapping_bitfield = self._config.get(
            CONF_BINARY_SENSOR_BITFIELD, False
        )
        self._binary_mapping = (
            validate_binary_sensor_mapping(
                self._config.get(CONF_BINARY_SENSOR_MAPPING),
                bitfield=self._binary_mapping_bitfield,
            )
            if self._binary_mapping_supplied
            and isinstance(self._binary_mapping_bitfield, bool)
            else None
        )

        device_class = self._config.get(CONF_DEVICE_CLASS)
        self._attr_device_class = (
            BinarySensorDeviceClass(device_class)
            if device_class
            else None
        )

    def status_updated(self):
        """Update binary sensor state."""
        raw_state = self.dps(self._dp_id)

        if raw_state is None:
            self._attr_is_on = None
            return

        if self._binary_mapping_supplied:
            if self._binary_mapping is None:
                self._attr_is_on = None
                self.warning(
                    "Invalid catalog binary sensor mapping for entity %s",
                    self.entity_id,
                )
                return
            self._attr_is_on = evaluate_binary_sensor_mapping(
                raw_state,
                self._binary_mapping,
                bitfield=self._binary_mapping_bitfield,
            )
            if self._attr_is_on is None:
                self.warning(
                    "State for entity %s did not match catalog binary mapping",
                    self.entity_id,
                )
            return

        state = str(raw_state).lower()

        if state == self._config[CONF_STATE_ON].lower():
            self._attr_is_on = True
        elif state == self._config[CONF_STATE_OFF].lower():
            self._attr_is_on = False
        else:
            self._attr_is_on = None
            self.warning(
                "State for entity %s did not match configured state patterns",
                self.entity_id,
            )

    async def restore_state_when_connected(self):
        """Binary sensors do not restore values to the Tuya device."""
        return


async_setup_entry = partial(
    async_setup_entry,
    DOMAIN,
    LocaltuyaBinarySensor,
    flow_schema,
)
