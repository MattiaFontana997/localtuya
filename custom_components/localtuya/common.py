"""Code shared between all platforms."""
import asyncio
import copy
import json.decoder
import logging
import time
from contextlib import suppress
from datetime import timedelta

from homeassistant.const import (
    CONF_DEVICE_ID, CONF_DEVICES, CONF_ENTITIES, CONF_FRIENDLY_NAME, CONF_HOST,
    CONF_ID, CONF_PLATFORM, CONF_SCAN_INTERVAL, STATE_UNKNOWN,
)
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect, async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.restore_state import RestoreEntity

from . import pytuya
from .advanced_mapping import (
    CONF_ADVANCED_MAPPING,
    CONF_ADVANCED_MAPPING_BY_DP,
    advanced_mapping_by_dp_references,
    advanced_mapping_dp_references,
    effective_mapping_metadata,
    map_value_from_dps,
    map_value_to_dps,
    validate_advanced_mapping,
    validate_advanced_mapping_by_dp,
)
from .const import (
    ATTR_STATE, ATTR_UPDATED_AT, CONF_DEFAULT_VALUE, CONF_ENABLE_DEBUG,
    CONF_EXTRA_STATE_ATTRIBUTES_DPS, CONF_MAPPED_EXTRA_STATE_ATTRIBUTES_DPS,
    CONF_MAPPED_EXTRA_STATE_ATTRIBUTE_MAPPINGS,
    CONF_LOCAL_KEY, CONF_MODEL, CONF_PASSIVE_ENTITY, CONF_PROTOCOL_VERSION, CONF_RESET_DPIDS,
    CONF_RESTORE_ON_RECONNECT, DATA_CLOUD, DOMAIN, TUYA_DEVICES,
)

_LOGGER = logging.getLogger(__name__)
MAX_EXTRA_STATE_ATTRIBUTES = 32
MAX_NON_PERSISTENT_DPS = 32
CONF_ENTITY_REGISTRY_ENABLED_DEFAULT = "entity_registry_enabled_default"
CONF_NON_PERSISTENT_DPS = "non_persistent_dps"


def get_non_persistent_dps(config):
    """Return validated catalog-provided DPS that must not remain cached."""
    configured = config.get(CONF_NON_PERSISTENT_DPS)
    if not isinstance(configured, list) or not configured:
        return set()
    result = set()
    for raw_dp in configured:
        if isinstance(raw_dp, bool):
            continue
        try:
            dp_id = int(raw_dp)
        except (TypeError, ValueError):
            continue
        if 0 < dp_id <= 65535:
            result.add(dp_id)
        if len(result) >= MAX_NON_PERSISTENT_DPS:
            break
    return result


def prune_missing_non_persistent_dps(cached_status, incoming_status, dp_ids):
    """Drop transient DPS that were not present in the latest device update."""
    if not isinstance(cached_status, dict) or not isinstance(incoming_status, dict):
        return
    incoming_keys = {str(key) for key in incoming_status}
    for dp_id in dp_ids:
        key = str(dp_id)
        if key not in incoming_keys:
            cached_status.pop(key, None)
            cached_status.pop(dp_id, None)


def _get_state_attribute_dps(config, key):
    """Return validated catalog-provided DPS state attributes for one key."""
    configured = config.get(key)
    if not isinstance(configured, dict):
        return {}
    result = {}
    for raw_name, raw_dp in configured.items():
        if not isinstance(raw_name, str):
            continue
        name = raw_name.strip()
        if not name or name == ATTR_STATE or name in result or isinstance(raw_dp, bool):
            continue
        try:
            dp_id = int(raw_dp)
        except (TypeError, ValueError):
            continue
        if dp_id <= 0 or dp_id > 65535:
            continue
        result[name] = dp_id
        if len(result) >= MAX_EXTRA_STATE_ATTRIBUTES:
            break
    return result


def get_extra_state_attribute_dps(config):
    """Return validated catalog-provided raw DPS state attributes."""
    return _get_state_attribute_dps(config, CONF_EXTRA_STATE_ATTRIBUTES_DPS)


