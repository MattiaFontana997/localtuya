"""Zero-config results never retain unrelated candidate secrets."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from custom_components.localtuya.zero_config import evaluate_zero_config


class ZeroConfigNoSecretsTests(unittest.TestCase):
    def test_unrelated_attributes_are_not_retained(self):
        candidate = SimpleNamespace(confidence="high", config={"id": 1}, local_key="secret")
        self.assertNotIn("secret", repr(evaluate_zero_config([candidate])))


if __name__ == "__main__":
    unittest.main()
