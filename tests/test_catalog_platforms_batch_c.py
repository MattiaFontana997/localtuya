"""Regression tests for catalog-driven Batch C platform runtimes."""

import base64
from datetime import datetime, timezone
import json
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock

from homeassistant.components.lawn_mower.const import (
    SERVICE_DOCK,
    SERVICE_START_MOWING,
    LawnMowerActivity,
)

from custom_components.localtuya.camera import LocaltuyaCamera
from custom_components.localtuya.common import TuyaDevice
from custom_components.localtuya.const import (
    CONF_CAMERA_MOTION_DP,
    CONF_CAMERA_MOTION_OFF,
    CONF_CAMERA_MOTION_ON,
    CONF_CAMERA_SNAPSHOT_DP,
    CONF_CAMERA_SNAPSHOT_ENCODING,
    CONF_CAMERA_SWITCH_DP,
    CONF_CAMERA_SWITCH_OFF,
    CONF_CAMERA_SWITCH_ON,
    CONF_DATETIME_DAY_DP,
    CONF_DATETIME_HOUR_DP,
    CONF_DATETIME_MINUTE_DP,
    CONF_DATETIME_MONTH_DP,
    CONF_DATETIME_SECOND_DP,
    CONF_DATETIME_TIMESTAMP_SCALING,
    CONF_DATETIME_YEAR_DP,
    CONF_EVENT_DP,
    CONF_EVENT_TYPES,
    CONF_INFRARED_SEND_DP,
    CONF_LAWN_MOWER_ACTIVITY_DP,
    CONF_LAWN_MOWER_ACTIVITY_VALUES,
    CONF_LAWN_MOWER_COMMAND_DP,
    CONF_LAWN_MOWER_COMMAND_VALUES,
    CONF_REMOTE_SEND_DP,
    PLATFORMS,
)
from custom_components.localtuya.datetime import LocaltuyaDateTime
from custom_components.localtuya.device_catalog import validate_catalog
from custom_components.localtuya.event import LocaltuyaEvent
from custom_components.localtuya.infrared import LocaltuyaInfrared, _pulses_to_base64
from custom_components.localtuya.lawn_mower import LocaltuyaLawnMower
from custom_components.localtuya.remote import LocaltuyaRemote


class _Device:
    def __init__(self):
        self.set_dp = AsyncMock()
        self.set_dps = AsyncMock()
        self.is_connecting = False


def _entity(cls, config, state):
    entity = object.__new__(cls)
    entity._config = config
    entity._dp_id = config["id"]
    entity._device = _Device()
    entity.has_config = lambda key: key in config and config[key] is not None
    entity.dps = lambda dp: state.get(dp)
    entity.warning = lambda *args, **kwargs: None
    return entity


