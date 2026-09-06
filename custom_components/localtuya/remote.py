"""Platform for catalog-driven Tuya IR/RF remote control devices."""

import asyncio
import json
import logging
from functools import partial
from itertools import product

import voluptuous as vol
from homeassistant.components.remote import (
    ATTR_ALTERNATIVE,
    ATTR_COMMAND_TYPE,
    ATTR_DELAY_SECS,
    ATTR_DEVICE,
    ATTR_NUM_REPEATS,
    DEFAULT_DELAY_SECS,
    DOMAIN,
    RemoteEntity,
    RemoteEntityFeature,
)
from homeassistant.const import ATTR_COMMAND, CONF_DEVICE_ID
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.storage import Store

from .common import LocalTuyaEntity, async_setup_entry
from .const import (
    CONF_REMOTE_CODE_TYPE_DP,
    CONF_REMOTE_CODE_TYPE_VALUE,
    CONF_REMOTE_CONTROL_DP,
    CONF_REMOTE_DELAY_DP,
    CONF_REMOTE_LEARN_COMMAND,
    CONF_REMOTE_LEARN_EXIT_COMMAND,
    CONF_REMOTE_RECEIVE_DP,
    CONF_REMOTE_RF_LEARN_COMMAND,
    CONF_REMOTE_RF_LEARN_EXIT_COMMAND,
    CONF_REMOTE_RF_SEND_COMMAND,
    CONF_REMOTE_SEND_COMMAND,
    CONF_REMOTE_SEND_DP,
)

_LOGGER = logging.getLogger(__name__)

_STORAGE_VERSION = 1
_LEARNING_TIMEOUT = 30.0


def flow_schema(dps):
    """Return schema used in config flow."""
    return {
        vol.Optional(CONF_REMOTE_SEND_DP): vol.In(dps),
        vol.Optional(CONF_REMOTE_RECEIVE_DP): vol.In(dps),
        vol.Optional(CONF_REMOTE_CONTROL_DP): vol.In(dps),
        vol.Optional(CONF_REMOTE_DELAY_DP): vol.In(dps),
        vol.Optional(CONF_REMOTE_CODE_TYPE_DP): vol.In(dps),
    }


def _ensure_commands(command):
    if isinstance(command, str):
        return [command]
    return [str(item) for item in command]


