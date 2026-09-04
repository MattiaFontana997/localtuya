"""Config flow for LocalTuya integration integration."""
import asyncio
import copy
import errno
import logging
import time

import homeassistant.helpers.config_validation as cv
import homeassistant.helpers.entity_registry as er
import voluptuous as vol
from homeassistant import config_entries, core, exceptions
from homeassistant.const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_DEVICE_ID,
    CONF_DEVICES,
    CONF_ENTITIES,
    CONF_FRIENDLY_NAME,
    CONF_HOST,
    CONF_ID,
    CONF_NAME,
    CONF_PLATFORM,
    CONF_REGION,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)
from homeassistant.core import callback
from homeassistant.helpers.importlib import async_import_module
from homeassistant.helpers.translation import async_get_translations
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
)

from .cloud_api import TuyaCloudApi
from .common import pytuya
from .const import (
    ATTR_UPDATED_AT,
    CONF_ACTION,
    CONF_ADD_DEVICE,
    CONF_DPS_STRINGS,
    CONF_EDIT_DEVICE,
    CONF_REVIEW_MAPPING,
    CONF_ENABLE_DEBUG,
    CONF_LOCAL_KEY,
    CONF_MANUAL_DPS,
    CONF_MODEL,
    CONF_NO_CLOUD,
    CONF_PRODUCT_NAME,
    CONF_PRODUCT_KEY,
    CONF_PROTOCOL_VERSION,
    CONF_PREPARE_CONTRIBUTION,
    CONF_RESET_DPIDS,
    CONF_SETUP_CLOUD,
    CONF_USER_ID,
    CONF_ENABLE_ADD_ENTITIES,
    DATA_CLOUD,
    DATA_DISCOVERY,
    DATA_DEVICE_CATALOG,
    DOMAIN,
    PLATFORMS,
)
from .discovery import discover
from .device_mapper import (
    EntityCandidate,
    MappingConfidence,
)
from .mapping_resolver import (
    resolve_entity_candidates,
)
from .mapping_review import (
    MappingReviewKind,
    apply_existing_mapping_reviews,
    build_existing_mapping_reviews,
    default_existing_mapping_selection,
)
from .mapping_export import (
    build_mapping_contribution_package,
)

_LOGGER = logging.getLogger(__name__)

ENTRIES_VERSION = 2

PLATFORM_TO_ADD = "platform_to_add"
NO_ADDITIONAL_ENTITIES = "no_additional_entities"
SELECTED_DEVICE = "selected_device"
AUTO_ENTITY_SELECTION = "auto_entity_selection"
MAPPING_REVIEW_SELECTION = "mapping_review_selection"
CONTRIBUTION_CONFIRM = "contribution_confirm"
CONTRIBUTION_JSON = "contribution_json"

CUSTOM_DEVICE = "..."

PROTOCOL_AUTO = "auto"

SUPPORTED_PROTOCOL_VERSIONS = (
    "3.5",
    "3.4",
    "3.3",
    "3.2",
    "3.1",
)

PROTOCOL_OPTIONS = (
    PROTOCOL_AUTO,
    *SUPPORTED_PROTOCOL_VERSIONS,
)

PROTOCOL_PROBE_TIMEOUT = 8.0


_MAPPING_STATUS_FALLBACKS = {
    "mapping_status_verified":
        "Verified",
    "mapping_status_community":
        "Community",
    "mapping_status_experimental":
        "Experimental",
    "mapping_status_auto_detected":
        "Auto-detected",
    "mapping_status_suggested":
        "Suggested",
}


async def _async_mapping_status_labels(
    hass,
) -> dict[str, str]:
    """Load localized mapping status labels."""
    labels = dict(
        _MAPPING_STATUS_FALLBACKS
    )

    language = getattr(
        getattr(
            hass,
            "config",
            None,
        ),
        "language",
        "en",
    )

    try:
        translations = (
            await async_get_translations(
                hass,
                language,
                "common",
                {DOMAIN},
            )
        )
    except Exception as ex:
        _LOGGER.debug(
            "Unable to load mapping status "
            "translations for %s: %s",
            language,
            ex,
        )
        return labels

    prefix = (
        f"component.{DOMAIN}.common."
    )

    for key in labels:
        translated = translations.get(
            f"{prefix}{key}"
        )

        if (
            isinstance(
                translated,
                str,
            )
            and translated
        ):
            labels[key] = translated

    return labels


def _candidate_review_label(
    candidate: EntityCandidate,
    status_labels: dict[str, str] | None = None,
) -> str:
    """Return a localized review label."""
    if status_labels is None:
        status_labels = (
            _MAPPING_STATUS_FALLBACKS
        )

    entity_name = candidate.config.get(
        CONF_FRIENDLY_NAME,
        "Tuya entity",
    )

    status = status_labels.get(
        candidate.display_status_key,
        candidate.display_status_key,
    )

    return (
        f"{entity_name} "
        f"— {candidate.platform} "
        f"· {status} "
        f"(DP {candidate.primary_dp})"
    )


_ACTION_TRANSLATION_KEYS = {
    CONF_ADD_DEVICE:
        "action_add_device",
    CONF_EDIT_DEVICE:
        "action_edit_device",
    CONF_REVIEW_MAPPING:
        "action_review_mapping",
    CONF_PREPARE_CONTRIBUTION:
        "action_prepare_contribution",
    CONF_SETUP_CLOUD:
        "action_setup_cloud",
}

_ACTION_FALLBACKS = {
    CONF_ADD_DEVICE:
        "Add a new device",
    CONF_EDIT_DEVICE:
        "Edit a device",
    CONF_REVIEW_MAPPING:
        "Review device mapping",
    CONF_PREPARE_CONTRIBUTION:
        "Prepare community contribution",
    CONF_SETUP_CLOUD:
        "Reconfigure Cloud API account",
}


_MAPPING_CHANGE_FALLBACKS = {
    "mapping_change_update":
        "Update",
    "mapping_change_new":
        "New entity",
}


async def _async_mapping_change_labels(
    hass,
) -> dict[str, str]:
    """Load localized existing-device mapping change labels."""
    labels = dict(
        _MAPPING_CHANGE_FALLBACKS
    )

    language = getattr(
        getattr(
            hass,
            "config",
            None,
        ),
        "language",
        "en",
    )

    try:
        translations = (
            await async_get_translations(
                hass,
                language,
                "common",
                {DOMAIN},
            )
        )
    except Exception as ex:
        _LOGGER.debug(
            "Unable to load mapping change "
            "translations for %s: %s",
            language,
            ex,
        )
        return labels

    prefix = (
        f"component.{DOMAIN}.common."
    )

    for key in labels:
        translated = translations.get(
            f"{prefix}{key}"
        )

        if (
            isinstance(
                translated,
                str,
            )
            and translated
        ):
            labels[key] = translated

    return labels