def get_mapped_extra_state_attribute_dps(config):
    """Return validated catalog DPS attributes that must use declarative mapping."""
    return _get_state_attribute_dps(config, CONF_MAPPED_EXTRA_STATE_ATTRIBUTES_DPS)


def get_mapped_extra_state_attribute_mappings(config):
    """Return validated attribute-name -> declarative mapping rules."""
    configured = config.get(CONF_MAPPED_EXTRA_STATE_ATTRIBUTE_MAPPINGS)
    if not isinstance(configured, dict) or not configured:
        return {}
    result = {}
    for raw_name, raw_rules in configured.items():
        if not isinstance(raw_name, str):
            continue
        name = raw_name.strip()
        if not name or name in result:
            continue
        rules = validate_advanced_mapping(raw_rules)
        if rules is None:
            continue
        result[name] = rules
        if len(result) >= MAX_EXTRA_STATE_ATTRIBUTES:
            break
    return result


async def async_setup_entry(domain, entity_class, flow_schema, hass, config_entry, async_add_entities):
    """Set up a Tuya platform based on a config entry."""
    entities = []
    dps_config_fields = tuple(get_dps_for_platform(flow_schema))
    for dev_id, dev_entry in config_entry.data[CONF_DEVICES].items():
        entities_to_setup = [entity for entity in dev_entry[CONF_ENTITIES] if entity[CONF_PLATFORM] == domain]
        if not entities_to_setup:
            continue
        device = hass.data[DOMAIN][TUYA_DEVICES][dev_id]
        device_entities = []
        for entity_config in entities_to_setup:
            for dp_conf in dps_config_fields:
                dp_id = entity_config.get(dp_conf)
                if dp_id is not None:
                    device.dps_to_request[dp_id] = None
            for dp_id in get_extra_state_attribute_dps(entity_config).values():
                device.dps_to_request[dp_id] = None
            for dp_id in get_mapped_extra_state_attribute_dps(entity_config).values():
                device.dps_to_request[dp_id] = None
            for rules in get_mapped_extra_state_attribute_mappings(entity_config).values():
                for dp_id in advanced_mapping_dp_references(rules):
                    device.dps_to_request[dp_id] = None
            for dp_id in advanced_mapping_dp_references(entity_config.get(CONF_ADVANCED_MAPPING)):
                device.dps_to_request[dp_id] = None
            for dp_id in advanced_mapping_by_dp_references(entity_config.get(CONF_ADVANCED_MAPPING_BY_DP)):
                device.dps_to_request[dp_id] = None
            entity = entity_class(device, dev_entry, entity_config[CONF_ID])
            device_entities.append(entity)
        device.add_entities(device_entities)
        entities.extend(device_entities)
    if entities:
        async_add_entities(entities)


def get_dps_for_platform(flow_schema):
    """Return config keys for all platform keys that depends on a datapoint."""
    for key, value in flow_schema(None).items():
        if hasattr(value, "container") and value.container is None:
            yield key.schema


def get_entity_config(config_entry, dp_id):
    """Return entity config for a given DPS id."""
    for entity in config_entry[CONF_ENTITIES]:
        if entity[CONF_ID] == dp_id:
            return entity
    raise Exception(f"missing entity config for id {dp_id}")


@callback
def async_config_entry_by_device_id(hass, device_id):
    """Look up config entry by device id."""
    for entry in hass.config_entries.async_entries(DOMAIN):
        if device_id in entry.data.get(CONF_DEVICES, []):
            return entry
    _LOGGER.debug("Missing device configuration for device_id %s", device_id)
    return None


