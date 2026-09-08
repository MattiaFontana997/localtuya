"""Regression tests for LocalTuya's Home Assistant configuration schema."""

from __future__ import annotations

import unittest

from custom_components.localtuya import CONFIG_SCHEMA


class ConfigSchemaTests(unittest.TestCase):
    """Keep LocalTuya explicitly config-entry-only for Home Assistant."""

    def test_empty_home_assistant_yaml_config_is_accepted(self):
        """The integration schema accepts the global config when no YAML is used."""
        self.assertEqual(
            CONFIG_SCHEMA({}),
            {},
        )


if __name__ == "__main__":
    unittest.main()
