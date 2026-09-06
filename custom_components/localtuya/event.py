"""Platform to expose Tuya datapoint notifications as Home Assistant events."""

import logging
from functools import partial

import voluptuous as vol
from homeassistant.components.event import DOMAIN, EventDeviceClass, EventEntity
from homeassistant.const import CONF_DEVICE_ID
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .common import LocalTuyaEntity, async_setup_entry
from .const import CONF_EVENT_DEVICE_CLASS, CONF_EVENT_DP, CONF_EVENT_TYPES

_LOGGER = logging.getLogger(__name__)


def flow_schema(dps):
    """Return schema used in config flow."""
    return {
        vol.Optional(CONF_EVENT_DP): vol.In(dps),
        vol.Optional(CONF_EVENT_DEVICE_CLASS): vol.In(
            [device_class.value for device_class in EventDeviceClass]
        ),
    }


def _normalize_event_types(value):
    """Normalize catalog event values to friendly -> raw mappings."""
    if isinstance(value, dict):
        return {
            str(friendly): raw
            for friendly, raw in value.items()
            if isinstance(friendly, str) and friendly
        }
    if isinstance(value, (list, tuple)):
        return {str(raw): raw for raw in value}
    return {}


def _friendly_for_raw(values, raw):
    for friendly, configured_raw in values.items():
        if raw == configured_raw:
            return friendly
    return None


class LocaltuyaEvent(LocalTuyaEntity, EventEntity):
    """Representation of a Tuya event datapoint."""

    def __init__(self, device, config_entry, eventid, **kwargs):
        """Initialize the Tuya event entity."""
        super().__init__(device, config_entry, eventid, _LOGGER, **kwargs)
        self._event_dp = self._config.get(CONF_EVENT_DP, self._dp_id)
        self._event_values = _normalize_event_types(
            self._config.get(CONF_EVENT_TYPES, {})
        )
        self._attr_event_types = list(self._event_values)

        device_class = self._config.get(CONF_EVENT_DEVICE_CLASS)
        if device_class:
            try:
                self._attr_device_class = EventDeviceClass(device_class)
            except ValueError:
                self.warning("Ignoring unsupported event device class %r", device_class)

    async def async_added_to_hass(self):
        """Subscribe to raw Tuya push messages as well as normal state updates."""
        await super().async_added_to_hass()
        signal = f"localtuya_raw_{self._dev_config_entry[CONF_DEVICE_ID]}"
        self.async_on_remove(
            async_dispatcher_connect(self.hass, signal, self._handle_raw_status)
        )

    def status_updated(self):
        """Events are driven by received DPS deltas, not by cached state changes."""

    @callback
    def _handle_raw_status(self, received):
        """Trigger one HA event for every received event datapoint value."""
        if not isinstance(received, dict):
            return

        key = str(self._event_dp)
        if key in received:
            raw = received[key]
        elif self._event_dp in received:
            raw = received[self._event_dp]
        else:
            return

        if raw is None:
            return

        event_type = _friendly_for_raw(self._event_values, raw)
        if event_type is None:
            self.warning("Ignoring unsupported event value %r", raw)
            return

        attributes = dict(self.extra_state_attributes)
        attributes["raw_value"] = raw
        self._trigger_event(event_type, attributes)
        self.async_write_ha_state()


async_setup_entry = partial(async_setup_entry, DOMAIN, LocaltuyaEvent, flow_schema)
