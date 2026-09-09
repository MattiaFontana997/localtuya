"""Copy isolation for zero-config persisted entity configs."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from custom_components.localtuya.zero_config import evaluate_zero_config


class ZeroConfigCopyTests(unittest.TestCase):
    def test_result_entities_are_deep_copied(self):
        config = {"id": 1, "platform": "switch", "nested": {"x": 1}}
        candidate = SimpleNamespace(confidence=SimpleNamespace(value="high"), config=config)
        result = evaluate_zero_config([candidate])
        result.entities[0]["nested"]["x"] = 2
        self.assertEqual(config["nested"]["x"], 1)


if __name__ == "__main__":
    unittest.main()
