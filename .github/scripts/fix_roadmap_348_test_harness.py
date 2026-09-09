from pathlib import Path


def replace_once(path: str, old: str, new: str, label: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected 1 match, found {count}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


# The heartbeat implementation intentionally detaches the closed transport from
# the parent. Keep a reference in the test before exercising the failure path.
replace_once(
    "tests/test_gateway_shared_transport.py",
    '''        self.parent.heartbeat = AsyncMock(side_effect=TimeoutError())\n\n        await first._shared._heartbeat_loop()\n\n        self.assertFalse(first._shared.alive)\n        self.assertEqual(first_listener.disconnects, 1)\n        self.assertEqual(second_listener.disconnects, 1)\n        self.parent.transport.close.assert_called_once()\n''',
    '''        self.parent.heartbeat = AsyncMock(side_effect=TimeoutError())\n        physical_transport = self.parent.transport\n\n        await first._shared._heartbeat_loop()\n\n        self.assertFalse(first._shared.alive)\n        self.assertEqual(first_listener.disconnects, 1)\n        self.assertEqual(second_listener.disconnects, 1)\n        self.assertIsNone(self.parent.transport)\n        physical_transport.close.assert_called_once()\n''',
    "gateway heartbeat assertion",
)

# Runtime health tests use a deliberately tiny fake Home Assistant object. Mock
# the HA issue-registry side effect while keeping the production synchronization
# enabled and separately tested in test_repair_issues.py.
replace_once(
    "tests/test_health_runtime.py",
    '''        self.hass = SimpleNamespace(\n            data={\n                DOMAIN: {\n                    TUYA_DEVICES: {\n                        self.device_id: SimpleNamespace(\n                            connected=True,\n                        )\n                    }\n                }\n            }\n        )\n''',
    '''        self.hass = SimpleNamespace(\n            data={\n                DOMAIN: {\n                    TUYA_DEVICES: {\n                        self.device_id: SimpleNamespace(\n                            connected=True,\n                        )\n                    }\n                }\n            }\n        )\n        self.issue_sync_patcher = patch(\n            "custom_components.localtuya.health_runtime.async_sync_device_health_issue"\n        )\n        self.issue_sync = self.issue_sync_patcher.start()\n        self.addCleanup(self.issue_sync_patcher.stop)\n''',
    "health runtime issue registry mock",
)
replace_once(
    "tests/test_health_runtime.py",
    '''        self.assertIsNone(result["preflight"])\n        self.assertEqual(result["probe_error_type"], "RuntimeError")\n        self.assertNotIn(private_message, repr(result))\n''',
    '''        self.assertFalse(result["preflight"]["ok"])\n        self.assertEqual(result["preflight"]["failure"], "probe_error")\n        self.assertEqual(result["preflight"]["recommended_action"], "retry")\n        self.assertEqual(result["probe_error_type"], "RuntimeError")\n        self.assertNotIn(private_message, repr(result))\n''',
    "health runtime exception expectation",
)
replace_once(
    "tests/test_health_runtime.py",
    '''        self.assertIsNone(result["preflight"])\n        self.assertEqual(result["probe_error_type"], "TimeoutError")\n''',
    '''        self.assertFalse(result["preflight"]["ok"])\n        self.assertEqual(result["preflight"]["failure"], "probe_error")\n        self.assertEqual(result["preflight"]["recommended_action"], "retry")\n        self.assertEqual(result["probe_error_type"], "TimeoutError")\n''',
    "health runtime timeout expectation",
)

# Host-repair tests also use a fake hass. Only mock clearing of the new health
# issues; host-recovery issue clearing remains visible to the assertions.
replace_once(
    "tests/test_repairs.py",
    '''        self.hass = SimpleNamespace(\n            config_entries=FakeConfigEntries([self.entry]),\n            data={DOMAIN: {}},\n        )\n''',
    '''        self.hass = SimpleNamespace(\n            config_entries=FakeConfigEntries([self.entry]),\n            data={DOMAIN: {}},\n        )\n        self.health_clear_patcher = patch(\n            "custom_components.localtuya.repairs.async_clear_device_health_issues"\n        )\n        self.health_clear = self.health_clear_patcher.start()\n        self.addCleanup(self.health_clear_patcher.stop)\n''',
    "repair fake issue registry mock",
)

# These diagnostics tests cover redaction/mapping, not live health. Stubbing the
# health snapshot avoids a real 10-second LAN probe and the HA issue registry on
# their SimpleNamespace hass while preserving production behavior elsewhere.
replace_once(
    "tests/test_mapping_diagnostics.py",
    '''class DeviceDiagnosticsIntegrationTests(\n    unittest.IsolatedAsyncioTestCase\n):\n    """Test complete Home Assistant device diagnostics."""\n\n''',
    '''class DeviceDiagnosticsIntegrationTests(\n    unittest.IsolatedAsyncioTestCase\n):\n    """Test complete Home Assistant device diagnostics."""\n\n    def setUp(self):\n        from unittest.mock import AsyncMock, patch\n\n        self.health_patcher = patch(\n            "custom_components.localtuya.diagnostics.async_build_device_health_snapshot",\n            new=AsyncMock(\n                return_value={\n                    "runtime_present": False,\n                    "runtime_connected": None,\n                    "preflight": {\n                        "ok": False,\n                        "failure": "probe_error",\n                        "recommended_action": "retry",\n                    },\n                }\n            ),\n        )\n        self.health_patcher.start()\n        self.addCleanup(self.health_patcher.stop)\n\n''',
    "mapping diagnostics health stub",
)

print("Final roadmap test harness fixes applied")
