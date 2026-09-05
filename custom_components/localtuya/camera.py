"""Platform to expose DP-driven Tuya cameras."""

import base64
import binascii
import logging
from functools import partial

import voluptuous as vol
from homeassistant.components.camera import DOMAIN, Camera as CameraEntity, CameraEntityFeature

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


def flow_schema(dps):
    return {
        vol.Optional(CONF_CAMERA_SWITCH_DP): vol.In(dps),
        vol.Optional(CONF_CAMERA_SNAPSHOT_DP): vol.In(dps),
        vol.Optional(CONF_CAMERA_RECORD_DP): vol.In(dps),
        vol.Optional(CONF_CAMERA_MOTION_DP): vol.In(dps),
    }


def _decode_snapshot(raw, encoding):
    if raw is None:
        return None
    if isinstance(raw, bytes):
        return raw
    if not isinstance(raw, str):
        return None
    try:
        if encoding == "base64":
            return base64.b64decode(raw, validate=True)
        if encoding == "hex":
            return bytes.fromhex(raw)
        return raw.encode()
    except (ValueError, binascii.Error):
        return None


class LocaltuyaCamera(LocalTuyaEntity, CameraEntity):
    def __init__(self, device, config_entry, dp_id, **kwargs):
        CameraEntity.__init__(self)
        LocalTuyaEntity.__init__(self, device, config_entry, dp_id, _LOGGER, **kwargs)
        if self.has_config(CONF_CAMERA_SWITCH_DP):
            self._attr_supported_features |= CameraEntityFeature.ON_OFF

    @property
    def is_on(self):
        if not self.has_config(CONF_CAMERA_SWITCH_DP):
            return None
        raw = self.dps(self._config[CONF_CAMERA_SWITCH_DP])
        if raw == self._config.get(CONF_CAMERA_SWITCH_ON, True):
            return True
        if raw == self._config.get(CONF_CAMERA_SWITCH_OFF, False):
            return False
        return None

    @property
    def is_recording(self):
        if not self.has_config(CONF_CAMERA_RECORD_DP):
            return None
        raw = self.dps(self._config[CONF_CAMERA_RECORD_DP])
        if raw == self._config.get(CONF_CAMERA_RECORD_ON, True):
            return True
        if raw == self._config.get(CONF_CAMERA_RECORD_OFF, False):
            return False
        return None

    @property
    def motion_detection_enabled(self):
        if not self.has_config(CONF_CAMERA_MOTION_DP):
            return None
        raw = self.dps(self._config[CONF_CAMERA_MOTION_DP])
        if raw == self._config.get(CONF_CAMERA_MOTION_ON, True):
            return True
        if raw == self._config.get(CONF_CAMERA_MOTION_OFF, False):
            return False
        return None

    async def async_camera_image(self, width=None, height=None):
        if not self.has_config(CONF_CAMERA_SNAPSHOT_DP):
            return None
        return _decode_snapshot(
            self.dps(self._config[CONF_CAMERA_SNAPSHOT_DP]),
            self._config.get(CONF_CAMERA_SNAPSHOT_ENCODING, "base64"),
        )

    async def async_turn_on(self):
        if not self.has_config(CONF_CAMERA_SWITCH_DP):
            raise NotImplementedError()
        await self._device.set_dp(self._config.get(CONF_CAMERA_SWITCH_ON, True), self._config[CONF_CAMERA_SWITCH_DP])

    async def async_turn_off(self):
        if not self.has_config(CONF_CAMERA_SWITCH_DP):
            raise NotImplementedError()
        await self._device.set_dp(self._config.get(CONF_CAMERA_SWITCH_OFF, False), self._config[CONF_CAMERA_SWITCH_DP])

    async def async_enable_motion_detection(self):
        if not self.has_config(CONF_CAMERA_MOTION_DP):
            raise NotImplementedError()
        await self._device.set_dp(self._config.get(CONF_CAMERA_MOTION_ON, True), self._config[CONF_CAMERA_MOTION_DP])

    async def async_disable_motion_detection(self):
        if not self.has_config(CONF_CAMERA_MOTION_DP):
            raise NotImplementedError()
        await self._device.set_dp(self._config.get(CONF_CAMERA_MOTION_OFF, False), self._config[CONF_CAMERA_MOTION_DP])


async_setup_entry = partial(async_setup_entry, DOMAIN, LocaltuyaCamera, flow_schema)
