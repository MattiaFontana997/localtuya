"""Zero-config preserves validated platform configuration."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from custom_components.localtuya.zero_config import evaluate_zero_config


class ZeroConfigPlatformPassthroughTests(unittest.TestCase):
    def test_platform_is_preserved(self):
        candidate = SimpleNamespace(confidence=SimpleNamespace(value="high"), config={"id": 1, "platform": "switch"})
        self.assertEqual(evaluate_zero_config([candidate]).entities[0]["platform"], "switch")


if __name__ == "__main__":
    unittest.main()
