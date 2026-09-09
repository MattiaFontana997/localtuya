"""The LocalTuya integration."""
import asyncio
import copy
import logging
import time
from datetime import timedelta

import homeassistant.helpers.config_validation as cv
import homeassistant.helpers.entity_registry as er
import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_DEVICE_ID,
    CONF_DEVICES,
    CONF_ENTITIES,
    CONF_HOST,
    CONF_ID,
    CONF_PLATFORM,
    CONF_REGION,
    CONF_USERNAME,
    EVENT_HOMEASSISTANT_STOP,
    SERVICE_RELOAD,
)
from homeassistant.core import HomeAssistant, SupportsResponse
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.service import async_register_admin_service

from .cloud_api import TuyaCloudApi
from .common import TuyaDevice, async_config_entry_by_device_id
from .config_flow import (
    ENTRIES_VERSION,
    async_get_entity_candidates,
    validate_input,
)
from .const import (
    ATTR_UPDATED_AT,
    CONF_DPS_STRINGS,
    CONF_NO_CLOUD,
    CONF_PRODUCT_KEY,
    CONF_USER_ID,
    DATA_CLOUD,
    DATA_DISCOVERY,
    DATA_DEVICE_CATALOG,
    DOMAIN,
    TUYA_DEVICES,
)
from .device_catalog import DeviceCatalog
from .discovery import TuyaDiscovery
from .host_recovery import (
    HostRecoveryOutcome,
    async_recover_discovered_host,
)
from .health_service import (
    DeviceHealthTargetNotFound,
    async_check_configured_device_health,
)
from .mapping_export import build_mapping_submission

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

LOADED_PLATFORMS = "loaded_platforms"
LOADED_DEVICES = "loaded_devices"

RECONNECT_INTERVAL = timedelta(seconds=60)
CATALOG_REFRESH_INTERVAL = timedelta(hours=24)

CONF_DP = "dp"
CONF_VALUE = "value"

SERVICE_SET_DP = "set_dp"
SERVICE_SET_DP_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_DEVICE_ID): cv.string,
        vol.Required(CONF_DP): int,
        vol.Required(CONF_VALUE): object,
    }
)

SERVICE_REFRESH_DEVICE_CATALOG = (
    "refresh_device_catalog"
)

SERVICE_EXPORT_DEVICE_MAPPING = (
    "export_device_mapping"
)

SERVICE_EXPORT_DEVICE_MAPPING_SCHEMA = vol.Schema(
    {
        vol.Required(
            CONF_DEVICE_ID
        ): cv.string,
    }
)