class BatchCPlatformRuntimeTests(unittest.IsolatedAsyncioTestCase):
    def test_unsolicited_listener_preserves_exact_raw_delta(self):
        """The dispatcher wrapper must expose only the pushed DPS payload."""
        device = object.__new__(TuyaDevice)
        original_listener = Mock()
        dispatcher = SimpleNamespace(listener=original_listener)
        interface = SimpleNamespace(
            dispatcher=dispatcher,
            _decode_payload=Mock(return_value={"dps": {"1": "click"}}),
        )
        device._interface = interface
        device.debug = Mock()
        device._dispatch_raw_status = Mock()

        device._install_raw_status_listener()
        message = SimpleNamespace(payload=b"raw")
        dispatcher.listener(message)

        original_listener.assert_called_once_with(message)
        device._dispatch_raw_status.assert_called_once_with({"1": "click"})

    def test_event_repeated_raw_values_trigger_repeated_events(self):
        config = {
            "id": 1,
            "friendly_name": "Button event",
            CONF_EVENT_DP: 1,
            CONF_EVENT_TYPES: {"single": "click"},
        }
        event = _entity(LocaltuyaEvent, config, {1: "click"})
        event._event_dp = 1
        event._event_values = {"single": "click"}
        event._trigger_event = Mock()
        event.async_write_ha_state = Mock()
        event._state = None
        event._last_state = None
        event._status = {}
        event._extra_state_attribute_dps = {}
        event.debug = lambda *args, **kwargs: None

        event._handle_raw_status({"1": "click"})
        event._handle_raw_status({"1": "click"})
        self.assertEqual(event._trigger_event.call_count, 2)
        self.assertEqual(event._trigger_event.call_args.args[0], "single")

    async def test_camera_decodes_snapshot_and_exact_controls(self):
        encoded = base64.b64encode(b"jpeg-bytes").decode()
        config = {
            "id": 5,
            CONF_CAMERA_SNAPSHOT_DP: 5,
            CONF_CAMERA_SNAPSHOT_ENCODING: "base64",
            CONF_CAMERA_SWITCH_DP: 1,
            CONF_CAMERA_SWITCH_ON: "ON",
            CONF_CAMERA_SWITCH_OFF: "OFF",
            CONF_CAMERA_MOTION_DP: 2,
            CONF_CAMERA_MOTION_ON: "enabled",
            CONF_CAMERA_MOTION_OFF: "disabled",
        }
        camera = _entity(LocaltuyaCamera, config, {1: "ON", 2: "disabled", 5: encoded})
        camera._snapshot_encoding = "base64"
        camera._switch_on = "ON"
        camera._switch_off = "OFF"
        camera._motion_on = "enabled"
        camera._motion_off = "disabled"
        self.assertEqual(await camera.async_camera_image(), b"jpeg-bytes")
        self.assertTrue(camera.is_on)
        self.assertFalse(camera.motion_detection_enabled)
        await camera.async_disable_motion_detection()
        camera._device.set_dp.assert_awaited_once_with("disabled", 2)

    async def test_datetime_timestamp_and_split_component_writes(self):
        timestamp = _entity(
            LocaltuyaDateTime,
            {"id": 1, CONF_DATETIME_TIMESTAMP_SCALING: 0.001},
            {1: 1_700_000_000_000},
        )
        timestamp._timestamp_scaling = 0.001
        timestamp._timezone_mode = "utc"
        self.assertEqual(
            timestamp.native_value,
            datetime.fromtimestamp(1_700_000_000, timezone.utc),
        )
        await timestamp.async_set_value(datetime.fromtimestamp(1_700_000_100, timezone.utc))
        timestamp._device.set_dp.assert_awaited_once_with(1_700_000_100_000, 1)

        config = {
            "id": 2,
            CONF_DATETIME_YEAR_DP: 2,
            CONF_DATETIME_MONTH_DP: 3,
            CONF_DATETIME_DAY_DP: 4,
            CONF_DATETIME_HOUR_DP: 5,
            CONF_DATETIME_MINUTE_DP: 6,
            CONF_DATETIME_SECOND_DP: 7,
        }
        split = _entity(LocaltuyaDateTime, config, {2: 2026, 3: 9, 4: 5, 5: 20, 6: 30, 7: 15})
        split._timestamp_scaling = 1.0
        split._timezone_mode = "utc"
        self.assertEqual(split.native_value, datetime(2026, 9, 5, 20, 30, 15, tzinfo=timezone.utc))
        await split.async_set_value(datetime(2027, 1, 2, 3, 4, 5, tzinfo=timezone.utc))
        split._device.set_dps.assert_awaited_once_with({2: 2027, 3: 1, 4: 2, 5: 3, 6: 4, 7: 5})

    async def test_lawn_mower_maps_activity_and_commands(self):
        config = {
            "id": 8,
            CONF_LAWN_MOWER_ACTIVITY_DP: 8,
            CONF_LAWN_MOWER_ACTIVITY_VALUES: {"mowing": "WORK", "docked": "HOME"},
            CONF_LAWN_MOWER_COMMAND_DP: 9,
            CONF_LAWN_MOWER_COMMAND_VALUES: {SERVICE_START_MOWING: "START", SERVICE_DOCK: "HOME"},
        }
        mower = _entity(LocaltuyaLawnMower, config, {8: "WORK"})
        mower._activity_values = config[CONF_LAWN_MOWER_ACTIVITY_VALUES]
        mower._command_values = config[CONF_LAWN_MOWER_COMMAND_VALUES]
        self.assertEqual(mower.activity, LawnMowerActivity.MOWING)
        await mower.async_dock()
        mower._device.set_dp.assert_awaited_once_with("HOME", 9)

    async def test_remote_raw_command_uses_tuya_single_dp_json(self):
        remote = _entity(LocaltuyaRemote, {"id": 201, CONF_REMOTE_SEND_DP: 201}, {})
        remote._send_dp = 201
        remote._control_dp = None
        remote._delay_dp = None
        remote._type_dp = None
        remote._code_type_value = 0
        remote._send_command = "send_ir"
        remote._rf_send_command = "rfstudy_send"
        remote._storage_loaded = True
        remote._codes = {}
        remote._flags = {}
        remote._async_load_storage = AsyncMock()
        remote._async_save_storage = AsyncMock()
        await remote.async_send_command(["b64:ABC"], num_repeats=1, delay_secs=0)
        raw = remote._device.set_dp.await_args.args[0]
        self.assertEqual(remote._device.set_dp.await_args.args[1], 201)
        self.assertEqual(json.loads(raw)["key1"], "1ABC")

    async def test_infrared_tuya_pulse_encoding_and_send(self):
        code = _pulses_to_base64([9000, 4500, 560, 560])
        self.assertEqual(len(base64.b64decode(code)), 8)
        infrared = _entity(LocaltuyaInfrared, {"id": 201, CONF_INFRARED_SEND_DP: 201}, {})
        infrared._send_dp = 201
        infrared._control_dp = None
        infrared._type_dp = None
        infrared._code_type_value = 0
        infrared._send_command = "send_ir"
        await infrared._async_send_raw_code(code)
        raw = infrared._device.set_dp.await_args.args[0]
        self.assertEqual(json.loads(raw)["key1"], "1" + code)

    def test_catalog_accepts_every_registered_platform(self):
        payload = {
            "schema_version": 2,
            "mappings": [
                {
                    "id": "all-platforms",
                    "match": {
                        "product_ids": ["example-product"],
                        "required_dps": list(range(1, len(PLATFORMS) + 1)),
                        "optional_dps": [],
                    },
                    "entities": [
                        {"platform": platform, "config": {"id": index}}
                        for index, platform in enumerate(PLATFORMS, 1)
                    ],
                }
            ],
        }
        validated = validate_catalog(payload)
        self.assertEqual(len(validated["mappings"]), 1)
        self.assertEqual(
            {entity["platform"] for entity in validated["mappings"][0]["entities"]},
            set(PLATFORMS),
        )


if __name__ == "__main__":
    unittest.main()
