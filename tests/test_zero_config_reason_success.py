"""Success reason code for zero-config."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from custom_components.localtuya.zero_config import evaluate_zero_config


class ZeroConfigSuccessReasonTests(unittest.TestCase):
    def test_success_reason_is_stable(self):
        candidate = SimpleNamespace(confidence=SimpleNamespace(value="high"), config={"id": 1})
        self.assertEqual(evaluate_zero_config([candidate]).reason, "all_candidates_high_confidence")


if __name__ == "__main__":
    unittest.main()