def _existing_mapping_review_label(
    review,
    status_labels,
    change_labels,
) -> str:
    """Return label for one actionable existing-device mapping change."""
    entity_name = (
        review.proposed_config.get(
            CONF_FRIENDLY_NAME
        )
        or review.candidate.config.get(
            CONF_FRIENDLY_NAME
        )
        or "Tuya entity"
    )

    status = status_labels.get(
        review.candidate.display_status_key,
        review.candidate.display_status_key,
    )

    if (
        review.kind
        == MappingReviewKind.NEW
    ):
        change = change_labels[
            "mapping_change_new"
        ]

    else:
        change = change_labels[
            "mapping_change_update"
        ]

        if review.changed_keys:
            change = (
                f"{change}: "
                f"{', '.join(review.changed_keys)}"
            )

    return (
        f"{entity_name} "
        f"— {review.candidate.platform} "
        f"· {status} "
        f"· {change} "
        f"(DP {review.candidate.primary_dp})"
    )


async def _async_action_labels(
    hass,
) -> dict[str, str]:
    """Return localized labels for the main options actions."""
    labels = dict(
        _ACTION_FALLBACKS
    )

    language = getattr(
        getattr(
            hass,
            "config",
            None,
        ),
        "language",
        "en",
    )

    try:
        translations = (
            await async_get_translations(
                hass,
                language,
                "common",
                {DOMAIN},
            )
        )
    except Exception as ex:
        _LOGGER.debug(
            "Unable to load action translations "
            "for %s: %s",
            language,
            ex,
        )
        return labels

    prefix = (
        f"component.{DOMAIN}.common."
    )

    for (
        action,
        translation_key,
    ) in _ACTION_TRANSLATION_KEYS.items():
        translated = translations.get(
            f"{prefix}{translation_key}"
        )

        if (
            isinstance(
                translated,
                str,
            )
            and translated
        ):
            labels[action] = translated

    return labels


def _configure_schema(
    action_labels: dict[str, str],
):
    """Build the translated main options schema."""
    return vol.Schema(
        {
            vol.Required(
                CONF_ACTION,
                default=CONF_ADD_DEVICE,
            ): vol.In(
                action_labels
            ),
        }
    )


CLOUD_SETUP_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_REGION, default="eu"): vol.In(["eu", "us", "cn", "in"]),
        vol.Optional(CONF_CLIENT_ID): cv.string,
        vol.Optional(CONF_CLIENT_SECRET): cv.string,
        vol.Optional(CONF_USER_ID): cv.string,
        vol.Optional(CONF_USERNAME, default=DOMAIN): cv.string,
        vol.Required(CONF_NO_CLOUD, default=False): bool,
    }
)


DEVICE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_FRIENDLY_NAME): cv.string,
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_DEVICE_ID): cv.string,
        vol.Required(CONF_LOCAL_KEY): cv.string,
        vol.Required(CONF_PROTOCOL_VERSION, default=PROTOCOL_AUTO): vol.In(PROTOCOL_OPTIONS),
        vol.Required(CONF_ENABLE_DEBUG, default=False): bool,
        vol.Optional(CONF_SCAN_INTERVAL): int,
        vol.Optional(CONF_MANUAL_DPS): cv.string,
        vol.Optional(CONF_RESET_DPIDS): str,
    }
)

PICK_ENTITY_SCHEMA = vol.Schema(
    {vol.Required(PLATFORM_TO_ADD, default="switch"): vol.In(PLATFORMS)}
)


def devices_schema(discovered_devices, cloud_devices_list, add_custom_device=True):
    """Create schema for devices step."""
    devices = {}
    for dev_id, dev_host in discovered_devices.items():
        dev_name = dev_id
        if dev_id in cloud_devices_list.keys():
            dev_name = cloud_devices_list[dev_id][CONF_NAME]
        devices[dev_id] = f"{dev_name} ({dev_host})"

    if add_custom_device:
        devices.update({CUSTOM_DEVICE: CUSTOM_DEVICE})

    # devices.update(
    #     {
    #         ent.data[CONF_DEVICE_ID]: ent.data[CONF_FRIENDLY_NAME]
    #         for ent in entries
    #     }
    # )
    return vol.Schema({vol.Required(SELECTED_DEVICE): vol.In(devices)})


def options_schema(entities):
    """Create schema for options."""
    entity_names = [
        f"{entity[CONF_ID]}: {entity[CONF_FRIENDLY_NAME]}" for entity in entities
    ]
    return vol.Schema(
        {
            vol.Required(CONF_FRIENDLY_NAME): cv.string,
            vol.Required(CONF_HOST): cv.string,
            vol.Required(CONF_LOCAL_KEY): cv.string,
            vol.Required(CONF_PROTOCOL_VERSION, default=PROTOCOL_AUTO): vol.In(PROTOCOL_OPTIONS),
            vol.Required(CONF_ENABLE_DEBUG, default=False): bool,
            vol.Optional(CONF_SCAN_INTERVAL): int,
            vol.Optional(CONF_MANUAL_DPS): cv.string,
            vol.Optional(CONF_RESET_DPIDS): cv.string,
            vol.Required(
                CONF_ENTITIES, description={"suggested_value": entity_names}
            ): cv.multi_select(entity_names),
            vol.Required(CONF_ENABLE_ADD_ENTITIES, default=False): bool,
        }
    )


def schema_defaults(schema, dps_list=None, **defaults):
    """Create a new schema with default values filled in."""
    copy = schema.extend({})
    for field, field_type in copy.schema.items():
        if isinstance(field_type, vol.In):
            value = None
            for dps in dps_list or []:
                if dps.startswith(f"{defaults.get(field)} "):
                    value = dps
                    break

            if value in field_type.container:
                field.default = vol.default_factory(value)
                continue

        if field.schema in defaults:
            field.default = vol.default_factory(defaults[field])
    return copy


def dps_string_list(dps_data):
    """Return list of friendly DPS values."""
    return [f"{id} (value: {value})" for id, value in dps_data.items()]


def gen_dps_strings():
    """Generate list of DPS values."""
    return [f"{dp} (value: ?)" for dp in range(1, 256)]


def _detected_dp_ids(dps_strings):
    """Return integer DP ids from LocalTuya friendly DPS strings."""
    result = set()

    for dp_string in dps_strings:
        try:
            result.add(int(str(dp_string).split(" ", 1)[0]))
        except (TypeError, ValueError):
            continue

    return result