SERVICE_CHECK_DEVICE_HEALTH = (
    "check_device_health"
)
SERVICE_CHECK_DEVICE_HEALTH_SCHEMA = vol.Schema(
    {
        vol.Required(
            CONF_DEVICE_ID
        ): cv.string,
    }
)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the LocalTuya integration component."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][TUYA_DEVICES] = {}

    device_catalog = DeviceCatalog(hass)

    # Reading the bundled JSON touches the filesystem and must
    # not happen inside Home Assistant's event loop.
    await device_catalog.async_load_builtin_catalog()

    hass.data[DOMAIN][DATA_DEVICE_CATALOG] = (
        device_catalog
    )

    # Restore the last valid catalog before attempting any
    # network access. LocalTuya therefore remains usable when
    # GitHub or the Internet is unavailable.
    await device_catalog.async_load_cache()

    # Remote availability must never block LocalTuya startup.
    hass.async_create_task(
        device_catalog.async_refresh()
    )

    host_recovery_tasks = {}

    async def _handle_reload(service):
        """Handle reload service call."""
        _LOGGER.info("Service %s.reload called: reloading integration", DOMAIN)

        current_entries = hass.config_entries.async_entries(DOMAIN)

        reload_tasks = [
            hass.config_entries.async_reload(entry.entry_id)
            for entry in current_entries
        ]

        await asyncio.gather(*reload_tasks)

    async def _handle_set_dp(event):
        """Handle set_dp service call."""
        dev_id = event.data[CONF_DEVICE_ID]
        if dev_id not in hass.data[DOMAIN][TUYA_DEVICES]:
            raise HomeAssistantError("unknown device id")

        device = hass.data[DOMAIN][TUYA_DEVICES][dev_id]
        if not device.connected:
            raise HomeAssistantError("not connected to device")

        await device.set_dp(event.data[CONF_VALUE], event.data[CONF_DP])

    async def _handle_refresh_device_catalog(service):
        """Refresh the remote community device catalog."""
        success = await device_catalog.async_refresh()

        return {
            "success": success,
            "mappings": (
                device_catalog.mapping_count
            ),
            "cache_loaded": (
                device_catalog.cache_loaded
            ),
        }

    async def _handle_export_device_mapping(service):
        """Return a privacy-safe community mapping."""
        dev_id = service.data[
            CONF_DEVICE_ID
        ]

        entry = async_config_entry_by_device_id(
            hass,
            dev_id,
        )

        if (
            entry is None
            or dev_id
            not in entry.data[CONF_DEVICES]
        ):
            raise HomeAssistantError(
                "unknown LocalTuya device id"
            )

        device_data = entry.data[
            CONF_DEVICES
        ][dev_id]

        cloud_device = {}

        cloud_api = hass.data[
            DOMAIN
        ].get(DATA_CLOUD)

        if cloud_api is not None:
            candidate = (
                cloud_api.device_list.get(
                    dev_id
                )
            )

            if isinstance(
                candidate,
                dict,
            ):
                cloud_device = candidate

        try:
            discovery = hass.data[
                DOMAIN
            ].get(
                DATA_DISCOVERY
            )

            discovered_devices = getattr(
                discovery,
                "devices",
                {},
            )

            if not isinstance(
                discovered_devices,
                dict,
            ):
                discovered_devices = {}

            candidate_device_data = (
                copy.deepcopy(
                    device_data
                )
            )

            candidate_device_data[
                CONF_DEVICE_ID
            ] = dev_id

            generic_candidates = (
                await async_get_entity_candidates(
                    hass,
                    candidate_device_data,
                    discovered_devices,
                    device_data.get(
                        CONF_DPS_STRINGS,
                        [],
                    ),
                    include_catalog=False,
                )
            )

            baseline_entities = [
                {
                    "platform":
                        candidate.platform,
                    "config":
                        copy.deepcopy(
                            candidate.config
                        ),
                }
                for candidate
                in generic_candidates
            ]

            return build_mapping_submission(
                device_data,
                cloud_device=cloud_device,
                baseline_entities=(
                    baseline_entities
                ),
            )

        except ValueError as ex:
            raise HomeAssistantError(
                str(ex)
            ) from ex

    async def _handle_check_device_health(service):
        """Return a bounded privacy-safe health report for one device."""
        try:
            return await async_check_configured_device_health(
                hass,
                service.data[CONF_DEVICE_ID],
            )
        except DeviceHealthTargetNotFound as ex:
            raise HomeAssistantError(
                "unknown LocalTuya device id"
            ) from ex

    async def _async_recover_discovered_device(
        device_id,
        device_ip,
        product_key,
    ):
        """Validate a discovered address before persisting it."""
        result = None

        try:
            entry = async_config_entry_by_device_id(
                hass,
                device_id,
            )

            if entry is None:
                return

            result = await async_recover_discovered_host(
                hass,
                entry,
                device_id,
                str(device_ip),
                validator=validate_input,
                product_key=(
                    str(product_key)
                    if product_key is not None
                    else None
                ),
            )

            _LOGGER.debug(
                "Validated Tuya host recovery result: %s",
                result.as_dict(),
            )

        except asyncio.CancelledError:
            raise
        except Exception as ex:  # pylint: disable=broad-except
            _LOGGER.debug(
                "Unexpected Tuya host recovery failure: %s",
                type(ex).__name__,
            )
        finally:
            host_recovery_tasks.pop(
                device_id,
                None,
            )

        if (
            result is not None
            and result.outcome
            is HostRecoveryOutcome.UNCHANGED
        ):
            runtime_device = hass.data[
                DOMAIN
            ][TUYA_DEVICES].get(
                device_id
            )

            if (
                runtime_device is not None
                and not runtime_device.connected
            ):
                runtime_device.async_connect()

    def _gateway_child_targets(gateway_id):
        """Return configured child devices routed through one gateway."""
        targets = []

        for candidate_entry in hass.config_entries.async_entries(DOMAIN):
            devices = candidate_entry.data.get(CONF_DEVICES, {})
            if not isinstance(devices, dict):
                continue

            for child_id, child_data in devices.items():
                if not isinstance(child_data, dict):
                    continue
                if str(child_data.get("gateway_id") or "") != gateway_id:
                    continue
                targets.append((candidate_entry, str(child_id)))

        return targets

    async def _async_recover_gateway_children(
        gateway_id,
        device_ip,
        targets,
    ):
        """Recover gateway-backed child hosts sequentially and safely."""
        task_key = f"gateway:{gateway_id}"
        current_task = asyncio.current_task()

        try:
            for entry, child_id in targets:
                devices = entry.data.get(CONF_DEVICES, {})
                child_data = (
                    devices.get(child_id)
                    if isinstance(devices, dict)
                    else None
                )
                if not isinstance(child_data, dict):
                    continue

                configured_host = str(
                    child_data.get(CONF_HOST) or ""
                )

                if configured_host == device_ip:
                    runtime_device = hass.data[DOMAIN][TUYA_DEVICES].get(
                        child_id
                    )
                    if (
                        runtime_device is not None
                        and not runtime_device.connected
                    ):
                        runtime_device.async_connect()
                    continue

                try:
                    result = await async_recover_discovered_host(
                        hass,
                        entry,
                        child_id,
                        device_ip,
                        validator=validate_input,
                        # productKey belongs to the gateway, not the child.
                        product_key=None,
                    )
                    _LOGGER.debug(
                        "Validated Tuya gateway child host recovery result: %s",
                        result.as_dict(),
                    )
                except asyncio.CancelledError:
                    raise
                except Exception as ex:  # pylint: disable=broad-except
                    _LOGGER.debug(
                        "Unexpected Tuya gateway child recovery failure: %s",
                        type(ex).__name__,
                    )
        finally:
            host_recovery_tasks.pop(task_key, None)
            for _entry, child_id in targets:
                if host_recovery_tasks.get(child_id) is current_task:
                    host_recovery_tasks.pop(child_id, None)

    def _schedule_gateway_child_recovery(gateway_id, device_ip):
        """Schedule one serialized recovery pass for a gateway's children."""
        targets = _gateway_child_targets(gateway_id)
        if not targets:
            return

        task_key = f"gateway:{gateway_id}"
        existing_gateway_task = host_recovery_tasks.get(task_key)
        if (
            existing_gateway_task is not None
            and not existing_gateway_task.done()
        ):
            return

        pending_targets = []
        for entry, child_id in targets:
            existing_child_task = host_recovery_tasks.get(child_id)
            if (
                existing_child_task is not None
                and not existing_child_task.done()
            ):
                continue
            pending_targets.append((entry, child_id))

        if not pending_targets:
            return

        task = hass.async_create_task(
            _async_recover_gateway_children(
                gateway_id,
                device_ip,
                pending_targets,
            )
        )
        host_recovery_tasks[task_key] = task
        for _entry, child_id in pending_targets:
            host_recovery_tasks[child_id] = task

    def _device_discovered(device):
        """Reconnect configured devices and safely recover changed addresses."""
        device_ip = device.get("ip")
        device_id = device.get("gwId") or device.get("id")
        product_key = device.get("productKey")

        if not device_id or not device_ip:
            _LOGGER.debug(
                "Ignoring incomplete Tuya discovery payload"
            )
            return

        device_id = str(device_id)
        device_ip = str(device_ip)

        # A BLE/Zigbee child has no own LAN address. When the gateway is
        # rediscovered at a new IP, validate that address through each
        # configured child before persisting it. The child Device ID and
        # cid/node_id remain unchanged; only the gateway transport host moves.
        _schedule_gateway_child_recovery(
            device_id,
            device_ip,
        )

        entry = async_config_entry_by_device_id(
            hass,
            device_id,
        )
        if (
            entry is None
            or device_id not in entry.data[CONF_DEVICES]
        ):
            return

        dev_entry = entry.data[CONF_DEVICES][device_id]
        configured_host = str(
            dev_entry.get(CONF_HOST) or ""
        )

        if configured_host != device_ip:
            existing_task = host_recovery_tasks.get(
                device_id
            )

            if (
                existing_task is None
                or existing_task.done()
            ):
                task = hass.async_create_task(
                    _async_recover_discovered_device(
                        device_id,
                        device_ip,
                        product_key,
                    )
                )
                host_recovery_tasks[
                    device_id
                ] = task

            return

        if (
            product_key is not None
            and dev_entry.get(CONF_PRODUCT_KEY)
            != product_key
        ):
            new_data = copy.deepcopy(
                dict(entry.data)
            )
            new_data[CONF_DEVICES][device_id][
                CONF_PRODUCT_KEY
            ] = product_key
            new_data[ATTR_UPDATED_AT] = str(
                int(time.time() * 1000)
            )
            hass.config_entries.async_update_entry(
                entry,
                data=new_data,
            )
            return

        runtime_device = hass.data[DOMAIN][
            TUYA_DEVICES
        ].get(device_id)

        if runtime_device is None:
            _LOGGER.warning(
                "Could not find configured LocalTuya runtime device"
            )
        elif not runtime_device.connected:
            runtime_device.async_connect()

    def _shutdown(event):
        """Clean up resources when shutting down."""
        discovery.close()
        remove_catalog_refresh()
        remove_reconnect()

        for task in tuple(
            host_recovery_tasks.values()
        ):
            task.cancel()

        host_recovery_tasks.clear()

    async def _async_refresh_catalog(now):
        """Refresh community mappings periodically."""
        await device_catalog.async_refresh()

    async def _async_reconnect(now):
        """Rediscover and reconnect devices that are currently offline."""
        disconnected = [
            (device_id, device)
            for device_id, device
            in hass.data[DOMAIN][TUYA_DEVICES].items()
            if not device.connected
        ]

        if not disconnected:
            return

        discovery_service = hass.data[
            DOMAIN
        ].get(DATA_DISCOVERY)

        request_discovery = getattr(
            discovery_service,
            "async_request_discovery",
            None,
        )

        if callable(request_discovery):
            try:
                await request_discovery()
                await asyncio.sleep(1.0)
            except Exception as ex:  # pylint: disable=broad-except
                _LOGGER.debug(
                    "Active Tuya rediscovery before reconnect failed: %s",
                    type(ex).__name__,
                )

        for device_id, device in disconnected:
            if device_id in host_recovery_tasks:
                continue

            if not device.connected:
                device.async_connect()

    remove_catalog_refresh = (
        async_track_time_interval(
            hass,
            _async_refresh_catalog,
            CATALOG_REFRESH_INTERVAL,
        )
    )

    remove_reconnect = async_track_time_interval(
        hass,
        _async_reconnect,
        RECONNECT_INTERVAL,
    )

    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_RELOAD,
        _handle_reload,
    )

    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_REFRESH_DEVICE_CATALOG,
        _handle_refresh_device_catalog,
        supports_response=(
            SupportsResponse.ONLY
        ),
    )

    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_EXPORT_DEVICE_MAPPING,
        _handle_export_device_mapping,
        schema=(
            SERVICE_EXPORT_DEVICE_MAPPING_SCHEMA
        ),
        supports_response=(
            SupportsResponse.ONLY
        ),
    )

    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_CHECK_DEVICE_HEALTH,
        _handle_check_device_health,
        schema=(
            SERVICE_CHECK_DEVICE_HEALTH_SCHEMA
        ),
        supports_response=(
            SupportsResponse.ONLY
        ),
    )

    hass.services.async_register(
        DOMAIN, SERVICE_SET_DP, _handle_set_dp, schema=SERVICE_SET_DP_SCHEMA
    )

    discovery = TuyaDiscovery(
        _device_discovered,
        hass=hass,
    )
    try:
        await discovery.start()
        hass.data[DOMAIN][DATA_DISCOVERY] = discovery
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _shutdown)
    except Exception:  # pylint: disable=broad-except
        _LOGGER.exception("failed to set up discovery")

    return True


