"""Platform to expose locally available Tuya camera datapoints."""

import base64
import binascii
import logging
from functools import partial
from urllib.parse import unquote_to_bytes

import voluptuous as vol
from homeassistant.components.camera import Camera as CameraEntity
from homeassistant.components.camera import CameraEntityFeature, DOMAIN

from .common import LocalTuyaEntity, async_setup_entry
from .const import (
    CONF_CAMERA_MOTION_DP,
    CONF_CAMERA_MOTION_OFF,
    CONF_CAMERA_MOTION_ON,
    CONF_CAMERA_RECORD_DP,
    CONF_CAMERA_RECORD_OFF,
    CONF_CAMERA_RECORD_ON,
    CONF_CAMERA_SNAPSHOT_DP,
    CONF_CAMERA_SNAPSHOT_ENCODING,
    CONF_CAMERA_SWITCH_DP,
    CONF_CAMERA_SWITCH_OFF,
    CONF_CAMERA_SWITCH_ON,
)

_LOGGER = logging.getLogger(__name__)

_SNAPSHOT_ENCODINGS = ("auto", "base64", "hex", "raw", "data_url")


def flow_schema(dps):
    """Return schema used in config flow."""
    return {
        vol.Optional(CONF_CAMERA_SWITCH_DP): vol.In(dps),
        vol.Optional(CONF_CAMERA_SNAPSHOT_DP): vol.In(dps),
        vol.Optional(CONF_CAMERA_RECORD_DP): vol.In(dps),
        vol.Optional(CONF_CAMERA_MOTION_DP): vol.In(dps),
        vol.Optional(CONF_CAMERA_SNAPSHOT_ENCODING, default="auto"): vol.In(
            _SNAPSHOT_ENCODINGS
        ),
    }


def _decode_snapshot(value, encoding):
    """Decode catalog-described Tuya snapshot payloads into image bytes."""
    if value is None:
        return None
    if isinstance(value, bytes):
        return value
    if not isinstance(value, str):
        return None

    value = value.strip()
    if not value:
        return None

    try:
        if encoding == "data_url" or (encoding == "auto" and value.startswith("data:")):
            header, payload = value.split(",", 1)
            if ";base64" in header:
                return base64.b64decode(payload, validate=True)
            return unquote_to_bytes(payload)
        if encoding == "hex":
            return bytes.fromhex(value)
        if encoding == "base64":
            return base64.b64decode(value, validate=True)
        if encoding == "raw":
            return value.encode("latin-1")
        if encoding == "auto":
            try:
                return base64.b64decode(value, validate=True)
            except (binascii.Error, ValueError):
                return value.encode("latin-1")
    except (binascii.Error, UnicodeEncodeError, ValueError):
        return None
    return None


def _exact_bool(raw, on_value, off_value):
    if raw == on_value:
        return True
    if raw == off_value:
        return False
    return None


class LocaltuyaCamera(LocalTuyaEntity, CameraEntity):
    """Representation of a Tuya camera."""

    def __init__(self, device, config_entry, cameraid, **kwargs):
        """Initialize the Tuya camera."""
        super().__init__(device, config_entry, cameraid, _LOGGER, **kwargs)
        self._switch_on = self._config.get(CONF_CAMERA_SWITCH_ON, True)
        self._switch_off = self._config.get(CONF_CAMERA_SWITCH_OFF, False)
        self._record_on = self._config.get(CONF_CAMERA_RECORD_ON, True)
        self._record_off = self._config.get(CONF_CAMERA_RECORD_OFF, False)
        self._motion_on = self._config.get(CONF_CAMERA_MOTION_ON, True)
        self._motion_off = self._config.get(CONF_CAMERA_MOTION_OFF, False)
        self._snapshot_encoding = self._config.get(
            CONF_CAMERA_SNAPSHOT_ENCODING, "auto"
        )

        features = CameraEntityFeature(0)
        if self.has_config(CONF_CAMERA_SWITCH_DP):
            features |= CameraEntityFeature.ON_OFF
        self._attr_supported_features = features

    @property
    def is_recording(self):
        """Return whether the camera reports local recording as active."""
        dp_id = self._config.get(CONF_CAMERA_RECORD_DP)
        if dp_id is None:
            return None
        return _exact_bool(self.dps(dp_id), self._record_on, self._record_off)

    @property
    def motion_detection_enabled(self):
        """Return whether camera-side motion detection is enabled."""
        dp_id = self._config.get(CONF_CAMERA_MOTION_DP)
        if dp_id is None:
            return None
        return _exact_bool(self.dps(dp_id), self._motion_on, self._motion_off)

    async def async_camera_image(self, width=None, height=None):
        """Return a locally published snapshot payload."""
        dp_id = self._config.get(CONF_CAMERA_SNAPSHOT_DP, self._dp_id)
        return _decode_snapshot(self.dps(dp_id), self._snapshot_encoding)

    @property
    def is_on(self):
        """Return camera power state when a dedicated power DP exists."""
        dp_id = self._config.get(CONF_CAMERA_SWITCH_DP)
        if dp_id is None:
            return True
        return _exact_bool(self.dps(dp_id), self._switch_on, self._switch_off)

    async def async_turn_off(self):
        """Turn off the camera using the exact catalog raw value."""
        dp_id = self._config.get(CONF_CAMERA_SWITCH_DP)
        if dp_id is None:
            raise NotImplementedError()
        await self._device.set_dp(self._switch_off, dp_id)

    async def async_turn_on(self):
        """Turn on the camera using the exact catalog raw value."""
        dp_id = self._config.get(CONF_CAMERA_SWITCH_DP)
        if dp_id is None:
            raise NotImplementedError()
        await self._device.set_dp(self._switch_on, dp_id)

    async def async_enable_motion_detection(self):
        """Enable camera-side motion detection."""
        dp_id = self._config.get(CONF_CAMERA_MOTION_DP)
        if dp_id is None:
            raise NotImplementedError()
        await self._device.set_dp(self._motion_on, dp_id)

    async def async_disable_motion_detection(self):
        """Disable camera-side motion detection."""
        dp_id = self._config.get(CONF_CAMERA_MOTION_DP)
        if dp_id is None:
            raise NotImplementedError()
        await self._device.set_dp(self._motion_off, dp_id)


async_setup_entry = partial(async_setup_entry, DOMAIN, LocaltuyaCamera, flow_schema)
