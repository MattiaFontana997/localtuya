"""Tests for Cloud mapper review flow."""

import unittest
from types import SimpleNamespace

from custom_components.localtuya.config_flow import (
    AUTO_ENTITY_SELECTION,
    LocalTuyaOptionsFlowHandler,
    async_get_cloud_entity_candidates,
)
from custom_components.localtuya.const import (
    CONF_DEFAULT_VALUE,
    DATA_CLOUD,
    DATA_DEVICE_CATALOG,
    DOMAIN,
)
from custom_components.localtuya.device_catalog import (
    CatalogMatch,
)


DEVICE_ID = "generic-review-test"


SPECIFICATION = {
    "functions": [
        {
            "dp_id": 1,
            "code": "switch_1",
            "type": "Boolean",
            "values": "{}",
        },
        {
            "dp_id": 10,
            "code": "temperature_offset",
            "type": "Integer",
            "values": (
                '{"unit":"℃","min":-30,'
                '"max":30,"scale":1,"step":5}'
            ),
        },
        {
            "dp_id": 11,
            "code": "relay_status",
            "type": "Enum",
            "values": (
                '{"range":["off","on","memory"]}'
            ),
        },
    ],
    "status": [
        {
            "dp_id": 1,
            "code": "switch_1",
            "type": "Boolean",
            "values": "{}",
        },
        {
            "dp_id": 10,
            "code": "temperature_offset",
            "type": "Integer",
            "values": (
                '{"unit":"℃","min":-30,'
                '"max":30,"scale":1,"step":5}'
            ),
        },
        {
            "dp_id": 11,
            "code": "relay_status",
            "type": "Enum",
            "values": (
                '{"range":["off","on","memory"]}'
            ),
        },
    ],
}


class FakeCloud:
    """Minimal Cloud API test double."""

    device_list = {
        DEVICE_ID: {
            "id": DEVICE_ID,
            "name": "Generic Device",
            "category": "test",
        }
    }

    async def async_get_device_specification(
        self,
        device_id,
    ):
        if device_id != DEVICE_ID:
            raise AssertionError(
                f"Unexpected device id {device_id}"
            )

        return "ok", SPECIFICATION


class ConfigFlowMapperTests(
    unittest.IsolatedAsyncioTestCase
):
    """Test automatic mapper review policy."""

    async def test_high_selected_medium_optional(self):
        hass = SimpleNamespace(
            data={
                DOMAIN: {
                    DATA_CLOUD: FakeCloud(),
                }
            }
        )

        candidates = (
            await async_get_cloud_entity_candidates(
                hass,
                {
                    "device_id": DEVICE_ID,
                    "friendly_name":
                        "Generic Device",
                },
                {},
                [
                    "1 (value: True)",
                    "10 (value: 0)",
                    "11 (value: memory)",
                ],
            )
        )

        self.assertEqual(
            len(candidates),
            3,
        )

        high_indexes = [
            str(index)
            for index, candidate
            in enumerate(candidates)
            if (
                candidate.confidence.value
                == "high"
            )
        ]

        medium_indexes = [
            str(index)
            for index, candidate
            in enumerate(candidates)
            if (
                candidate.confidence.value
                == "medium"
            )
        ]

        self.assertEqual(
            len(high_indexes),
            1,
        )
        self.assertEqual(
            len(medium_indexes),
            2,
        )

        flow = LocalTuyaOptionsFlowHandler(
            SimpleNamespace(
                data={},
            )
        )

        flow.auto_candidates = candidates

        result = (
            await flow.async_step_review_auto_entities()
        )

        defaults = result[
            "data_schema"
        ]({})[
            AUTO_ENTITY_SELECTION
        ]

        self.assertEqual(
            defaults,
            high_indexes,
        )

        self.assertFalse(
            set(defaults)
            & set(medium_indexes)
        )


    async def test_builtin_mapping_wins_and_catalog_only_enriches(
        self,
    ):
        """Remote catalog must not replace built-in mapper data."""

        class FakeCatalog:
            """Return a catalog mapping for the built-in switch."""

            def match(
                self,
                device,
                available_dps,
            ):
                self.last_device = device
                self.last_dps = set(
                    available_dps
                )

                return CatalogMatch(
                    mapping_id="catalog-precedence-test",
                    product_id="catalog-test-product",
                    confidence="verified",
                    required_dps=(1,),
                    entities=(
                        {
                            "platform": "switch",
                            "config": {
                                "id": 1,
                                "platform": "switch",

                                # This must NOT replace the
                                # built-in friendly name.
                                "friendly_name":
                                    "Remote Catalog Name",

                                # This does not exist in the
                                # generic candidate and therefore
                                # may safely enrich it.
                                CONF_DEFAULT_VALUE:
                                    "catalog-added-value",
                            },
                        },
                    ),
                )

        catalog = FakeCatalog()

        hass = SimpleNamespace(
            data={
                DOMAIN: {
                    DATA_CLOUD:
                        FakeCloud(),
                    DATA_DEVICE_CATALOG:
                        catalog,
                }
            }
        )

        candidates = (
            await async_get_cloud_entity_candidates(
                hass,
                {
                    "device_id": DEVICE_ID,
                    "friendly_name":
                        "Generic Device",
                },
                {},
                [
                    "1 (value: True)",
                    "10 (value: 0)",
                    "11 (value: memory)",
                ],
            )
        )

        switch_candidate = next(
            candidate
            for candidate in candidates
            if (
                candidate.platform
                == "switch"
                and candidate.primary_dp
                == 1
            )
        )

        # Built-in mapping still owns identity/name/confidence.
        self.assertEqual(
            switch_candidate.config[
                "friendly_name"
            ],
            "Generic Device",
        )

        self.assertEqual(
            switch_candidate.confidence.value,
            "high",
        )

        # Catalog was allowed to add missing knowledge.
        self.assertEqual(
            switch_candidate.config[
                CONF_DEFAULT_VALUE
            ],
            "catalog-added-value",
        )

        # Both sources remain traceable.
        self.assertIn(
            "switch_1",
            switch_candidate.matched_codes,
        )

        self.assertIn(
            "catalog:catalog-precedence-test",
            switch_candidate.matched_codes,
        )

        # LAN safety remains active.
        self.assertEqual(
            set(
                switch_candidate.referenced_dps
            ),
            {1},
        )

        self.assertEqual(
            catalog.last_dps,
            {1, 10, 11},
        )



if __name__ == "__main__":
    unittest.main()
