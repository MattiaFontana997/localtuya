"""Zero-config materializes candidate iterables exactly once by contract."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from custom_components.localtuya.zero_config import evaluate_zero_config


class ZeroConfigIterableOnceTests(unittest.TestCase):
    def test_generator_is_supported(self):
        candidates = (SimpleNamespace(confidence="high", config={"id": value}) for value in (1, 2))
        result = evaluate_zero_config(candidates)
        self.assertEqual(len(result.entities), 2)


if __name__ == "__main__":
    unittest.main()