class LocaltuyaRemote(LocalTuyaEntity, RemoteEntity):
    """Representation of a Tuya IR/RF remote."""

    def __init__(self, device, config_entry, remoteid, **kwargs):
        """Initialize the Tuya remote."""
        super().__init__(device, config_entry, remoteid, _LOGGER, **kwargs)
        self._send_dp = self._config.get(CONF_REMOTE_SEND_DP, self._dp_id)
        self._receive_dp = self._config.get(CONF_REMOTE_RECEIVE_DP)
        self._control_dp = self._config.get(CONF_REMOTE_CONTROL_DP)
        self._delay_dp = self._config.get(CONF_REMOTE_DELAY_DP)
        self._type_dp = self._config.get(CONF_REMOTE_CODE_TYPE_DP)
        self._code_type_value = self._config.get(CONF_REMOTE_CODE_TYPE_VALUE, 0)
        self._send_command = self._config.get(CONF_REMOTE_SEND_COMMAND, "send_ir")
        self._rf_send_command = self._config.get(
            CONF_REMOTE_RF_SEND_COMMAND, "rfstudy_send"
        )
        self._learn_command = self._config.get(CONF_REMOTE_LEARN_COMMAND, "study")
        self._learn_exit_command = self._config.get(
            CONF_REMOTE_LEARN_EXIT_COMMAND, "study_exit"
        )
        self._rf_learn_command = self._config.get(
            CONF_REMOTE_RF_LEARN_COMMAND, "rf_study"
        )
        self._rf_learn_exit_command = self._config.get(
            CONF_REMOTE_RF_LEARN_EXIT_COMMAND, "rfstudy_exit"
        )
        self._storage = Store(
            device._hass,
            _STORAGE_VERSION,
            f"localtuya.remote.{self.unique_id}",
        )
        self._storage_loaded = False
        self._codes = {}
        self._flags = {}
        self._learn_lock = asyncio.Lock()
        self._attr_is_on = True

        features = RemoteEntityFeature(0)
        if self._receive_dp is not None:
            features |= RemoteEntityFeature.LEARN_COMMAND | RemoteEntityFeature.DELETE_COMMAND
        self._attr_supported_features = features

    async def _async_load_storage(self):
        if self._storage_loaded:
            return
        stored = await self._storage.async_load()
        if isinstance(stored, dict):
            codes = stored.get("codes")
            flags = stored.get("flags")
            if isinstance(codes, dict):
                self._codes = codes
            if isinstance(flags, dict):
                self._flags = flags
        self._storage_loaded = True

    async def _async_save_storage(self):
        await self._storage.async_save({"codes": self._codes, "flags": self._flags})

    def _extract_codes(self, commands, subdevice=None):
        result = []
        for command in commands:
            if command.startswith("b64:"):
                codes = [command[4:]]
            elif command.startswith("rf:"):
                codes = [command]
            else:
                if not subdevice:
                    raise ValueError("device must be specified for a learned command")
                try:
                    stored = self._codes[subdevice][command]
                except KeyError as err:
                    raise ValueError(
                        f"Command {command!r} not found for {subdevice}"
                    ) from err
                codes = list(stored) if isinstance(stored, list) else [stored]
            result.append(codes)
        return result

    def _encode_send_code(self, code, delay_ms, *, is_rf=False):
        """Build exact Tuya DPS writes for an IR or RF code."""
        if self._control_dp is not None:
            settings = {
                self._control_dp: self._send_command,
                self._send_dp: code,
            }
            if self._delay_dp is not None:
                settings[self._delay_dp] = int(delay_ms)
            if self._type_dp is not None:
                settings[self._type_dp] = self._code_type_value
            return settings

        if is_rf:
            payload = {
                "control": self._rf_send_command,
                "rf_type": "sub_2g",
                "mode": 0,
                "key1": {
                    "times": 6,
                    "intervals": 0,
                    "ver": "2",
                    "delay": 0,
                    "code": code,
                },
                "feq": 0,
                "rate": 0,
                "ver": "2",
            }
        else:
            payload = {
                "control": self._send_command,
                "head": "",
                "key1": "1" + code,
                "type": self._code_type_value,
                "delay": int(delay_ms),
            }
        return {self._send_dp: json.dumps(payload, separators=(",", ":"))}

    async def async_send_command(self, command, **kwargs):
        """Send raw or previously learned remote commands."""
        await self._async_load_storage()
        commands = _ensure_commands(command)
        subdevice = kwargs.get(ATTR_DEVICE)
        repeat = max(1, int(kwargs.get(ATTR_NUM_REPEATS, 1) or 1))
        delay = max(0.0, float(kwargs.get(ATTR_DELAY_SECS, DEFAULT_DELAY_SECS)))
        code_list = self._extract_codes(commands, subdevice)

        sent = False
        for _, codes in product(range(repeat), code_list):
            if sent and delay:
                await asyncio.sleep(delay)

            flag_key = subdevice or "__raw__"
            index = int(self._flags.get(flag_key, 0)) % len(codes)
            code = str(codes[index])
            is_rf = code.startswith("rf:")
            if is_rf:
                code = code[3:]
            settings = self._encode_send_code(code, delay * 1000, is_rf=is_rf)
            if len(settings) == 1:
                dp_id, raw = next(iter(settings.items()))
                await self._device.set_dp(raw, dp_id)
            else:
                await self._device.set_dps(settings)

            if len(codes) > 1:
                self._flags[flag_key] = (index + 1) % len(codes)
            sent = True

        if sent:
            await self._async_save_storage()

    async def _async_wait_for_received_code(self):
        """Wait for the next raw receive-DP push, including repeated values."""
        if self._receive_dp is None:
            raise NotImplementedError()

        loop = asyncio.get_running_loop()
        future = loop.create_future()
        signal = f"localtuya_raw_{self._dev_config_entry[CONF_DEVICE_ID]}"

        @callback
        def _handle(received):
            if not isinstance(received, dict) or future.done():
                return
            key = str(self._receive_dp)
            if key in received:
                raw = received[key]
            elif self._receive_dp in received:
                raw = received[self._receive_dp]
            else:
                return
            if raw is not None:
                future.set_result(str(raw))

        unsubscribe = async_dispatcher_connect(self.hass, signal, _handle)
        try:
            return await asyncio.wait_for(future, timeout=_LEARNING_TIMEOUT)
        finally:
            unsubscribe()

    async def _async_set_learning(self, enabled, *, is_rf=False):
        if self._control_dp is not None:
            value = self._learn_command if enabled else self._learn_exit_command
            await self._device.set_dp(value, self._control_dp)
            return

        if is_rf:
            control = self._rf_learn_command if enabled else self._rf_learn_exit_command
            payload = {
                "control": control,
                "rf_type": "sub_2g",
                "study_feq": "0",
                "ver": "2",
            }
        else:
            control = self._learn_command if enabled else self._learn_exit_command
            payload = {"control": control}
        await self._device.set_dp(
            json.dumps(payload, separators=(",", ":")),
            self._send_dp,
        )

    async def _async_learn_one(self, *, is_rf=False):
        wait_task = asyncio.create_task(self._async_wait_for_received_code())
        try:
            await self._async_set_learning(True, is_rf=is_rf)
            code = await wait_task
            return f"rf:{code}" if is_rf else code
        finally:
            if not wait_task.done():
                wait_task.cancel()
            await self._async_set_learning(False, is_rf=is_rf)

    async def async_learn_command(self, **kwargs):
        """Learn one or more IR/RF commands and persist them in HA storage."""
        if self._receive_dp is None:
            raise NotImplementedError()
        await self._async_load_storage()
        commands = _ensure_commands(kwargs.get(ATTR_COMMAND, []))
        subdevice = kwargs.get(ATTR_DEVICE)
        if not subdevice:
            raise ValueError("device is required when learning commands")
        alternative = bool(kwargs.get(ATTR_ALTERNATIVE, False))
        is_rf = kwargs.get(ATTR_COMMAND_TYPE) == "rf"

        async with self._learn_lock:
            for command in commands:
                first = await self._async_learn_one(is_rf=is_rf)
                stored = [first, await self._async_learn_one(is_rf=is_rf)] if alternative else first
                self._codes.setdefault(subdevice, {})[command] = stored
            await self._async_save_storage()

    async def async_delete_command(self, **kwargs):
        """Delete stored learned commands."""
        await self._async_load_storage()
        commands = _ensure_commands(kwargs.get(ATTR_COMMAND, []))
        subdevice = kwargs.get(ATTR_DEVICE)
        if not subdevice or subdevice not in self._codes:
            raise ValueError(f"Device not found: {subdevice!r}")

        missing = []
        for command in commands:
            if command in self._codes[subdevice]:
                del self._codes[subdevice][command]
            else:
                missing.append(command)
        if not self._codes[subdevice]:
            del self._codes[subdevice]
            self._flags.pop(subdevice, None)
        await self._async_save_storage()
        if missing and len(missing) == len(commands):
            raise ValueError(f"Commands not found: {missing!r}")


async_setup_entry = partial(async_setup_entry, DOMAIN, LocaltuyaRemote, flow_schema)