class TuyaDevice(pytuya.TuyaListener, pytuya.ContextualLogger):
    """Cache wrapper for pytuya.TuyaInterface."""

    def __init__(self, hass, config_entry, dev_id):
        super().__init__()
        self._hass = hass
        self._config_entry = config_entry
        self._dev_config_entry = copy.deepcopy(dict(config_entry.data[CONF_DEVICES][dev_id]))
        self._interface = None
        self._status = {}
        self.dps_to_request = {}
        self._is_closing = False
        self._connect_task = None
        self._disconnect_task = None
        self._unsub_interval = None
        self._entities = []
        self._non_persistent_dps = set()
        self._local_key = self._dev_config_entry[CONF_LOCAL_KEY]
        self._default_reset_dpids = None
        if CONF_RESET_DPIDS in self._dev_config_entry:
            self._default_reset_dpids = [int(item.strip()) for item in self._dev_config_entry[CONF_RESET_DPIDS].split(",")]
        self.set_logger(_LOGGER, self._dev_config_entry[CONF_DEVICE_ID])
        for entity in self._dev_config_entry[CONF_ENTITIES]:
            self.dps_to_request[entity[CONF_ID]] = None
            self._non_persistent_dps.update(get_non_persistent_dps(entity))
            for dp_id in advanced_mapping_dp_references(entity.get(CONF_ADVANCED_MAPPING)):
                self.dps_to_request[dp_id] = None
            for dp_id in advanced_mapping_by_dp_references(entity.get(CONF_ADVANCED_MAPPING_BY_DP)):
                self.dps_to_request[dp_id] = None

    def add_entities(self, entities):
        self._entities.extend(entities)

    @property
    def is_connecting(self):
        return self._connect_task is not None

    @property
    def connected(self):
        return self._interface is not None

    @callback
    def _connection_task_done(self, task):
        if self._connect_task is task:
            self._connect_task = None

    def async_connect(self):
        if self._is_closing or self._connect_task is not None or self._interface is not None:
            return
        task = self._config_entry.async_create_background_task(
            self._hass, self._make_connection(),
            f"LocalTuya connect {self._dev_config_entry[CONF_DEVICE_ID]}",
        )
        self._connect_task = task
        task.add_done_callback(self._connection_task_done)

    def _install_raw_status_listener(self):
        interface = self._interface
        dispatcher = getattr(interface, "dispatcher", None)
        original_listener = getattr(dispatcher, "listener", None)
        decode_payload = getattr(interface, "_decode_payload", None)
        if dispatcher is None or not callable(original_listener) or not callable(decode_payload):
            return

        def _raw_status_listener(message):
            received = {}
            try:
                decoded = decode_payload(message.payload)
                if isinstance(decoded, dict) and isinstance(decoded.get("dps"), dict):
                    received = dict(decoded["dps"])
            except Exception as ex:  # pylint: disable=broad-except
                self.debug("Unable to decode raw unsolicited status payload: %s", ex)
            original_listener(message)
            if received:
                self._dispatch_raw_status(received)
        dispatcher.listener = _raw_status_listener

    async def _make_connection(self):
        self.info("Trying to connect to %s...", self._dev_config_entry[CONF_HOST])
        try:
            self._interface = await pytuya.connect(
                self._dev_config_entry[CONF_HOST], self._dev_config_entry[CONF_DEVICE_ID],
                self._local_key, float(self._dev_config_entry[CONF_PROTOCOL_VERSION]),
                self._dev_config_entry.get(CONF_ENABLE_DEBUG, False), self,
            )
            self._interface.add_dps_to_request(self.dps_to_request)
            self._install_raw_status_listener()
        except Exception as ex:  # pylint: disable=broad-except
            self.warning(f"Failed to connect to {self._dev_config_entry[CONF_HOST]}: %s", ex)
            if self._interface is not None:
                await self._interface.close()
                self._interface = None

        if self._interface is not None:
            try:
                try:
                    self.debug("Retrieving initial state")
                    status = await self._interface.status()
                    if status is None:
                        raise Exception("Failed to retrieve status")
                    self._interface.start_heartbeat()
                    self.status_updated(status)
                except Exception as ex:
                    if self._default_reset_dpids:
                        self.debug("Initial state update failed, trying reset command for DP IDs: %s", self._default_reset_dpids)
                        await self._interface.reset(self._default_reset_dpids)
                        status = await self._interface.status()
                        if status is None or not status:
                            raise Exception("Failed to retrieve status") from ex
                        self._interface.start_heartbeat()
                        self.status_updated(status)
                    else:
                        self.error("Initial state update failed, giving up: %r", ex)
                        if self._interface is not None:
                            await self._interface.close()
                            self._interface = None
            except (UnicodeDecodeError, json.decoder.JSONDecodeError) as ex:
                self.warning("Initial state update failed (%s), trying key update", ex)
                await self.update_local_key()
                if self._interface is not None:
                    await self._interface.close()
                    self._interface = None

        if self._interface is not None:
            for entity in self._entities:
                await entity.restore_state_when_connected()

            @callback
            def _new_entity_handler(entity_id):
                self.debug("New entity %s was added to %s", entity_id, self._dev_config_entry[CONF_HOST])
                self._dispatch_status()
            signal = f"localtuya_entity_{self._dev_config_entry[CONF_DEVICE_ID]}"
            self._disconnect_task = async_dispatcher_connect(self._hass, signal, _new_entity_handler)
            if CONF_SCAN_INTERVAL in self._dev_config_entry and int(self._dev_config_entry[CONF_SCAN_INTERVAL]) > 0:
                self._unsub_interval = async_track_time_interval(
                    self._hass, self._async_refresh,
                    timedelta(seconds=int(self._dev_config_entry[CONF_SCAN_INTERVAL])),
                )
            self.info(f"Successfully connected to {self._dev_config_entry[CONF_HOST]}")

    async def update_local_key(self):
        dev_id = self._dev_config_entry[CONF_DEVICE_ID]
        cloud_api = self._hass.data.get(DOMAIN, {}).get(DATA_CLOUD)
        if cloud_api is None:
            self.warning("Cloud API unavailable while updating local key")
            return
        result = await cloud_api.async_get_devices_list()
        if result != "ok":
            self.warning("Unable to refresh Cloud device data")
            return
        cloud_device = cloud_api.device_list.get(dev_id)
        if cloud_device is None:
            self.warning("Device %s was not found in Cloud device data", dev_id)
            return
        new_local_key = cloud_device.get(CONF_LOCAL_KEY)
        if not new_local_key:
            self.warning("Cloud device data contains no local key for %s", dev_id)
            return
        if new_local_key == self._local_key:
            self.debug("Cloud local key for %s is unchanged", dev_id)
            return
        self._local_key = new_local_key
        self._dev_config_entry[CONF_LOCAL_KEY] = new_local_key
        new_data = copy.deepcopy(dict(self._config_entry.data))
        new_data[CONF_DEVICES][dev_id][CONF_LOCAL_KEY] = new_local_key
        new_data[ATTR_UPDATED_AT] = str(int(time.time() * 1000))
        self._hass.config_entries.async_update_entry(self._config_entry, data=new_data)
        self.info("Local key updated for device %s", dev_id)

    async def _async_refresh(self, _now):
        if self._interface is not None:
            await self._interface.update_dps()

    async def close(self):
        self._is_closing = True
        connect_task = self._connect_task
        if connect_task is not None:
            if connect_task is not asyncio.current_task() and not connect_task.done():
                connect_task.cancel()
                with suppress(asyncio.CancelledError):
                    await connect_task
            self._connect_task = None
        if self._unsub_interval is not None:
            self._unsub_interval()
            self._unsub_interval = None
        if self._disconnect_task is not None:
            self._disconnect_task()
            self._disconnect_task = None
        interface = self._interface
        self._interface = None
        if interface is not None:
            await interface.close()
        self._status.clear()
        self.info("Closed connection with device %s", self._dev_config_entry[CONF_FRIENDLY_NAME])

    async def set_dp(self, state, dp_index):
        interface = self._interface
        if interface is not None:
            try:
                await interface.set_dp(state, dp_index)
            except Exception:  # pylint: disable=broad-except
                self.exception("Failed to set DP %d to %s", dp_index, str(state))
                return
            if self._interface is interface:
                dp_key = str(dp_index)
                self._status[dp_key] = state
                if hasattr(interface, "dps_cache"):
                    interface.dps_cache[dp_key] = state
                self._dispatch_status()
        else:
            self.error("Not connected to device %s", self._dev_config_entry[CONF_FRIENDLY_NAME])

    async def set_dps(self, states):
        interface = self._interface
        if interface is not None:
            try:
                await interface.set_dps(states)
            except Exception:  # pylint: disable=broad-except
                self.exception("Failed to set DPs %r", states)
                return
            if self._interface is interface:
                normalized_states = {str(dp_index): value for dp_index, value in states.items()}
                self._status.update(normalized_states)
                if hasattr(interface, "dps_cache"):
                    interface.dps_cache.update(normalized_states)
                self._dispatch_status()
        else:
            self.error("Not connected to device %s", self._dev_config_entry[CONF_FRIENDLY_NAME])

    @callback
    def status_updated(self, status):
        prune_missing_non_persistent_dps(
            self._status, status, self._non_persistent_dps
        )
        self._status.update(status)
        self._dispatch_status()

    @callback
    def _dispatch_raw_status(self, received):
        if not isinstance(received, dict):
            return
        normalized = {str(dp_id): value for dp_id, value in received.items()}
        if normalized:
            signal = f"localtuya_raw_{self._dev_config_entry[CONF_DEVICE_ID]}"
            async_dispatcher_send(self._hass, signal, normalized)

    def _dispatch_status(self):
        signal = f"localtuya_{self._dev_config_entry[CONF_DEVICE_ID]}"
        async_dispatcher_send(self._hass, signal, self._status)

    @callback
    def disconnected(self):
        self._interface = None
        self._status.clear()
        if self._unsub_interval is not None:
            self._unsub_interval()
            self._unsub_interval = None
        if self._disconnect_task is not None:
            self._disconnect_task()
            self._disconnect_task = None
        signal = f"localtuya_{self._dev_config_entry[CONF_DEVICE_ID]}"
        async_dispatcher_send(self._hass, signal, None)
        if self._is_closing:
            self.debug("Device disconnected while closing")
        else:
            self.warning("Disconnected - waiting for discovery broadcast")