async def async_migrate_entry(hass, config_entry: ConfigEntry):
    """Migrate old entries merging all of them in one."""
    new_version = ENTRIES_VERSION
    stored_entries = hass.config_entries.async_entries(DOMAIN)
    if config_entry.version == 1:
        _LOGGER.debug("Migrating config entry from version %s", config_entry.version)

        if config_entry.entry_id == stored_entries[0].entry_id:
            _LOGGER.debug(
                "Migrating the first config entry (%s)", config_entry.entry_id
            )
            new_data = {}
            new_data[CONF_REGION] = "eu"
            new_data[CONF_CLIENT_ID] = ""
            new_data[CONF_CLIENT_SECRET] = ""
            new_data[CONF_USER_ID] = ""
            new_data[CONF_USERNAME] = DOMAIN
            new_data[CONF_NO_CLOUD] = True
            new_data[CONF_DEVICES] = {
                config_entry.data[CONF_DEVICE_ID]: copy.deepcopy(dict(config_entry.data))
            }
            new_data[ATTR_UPDATED_AT] = str(int(time.time() * 1000))
            hass.config_entries.async_update_entry(
                config_entry,
                title=DOMAIN,
                data=new_data,
                version=new_version,
            )
        else:
            _LOGGER.debug(
                "Merging the config entry %s into the main one", config_entry.entry_id
            )
            new_data = copy.deepcopy(dict(stored_entries[0].data))
            new_data[CONF_DEVICES].update(
                {config_entry.data[CONF_DEVICE_ID]: copy.deepcopy(dict(config_entry.data))}
            )
            new_data[ATTR_UPDATED_AT] = str(int(time.time() * 1000))
            hass.config_entries.async_update_entry(stored_entries[0], data=new_data)
            await hass.config_entries.async_remove(config_entry.entry_id)

    _LOGGER.info(
        "Entry %s successfully migrated to version %s.",
        config_entry.entry_id,
        new_version,
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up LocalTuya integration from a config entry."""
    if entry.version < ENTRIES_VERSION:
        _LOGGER.debug(
            "Skipping setup for entry %s since its version (%s) is old",
            entry.entry_id,
            entry.version,
        )
        return

    region = entry.data[CONF_REGION]
    client_id = entry.data[CONF_CLIENT_ID]
    secret = entry.data[CONF_CLIENT_SECRET]
    user_id = entry.data[CONF_USER_ID]
    tuya_api = TuyaCloudApi(hass, region, client_id, secret, user_id)
    no_cloud = True
    if CONF_NO_CLOUD in entry.data:
        no_cloud = entry.data.get(CONF_NO_CLOUD)
    if no_cloud:
        _LOGGER.info("Cloud API account not configured.")
        # wait 1 second to make sure possible migration has finished
        await asyncio.sleep(1)
    else:
        res = await tuya_api.async_get_access_token()
        if res != "ok":
            _LOGGER.error("Cloud API connection failed: %s", res)
        else:
            _LOGGER.info("Cloud API connection succeeded.")
            res = await tuya_api.async_get_devices_list()
    hass.data[DOMAIN][DATA_CLOUD] = tuya_api

    platforms = set()
    device_ids = set(entry.data[CONF_DEVICES])

    for dev_id in entry.data[CONF_DEVICES].keys():
        entities = entry.data[CONF_DEVICES][dev_id][CONF_ENTITIES]
        platforms = platforms.union(
            set(entity[CONF_PLATFORM] for entity in entities)
        )
        hass.data[DOMAIN][TUYA_DEVICES][dev_id] = TuyaDevice(hass, entry, dev_id)

    # Setup all platforms at once, letting HA handling each platform and avoiding
    # potential integration restarts while elements are still initialising.
    await hass.config_entries.async_forward_entry_setups(entry, platforms)

    hass.data[DOMAIN][entry.entry_id] = {
        LOADED_PLATFORMS: frozenset(platforms),
        LOADED_DEVICES: frozenset(device_ids),
    }

    async def setup_entities(device_ids):
        for dev_id in device_ids:
            hass.data[DOMAIN][TUYA_DEVICES][dev_id].async_connect()

    hass.async_create_task(setup_entities(entry.data[CONF_DEVICES].keys()))

    entry.async_on_unload(entry.add_update_listener(update_listener))

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: ConfigEntry
) -> bool:
    """Unload a config entry."""
    runtime = hass.data[DOMAIN].get(entry.entry_id, {})

    platforms = runtime.get(LOADED_PLATFORMS, ())
    device_ids = runtime.get(LOADED_DEVICES, ())

    unload_ok = await hass.config_entries.async_unload_platforms(
        entry,
        platforms,
    )

    if not unload_ok:
        return False

    for dev_id in device_ids:
        device = hass.data[DOMAIN][TUYA_DEVICES].pop(dev_id, None)
        if device is not None:
            await device.close()

    hass.data[DOMAIN].pop(entry.entry_id, None)

    return True


async def update_listener(hass, config_entry):
    """Schedule a reload after the config entry changes."""
    hass.config_entries.async_schedule_reload(config_entry.entry_id)


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: ConfigEntry, device_entry: DeviceEntry
) -> bool:
    """Remove a config entry from a device."""
    dev_id = list(device_entry.identifiers)[0][1].split("_")[-1]

    ent_reg = er.async_get(hass)
    entities = {
        ent.unique_id: ent.entity_id
        for ent in er.async_entries_for_config_entry(ent_reg, config_entry.entry_id)
        if dev_id in ent.unique_id
    }
    for entity_id in entities.values():
        ent_reg.async_remove(entity_id)

    if dev_id not in config_entry.data[CONF_DEVICES]:
        _LOGGER.info(
            "Device %s not found in config entry: finalizing device removal", dev_id
        )
        return True

    await hass.data[DOMAIN][TUYA_DEVICES][dev_id].close()

    new_data = copy.deepcopy(dict(config_entry.data))
    new_data[CONF_DEVICES].pop(dev_id)
    new_data[ATTR_UPDATED_AT] = str(int(time.time() * 1000))

    hass.config_entries.async_update_entry(
        config_entry,
        data=new_data,
    )

    _LOGGER.info("Device %s removed.", dev_id)

    return True