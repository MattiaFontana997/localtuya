"""Zero-config result entities are always represented as a list."""

from __future__ import annotations

import unittest

from custom_components.localtuya.zero_config import evaluate_zero_config


class ZeroConfigResultEntitiesTests(unittest.TestCase):
    def test_empty_result_entities_is_list(self):
        self.assertIsInstance(evaluate_zero_config([]).entities, list)


if __name__ == "__main__":
    unittest.main()
