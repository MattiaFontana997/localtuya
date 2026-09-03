"""Tests for LocalTuya integration lifecycle."""

import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import custom_components.localtuya as integration

from homeassistant.const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_DEVICE_ID,
    CONF_DEVICES,
    CONF_ENTITIES,
    CONF_HOST,
    CONF_PLATFORM,
    CONF_REGION,
    CONF_USERNAME,
)

from custom_components.localtuya.config_flow import (
    ENTRIES_VERSION,
)
from custom_components.localtuya.const import (
    ATTR_UPDATED_AT,
    CONF_NO_CLOUD,
    CONF_USER_ID,
    DATA_CLOUD,
    DOMAIN,
    TUYA_DEVICES,
)


class FakeConfigEntries:
    """Minimal Home Assistant config entries manager."""

    def __init__(
        self,
        entries=None,
        *,
        unload_result=True,
    ):
        self.entries = list(
            entries or []
        )
        self.unload_result = (
            unload_result
        )

        self.updated = []
        self.removed = []
        self.forwarded = []
        self.unloaded = []
        self.reloads = []

    def async_entries(
        self,
        domain=None,
    ):
        return list(
            self.entries
        )

    def async_update_entry(
        self,
        entry,
        **kwargs,
    ):
        self.updated.append(
            (entry, kwargs)
        )

        if "data" in kwargs:
            entry.data = kwargs["data"]

        if "version" in kwargs:
            entry.version = (
                kwargs["version"]
            )

        if "title" in kwargs:
            entry.title = (
                kwargs["title"]
            )

    async def async_remove(
        self,
        entry_id,
    ):
        self.removed.append(
            entry_id
        )

    async def async_forward_entry_setups(
        self,
        entry,
        platforms,
    ):
        self.forwarded.append(
            (
                entry.entry_id,
                set(platforms),
            )
        )

    async def async_unload_platforms(
        self,
        entry,
        platforms,
    ):
        self.unloaded.append(
            (
                entry.entry_id,
                set(platforms),
            )
        )

        return self.unload_result

    def async_schedule_reload(
        self,
        entry_id,
    ):
        self.reloads.append(
            entry_id
        )


class FakeEntry:
    """Minimal ConfigEntry replacement."""

    def __init__(
        self,
        entry_id,
        data,
        version=ENTRIES_VERSION,
    ):
        self.entry_id = entry_id
        self.data = data
        self.version = version
        self.title = "Test"

        self.update_listener = None
        self.unload_callbacks = []

    def add_update_listener(
        self,
        listener,
    ):
        self.update_listener = (
            listener
        )

        return lambda: None

    def async_on_unload(
        self,
        callback,
    ):
        self.unload_callbacks.append(
            callback
        )


class FakeTuyaDevice:
    """Simple lifecycle-aware Tuya device."""

    instances = {}

    def __init__(
        self,
        hass,
        entry,
        dev_id,
    ):
        self.hass = hass
        self.entry = entry
        self.dev_id = dev_id

        self.connect_calls = 0
        self.close_calls = 0

        self.__class__.instances[
            dev_id
        ] = self

    def async_connect(self):
        self.connect_calls += 1

    async def close(self):
        self.close_calls += 1


class FakeCloudApi:
    """Cloud API stub used for local-only setup."""

    def __init__(
        self,
        hass,
        region,
        client_id,
        secret,
        user_id,
    ):
        self.device_list = {}


