"""Acceptance tests for QR bulk onboarding."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from homeassistant.const import CONF_DEVICE_ID, CONF_DEVICES, CONF_ENTITIES, CONF_FRIENDLY_NAME

from custom_components.localtuya import qr_onboarding
from custom_components.localtuya.qr_onboarding import QrProvisioningError


class _FakeBulkFlow(qr_onboarding.QrOptionsFlowMixin):
    """Minimal flow harness for bulk onboarding orchestration."""

    def __init__(self):
        self.hass = SimpleNamespace()
        self.config_entry = SimpleNamespace(
            data={CONF_DEVICES: {}},
        )
        self._qr_devices = {}
        self._qr_cloud = object()
        self.saved = []

    def async_show_form(self, **kwargs):
        return {"type": "form", **kwargs}

    def async_show_menu(self, **kwargs):
        return {"type": "menu", **kwargs}

    def async_abort(self, **kwargs):
        return {"type": "abort", **kwargs}

    def async_create_entry(self, **kwargs):
        self.saved.append(kwargs)
        return {"type": "create_entry", **kwargs}


class BulkOnboardingTests(unittest.IsolatedAsyncioTestCase):
    """Verify sequential, isolated QR bulk provisioning semantics."""

    async def test_bulk_processes_selected_devices_sequentially(self):
        flow = _FakeBulkFlow()
        flow._qr_devices = {
            "a": {"id": "a", "name": "A"},
            "b": {"id": "b", "name": "B"},
        }

        prepared = [
            ({CONF_DEVICE_ID: "a", CONF_FRIENDLY_NAME: "A", CONF_ENTITIES: []}, []),
            ({CONF_DEVICE_ID: "b", CONF_FRIENDLY_NAME: "B", CONF_ENTITIES: []}, []),
        ]

        with patch.object(
            qr_onboarding,
            "async_prepare_qr_device",
            new=AsyncMock(side_effect=prepared),
        ) as prepare:
            result = await flow._async_bulk_prepare_devices(["a", "b"])

        self.assertEqual([item["device_id"] for item in result["successes"]], ["a", "b"])
        self.assertEqual(result["failures"], [])
        self.assertEqual(prepare.await_count, 2)
        self.assertEqual(
            [call.args[2]["id"] for call in prepare.await_args_list],
            ["a", "b"],
        )

    async def test_one_failure_does_not_abort_remaining_devices(self):
        flow = _FakeBulkFlow()
        flow._qr_devices = {
            "a": {"id": "a", "name": "A"},
            "b": {"id": "b", "name": "B"},
            "c": {"id": "c", "name": "C"},
        }

        with patch.object(
            qr_onboarding,
            "async_prepare_qr_device",
            new=AsyncMock(
                side_effect=[
                    ({CONF_DEVICE_ID: "a", CONF_FRIENDLY_NAME: "A", CONF_ENTITIES: []}, []),
                    QrProvisioningError("cannot_connect"),
                    ({CONF_DEVICE_ID: "c", CONF_FRIENDLY_NAME: "C", CONF_ENTITIES: []}, []),
                ]
            ),
        ):
            result = await flow._async_bulk_prepare_devices(["a", "b", "c"])

        self.assertEqual([item["device_id"] for item in result["successes"]], ["a", "c"])
        self.assertEqual(result["failures"], [{"device_id": "b", "reason": "cannot_connect"}])

    async def test_bulk_does_not_offer_already_configured_devices(self):
        flow = _FakeBulkFlow()
        flow.config_entry = SimpleNamespace(
            data={CONF_DEVICES: {"a": {CONF_FRIENDLY_NAME: "Already"}}},
        )
        flow._qr_devices = {
            "a": {"id": "a", "name": "Already"},
            "b": {"id": "b", "name": "New"},
        }

        eligible = flow._bulk_eligible_devices()
        self.assertEqual(list(eligible), ["b"])


if __name__ == "__main__":
    unittest.main()
