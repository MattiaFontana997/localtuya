"""Platform for Home Assistant's infrared emitter entity on Tuya hardware."""

import asyncio
import base64
import json
import logging
import struct
from functools import partial

import voluptuous as vol
from homeassistant.components.infrared import DOMAIN, InfraredCommand, InfraredEmitterEntity

from .common import LocalTuyaEntity, async_setup_entry
from .const import (
    CONF_INFRARED_CODE_TYPE_DP,
    CONF_INFRARED_CODE_TYPE_VALUE,
    CONF_INFRARED_CONTROL_DP,
    CONF_INFRARED_SEND_COMMAND,
    CONF_INFRARED_SEND_DP,
)

_LOGGER = logging.getLogger(__name__)


def flow_schema(dps):
    """Return schema used in config flow."""
    return {
        vol.Optional(CONF_INFRARED_SEND_DP): vol.In(dps),
        vol.Optional(CONF_INFRARED_CONTROL_DP): vol.In(dps),
        vol.Optional(CONF_INFRARED_CODE_TYPE_DP): vol.In(dps),
    }


def _pulses_to_base64(pulses):
    """Encode Tuya's little-endian uint16 pulse representation."""
    normalized = [int(abs(pulse)) for pulse in pulses]
    if any(pulse < 0 or pulse > 65535 for pulse in normalized):
        raise ValueError("Infrared pulse is outside Tuya uint16 range")
    fmt = "<" + str(len(normalized)) + "H"
    return base64.b64encode(struct.pack(fmt, *normalized)).decode("ascii")


def _base64_to_pulses(code):
    raw = base64.b64decode(code, validate=True)
    if len(raw) % 2:
        raise ValueError("Invalid Tuya infrared code length")
    fmt = "<" + str(len(raw) // 2) + "H"
    return list(struct.unpack(fmt, raw))


class TuyaRawInfraredCommand(InfraredCommand):
    """Infrared command carrying a native uncompressed Tuya base64 code."""

    def __init__(self, code):
        super().__init__(modulation=38000, repeat_count=0)
        self.code = code

    def get_raw_timings(self):
        pulses = _base64_to_pulses(self.code)
        return [pulse if index % 2 == 0 else -pulse for index, pulse in enumerate(pulses)]


class LocaltuyaInfrared(LocalTuyaEntity, InfraredEmitterEntity):
    """Representation of a Tuya infrared emitter."""

    def __init__(self, device, config_entry, infraredid, **kwargs):
        """Initialize the Tuya infrared emitter."""
        super().__init__(device, config_entry, infraredid, _LOGGER, **kwargs)
        self._send_dp = self._config.get(CONF_INFRARED_SEND_DP, self._dp_id)
        self._control_dp = self._config.get(CONF_INFRARED_CONTROL_DP)
        self._type_dp = self._config.get(CONF_INFRARED_CODE_TYPE_DP)
        self._code_type_value = self._config.get(CONF_INFRARED_CODE_TYPE_VALUE, 0)
        self._send_command = self._config.get(CONF_INFRARED_SEND_COMMAND, "send_ir")

    def _package(self, code):
        if self._control_dp is not None:
            settings = {
                self._control_dp: self._send_command,
                self._send_dp: code,
            }
            if self._type_dp is not None:
                settings[self._type_dp] = self._code_type_value
            return settings
        return {
            self._send_dp: json.dumps(
                {
                    "control": self._send_command,
                    "type": self._code_type_value,
                    "head": "",
                    "key1": "1" + code,
                },
                separators=(",", ":"),
            )
        }

    async def _async_send_raw_code(self, code):
        settings = self._package(code)
        if len(settings) == 1:
            dp_id, raw = next(iter(settings.items()))
            await self._device.set_dp(raw, dp_id)
        else:
            await self._device.set_dps(settings)

    async def async_send_command(self, command):
        """Convert an HA infrared command and transmit it using Tuya encoding."""
        if isinstance(command, TuyaRawInfraredCommand):
            await self._async_send_raw_code(command.code)
            return

        timings = command.get_raw_timings()
        split = {}
        raw = []
        for index, timing in enumerate(timings):
            duration = abs(int(timing))
            if duration > 50000:
                split[index] = duration - 5000
                raw.append(5000)
            else:
                raw.append(duration)

        if len(raw) % 2 == 1:
            raw.append(5000)

        start = 0
        for index, pause in split.items():
            if index > start:
                await self._async_send_raw_code(_pulses_to_base64(raw[start:index]))
            start = index
            await asyncio.sleep(pause / 1_000_000.0)
        if start < len(raw):
            await self._async_send_raw_code(_pulses_to_base64(raw[start:]))


async_setup_entry = partial(async_setup_entry, DOMAIN, LocaltuyaInfrared, flow_schema)