class IntegrationLifecycleTests(
    unittest.IsolatedAsyncioTestCase
):
    """Test LocalTuya config-entry lifecycle."""

    def setUp(self):
        FakeTuyaDevice.instances = {}

    @staticmethod
    def _device_config():
        return {
            "device1": {
                CONF_HOST:
                    "192.168.1.20",
                CONF_ENTITIES: [
                    {
                        CONF_PLATFORM:
                            "switch",
                    },
                    {
                        CONF_PLATFORM:
                            "sensor",
                    },
                ],
            },
            "device2": {
                CONF_HOST:
                    "192.168.1.21",
                CONF_ENTITIES: [
                    {
                        CONF_PLATFORM:
                            "switch",
                    },
                ],
            },
        }

    @classmethod
    def _modern_entry(
        cls,
        entry_id="entry1",
    ):
        return FakeEntry(
            entry_id,
            {
                CONF_REGION: "eu",
                CONF_CLIENT_ID: "",
                CONF_CLIENT_SECRET: "",
                CONF_USER_ID: "",
                CONF_NO_CLOUD: True,
                CONF_DEVICES:
                    cls._device_config(),
            },
        )

    async def test_setup_entry_creates_devices_and_platforms(self):
        """Current entries create devices and forward unique platforms."""
        entry = (
            self._modern_entry()
        )

        manager = FakeConfigEntries(
            [entry]
        )

        tasks = []

        def create_task(coro):
            task = asyncio.create_task(
                coro
            )
            tasks.append(task)
            return task

        hass = SimpleNamespace(
            data={
                DOMAIN: {
                    TUYA_DEVICES: {},
                }
            },
            config_entries=manager,
            async_create_task=create_task,
        )

        with (
            patch.object(
                integration,
                "TuyaDevice",
                FakeTuyaDevice,
            ),
            patch.object(
                integration,
                "TuyaCloudApi",
                FakeCloudApi,
            ),
            patch.object(
                integration.asyncio,
                "sleep",
                new=AsyncMock(),
            ),
        ):
            result = (
                await integration
                .async_setup_entry(
                    hass,
                    entry,
                )
            )

            if tasks:
                await asyncio.gather(
                    *tasks
                )

        self.assertTrue(result)

        self.assertEqual(
            set(
                hass.data[
                    DOMAIN
                ][TUYA_DEVICES]
            ),
            {
                "device1",
                "device2",
            },
        )

        self.assertEqual(
            manager.forwarded,
            [
                (
                    "entry1",
                    {
                        "switch",
                        "sensor",
                    },
                )
            ],
        )

        runtime = hass.data[
            DOMAIN
        ]["entry1"]

        self.assertEqual(
            runtime[
                integration
                .LOADED_PLATFORMS
            ],
            frozenset(
                {
                    "switch",
                    "sensor",
                }
            ),
        )

        self.assertEqual(
            runtime[
                integration
                .LOADED_DEVICES
            ],
            frozenset(
                {
                    "device1",
                    "device2",
                }
            ),
        )

        self.assertEqual(
            FakeTuyaDevice.instances[
                "device1"
            ].connect_calls,
            1,
        )

        self.assertEqual(
            FakeTuyaDevice.instances[
                "device2"
            ].connect_calls,
            1,
        )

        self.assertIn(
            DATA_CLOUD,
            hass.data[DOMAIN],
        )

        self.assertIs(
            entry.update_listener,
            integration.update_listener,
        )

    async def test_old_entry_is_not_setup(self):
        """An entry awaiting migration must not start devices."""
        entry = FakeEntry(
            "old-entry",
            {},
            version=(
                ENTRIES_VERSION - 1
            ),
        )

        hass = SimpleNamespace(
            data={
                DOMAIN: {
                    TUYA_DEVICES: {},
                }
            }
        )

        with patch.object(
            integration,
            "TuyaCloudApi",
        ) as cloud:
            result = (
                await integration
                .async_setup_entry(
                    hass,
                    entry,
                )
            )

        self.assertIsNone(
            result
        )

        cloud.assert_not_called()

    async def test_unload_entry_closes_devices(self):
        """Successful unload removes and closes owned devices."""
        entry = (
            self._modern_entry()
        )

        device1 = FakeTuyaDevice(
            None,
            entry,
            "device1",
        )
        device2 = FakeTuyaDevice(
            None,
            entry,
            "device2",
        )

        manager = FakeConfigEntries(
            [entry]
        )

        hass = SimpleNamespace(
            config_entries=manager,
            data={
                DOMAIN: {
                    TUYA_DEVICES: {
                        "device1":
                            device1,
                        "device2":
                            device2,
                    },
                    entry.entry_id: {
                        integration
                        .LOADED_PLATFORMS:
                            frozenset(
                                {
                                    "switch",
                                    "sensor",
                                }
                            ),
                        integration
                        .LOADED_DEVICES:
                            frozenset(
                                {
                                    "device1",
                                    "device2",
                                }
                            ),
                    },
                }
            },
        )

        result = (
            await integration
            .async_unload_entry(
                hass,
                entry,
            )
        )

        self.assertTrue(result)

        self.assertEqual(
            device1.close_calls,
            1,
        )
        self.assertEqual(
            device2.close_calls,
            1,
        )

        self.assertNotIn(
            entry.entry_id,
            hass.data[DOMAIN],
        )

        self.assertEqual(
            hass.data[
                DOMAIN
            ][TUYA_DEVICES],
            {},
        )

    async def test_failed_unload_keeps_runtime(self):
        """Failed platform unload must not tear down devices."""
        entry = (
            self._modern_entry()
        )

        device = FakeTuyaDevice(
            None,
            entry,
            "device1",
        )

        manager = FakeConfigEntries(
            [entry],
            unload_result=False,
        )

        hass = SimpleNamespace(
            config_entries=manager,
            data={
                DOMAIN: {
                    TUYA_DEVICES: {
                        "device1":
                            device,
                    },
                    entry.entry_id: {
                        integration
                        .LOADED_PLATFORMS:
                            frozenset(
                                {
                                    "switch",
                                }
                            ),
                        integration
                        .LOADED_DEVICES:
                            frozenset(
                                {
                                    "device1",
                                }
                            ),
                    },
                }
            },
        )

        result = (
            await integration
            .async_unload_entry(
                hass,
                entry,
            )
        )

        self.assertFalse(result)

        self.assertEqual(
            device.close_calls,
            0,
        )

        self.assertIn(
            "device1",
            hass.data[
                DOMAIN
            ][TUYA_DEVICES],
        )

        self.assertIn(
            entry.entry_id,
            hass.data[DOMAIN],
        )

    async def test_migrate_first_legacy_entry(self):
        """First v1 entry becomes the modern combined entry."""
        legacy_data = {
            CONF_DEVICE_ID:
                "legacy-device",
            CONF_HOST:
                "192.168.1.40",
            CONF_ENTITIES: [],
        }

        entry = FakeEntry(
            "legacy-1",
            legacy_data,
            version=1,
        )

        manager = FakeConfigEntries(
            [entry]
        )

        hass = SimpleNamespace(
            config_entries=manager
        )

        result = (
            await integration
            .async_migrate_entry(
                hass,
                entry,
            )
        )

        self.assertTrue(result)

        self.assertEqual(
            entry.version,
            ENTRIES_VERSION,
        )

        self.assertEqual(
            entry.title,
            DOMAIN,
        )

        self.assertTrue(
            entry.data[
                CONF_NO_CLOUD
            ]
        )

        self.assertEqual(
            entry.data[
                CONF_USERNAME
            ],
            DOMAIN,
        )

        self.assertIn(
            "legacy-device",
            entry.data[
                CONF_DEVICES
            ],
        )

        self.assertIn(
            ATTR_UPDATED_AT,
            entry.data,
        )

    async def test_migrate_secondary_legacy_entry(self):
        """Later v1 entries are merged into the first entry."""
        main = self._modern_entry(
            "main"
        )

        legacy = FakeEntry(
            "legacy-2",
            {
                CONF_DEVICE_ID:
                    "legacy-device",
                CONF_HOST:
                    "192.168.1.41",
                CONF_ENTITIES: [],
            },
            version=1,
        )

        manager = FakeConfigEntries(
            [
                main,
                legacy,
            ]
        )

        hass = SimpleNamespace(
            config_entries=manager
        )

        result = (
            await integration
            .async_migrate_entry(
                hass,
                legacy,
            )
        )

        self.assertTrue(result)

        self.assertIn(
            "legacy-device",
            main.data[
                CONF_DEVICES
            ],
        )

        self.assertIn(
            "legacy-2",
            manager.removed,
        )

        self.assertIn(
            ATTR_UPDATED_AT,
            main.data,
        )

    async def test_update_listener_schedules_reload(self):
        """Config entry updates schedule one HA reload."""
        entry = (
            self._modern_entry()
        )

        manager = FakeConfigEntries(
            [entry]
        )

        hass = SimpleNamespace(
            config_entries=manager
        )

        await integration.update_listener(
            hass,
            entry,
        )

        self.assertEqual(
            manager.reloads,
            [
                entry.entry_id,
            ],
        )


if __name__ == "__main__":
    unittest.main()
