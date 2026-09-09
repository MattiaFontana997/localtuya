"""Empty compatibility matrix behavior."""

from __future__ import annotations

import unittest

from custom_components.localtuya.compatibility_matrix import build_compatibility_matrix


class CompatibilityMatrixEmptyTests(unittest.TestCase):
    def test_empty_records_return_empty_rows(self):
        self.assertEqual(build_compatibility_matrix([]), [])


if __name__ == "__main__":
    unittest.main()
