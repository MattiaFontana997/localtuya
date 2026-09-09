"""Zero-config returns copied entity configs."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from custom_components.localtuya.zero_config import evaluate_zero_config


class ZeroConfigEntityCopyTests(unittest.TestCase):
    def test_source_and_result_are_distinct_objects(self):
        config = {"id": 1}
        result = evaluate_zero_config([SimpleNamespace(confidence="high", config=config)])
        self.assertIsNot(result.entities[0], config)


if __name__ == "__main__":
    unittest.main()