class LocalTuyaEntity(RestoreEntity, pytuya.ContextualLogger):
    """Representation of a Tuya entity."""

    def __init__(self, device, config_entry, dp_id, logger, **kwargs):
        super().__init__()
        self._device = device
        self._dev_config_entry = config_entry
        self._config = get_entity_config(config_entry, dp_id)
        enabled_default = self._config.get(CONF_ENTITY_REGISTRY_ENABLED_DEFAULT)
        if isinstance(enabled_default, bool):
            self._attr_entity_registry_enabled_default = enabled_default
        self._dp_id = dp_id
        self._status = {}
        self._state = None
        self._last_state = None
        self._extra_state_attribute_dps = get_extra_state_attribute_dps(self._config)
        self._mapped_extra_state_attribute_dps = get_mapped_extra_state_attribute_dps(self._config)
        self._mapped_extra_state_attribute_mappings = get_mapped_extra_state_attribute_mappings(self._config)
        self._advanced_mapping = validate_advanced_mapping(self._config.get(CONF_ADVANCED_MAPPING)) or []
        self._advanced_mapping_by_dp = (
            validate_advanced_mapping_by_dp(self._config.get(CONF_ADVANCED_MAPPING_BY_DP)) or {}
        )
        self._default_value = self._config.get(CONF_DEFAULT_VALUE)
        self._is_passive_entity = self._config.get(CONF_PASSIVE_ENTITY) or False
        self._restore_on_reconnect = self._config.get(CONF_RESTORE_ON_RECONNECT) or False
        self.set_logger(logger, self._dev_config_entry[CONF_DEVICE_ID])

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self.debug("Adding %s with configuration: %s", self.entity_id, self._config)
        state = await self.async_get_last_state()
        if state:
            self.status_restored(state)

        @callback
        def _update_handler(status):
            if status is None:
                status = {}
            if self._status != status:
                self._status = status.copy()
                if status:
                    self.status_updated()
                self.async_write_ha_state()
        signal = f"localtuya_{self._dev_config_entry[CONF_DEVICE_ID]}"
        self.async_on_remove(async_dispatcher_connect(self.hass, signal, _update_handler))
        signal = f"localtuya_entity_{self._dev_config_entry[CONF_DEVICE_ID]}"
        async_dispatcher_send(self.hass, signal, self.entity_id)

    @property
    def extra_state_attributes(self):
        attributes = {}
        if self._state is not None:
            attributes[ATTR_STATE] = self._state
        elif self._last_state is not None:
            attributes[ATTR_STATE] = self._last_state
        for name, dp_id in self._extra_state_attribute_dps.items():
            dp_key = str(dp_id)
            if dp_key in self._status:
                attributes[name] = self._status[dp_key]
        for name, dp_id in getattr(self, "_mapped_extra_state_attribute_dps", {}).items():
            dp_key = str(dp_id)
            if dp_key in self._status:
                rules = getattr(self, "_mapped_extra_state_attribute_mappings", {}).get(name)
                if rules:
                    attributes[name] = map_value_from_dps(
                        self.raw_dps(dp_id), rules, self._status
                    )[0]
                else:
                    attributes[name] = self.dps(dp_id)
        self.debug("Entity %s - Additional attributes: %s", self.name, attributes)
        return attributes

    @property
    def device_info(self):
        model = self._dev_config_entry.get(CONF_MODEL, "Tuya generic")
        return DeviceInfo(
            identifiers={(DOMAIN, f"local_{self._dev_config_entry[CONF_DEVICE_ID]}")},
            name=self._dev_config_entry[CONF_FRIENDLY_NAME], manufacturer="Tuya",
            model=f"{model} ({self._dev_config_entry[CONF_DEVICE_ID]})",
            sw_version=str(self._dev_config_entry[CONF_PROTOCOL_VERSION]),
        )

    @property
    def name(self):
        return self._config[CONF_FRIENDLY_NAME]

    @property
    def should_poll(self):
        return False

    @property
    def unique_id(self):
        return f"local_{self._dev_config_entry[CONF_DEVICE_ID]}_{self._dp_id}"

    def has_config(self, attr):
        value = self._config.get(attr, "-1")
        return value is not None and value != "-1"

    @property
    def available(self):
        return str(self._dp_id) in self._status

    def raw_dps(self, dp_index):
        """Return one cached raw Tuya DP without advanced mapping."""
        if dp_index is None:
            return None
        value = self._status.get(str(dp_index))
        if value is None:
            self.warning("Entity %s is requesting unknown DPS index %s", self.entity_id, dp_index)
        return value

    def _mapping_for_dp(self, dp_index):
        """Return a validated mapping for one DP, preserving legacy primary rules."""
        if dp_index is None or isinstance(dp_index, bool):
            return []
        try:
            dp_id = int(dp_index)
        except (TypeError, ValueError):
            return []
        by_dp = getattr(self, "_advanced_mapping_by_dp", {})
        mapped = by_dp.get(str(dp_id)) if isinstance(by_dp, dict) else None
        if mapped:
            return mapped
        legacy = getattr(self, "_advanced_mapping", [])
        return legacy if dp_id == int(self._dp_id) else []

    def has_advanced_mapping(self, dp_index=None):
        """Return whether one logical DP has a declarative catalog mapping."""
        dp_index = self._dp_id if dp_index is None else dp_index
        return bool(self._mapping_for_dp(dp_index))

    def mapped_numeric_metadata(self, dp_index=None):
        """Return active declarative range/step metadata for one logical DP."""
        dp_index = self._dp_id if dp_index is None else dp_index
        rules = self._mapping_for_dp(dp_index)
        if not rules:
            return {}
        raw = self.raw_dps(dp_index)
        return effective_mapping_metadata(raw, rules, self._status)

    def _mapped_dps_value(self, dp_index, seen):
        value = self.raw_dps(dp_index)
        rules = self._mapping_for_dp(dp_index)
        if value is None or not rules:
            return value
        dp_id = int(dp_index)
        if dp_id in seen:
            self.warning("Advanced mapping redirect cycle at DPS %s", dp_id)
            return value
        mapped, redirect_dp = map_value_from_dps(value, rules, self._status)
        if redirect_dp is not None:
            return self._mapped_dps_value(redirect_dp, seen | {dp_id})
        return mapped

    def dps(self, dp_index):
        """Return a DP value after any declarative per-DP mapping."""
        return self._mapped_dps_value(dp_index, set())

    def dps_conf(self, conf_item):
        dp_index = self._config.get(conf_item)
        if dp_index is None:
            self.warning("Entity %s is requesting unset index for option %s", self.entity_id, conf_item)
        return self.dps(dp_index)

    async def set_mapped_dp(self, state, dp_index=None):
        """Write an HA value using the mapping attached to its logical DP."""
        dp_index = self._dp_id if dp_index is None else dp_index
        rules = self._mapping_for_dp(dp_index)
        if not rules:
            await self._device.set_dp(state, dp_index)
            return
        states = map_value_to_dps(state, rules, self._status, int(dp_index))
        if len(states) == 1:
            target_dp, raw_value = next(iter(states.items()))
            await self._device.set_dp(raw_value, target_dp)
        else:
            await self._device.set_dps(states)

    async def set_mapped_dps(self, states):
        """Map several logical DPS and send one conflict-free grouped write."""
        writes = {}
        for raw_dp, state in states.items():
            dp_id = int(raw_dp)
            rules = self._mapping_for_dp(dp_id)
            mapped = map_value_to_dps(state, rules, self._status, dp_id) if rules else {dp_id: state}
            for target_dp, raw_value in mapped.items():
                target_dp = int(target_dp)
                if target_dp in writes and writes[target_dp] != raw_value:
                    raise ValueError(f"Conflicting advanced mapping writes for DP {target_dp}")
                writes[target_dp] = raw_value
        if not writes:
            return
        if len(writes) == 1:
            target_dp, raw_value = next(iter(writes.items()))
            await self._device.set_dp(raw_value, target_dp)
        else:
            await self._device.set_dps(writes)

    def status_updated(self):
        state = self.dps(self._dp_id)
        self._state = state
        if state is not None and not self._device.is_connecting:
            self._last_state = state

    def status_restored(self, stored_state):
        raw_state = stored_state.attributes.get(ATTR_STATE)
        if raw_state is not None:
            self._last_state = raw_state
            self.debug("Restoring state for entity: %s - state: %s", self.name, str(self._last_state))

    def default_value(self):
        if self._default_value is None:
            self._default_value = self.entity_default_value()
        return self._default_value

    def entity_default_value(self):  # pylint: disable=no-self-use
        return 0

    @property
    def restore_on_reconnect(self):
        return self._restore_on_reconnect

    async def restore_state_when_connected(self):
        if (not self.restore_on_reconnect) and ((str(self._dp_id) in self._status) or (not self._is_passive_entity)):
            self.debug(
                "Entity %s (DP %d) - Not restoring as restore on reconnect is disabled for this entity and the entity has an initial status or it is not a passive entity",
                self.name, self._dp_id,
            )
            return
        self.debug("Attempting to restore state for entity: %s", self.name)
        restore_state = self._state
        if restore_state == STATE_UNKNOWN or restore_state is None:
            restore_state = self._last_state
        if restore_state is None:
            if self._is_passive_entity:
                restore_state = self.default_value()
            else:
                return
        self.debug("Entity %s (DP %d) - Restoring state: %s", self.name, self._dp_id, str(restore_state))
        await self.set_mapped_dp(restore_state, self._dp_id)
