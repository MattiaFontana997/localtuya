"""Regression tests for LocalTuya mapping-status translations."""

from __future__ import annotations

import json
from pathlib import Path
import unittest


from custom_components.localtuya import (
    device_mapper as localtuya_device_mapper,
)


TRANSLATIONS_DIR = (
    Path(
        localtuya_device_mapper.__file__
    ).resolve().parent
    / "translations"
)


EXPECTED = {
    "en": {
        "mapping_status_verified": "Verified",
        "mapping_status_community": "Community",
        "mapping_status_experimental": "Experimental",
        "mapping_status_auto_detected": "Auto-detected",
        "mapping_status_suggested": "Suggested",
    },
    "it": {
        "mapping_status_verified": "Verificato",
        "mapping_status_community": "Dalla community",
        "mapping_status_experimental": "Sperimentale",
        "mapping_status_auto_detected": "Rilevato automaticamente",
        "mapping_status_suggested": "Suggerito",
    },
    "de": {
        "mapping_status_verified": "Verifiziert",
        "mapping_status_community": "Aus der Community",
        "mapping_status_experimental": "Experimentell",
        "mapping_status_auto_detected": "Automatisch erkannt",
        "mapping_status_suggested": "Vorgeschlagen",
    },
    "zh-Hans": {
        "mapping_status_verified": "已验证",
        "mapping_status_community": "社区提供",
        "mapping_status_experimental": "实验性",
        "mapping_status_auto_detected": "自动检测",
        "mapping_status_suggested": "建议",
    },
}


class MappingTranslationTests(
    unittest.TestCase
):
    """Validate user-facing mapping status translations."""

    def test_mapping_status_translations(self):
        for language, expected in EXPECTED.items():
            path = (
                TRANSLATIONS_DIR
                / f"{language}.json"
            )

            self.assertTrue(
                path.exists(),
                language,
            )

            payload = json.loads(
                path.read_text(
                    encoding="utf-8"
                )
            )

            common = payload.get(
                "common",
                {},
            )

            for key, value in expected.items():
                self.assertEqual(
                    common.get(key),
                    value,
                    f"{language}: {key}",
                )


if __name__ == "__main__":
    unittest.main()