async def async_get_entity_candidates(
    hass,
    device_data,
    discovered_devices,
    dps_strings,
    *,
    include_catalog=True,
):
    """Build entity suggestions from every available mapping source."""
    domain_data = hass.data.get(
        DOMAIN,
        {},
    )

    device_id = device_data.get(
        CONF_DEVICE_ID
    )

    if not device_id:
        return []

    discovered = (
        discovered_devices.get(
            device_id,
            {},
        )
    )

    if not isinstance(
        discovered,
        dict,
    ):
        discovered = {}

    cloud_device = {}
    specification = {}

    cloud_api = domain_data.get(
        DATA_CLOUD
    )

    # Cloud metadata is optional enrichment.
    # A failure here must not disable bundled/cached mappings.
    if cloud_api is not None:
        candidate = (
            cloud_api.device_list.get(
                device_id
            )
        )

        if isinstance(
            candidate,
            dict,
        ):
            cloud_device = candidate

            try:
                (
                    result,
                    cloud_specification,
                ) = await (
                    cloud_api
                    .async_get_device_specification(
                        device_id
                    )
                )

                if (
                    result == "ok"
                    and isinstance(
                        cloud_specification,
                        dict,
                    )
                ):
                    specification = (
                        cloud_specification
                    )

                else:
                    _LOGGER.debug(
                        "No usable Tuya Cloud "
                        "specification for device %s: %s",
                        device_id,
                        result,
                    )

            except Exception as ex:
                _LOGGER.debug(
                    "Unable to retrieve Tuya Cloud "
                    "specification for device %s: %s",
                    device_id,
                    ex,
                )

    # LAN/discovery information is the base.
    # Cloud metadata only supplements it.
    mapper_device = {
        **discovered,
        **cloud_device,
    }

    # Existing devices may already have learned productKey
    # from LAN discovery and stored it in their config.
    product_key = device_data.get(
        CONF_PRODUCT_KEY
    )

    if (
        product_key
        and not any(
            mapper_device.get(key)
            for key in (
                "product_id",
                "productId",
                "product_key",
                "productKey",
            )
        )
    ):
        mapper_device[
            "product_key"
        ] = product_key

    friendly_name = device_data.get(
        CONF_FRIENDLY_NAME
    )

    if friendly_name:
        mapper_device[
            "name"
        ] = friendly_name

    detected_ids = _detected_dp_ids(
        dps_strings
    )

    catalog_client = (
        domain_data.get(
            DATA_DEVICE_CATALOG
        )
        if include_catalog
        else None
    )

    return resolve_entity_candidates(
        mapper_device,
        specification,
        detected_ids,
        catalog_client=(
            catalog_client
        ),
    )


async def platform_schema(
    hass, platform, dps_strings, allow_id=True
):
    """Generate input validation schema for a platform."""
    schema = {}

    if allow_id:
        schema[vol.Required(CONF_ID)] = vol.In(dps_strings)

    schema[vol.Required(CONF_FRIENDLY_NAME)] = str

    return vol.Schema(schema).extend(
        await flow_schema(hass, platform, dps_strings)
    )


async def flow_schema(hass, platform, dps_strings):
    """Return flow schema for a specific platform."""
    module = await async_import_module(
        hass,
        f"{__package__}.{platform}",
    )
    return module.flow_schema(dps_strings)


def strip_dps_values(user_input, dps_strings):
    """Remove values and keep only index for DPS config items."""
    stripped = {}
    for field, value in user_input.items():
        if value in dps_strings:
            stripped[field] = int(user_input[field].split(" ")[0])
        else:
            stripped[field] = user_input[field]
    return stripped


async def _async_probe_protocol(
    data,
    protocol_version,
    reset_ids,
):
    """Probe one Tuya LAN protocol and return detected datapoints."""
    interface = None

    try:
        async with asyncio.timeout(PROTOCOL_PROBE_TIMEOUT):
            interface = await pytuya.connect(
                data[CONF_HOST],
                data[CONF_DEVICE_ID],
                data[CONF_LOCAL_KEY],
                float(protocol_version),
                data.get(CONF_ENABLE_DEBUG, False),
            )

            try:
                detected_dps = (
                    await interface.detect_available_dps()
                )

            except Exception as ex:
                if (
                    protocol_version == "3.3"
                    and reset_ids
                ):
                    _LOGGER.debug(
                        "Initial DPS detection failed using "
                        "protocol %s (%s); trying reset IDs %s",
                        protocol_version,
                        ex,
                        reset_ids,
                    )

                    await interface.reset(reset_ids)

                    detected_dps = (
                        await interface.detect_available_dps()
                    )
                else:
                    raise

            return detected_dps or {}

    finally:
        if interface is not None:
            try:
                await interface.close()
            except Exception as ex:
                _LOGGER.debug(
                    "Error closing protocol %s probe: %s",
                    protocol_version,
                    ex,
                )


async def validate_input(
    hass: core.HomeAssistant,
    data,
):
    """Validate input and resolve the Tuya LAN protocol."""
    reset_ids = []

    reset_ids_value = data.get(CONF_RESET_DPIDS)

    if reset_ids_value:
        try:
            reset_ids = [
                int(value.strip())
                for value in reset_ids_value.split(",")
                if value.strip()
            ]
        except ValueError as ex:
            raise InvalidAuth from ex

        _LOGGER.debug(
            "Reset DPIDs configured: %s",
            reset_ids,
        )

    requested_protocol = data.get(
        CONF_PROTOCOL_VERSION,
        PROTOCOL_AUTO,
    )

    detected_dps = {}
    resolved_protocol = None

    if requested_protocol == PROTOCOL_AUTO:
        _LOGGER.debug(
            "Auto-detecting Tuya protocol for host %s",
            data[CONF_HOST],
        )

        for protocol_version in SUPPORTED_PROTOCOL_VERSIONS:
            try:
                detected_dps = await _async_probe_protocol(
                    data,
                    protocol_version,
                    reset_ids,
                )

            except Exception as ex:
                _LOGGER.debug(
                    "Protocol %s probe failed for host %s: %s: %s",
                    protocol_version,
                    data[CONF_HOST],
                    type(ex).__name__,
                    ex,
                )
                continue

            if not detected_dps:
                _LOGGER.debug(
                    "Protocol %s connected but returned no DPS",
                    protocol_version,
                )
                continue

            resolved_protocol = protocol_version

            _LOGGER.info(
                "Detected Tuya protocol %s for device %s",
                protocol_version,
                data[CONF_DEVICE_ID],
            )

            break

        if resolved_protocol is None:
            raise CannotConnect

    else:
        if (
            requested_protocol
            not in SUPPORTED_PROTOCOL_VERSIONS
        ):
            raise CannotConnect

        try:
            detected_dps = await _async_probe_protocol(
                data,
                requested_protocol,
                reset_ids,
            )

        except (
            ConnectionRefusedError,
            ConnectionResetError,
            OSError,
            TimeoutError,
        ) as ex:
            raise CannotConnect from ex

        except ValueError as ex:
            raise InvalidAuth from ex

        except Exception as ex:
            _LOGGER.debug(
                "DPS detection failed using protocol %s: %s",
                requested_protocol,
                ex,
            )
            detected_dps = {}

        resolved_protocol = requested_protocol

    manual_dps_value = data.get(CONF_MANUAL_DPS)

    if manual_dps_value:
        manual_dps = [
            value.strip()
            for value in manual_dps_value.split(",")
            if value.strip()
        ]

        _LOGGER.debug(
            "Manual DPS configured: %s",
            manual_dps,
        )

        for dp in manual_dps:
            if str(dp) not in detected_dps:
                detected_dps[str(dp)] = -1

    for dp in reset_ids:
        if str(dp) not in detected_dps:
            detected_dps[str(dp)] = -1

    if not detected_dps:
        raise EmptyDpsList

    _LOGGER.debug(
        "Total DPS using protocol %s: %s",
        resolved_protocol,
        detected_dps,
    )

    return (
        dps_string_list(detected_dps),
        resolved_protocol,
    )


