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
from .config_flow import ENTRIES_VERSION
from .const import (
    ATTR_UPDATED_AT,
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
from .mapping_export import build_mapping_submission
from .discovery import TuyaDiscovery

_LOGGER = logging.getLogger(__name__)

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


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the LocalTuya integration component."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][TUYA_DEVICES] = {}

    device_catalog = DeviceCatalog(hass)
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

    device_cache = {}

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
            return build_mapping_submission(
                device_data,
                cloud_device=cloud_device,
            )
        except ValueError as ex:
            raise HomeAssistantError(
                str(ex)
            ) from ex

    def _device_discovered(device):
        """Update address of device if it has changed."""
        device_ip = device.get("ip")
        device_id = device.get("gwId") or device.get("id")
        product_key = device.get("productKey")

        if not device_id or not device_ip:
            _LOGGER.debug(
                "Ignoring incomplete Tuya discovery payload: %s",
                device,
            )
            return

        # If device is not in cache, check if a config entry exists
        entry = async_config_entry_by_device_id(hass, device_id)
        if entry is None:
            return

        if device_id not in device_cache:
            if entry and device_id in entry.data[CONF_DEVICES]:
                # Save address from config entry in cache to trigger
                # potential update below
                host_ip = entry.data[CONF_DEVICES][device_id][CONF_HOST]
                device_cache[device_id] = host_ip

        if device_id not in device_cache:
            return

        dev_entry = entry.data[CONF_DEVICES][device_id]

        new_data = copy.deepcopy(dict(entry.data))
        updated = False

        if device_cache[device_id] != device_ip:
            updated = True
            new_data[CONF_DEVICES][device_id][CONF_HOST] = device_ip
            device_cache[device_id] = device_ip

        if (
            product_key is not None
            and dev_entry.get(CONF_PRODUCT_KEY) != product_key
        ):
            updated = True
            new_data[CONF_DEVICES][device_id][CONF_PRODUCT_KEY] = product_key

        # Update settings if something changed, otherwise try to connect. Updating
        # settings triggers a reload of the config entry, which tears down the device
        # so no need to connect in that case.
        if updated:
            _LOGGER.debug(
                "Updating keys for device %s: %s %s", device_id, device_ip, product_key
            )
            new_data[ATTR_UPDATED_AT] = str(int(time.time() * 1000))
            hass.config_entries.async_update_entry(entry, data=new_data)

        elif device_id in hass.data[DOMAIN][TUYA_DEVICES]:
            _LOGGER.debug("Device %s found with IP %s", device_id, device_ip)

        device = hass.data[DOMAIN][TUYA_DEVICES].get(device_id)
        if not device:
            _LOGGER.warning(f"Could not find device for device_id {device_id}")
        elif not device.connected:
            device.async_connect()


    def _shutdown(event):
        """Clean up resources when shutting down."""
        discovery.close()
        remove_catalog_refresh()

    async def _async_refresh_catalog(now):
        """Refresh community mappings periodically."""
        await device_catalog.async_refresh()

    async def _async_reconnect(now):
        """Try connecting to devices not already connected to."""
        for device_id, device in hass.data[DOMAIN][TUYA_DEVICES].items():
            if not device.connected:
                device.async_connect()

    remove_catalog_refresh = (
        async_track_time_interval(
            hass,
            _async_refresh_catalog,
            CATALOG_REFRESH_INTERVAL,
        )
    )

    async_track_time_interval(
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

    hass.services.async_register(
        DOMAIN, SERVICE_SET_DP, _handle_set_dp, schema=SERVICE_SET_DP_SCHEMA
    )

    discovery = TuyaDiscovery(_device_discovered)
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
