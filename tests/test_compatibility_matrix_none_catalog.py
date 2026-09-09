"""Invalid catalog inputs produce no compatibility evidence."""

from __future__ import annotations

import unittest

from custom_components.localtuya.compatibility_matrix import records_from_catalog


class CompatibilityInvalidCatalogTests(unittest.TestCase):
    def test_non_dict_catalog_has_no_records(self):
        self.assertEqual(records_from_catalog([]), [])


if __name__ == "__main__":
    unittest.main()
