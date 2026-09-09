"""Acceptance tests for the generated real-world compatibility matrix."""

from __future__ import annotations

import unittest

from custom_components.localtuya.compatibility_matrix import (
    CompatibilityRecord,
    build_compatibility_matrix,
)


class CompatibilityMatrixTests(unittest.TestCase):
    """Verify deterministic matrix rows and confidence semantics."""

    def test_verified_hardware_record_is_real_tested(self):
        rows = build_compatibility_matrix(
            [
                CompatibilityRecord(
                    product_id="prod-1",
                    category="dj",
                    protocol="3.5",
                    mapping_id="map-1",
                    confidence="verified",
                    hardware_tested=True,
                    transport="direct",
                )
            ]
        )
        self.assertEqual(rows[0]["status"], "verified")
        self.assertTrue(rows[0]["hardware_tested"])

    def test_verified_without_hardware_evidence_is_downgraded(self):
        rows = build_compatibility_matrix(
            [
                CompatibilityRecord(
                    product_id="prod-1",
                    category="wk",
                    protocol="3.4",
                    mapping_id="map-1",
                    confidence="verified",
                    hardware_tested=False,
                    transport="gateway_child",
                )
            ]
        )
        self.assertEqual(rows[0]["status"], "community")

    def test_rows_are_sorted_and_do_not_expose_device_identifiers(self):
        rows = build_compatibility_matrix(
            [
                CompatibilityRecord("z", "wk", "3.4", "m2", "community", True, "direct"),
                CompatibilityRecord("a", "dj", "3.5", "m1", "verified", True, "direct"),
            ]
        )
        self.assertEqual([row["product_id"] for row in rows], ["a", "z"])
        self.assertNotIn("device_id", rows[0])
        self.assertNotIn("local_key", rows[0])
        self.assertNotIn("host", rows[0])


if __name__ == "__main__":
    unittest.main()
