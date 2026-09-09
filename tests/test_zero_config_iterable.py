"""Zero-config accepts any finite candidate iterable."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from custom_components.localtuya.zero_config import ZeroConfigDecision, evaluate_zero_config


class ZeroConfigIterableTests(unittest.TestCase):
    def test_tuple_candidates_are_supported(self):
        candidates = (SimpleNamespace(confidence="high", config={"id": 1}),)
        self.assertEqual(evaluate_zero_config(candidates).decision, ZeroConfigDecision.AUTO_CONFIGURE)


if __name__ == "__main__":
    unittest.main()
