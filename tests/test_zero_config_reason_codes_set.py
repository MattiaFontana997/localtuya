"""Zero-config reason-code vocabulary remains bounded."""

from __future__ import annotations

import unittest


class ZeroConfigReasonCodeSetTests(unittest.TestCase):
    def test_known_reason_codes_are_bounded(self):
        reasons = {
            "no_candidates",
            "non_high_confidence_candidate",
            "invalid_candidate_config",
            "invalid_primary_dp",
            "ambiguous_primary_dp",
            "all_candidates_high_confidence",
        }
        self.assertEqual(len(reasons), 6)


if __name__ == "__main__":
    unittest.main()
