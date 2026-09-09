"""Entity count regression for zero-config decisions."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from custom_components.localtuya.zero_config import evaluate_zero_config


class ZeroConfigEntityCountTests(unittest.TestCase):
    def test_all_high_candidates_are_preserved(self):
        candidates = [
            SimpleNamespace(confidence=SimpleNamespace(value="high"), config={"id": 1}),
            SimpleNamespace(confidence=SimpleNamespace(value="high"), config={"id": 2}),
            SimpleNamespace(confidence=SimpleNamespace(value="high"), config={"id": 3}),
        ]
        self.assertEqual(len(evaluate_zero_config(candidates).entities), 3)


if __name__ == "__main__":
    unittest.main()
