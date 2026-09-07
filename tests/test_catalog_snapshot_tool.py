"""Regression tests for the bundled catalog synchronization tool."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "sync_builtin_catalog",
    ROOT / "tools" / "sync_builtin_catalog.py",
)
assert SPEC is not None and SPEC.loader is not None
sync_builtin_catalog = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sync_builtin_catalog)


class CatalogSnapshotToolTests(unittest.TestCase):
    """Validate V3 source compatibility for the V2 offline snapshot."""

    def test_v3_source_keeps_verified_product_mapping_only(self):
        catalog = {
            "schema_version": 3,
            "mappings": [
                {
                    "id": "verified-product",
                    "confidence": "verified",
                    "match": {
                        "product_ids": ["product-b", "product-a"],
                        "category": "dj",
                        "required_dps": [24, 20],
                        "optional_dps": [23],
                    },
                    "entities": [{"platform": "light", "config": {"id": 20}}],
                },
                {
                    "id": "productless-fingerprint",
                    "confidence": "experimental",
                    "match": {
                        "product_ids": [],
                        "category": "dj",
                        "required_dps": [20, 21],
                        "optional_dps": [],
                        "fingerprint": {"mode": "exact_dps"},
                    },
                    "entities": [{"platform": "light", "config": {"id": 20}}],
                },
            ],
        }

        snapshot = sync_builtin_catalog.build_snapshot(catalog)

        self.assertEqual(snapshot["schema_version"], 2)
        self.assertEqual(len(snapshot["mappings"]), 1)
        mapping = snapshot["mappings"][0]
        self.assertEqual(mapping["id"], "verified-product")
        self.assertEqual(
            mapping["match"],
            {
                "product_ids": ["product-a", "product-b"],
                "category": "dj",
                "required_dps": [20, 24],
                "optional_dps": [23],
            },
        )


if __name__ == "__main__":
    unittest.main()
