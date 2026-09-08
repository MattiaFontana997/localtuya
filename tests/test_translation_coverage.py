"""Translation completeness regression tests."""

from __future__ import annotations

import json
from pathlib import Path
import re
import unittest

from custom_components.localtuya import (
    device_mapper as localtuya_device_mapper,
)


ROOT = Path(
    localtuya_device_mapper.__file__
).resolve().parent

TRANSLATIONS = ROOT / "translations"

LANGUAGES = (
    "it",
    "de",
    "zh-Hans",
    "pt-BR",
)

# Values that are intentionally identical across languages.
ALLOW_IDENTICAL_VALUES = {
    "LocalTuya",
    "ID",
    "DP",
    "Client ID",
    "User ID",
}

# Specific translations that are correctly identical to English.
ALLOW_IDENTICAL_PATHS = {
    "pt-BR": {
        (
            "common",
            "mapping_status_experimental",
        ),
    },
}

PLACEHOLDER_RE = re.compile(
    r"\{[^{}]+\}"
)


def flatten(
    value,
    prefix=(),
):
    """Flatten translation JSON into path/value pairs."""
    result = {}

    if isinstance(value, dict):
        for key, child in value.items():
            result.update(
                flatten(
                    child,
                    prefix + (key,),
                )
            )
    else:
        result[prefix] = value

    return result


class TranslationCoverageTests(
    unittest.TestCase
):
    """Validate complete LocalTuya translations."""

    @classmethod
    def setUpClass(cls):
        cls.english = json.loads(
            (
                TRANSLATIONS
                / "en.json"
            ).read_text(
                encoding="utf-8"
            )
        )

        cls.english_flat = flatten(
            cls.english
        )

    def test_custom_integration_translation_layout(
        self,
    ):
        """Custom integrations must ship English in translations/en.json only."""
        self.assertTrue(
            (TRANSLATIONS / "en.json").is_file(),
            "translations/en.json is required for Home Assistant custom integrations",
        )
        self.assertFalse(
            (ROOT / "strings.json").exists(),
            "Custom integrations must not ship strings.json; use translations/en.json",
        )

    def test_host_recovery_repair_translation_contract(
        self,
    ):
        """The fixable host-recovery issue must keep its complete HA repair UI."""
        issue = (
            self.english.get("issues", {})
            .get("host_recovery_failed")
        )

        self.assertIsInstance(issue, dict)
        self.assertIn("{device_name}", issue["title"])
        self.assertNotIn(
            "description",
            issue,
            "Fixable HA issues use fix_flow instead of a top-level description",
        )

        fix_flow = issue.get("fix_flow", {})
        errors = fix_flow.get("error", {})
        self.assertEqual(
            set(errors),
            {
                "cannot_connect",
                "invalid_auth",
                "empty_dps",
                "invalid_host",
                "unknown",
                "stale",
                "device_not_found",
                "discovery_unavailable",
                "discovery_failed",
            },
        )

        steps = fix_flow.get("step", {})
        self.assertEqual(
            set(steps),
            {"init", "manual_host"},
        )
        self.assertEqual(
            set(steps["init"]["menu_options"]),
            {"rediscover", "manual_host"},
        )
        self.assertEqual(
            set(steps["manual_host"]["data"]),
            {"host"},
        )

    def test_supported_languages_have_all_keys(
        self,
    ):
        """Every supported language must contain every English key."""
        required = set(
            self.english_flat
        )

        for language in LANGUAGES:
            payload = json.loads(
                (
                    TRANSLATIONS
                    / f"{language}.json"
                ).read_text(
                    encoding="utf-8"
                )
            )

            available = set(
                flatten(payload)
            )

            missing = sorted(
                required - available
            )

            self.assertEqual(
                missing,
                [],
                (
                    f"{language} has missing "
                    f"translation keys: {missing}"
                ),
            )

    def test_translation_placeholders_match_english(
        self,
    ):
        """Translations must preserve HA placeholders."""
        for language in LANGUAGES:
            payload = json.loads(
                (
                    TRANSLATIONS
                    / f"{language}.json"
                ).read_text(
                    encoding="utf-8"
                )
            )

            current = flatten(
                payload
            )

            for path, en_value in (
                self.english_flat.items()
            ):
                translated = current[path]

                if (
                    not isinstance(en_value, str)
                    or not isinstance(
                        translated,
                        str,
                    )
                ):
                    continue

                self.assertEqual(
                    sorted(
                        PLACEHOLDER_RE.findall(
                            translated
                        )
                    ),
                    sorted(
                        PLACEHOLDER_RE.findall(
                            en_value
                        )
                    ),
                    (
                        f"{language}: "
                        f"{'.'.join(path)}"
                    ),
                )

    def test_no_unexpected_english_fallbacks(
        self,
    ):
        """Non-English translations must not silently fall back to English."""
        for language in LANGUAGES:
            payload = json.loads(
                (
                    TRANSLATIONS
                    / f"{language}.json"
                ).read_text(
                    encoding="utf-8"
                )
            )

            current = flatten(
                payload
            )

            allowed_paths = (
                ALLOW_IDENTICAL_PATHS.get(
                    language,
                    set(),
                )
            )

            leftovers = []

            for path, en_value in (
                self.english_flat.items()
            ):
                if not isinstance(
                    en_value,
                    str,
                ):
                    continue

                if (
                    current[path] == en_value
                    and en_value
                    not in ALLOW_IDENTICAL_VALUES
                    and path not in allowed_paths
                ):
                    leftovers.append(
                        ".".join(path)
                    )

            self.assertEqual(
                leftovers,
                [],
                (
                    f"{language} still contains "
                    f"English fallbacks: "
                    f"{leftovers}"
                ),
            )


if __name__ == "__main__":
    unittest.main()
