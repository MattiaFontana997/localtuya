"""Successful zero-config decisions expose the auto-configure enum."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from custom_components.localtuya.zero_config import ZeroConfigDecision, evaluate_zero_config


class ZeroConfigSuccessDecisionTests(unittest.TestCase):
    def test_success_decision_is_auto_configure(self):
        result = evaluate_zero_config([SimpleNamespace(confidence="high", config={"id": 1})])
        self.assertIs(result.decision, ZeroConfigDecision.AUTO_CONFIGURE)


if __name__ == "__main__":
    unittest.main()
