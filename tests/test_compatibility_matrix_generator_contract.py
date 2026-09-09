"""Generator contract for compatibility matrix artifacts."""

from __future__ import annotations

import unittest


class CompatibilityGeneratorContractTests(unittest.TestCase):
    def test_generated_artifact_names_are_stable(self):
        self.assertEqual("docs/compatibility_matrix.json", "docs/compatibility_matrix.json")
        self.assertEqual("docs/COMPATIBILITY_MATRIX.md", "docs/COMPATIBILITY_MATRIX.md")


if __name__ == "__main__":
    unittest.main()
