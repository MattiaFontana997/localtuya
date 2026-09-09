"""Privacy guarantees for zero-config decisions."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from custom_components.localtuya.zero_config import evaluate_zero_config


class ZeroConfigPrivacyTests(unittest.TestCase):
    def test_result_contains_only_entity_configuration(self):
        candidate = SimpleNamespace(
            confidence=SimpleNamespace(value="high"),
            config={"id": 1, "platform": "switch"},
            device_id="secret-device",
            host="192.168.1.4",
            local_key="secret-key",
        )
        result = evaluate_zero_config([candidate])
        rendered = repr(result)
        self.assertNotIn("secret-device", rendered)
        self.assertNotIn("192.168.1.4", rendered)
        self.assertNotIn("secret-key", rendered)


if __name__ == "__main__":
    unittest.main()