async def attempt_cloud_connection(hass, user_input):
    """Create device."""
    cloud_api = TuyaCloudApi(
        hass,
        user_input.get(CONF_REGION),
        user_input.get(CONF_CLIENT_ID),
        user_input.get(CONF_CLIENT_SECRET),
        user_input.get(CONF_USER_ID),
    )

    res = await cloud_api.async_get_access_token()
    if res != "ok":
        _LOGGER.error("Cloud API connection failed: %s", res)
        return cloud_api, {"reason": "authentication_failed", "msg": res}

    res = await cloud_api.async_get_devices_list()
    if res != "ok":
        _LOGGER.error("Cloud API get_devices_list failed: %s", res)
        return cloud_api, {"reason": "device_list_failed", "msg": res}
    _LOGGER.info("Cloud API connection succeeded.")

    return cloud_api, {}


class LocaltuyaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for LocalTuya integration."""

    VERSION = ENTRIES_VERSION
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get options flow for this handler."""
        return LocalTuyaOptionsFlowHandler(config_entry)

    def __init__(self):
        """Initialize a new LocaltuyaConfigFlow."""

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        placeholders = {}
        if user_input is not None:
            if user_input.get(CONF_NO_CLOUD):
                for i in [CONF_CLIENT_ID, CONF_CLIENT_SECRET, CONF_USER_ID]:
                    user_input[i] = ""
                return await self._create_entry(user_input)

            cloud_api, res = await attempt_cloud_connection(self.hass, user_input)

            if not res:
                return await self._create_entry(user_input)
            errors["base"] = res["reason"]
            placeholders = {"msg": res["msg"]}

        defaults = {}
        defaults.update(user_input or {})

        return self.async_show_form(
            step_id="user",
            data_schema=schema_defaults(CLOUD_SETUP_SCHEMA, **defaults),
            errors=errors,
            description_placeholders=placeholders,
        )

    async def _create_entry(self, user_input):
        """Register new entry."""
        # if self._async_current_entries():
        #     return self.async_abort(reason="already_configured")

        await self.async_set_unique_id(user_input.get(CONF_USER_ID))
        user_input[CONF_DEVICES] = {}

        return self.async_create_entry(
            title=user_input.get(CONF_USERNAME),
            data=user_input,
        )

    async def async_step_import(self, user_input):
        """Handle import from YAML."""
        _LOGGER.error(
            "Configuration via YAML file is no longer supported by this integration."
        )


class LocalTuyaOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for LocalTuya integration."""

    def __init__(self, config_entry):
        """Initialize localtuya options flow."""
        self._config_entry = config_entry
        # self.dps_strings = config_entry.data.get(CONF_DPS_STRINGS, gen_dps_strings())
        # self.entities = config_entry.data[CONF_ENTITIES]
        self.selected_device = None
        self.editing_device = False
        self.device_data = None
        self.dps_strings = []
        self.selected_platform = None
        self.discovered_devices = {}
        self.entities = []
        self.auto_candidates = []
        self.mapping_reviews = []
        self.contribution_package = None

    async def async_step_init(self, user_input=None):
        """Manage basic options."""
        # device_id = self.config_entry.data[CONF_DEVICE_ID]
        if user_input is not None:
            if user_input.get(CONF_ACTION) == CONF_SETUP_CLOUD:
                return await self.async_step_cloud_setup()
            if user_input.get(CONF_ACTION) == CONF_ADD_DEVICE:
                return await self.async_step_add_device()
            if user_input.get(CONF_ACTION) == CONF_EDIT_DEVICE:
                return await self.async_step_edit_device()
            if user_input.get(CONF_ACTION) == CONF_REVIEW_MAPPING:
                return await self.async_step_review_mapping_device()
            if (
                user_input.get(CONF_ACTION)
                == CONF_PREPARE_CONTRIBUTION
            ):
                return await (
                    self.async_step_prepare_contribution_device()
                )

        action_labels = (
            await _async_action_labels(
                self.hass
            )
        )

        return self.async_show_form(
            step_id="init",
            data_schema=_configure_schema(
                action_labels
            ),
        )

    async def async_step_prepare_contribution_device(
        self,
        user_input=None,
    ):
        """Select a configured device for a community contribution."""
        errors = {}

        if user_input is not None:
            self.selected_device = user_input[
                SELECTED_DEVICE
            ]

            device_data = copy.deepcopy(
                self.config_entry.data[
                    CONF_DEVICES
                ][
                    self.selected_device
                ]
            )

            cloud_device = {}

            domain_data = self.hass.data.get(
                DOMAIN,
                {},
            )

            cloud_api = domain_data.get(
                DATA_CLOUD
            )

            if cloud_api is not None:
                device_list = getattr(
                    cloud_api,
                    "device_list",
                    {},
                )

                if isinstance(
                    device_list,
                    dict,
                ):
                    candidate = device_list.get(
                        self.selected_device
                    )

                    if isinstance(
                        candidate,
                        dict,
                    ):
                        cloud_device = candidate

            try:
                discovery = domain_data.get(
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
                ] = self.selected_device

                generic_candidates = (
                    await async_get_entity_candidates(
                        self.hass,
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

                self.contribution_package = (
                    build_mapping_contribution_package(
                        device_data,
                        cloud_device=cloud_device,
                        baseline_entities=(
                            baseline_entities
                        ),
                    )
                )

                return await (
                    self.async_step_prepare_contribution_review()
                )

            except ValueError as ex:
                _LOGGER.debug(
                    "Unable to prepare LocalTuya "
                    "community contribution: %s",
                    ex,
                )

                errors[
                    "base"
                ] = (
                    "contribution_not_available"
                )

        devices = {}

        for (
            device_id,
            device_data,
        ) in self.config_entry.data[
            CONF_DEVICES
        ].items():
            devices[
                device_id
            ] = device_data.get(
                CONF_FRIENDLY_NAME,
                "LocalTuya device",
            )

        return self.async_show_form(
            step_id=(
                "prepare_contribution_device"
            ),
            data_schema=vol.Schema(
                {
                    vol.Required(
                        SELECTED_DEVICE
                    ): vol.In(
                        devices
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_prepare_contribution_review(
        self,
        user_input=None,
    ):
        """Review exactly what will be included in a contribution."""
        if (
            not isinstance(
                self.contribution_package,
                dict,
            )
            or self.selected_device is None
        ):
            return await (
                self.async_step_prepare_contribution_device()
            )

        errors = {}

        if user_input is not None:
            if user_input.get(
                CONTRIBUTION_CONFIRM,
                False,
            ):
                return await (
                    self.async_step_prepare_contribution_result()
                )

            errors[
                "base"
            ] = (
                "contribution_confirmation_required"
            )

        preview = self.contribution_package[
            "preview"
        ]

        configured_device = (
            self.config_entry.data[
                CONF_DEVICES
            ][
                self.selected_device
            ]
        )

        device_name = configured_device.get(
            CONF_FRIENDLY_NAME,
            "LocalTuya device",
        )

        status_labels = (
            await _async_mapping_status_labels(
                self.hass
            )
        )

        confidence = preview.get(
            "confidence",
            "experimental",
        )

        if confidence == "experimental":
            confidence = status_labels[
                "mapping_status_experimental"
            ]

        observed_dps = ", ".join(
            str(dp)
            for dp
            in preview.get(
                "observed_dps",
                []
            )
        )

        required_dps = ", ".join(
            str(dp)
            for dp
            in preview.get(
                "required_dps",
                []
            )
        )

        return self.async_show_form(
            step_id=(
                "prepare_contribution_review"
            ),
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONTRIBUTION_CONFIRM,
                        default=False,
                    ): bool,
                }
            ),
            errors=errors,
            description_placeholders={
                "device":
                    str(device_name),
                "product_id":
                    str(
                        preview.get(
                            "product_id",
                            "—",
                        )
                    ),
                "category":
                    str(
                        preview.get(
                            "category",
                        )
                        or "—"
                    ),
                "protocol_version":
                    str(
                        preview.get(
                            "protocol_version",
                            "—",
                        )
                    ),
                "entity_count":
                    str(
                        preview.get(
                            "entity_count",
                            0,
                        )
                    ),
                "observed_dps":
                    observed_dps,
                "required_dps":
                    required_dps,
                "confidence":
                    str(confidence),
                "filename":
                    str(
                        self.contribution_package[
                            "suggested_filename"
                        ]
                    ),
            },
        )

    async def async_step_prepare_contribution_result(
        self,
        user_input=None,
    ):
        """Show sanitized JSON after explicit user confirmation."""
        if not isinstance(
            self.contribution_package,
            dict,
        ):
            return await (
                self.async_step_prepare_contribution_device()
            )

        if user_input is not None:
            return self.async_external_step(
                step_id=(
                    "prepare_contribution_result"
                ),
                url=str(
                    self.contribution_package[
                        "new_submission_url"
                    ]
                ),
            )

        submission_json = (
            self.contribution_package[
                "submission_json"
            ]
        )

        return self.async_show_form(
            step_id=(
                "prepare_contribution_result"
            ),
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONTRIBUTION_JSON,
                        description={
                            "suggested_value":
                                submission_json
                        },
                    ): TextSelector(
                        TextSelectorConfig(
                            multiline=True,
                        )
                    ),
                }
            ),
            description_placeholders={
                "filename":
                    str(
                        self.contribution_package[
                            "suggested_filename"
                        ]
                    ),
                "new_submission_url":
                    str(
                        self.contribution_package[
                            "new_submission_url"
                        ]
                    ),
                "repository_url":
                    str(
                        self.contribution_package[
                            "repository_url"
                        ]
                    ),
            },
        )

    async def async_step_review_mapping_device(
        self,
        user_input=None,
    ):
        """Select and resolve mapping for an existing device."""
        errors = {}

        if user_input is not None:
            self.selected_device = (
                user_input[
                    SELECTED_DEVICE
                ]
            )

            existing_device = (
                self.config_entry.data[
                    CONF_DEVICES
                ][
                    self.selected_device
                ]
            )

            self.entities = copy.deepcopy(
                existing_device.get(
                    CONF_ENTITIES,
                    [],
                )
            )

            self.device_data = (
                copy.deepcopy(
                    existing_device
                )
            )

            self.device_data[
                CONF_DEVICE_ID
            ] = self.selected_device

            try:
                probe_data = (
                    copy.deepcopy(
                        existing_device
                    )
                )

                probe_data[
                    CONF_DEVICE_ID
                ] = self.selected_device

                (
                    self.dps_strings,
                    resolved_protocol,
                ) = await validate_input(
                    self.hass,
                    probe_data,
                )

                self.device_data[
                    CONF_PROTOCOL_VERSION
                ] = resolved_protocol

                domain_data = (
                    self.hass.data.get(
                        DOMAIN,
                        {},
                    )
                )

                discovery = (
                    domain_data.get(
                        DATA_DISCOVERY
                    )
                )

                discovered = getattr(
                    discovery,
                    "devices",
                    {},
                )

                self.discovered_devices = (
                    discovered
                    if isinstance(
                        discovered,
                        dict,
                    )
                    else {}
                )

                # A manual mapping review is a good moment
                # to try the latest catalog. Failure is safe:
                # DeviceCatalog keeps cache/bundled fallback.
                catalog_client = (
                    domain_data.get(
                        DATA_DEVICE_CATALOG
                    )
                )

                refresh = getattr(
                    catalog_client,
                    "async_refresh",
                    None,
                )

                if callable(refresh):
                    try:
                        await refresh()
                    except Exception as ex:
                        _LOGGER.debug(
                            "Unable to refresh device "
                            "catalog during mapping "
                            "review: %s",
                            ex,
                        )

                candidates = (
                    await async_get_entity_candidates(
                        self.hass,
                        self.device_data,
                        self.discovered_devices,
                        self.dps_strings,
                    )
                )

                self.mapping_reviews = (
                    build_existing_mapping_reviews(
                        self.entities,
                        candidates,
                    )
                )

                return await (
                    self.async_step_review_mapping_changes()
                )

            except CannotConnect:
                errors["base"] = (
                    "cannot_connect"
                )
            except InvalidAuth:
                errors["base"] = (
                    "invalid_auth"
                )
            except EmptyDpsList:
                errors["base"] = (
                    "empty_dps"
                )
            except Exception as ex:
                _LOGGER.exception(
                    "Unable to review LocalTuya "
                    "device mapping: %s",
                    ex,
                )
                errors["base"] = "unknown"

        devices = {}

        for (
            device_id,
            device,
        ) in (
            self.config_entry.data[
                CONF_DEVICES
            ].items()
        ):
            name = device.get(
                CONF_FRIENDLY_NAME,
                device_id,
            )

            host = device.get(
                CONF_HOST,
                "?",
            )

            devices[
                device_id
            ] = (
                f"{name} ({host})"
            )

        return self.async_show_form(
            step_id=(
                "review_mapping_device"
            ),
            data_schema=vol.Schema(
                {
                    vol.Required(
                        SELECTED_DEVICE
                    ): vol.In(
                        devices
                    )
                }
            ),
            errors=errors,
        )

    async def async_step_review_mapping_changes(
        self,
        user_input=None,
    ):
        """Review and explicitly apply mapping changes."""
        actionable_reviews = [
            review
            for review
            in self.mapping_reviews
            if review.actionable
        ]

        if user_input is not None:
            selected = set(
                user_input.get(
                    MAPPING_REVIEW_SELECTION,
                    [],
                )
            )

            if selected:
                updated_entities = (
                    apply_existing_mapping_reviews(
                        self.entities,
                        self.mapping_reviews,
                        selected,
                    )
                )

                new_data = copy.deepcopy(
                    dict(
                        self.config_entry.data
                    )
                )

                device_config = (
                    copy.deepcopy(
                        new_data[
                            CONF_DEVICES
                        ][
                            self.selected_device
                        ]
                    )
                )

                device_config[
                    CONF_ENTITIES
                ] = updated_entities

                # Store the DPS list actually observed during
                # this explicit review. No other device settings
                # are silently changed.
                device_config[
                    CONF_DPS_STRINGS
                ] = list(
                    self.dps_strings
                )

                new_data[
                    CONF_DEVICES
                ][
                    self.selected_device
                ] = device_config

                new_data[
                    ATTR_UPDATED_AT
                ] = str(
                    int(
                        time.time()
                        * 1000
                    )
                )

                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data=new_data,
                )

            return self.async_create_entry(
                title="",
                data={},
            )

        status_labels = (
            await _async_mapping_status_labels(
                self.hass
            )
        )

        change_labels = (
            await _async_mapping_change_labels(
                self.hass
            )
        )

        options = {
            review.key:
                _existing_mapping_review_label(
                    review,
                    status_labels,
                    change_labels,
                )
            for review
            in actionable_reviews
        }

        default_selection = (
            default_existing_mapping_selection(
                self.mapping_reviews
            )
        )

        current_count = sum(
            1
            for review
            in self.mapping_reviews
            if (
                review.kind
                == MappingReviewKind.CURRENT
            )
        )

        conflict_count = sum(
            1
            for review
            in self.mapping_reviews
            if (
                review.kind
                == MappingReviewKind.CONFLICT
            )
        )

        configured_device = (
            self.config_entry.data[
                CONF_DEVICES
            ][
                self.selected_device
            ]
        )

        device_name = (
            configured_device.get(
                CONF_FRIENDLY_NAME
            )
            or self.selected_device
        )

        return self.async_show_form(
            step_id=(
                "review_mapping_changes"
            ),
            data_schema=vol.Schema(
                {
                    vol.Required(
                        MAPPING_REVIEW_SELECTION,
                        default=(
                            default_selection
                        ),
                    ): cv.multi_select(
                        options
                    ),
                }
            ),
            description_placeholders={
                "device":
                    str(device_name),
                "actionable":
                    str(
                        len(
                            actionable_reviews
                        )
                    ),
                "current":
                    str(current_count),
                "conflicts":
                    str(conflict_count),
            },
        )

    async def async_step_cloud_setup(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        placeholders = {}
        if user_input is not None:
            if user_input.get(CONF_NO_CLOUD):
                new_data = copy.deepcopy(dict(self.config_entry.data))
                new_data.update(user_input)
                for i in [CONF_CLIENT_ID, CONF_CLIENT_SECRET, CONF_USER_ID]:
                    new_data[i] = ""
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data=new_data,
                )
                return self.async_create_entry(
                    title=new_data.get(CONF_USERNAME), data={}
                )

            cloud_api, res = await attempt_cloud_connection(self.hass, user_input)

            if not res:
                new_data = copy.deepcopy(dict(self.config_entry.data))
                new_data.update(user_input)
                cloud_devs = cloud_api.device_list
                for dev_id, dev in new_data[CONF_DEVICES].items():
                    if CONF_MODEL not in dev and dev_id in cloud_devs:
                        model = cloud_devs[dev_id].get(CONF_PRODUCT_NAME)
                        new_data[CONF_DEVICES][dev_id][CONF_MODEL] = model
                new_data[ATTR_UPDATED_AT] = str(int(time.time() * 1000))

                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data=new_data,
                )
                return self.async_create_entry(
                    title=new_data.get(CONF_USERNAME), data={}
                )
            errors["base"] = res["reason"]
            placeholders = {"msg": res["msg"]}

        defaults = self.config_entry.data.copy()
        defaults.update(user_input or {})
        defaults[CONF_NO_CLOUD] = False

        return self.async_show_form(
            step_id="cloud_setup",
            data_schema=schema_defaults(CLOUD_SETUP_SCHEMA, **defaults),
            errors=errors,
            description_placeholders=placeholders,
        )

    async def async_step_add_device(self, user_input=None):
        """Handle adding a new device."""
        # Use cache if available or fallback to manual discovery
        self.editing_device = False
        self.selected_device = None
        errors = {}
        if user_input is not None:
            if user_input[SELECTED_DEVICE] != CUSTOM_DEVICE:
                self.selected_device = user_input[SELECTED_DEVICE]

            return await self.async_step_configure_device()

        self.discovered_devices = {}
        data = self.hass.data.get(DOMAIN)

        if data and DATA_DISCOVERY in data:
            discovery = data[
                DATA_DISCOVERY
            ]

            try:
                await (
                    discovery
                    .async_request_discovery()
                )

                # Active REQ_DEVINFO replies are normally
                # immediate. Give the listener a short window
                # to populate its cache before building the UI.
                await asyncio.sleep(1.0)

            except Exception as ex:
                _LOGGER.debug(
                    "Active Tuya discovery refresh "
                    "failed: %s",
                    ex,
                )

            self.discovered_devices = (
                discovery.devices
            )
        else:
            try:
                self.discovered_devices = (
                    await discover(
                        hass=self.hass
                    )
                )
            except OSError as ex:
                if ex.errno == errno.EADDRINUSE:
                    errors["base"] = "address_in_use"
                else:
                    errors["base"] = "discovery_failed"
            except Exception as ex:
                _LOGGER.exception("discovery failed: %s", ex)
                errors["base"] = "discovery_failed"

        devices = {
            dev_id: dev["ip"]
            for dev_id, dev in self.discovered_devices.items()
            if dev["gwId"] not in self.config_entry.data[CONF_DEVICES]
        }

        return self.async_show_form(
            step_id="add_device",
            data_schema=devices_schema(
                devices, self.hass.data[DOMAIN][DATA_CLOUD].device_list
            ),
            errors=errors,
        )

    async def async_step_edit_device(self, user_input=None):
        """Handle editing a device."""
        self.editing_device = True
        # Use cache if available or fallback to manual discovery
        errors = {}
        if user_input is not None:
            self.selected_device = user_input[SELECTED_DEVICE]
            dev_conf = self.config_entry.data[CONF_DEVICES][self.selected_device]
            self.dps_strings = dev_conf.get(CONF_DPS_STRINGS, gen_dps_strings())
            self.entities = copy.deepcopy(dev_conf[CONF_ENTITIES])

            return await self.async_step_configure_device()

        devices = {}
        for dev_id, configured_dev in self.config_entry.data[CONF_DEVICES].items():
            devices[dev_id] = configured_dev[CONF_HOST]

        return self.async_show_form(
            step_id="edit_device",
            data_schema=devices_schema(
                devices, self.hass.data[DOMAIN][DATA_CLOUD].device_list, False
            ),
            errors=errors,
        )

    async def async_step_configure_device(self, user_input=None):
        """Handle input of basic info."""
        errors = {}
        dev_id = self.selected_device
        if user_input is not None:
            try:
                self.device_data = user_input.copy()
                if dev_id is not None:
                    # self.device_data[CONF_PRODUCT_KEY] = self.devices[
                    #     self.selected_device
                    # ]["productKey"]
                    cloud_devs = self.hass.data[DOMAIN][DATA_CLOUD].device_list
                    if dev_id in cloud_devs:
                        self.device_data[CONF_MODEL] = cloud_devs[dev_id].get(
                            CONF_PRODUCT_NAME
                        )
                if (
                    self.editing_device
                    and self.device_data.get(
                        CONF_PROTOCOL_VERSION
                    ) == PROTOCOL_AUTO
                ):
                    probe_data = dict(self.device_data)
                    probe_data[CONF_DEVICE_ID] = dev_id

                    (
                        self.dps_strings,
                        resolved_protocol,
                    ) = await validate_input(
                        self.hass,
                        probe_data,
                    )

                    self.device_data[
                        CONF_PROTOCOL_VERSION
                    ] = resolved_protocol

                    user_input[
                        CONF_PROTOCOL_VERSION
                    ] = resolved_protocol

                if self.editing_device:
                    if user_input[CONF_ENABLE_ADD_ENTITIES]:
                        self.editing_device = False
                        user_input[CONF_DEVICE_ID] = dev_id
                        self.device_data.update(
                            {
                                CONF_DEVICE_ID: dev_id,
                                CONF_DPS_STRINGS: self.dps_strings,
                            }
                        )
                        return await self.async_step_pick_entity_type()

                    self.device_data.update(
                        {
                            CONF_DEVICE_ID: dev_id,
                            CONF_DPS_STRINGS: self.dps_strings,
                            CONF_ENTITIES: [],
                        }
                    )
                    if len(user_input[CONF_ENTITIES]) == 0:
                        return self.async_abort(
                            reason="no_entities",
                            description_placeholders={},
                        )
                    if user_input[CONF_ENTITIES]:
                        entity_ids = [
                            int(entity.split(":")[0])
                            for entity in user_input[CONF_ENTITIES]
                        ]
                        self.entities = [
                            entity
                            for entity in self.entities
                            if entity[CONF_ID] in entity_ids
                        ]
                        return await self.async_step_configure_entity()

                (
                    self.dps_strings,
                    resolved_protocol,
                ) = await validate_input(
                    self.hass,
                    user_input,
                )

                self.device_data[
                    CONF_PROTOCOL_VERSION
                ] = resolved_protocol

                self.auto_candidates = (
                    await async_get_entity_candidates(
                        self.hass,
                        self.device_data,
                        self.discovered_devices,
                        self.dps_strings,
                    )
                )

                if self.auto_candidates:
                    return await (
                        self.async_step_review_auto_entities()
                    )

                return await self.async_step_pick_entity_type()
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except EmptyDpsList:
                errors["base"] = "empty_dps"
            except Exception as ex:
                _LOGGER.exception("Unexpected exception: %s", ex)
                errors["base"] = "unknown"

        defaults = {}
        if self.editing_device:
            # If selected device exists as a config entry, load config from it
            defaults = self.config_entry.data[CONF_DEVICES][dev_id].copy()
            cloud_devs = self.hass.data[DOMAIN][DATA_CLOUD].device_list
            placeholders = {"for_device": f" for device `{dev_id}`"}
            if dev_id in cloud_devs:
                cloud_local_key = cloud_devs[dev_id].get(CONF_LOCAL_KEY)
                if defaults[CONF_LOCAL_KEY] != cloud_local_key:
                    _LOGGER.info(
                        "New local_key detected for device %s",
                        dev_id,
                    )
                    defaults[CONF_LOCAL_KEY] = cloud_devs[dev_id].get(CONF_LOCAL_KEY)
                    note = "\nNOTE: a new local_key has been retrieved using cloud API"
                    placeholders = {"for_device": f" for device `{dev_id}`.{note}"}
            defaults[CONF_ENABLE_ADD_ENTITIES] = False
            schema = schema_defaults(options_schema(self.entities), **defaults)
        else:
            defaults[CONF_PROTOCOL_VERSION] = PROTOCOL_AUTO
            defaults[CONF_HOST] = ""
            defaults[CONF_DEVICE_ID] = ""
            defaults[CONF_LOCAL_KEY] = ""
            defaults[CONF_FRIENDLY_NAME] = ""
            if dev_id is not None:
                # Insert default values from discovery and cloud if present
                device = self.discovered_devices[dev_id]
                defaults[CONF_HOST] = device.get("ip")
                defaults[CONF_DEVICE_ID] = device.get("gwId")
                discovered_version = str(
                    device.get("version") or ""
                )

                if (
                    discovered_version
                    in SUPPORTED_PROTOCOL_VERSIONS
                ):
                    defaults[
                        CONF_PROTOCOL_VERSION
                    ] = discovered_version
                else:
                    defaults[
                        CONF_PROTOCOL_VERSION
                    ] = PROTOCOL_AUTO
                cloud_devs = self.hass.data[DOMAIN][DATA_CLOUD].device_list
                if dev_id in cloud_devs:
                    defaults[CONF_LOCAL_KEY] = cloud_devs[dev_id].get(CONF_LOCAL_KEY)
                    defaults[CONF_FRIENDLY_NAME] = cloud_devs[dev_id].get(CONF_NAME)
            schema = schema_defaults(DEVICE_SCHEMA, **defaults)

            placeholders = {"for_device": ""}

        return self.async_show_form(
            step_id="configure_device",
            data_schema=schema,
            errors=errors,
            description_placeholders=placeholders,
        )

    async def async_step_review_auto_entities(
        self,
        user_input=None,
    ):
        """Review automatically resolved entity suggestions."""
        status_labels = (
            await _async_mapping_status_labels(
                self.hass
            )
        )

        options = {
            str(index):
                _candidate_review_label(
                    candidate,
                    status_labels,
                )
            for index, candidate
            in enumerate(self.auto_candidates)
        }

        # HIGH-confidence mappings are selected automatically.
        # MEDIUM mappings are visible but require explicit approval.
        default_selection = [
            str(index)
            for index, candidate
            in enumerate(self.auto_candidates)
            if (
                candidate.confidence
                == MappingConfidence.HIGH
            )
        ]

        if user_input is not None:
            selected = set(
                user_input.get(
                    AUTO_ENTITY_SELECTION,
                    [],
                )
            )

            for index, candidate in enumerate(
                self.auto_candidates
            ):
                if str(index) not in selected:
                    continue

                self.entities.append(
                    copy.deepcopy(
                        candidate.config
                    )
                )

            # Suggestions are only temporary flow state.
            self.auto_candidates = []

            return await (
                self.async_step_pick_entity_type()
            )

        return self.async_show_form(
            step_id="review_auto_entities",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        AUTO_ENTITY_SELECTION,
                        default=default_selection,
                    ): cv.multi_select(options),
                }
            ),
        )

    async def async_step_pick_entity_type(self, user_input=None):
        """Handle asking if user wants to add another entity."""
        if user_input is not None:
            if user_input.get(NO_ADDITIONAL_ENTITIES):
                config = {
                    **self.device_data,
                    CONF_DPS_STRINGS: self.dps_strings,
                    CONF_ENTITIES: self.entities,
                }

                dev_id = self.device_data.get(CONF_DEVICE_ID)

                new_data = copy.deepcopy(dict(self.config_entry.data))
                new_data[ATTR_UPDATED_AT] = str(int(time.time() * 1000))
                new_data[CONF_DEVICES].update({dev_id: config})

                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data=new_data,
                )
                return self.async_create_entry(title="", data={})

            self.selected_platform = user_input[PLATFORM_TO_ADD]
            return await self.async_step_configure_entity()

        # Add a checkbox that allows bailing out from config flow if at least one
        # entity has been added
        schema = PICK_ENTITY_SCHEMA
        if self.entities:
            schema = schema.extend(
                {vol.Required(NO_ADDITIONAL_ENTITIES, default=True): bool}
            )

        return self.async_show_form(step_id="pick_entity_type", data_schema=schema)

    def available_dps_strings(self):
        """Return list of DPs use by the device's entities."""
        available_dps = []
        used_dps = [str(entity[CONF_ID]) for entity in self.entities]
        for dp_string in self.dps_strings:
            dp = dp_string.split(" ")[0]
            if dp not in used_dps:
                available_dps.append(dp_string)
        return available_dps

    async def async_step_entity(self, user_input=None):
        """Manage entity settings."""
        errors = {}
        if user_input is not None:
            entity = strip_dps_values(user_input, self.dps_strings)
            entity[CONF_ID] = self.current_entity[CONF_ID]
            entity[CONF_PLATFORM] = self.current_entity[CONF_PLATFORM]
            self.device_data[CONF_ENTITIES].append(entity)

            if len(self.entities) == len(self.device_data[CONF_ENTITIES]):
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    title=self.device_data[CONF_FRIENDLY_NAME],
                    data=self.device_data,
                )
                return self.async_create_entry(title="", data={})

        schema = await platform_schema(
            self.hass,
            self.current_entity[CONF_PLATFORM], self.dps_strings, allow_id=False
        )
        return self.async_show_form(
            step_id="entity",
            errors=errors,
            data_schema=schema_defaults(
                schema, self.dps_strings, **self.current_entity
            ),
            description_placeholders={
                "id": self.current_entity[CONF_ID],
                "platform": self.current_entity[CONF_PLATFORM],
            },
        )

    async def async_step_configure_entity(self, user_input=None):
        """Manage entity settings."""
        errors = {}
        if user_input is not None:
            if self.editing_device:
                entity = strip_dps_values(user_input, self.dps_strings)
                entity[CONF_ID] = self.current_entity[CONF_ID]
                entity[CONF_PLATFORM] = self.current_entity[CONF_PLATFORM]
                self.device_data[CONF_ENTITIES].append(entity)

                if len(self.entities) == len(self.device_data[CONF_ENTITIES]):
                    # finished editing device. Let's store the new config entry....
                    dev_id = self.device_data[CONF_DEVICE_ID]
                    new_data = copy.deepcopy(dict(self.config_entry.data))
                    entry_id = self.config_entry.entry_id

                    old_entities = self.config_entry.data[CONF_DEVICES][dev_id][
                        CONF_ENTITIES
                    ]
                    new_dp_ids = {
                        entity[CONF_ID]
                        for entity in self.device_data[CONF_ENTITIES]
                    }
                    removed_unique_ids = {
                        f"local_{dev_id}_{entity[CONF_ID]}"
                        for entity in old_entities
                        if entity[CONF_ID] not in new_dp_ids
                    }

                    if removed_unique_ids:
                        ent_reg = er.async_get(self.hass)
                        for reg_entity in er.async_entries_for_config_entry(
                            ent_reg, entry_id
                        ):
                            if reg_entity.unique_id in removed_unique_ids:
                                ent_reg.async_remove(reg_entity.entity_id)

                    new_data[CONF_DEVICES][dev_id] = self.device_data
                    new_data[ATTR_UPDATED_AT] = str(int(time.time() * 1000))
                    self.hass.config_entries.async_update_entry(
                        self.config_entry,
                        data=new_data,
                    )
                    return self.async_create_entry(title="", data={})
            else:
                user_input[CONF_PLATFORM] = self.selected_platform
                self.entities.append(strip_dps_values(user_input, self.dps_strings))
                # new entity added. Let's check if there are more left...
                user_input = None
                if len(self.available_dps_strings()) == 0:
                    user_input = {NO_ADDITIONAL_ENTITIES: True}
                return await self.async_step_pick_entity_type(user_input)

        if self.editing_device:
            schema = await platform_schema(
                self.hass,
                self.current_entity[CONF_PLATFORM], self.dps_strings, allow_id=False
            )
            schema = schema_defaults(schema, self.dps_strings, **self.current_entity)
            placeholders = {
                "entity": f"entity with DP {self.current_entity[CONF_ID]}",
                "platform": self.current_entity[CONF_PLATFORM],
            }
        else:
            available_dps = self.available_dps_strings()
            schema = await platform_schema(
                self.hass,
                self.selected_platform,
                available_dps,
            )
            placeholders = {
                "entity": "an entity",
                "platform": self.selected_platform,
            }

        return self.async_show_form(
            step_id="configure_entity",
            data_schema=schema,
            errors=errors,
            description_placeholders=placeholders,
        )

    async def async_step_yaml_import(self, user_input=None):
        """Manage YAML imports."""
        _LOGGER.error(
            "Configuration via YAML file is no longer supported by this integration."
        )
        # if user_input is not None:
        #     return self.async_create_entry(title="", data={})
        # return self.async_show_form(step_id="yaml_import")

    @property
    def current_entity(self):
        """Existing configuration for entity currently being edited."""
        return self.entities[len(self.device_data[CONF_ENTITIES])]


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""


class EmptyDpsList(exceptions.HomeAssistantError):
    """Error to indicate no datapoints found."""
