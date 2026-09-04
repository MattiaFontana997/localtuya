"""Translation structure regression tests."""

from __future__ import annotations

import json
from pathlib import Path
import unittest

from custom_components.localtuya import (
    device_mapper as localtuya_device_mapper,
)


ROOT = Path(
    localtuya_device_mapper.__file__
).resolve().parent

TRANSLATIONS = (
    ROOT / "translations"
)


def leaf_paths(
    value,
    prefix=(),
):
    """Return every leaf JSON path."""
    result = set()

    if isinstance(
        value,
        dict,
    ):
        for key, child in value.items():
            result.update(
                leaf_paths(
                    child,
                    prefix + (key,),
                )
            )
        return result

    result.add(
        prefix
    )

    return result


class TranslationCoverageTests(
    unittest.TestCase
):
    """Ensure supported languages follow the English schema."""

    def test_supported_languages_have_english_keys(
        self,
    ):
        english = json.loads(
            (
                TRANSLATIONS
                / "en.json"
            ).read_text(
                encoding="utf-8"
            )
        )

        required = leaf_paths(
            english
        )

        for language in (
            "it",
            "de",
            "zh-Hans",
        ):
            payload = json.loads(
                (
                    TRANSLATIONS
                    / f"{language}.json"
                ).read_text(
                    encoding="utf-8"
                )
            )

            available = leaf_paths(
                payload
            )

            missing = sorted(
                required - available
            )

            self.assertEqual(
                missing,
                [],
                (
                    f"{language} is missing "
                    f"{len(missing)} translation keys: "
                    f"{missing[:20]}"
                ),
            )

    def test_critical_localized_ui_strings(
        self,
    ):
        expected = {
            "it": {
                "action":
                    "Azione",
                "edit":
                    "Modifica un dispositivo",
                "verified":
                    "Verificato",
            },
            "de": {
                "action":
                    "Aktion",
                "edit":
                    "Gerät bearbeiten",
                "verified":
                    "Verifiziert",
            },
            "zh-Hans": {
                "action":
                    "操作",
                "edit":
                    "编辑设备",
                "verified":
                    "已验证",
            },
        }

        for (
            language,
            wanted,
        ) in expected.items():
            payload = json.loads(
                (
                    TRANSLATIONS
                    / f"{language}.json"
                ).read_text(
                    encoding="utf-8"
                )
            )

            self.assertEqual(
                payload[
                    "options"
                ][
                    "step"
                ][
                    "init"
                ][
                    "data"
                ][
                    "action"
                ],
                wanted[
                    "action"
                ],
            )

            self.assertEqual(
                payload[
                    "common"
                ][
                    "action_edit_device"
                ],
                wanted[
                    "edit"
                ],
            )

            self.assertEqual(
                payload[
                    "common"
                ][
                    "mapping_status_verified"
                ],
                wanted[
                    "verified"
                ],
            )


if __name__ == "__main__":
    unittest.main()
