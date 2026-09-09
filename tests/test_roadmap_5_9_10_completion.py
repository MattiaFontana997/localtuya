"""Final cross-feature gate for LocalTuya 6.7 roadmap items 5, 9 and 10."""

from __future__ import annotations

import asyncio
import json
import unittest
from pathlib import Path
from types import SimpleNamespace

from homeassistant.const import CONF_DEVICES, CONF_ENTITIES

from custom_components.localtuya.device_catalog import DeviceCatalog
from custom_components.localtuya.qr_onboarding import (
    QrConfigFlowMixin,
    QrOptionsFlowMixin,
)
from custom_components.localtuya.zero_config import (
    ZeroConfigDecision,
    evaluate_prepared_zero_config,
)


class _ConfigEntriesRecorder:
    def __init__(self) -> None:
        self.calls = []

    def async_update_entry(self, entry, *, data):
        self.calls.append((entry, data))


class _BulkSummaryFlow(QrOptionsFlowMixin):
    def __init__(self) -> None:
        self.config_entry = SimpleNamespace(data={CONF_DEVICES: {}})
        self.hass = SimpleNamespace(config_entries=_ConfigEntriesRecorder())
        self._qr_bulk_summary = None
        self._qr_bulk_result = {
            "successes": [
                {
                    "device_id": "auto-device",
                    "device_data": {
                        CONF_ENTITIES: [
                            {"id": 1, "platform": "switch"},
                        ]
                    },
                    "candidates": [],
                },
                {
                    "device_id": "review-device",
                    "device_data": {
                        CONF_ENTITIES: [
                            {"id": 2, "platform": "switch"},
                        ]
                    },
                    "candidates": [object()],
                },
            ],
            "failures": [
                {"device_id": "failed-device", "reason": "cannot_connect"},
            ],
        }

    def async_show_form(self, **kwargs):
        return kwargs


class Roadmap5910CompletionTests(unittest.TestCase):
    """Prove the final implementation is wired, fail-closed and publishable."""

    def test_bulk_lives_in_options_flow_only(self):
        required = (
            "_bulk_eligible_devices",
            "_async_bulk_prepare_devices",
            "async_step_qr_bulk_choose_devices",
            "async_step_qr_bulk_summary",
        )
        for name in required:
            self.assertTrue(hasattr(QrOptionsFlowMixin, name), name)
            self.assertFalse(hasattr(QrConfigFlowMixin, name), name)

    def test_prepared_zero_config_is_fail_closed(self):
        auto = evaluate_prepared_zero_config(
            {CONF_ENTITIES: [{"id": 1, "platform": "switch"}]},
            [],
        )
        self.assertEqual(auto.decision, ZeroConfigDecision.AUTO_CONFIGURE)

        review = evaluate_prepared_zero_config(
            {CONF_ENTITIES: [{"id": 1, "platform": "switch"}]},
            [object()],
        )
        self.assertEqual(review.decision, ZeroConfigDecision.REVIEW_REQUIRED)
        self.assertEqual(review.entities, [])

    def test_bulk_summary_persists_auto_only(self):
        flow = _BulkSummaryFlow()
        result = asyncio.run(flow.async_step_qr_bulk_summary())

        self.assertEqual(len(flow.hass.config_entries.calls), 1)
        persisted = flow.hass.config_entries.calls[0][1][CONF_DEVICES]
        self.assertIn("auto-device", persisted)
        self.assertNotIn("review-device", persisted)
        self.assertNotIn("failed-device", persisted)

        placeholders = result["description_placeholders"]
        self.assertEqual(placeholders["added_count"], "1")
        self.assertEqual(placeholders["review_count"], "1")
        self.assertEqual(placeholders["failed_count"], "1")

    def test_compatibility_schema_preserves_valid_evidence(self):
        raw = {
            "schema_version": 2,
            "mappings": [
                {
                    "id": "final-gate",
                    "confidence": "verified",
                    "match": {
                        "product_ids": ["product-final-gate"],
                        "category": "dj",
                        "required_dps": [20],
                        "optional_dps": [],
                    },
                    "compatibility": {
                        "hardware_tested": True,
                        "protocols": ["3.5"],
                        "transport": "gateway_child",
                        "home_assistant": "2026.9",
                        "localtuya": "6.7.0-dev",
                        "tested_at": "2026-09-09",
                    },
                    "entities": [
                        {
                            "platform": "switch",
                            "config": {"id": 20, "platform": "switch"},
                        }
                    ],
                }
            ],
        }
        normalized = DeviceCatalog._validate_catalog(raw)
        compatibility = normalized["mappings"][0]["compatibility"]
        self.assertTrue(compatibility["hardware_tested"])
        self.assertEqual(compatibility["transport"], "gateway_child")
        self.assertEqual(compatibility["protocols"], ["3.5"])

    def test_bulk_ui_translation_key_is_shipped(self):
        root = Path(__file__).resolve().parents[1]
        payload = json.loads(
            (root / "custom_components/localtuya/translations/en.json").read_text(
                encoding="utf-8"
            )
        )
        steps = payload["options"]["step"]
        menu = steps["add_device_method"]["menu_options"]
        self.assertIn("qr_bulk_choose_devices", menu)
        self.assertIn("qr_bulk_choose_devices", steps)
        self.assertIn("qr_bulk_summary", steps)


if __name__ == "__main__":
    unittest.main()
