"""Final regression gate for roadmap items 3, 4, 6 and 8."""

import unittest

from custom_components.localtuya.device_catalog import (
    match_catalog_mapping,
    validate_catalog,
)


class FinalCatalogAuthorityGate(unittest.TestCase):
    """Keep exact device metadata ahead of equally trusted generic mappings."""

    def test_exact_category_beats_generic_at_equal_trust(self):
        def mapping(mapping_id, category=None):
            match = {
                "product_ids": ["product-final-gate"],
                "required_dps": [1],
                "optional_dps": [],
            }
            if category is not None:
                match["category"] = category
            return {
                "id": mapping_id,
                "confidence": "verified",
                "match": match,
                "entities": [
                    {
                        "platform": "switch",
                        "config": {"id": 1, "platform": "switch"},
                    }
                ],
            }

        catalog = validate_catalog(
            {
                "schema_version": 2,
                "mappings": [
                    mapping("generic"),
                    mapping("exact-category", "cz"),
                ],
            }
        )

        result = match_catalog_mapping(
            catalog,
            {"product_id": "product-final-gate", "category": "cz"},
            {1},
        )

        self.assertIsNotNone(result)
        self.assertEqual(result.mapping_id, "exact-category")


if __name__ == "__main__":
    unittest.main()
