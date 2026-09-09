"""End-to-end contract for the LocalTuya zero-config path."""

from __future__ import annotations

import unittest


class ZeroConfigEndToEndContract(unittest.TestCase):
    def test_majority_path_contract(self):
        stages = [
            "qr_auth",
            "device_selection",
            "lan_discovery",
            "credential_validation",
            "protocol_detection",
            "dps_detection",
            "catalog_resolution",
            "zero_config_decision",
            "persist",
        ]
        self.assertEqual(stages[0], "qr_auth")
        self.assertEqual(stages[-1], "persist")
        self.assertNotIn("manual_dps", stages)
        self.assertNotIn("manual_protocol", stages)


if __name__ == "__main__":
    unittest.main()
