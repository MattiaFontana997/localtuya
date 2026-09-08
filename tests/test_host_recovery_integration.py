"""Integration-level tests for validated runtime host recovery."""

from __future__ import annotations

import asyncio
import copy
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import custom_components.localtuya as integration

from homeassistant.const import CONF_DEVICES, CONF_HOST

from custom_components.localtuya.config_flow import CannotConnect
from custom_components.localtuya.const import (
    CONF_ENABLE_DEBUG,
    CONF_LOCAL_KEY,
    CONF_PRODUCT_KEY,
    CONF_PROTOCOL_VERSION,
    DATA_DISCOVERY,
    DOMAIN,
    TUYA_DEVICES,
)


class FakeConfigEntries:
    """Minimal config entries manager for global setup tests."""

    def __init__(self, entries):
        self.entries = list(entries)
        self.updated = []

    def async_entries(self, domain=None):
        return list(self.entries)

    def async_update_entry(self, entry, *, data, **kwargs):
        self.updated.append(copy.deepcopy(data))
        entry.data = data

    async def async_reload(self, entry_id):
        return True


class FakeRuntimeDevice:
    """Small runtime device used to observe reconnect calls."""

    def __init__(self):
        self.connected = False
        self.connect_calls = 0

    def async_connect(self):
        self.connect_calls += 1


class FakeDiscovery:
    """Capture the discovery callback installed by LocalTuya."""

    instance = None

    def __init__(self, callback=None, *, hass=None):
        self.callback = callback
        self.hass = hass
        self.devices = {}
        self.request_calls = 0
        self.closed = False
        self.__class__.instance = self

    async def start(self):
        return None

    async def async_request_discovery(self):
        self.request_calls += 1
        return True

    def close(self):
        self.closed = True


class HostRecoveryRuntimeTests(unittest.IsolatedAsyncioTestCase):
    """Verify discovery never blindly persists a changed IP address."""

    async def asyncSetUp(self):
        FakeDiscovery.instance = None
        self.entry = SimpleNamespace(
            data={
                CONF_DEVICES: {
                    "device-1": {
                        CONF_HOST: "192.168.1.20",
                        CONF_LOCAL_KEY: "private-key",
                        CONF_PROTOCOL_VERSION: "3.5",
                        CONF_ENABLE_DEBUG: False,
                        CONF_PRODUCT_KEY: "old-product",
                    }
                }
            }
        )
        self.manager = FakeConfigEntries([self.entry])
        self.runtime_device = FakeRuntimeDevice()
        self.tasks = []
        self.intervals = []

        def create_task(coro):
            task = asyncio.create_task(coro)
            self.tasks.append(task)
            return task

        def track_interval(hass, callback, interval):
            self.intervals.append(callback)
            return lambda: None

        self.hass = SimpleNamespace(
            data={
                DOMAIN: {
                    TUYA_DEVICES: {
                        "device-1": self.runtime_device,
                    }
                }
            },
            config_entries=self.manager,
            async_create_task=create_task,
            services=SimpleNamespace(async_register=lambda *args, **kwargs: None),
            bus=SimpleNamespace(async_listen_once=lambda *args, **kwargs: None),
        )

        self.catalog = SimpleNamespace(
            async_load_builtin_catalog=AsyncMock(),
            async_load_cache=AsyncMock(),
            async_refresh=AsyncMock(return_value=True),
            mapping_count=0,
            cache_loaded=True,
        )

        self.patches = (
            patch.object(
                integration,
                "DeviceCatalog",
                return_value=self.catalog,
            ),
            patch.object(
                integration,
                "TuyaDiscovery",
                FakeDiscovery,
            ),
            patch.object(
                integration,
                "async_track_time_interval",
                side_effect=track_interval,
            ),
            patch.object(
                integration,
                "async_register_admin_service",
            ),
        )

        for item in self.patches:
            item.start()

        await integration.async_setup(self.hass, {})
        await asyncio.sleep(0)

    async def asyncTearDown(self):
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)
        for item in reversed(self.patches):
            item.stop()

    async def _drain_new_tasks(self):
        await asyncio.sleep(0)
        pending = [task for task in self.tasks if not task.done()]
        if pending:
            await asyncio.gather(*pending)

    async def test_changed_ip_is_persisted_only_after_lan_validation(self):
        validator = AsyncMock(return_value=(["1 (value: True)"], "3.5"))

        with patch.object(integration, "validate_input", validator):
            FakeDiscovery.instance.callback(
                {
                    "gwId": "device-1",
                    "ip": "192.168.1.44",
                    "productKey": "new-product",
                }
            )
            await self._drain_new_tasks()

        self.assertEqual(
            self.entry.data[CONF_DEVICES]["device-1"][CONF_HOST],
            "192.168.1.44",
        )
        self.assertEqual(
            self.entry.data[CONF_DEVICES]["device-1"][CONF_PRODUCT_KEY],
            "new-product",
        )
        self.assertEqual(len(self.manager.updated), 1)
        validator.assert_awaited_once()
        probe_data = validator.await_args.args[1]
        self.assertEqual(probe_data[CONF_HOST], "192.168.1.44")
        self.assertEqual(probe_data[CONF_LOCAL_KEY], "private-key")
        self.assertEqual(self.runtime_device.connect_calls, 0)

    async def test_rejected_candidate_never_overwrites_configured_host(self):
        validator = AsyncMock(side_effect=CannotConnect())

        with patch.object(integration, "validate_input", validator):
            FakeDiscovery.instance.callback(
                {
                    "gwId": "device-1",
                    "ip": "192.168.1.77",
                }
            )
            await self._drain_new_tasks()

        self.assertEqual(
            self.entry.data[CONF_DEVICES]["device-1"][CONF_HOST],
            "192.168.1.20",
        )
        self.assertEqual(self.manager.updated, [])
        self.assertEqual(self.runtime_device.connect_calls, 0)

    async def test_same_address_reconnects_without_validation(self):
        validator = AsyncMock()

        with patch.object(integration, "validate_input", validator):
            FakeDiscovery.instance.callback(
                {
                    "gwId": "device-1",
                    "ip": "192.168.1.20",
                    "productKey": "old-product",
                }
            )
            await self._drain_new_tasks()

        validator.assert_not_awaited()
        self.assertEqual(self.runtime_device.connect_calls, 1)
        self.assertEqual(self.manager.updated, [])

    async def test_periodic_reconnect_requests_active_discovery_first(self):
        self.assertEqual(len(self.intervals), 2)

        with patch.object(
            integration.asyncio,
            "sleep",
            new=AsyncMock(),
        ):
            await self.intervals[1](None)

        self.assertEqual(FakeDiscovery.instance.request_calls, 1)
        self.assertEqual(self.runtime_device.connect_calls, 1)


if __name__ == "__main__":
    unittest.main()
