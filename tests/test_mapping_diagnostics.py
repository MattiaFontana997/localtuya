"""Tests for privacy-safe LocalTuya mapping diagnostics."""

from __future__ import annotations

import unittest

from custom_components.localtuya.device_mapper import (
    EntityCandidate,
    MappingConfidence,
    MappingSource,
    MappingTrust,
)
from custom_components.localtuya.diagnostics import (
    build_mapping_diagnostics,
)


def candidate(
    platform,
    dp,
    *,
    source=MappingSource.GENERIC,
    trust=None,
    confidence=MappingConfidence.HIGH,
    matched_codes=(),
    referenced_dps=(),
):
    """Build a mapping candidate for diagnostics tests."""
    return EntityCandidate(
        platform=platform,
        primary_dp=dp,
        confidence=confidence,
        config={
            "id": dp,
            "platform": platform,

            # This must never be copied into diagnostics.
            "local_key": "secret",

            # Nor should arbitrary candidate configuration
            # values be dumped into diagnostics.
            "private_config_value": "do-not-export",
        },
        matched_codes=tuple(
            matched_codes
        ),
        referenced_dps=tuple(
            referenced_dps
        ),
        source=source,
        trust=trust,
    )


class MappingDiagnosticsTests(
    unittest.TestCase
):
    """Validate mapping diagnostics metadata."""

    def test_catalog_candidate_reports_source_and_mapping_id(
        self,
    ):
        result = build_mapping_diagnostics(
            [
                "1 (value: True)",
                "16 (value: 21)",
                "24 (value: 20.5)",
            ],
            [
                candidate(
                    "climate",
                    1,
                    source=(
                        MappingSource.CATALOG
                    ),
                    trust=(
                        MappingTrust.VERIFIED
                    ),
                    confidence=(
                        MappingConfidence.HIGH
                    ),
                    matched_codes=(
                        "switch",
                        (
                            "catalog:"
                            "thermostat-verified"
                        ),
                    ),
                    referenced_dps=(
                        1,
                        16,
                        24,
                    ),
                )
            ],
        )

        self.assertEqual(
            result["observed_dps"],
            [
                1,
                16,
                24,
            ],
        )

        self.assertEqual(
            len(
                result["candidates"]
            ),
            1,
        )

        mapping = (
            result["candidates"][0]
        )

        self.assertEqual(
            mapping["platform"],
            "climate",
        )

        self.assertEqual(
            mapping["primary_dp"],
            1,
        )

        self.assertEqual(
            mapping["source"],
            "catalog",
        )

        self.assertEqual(
            mapping["trust"],
            "verified",
        )

        self.assertEqual(
            mapping["confidence"],
            "high",
        )

        self.assertEqual(
            mapping[
                "catalog_mapping_id"
            ],
            "thermostat-verified",
        )

        self.assertEqual(
            mapping[
                "referenced_dps"
            ],
            [
                1,
                16,
                24,
            ],
        )

    def test_generic_candidate_has_no_catalog_mapping_id(
        self,
    ):
        result = build_mapping_diagnostics(
            [
                "27 (value: 0)",
            ],
            [
                candidate(
                    "number",
                    27,
                    source=(
                        MappingSource.GENERIC
                    ),
                    trust=None,
                    confidence=(
                        MappingConfidence.MEDIUM
                    ),
                    matched_codes=(
                        "temperature_offset",
                    ),
                    referenced_dps=(
                        27,
                    ),
                )
            ],
        )

        mapping = (
            result["candidates"][0]
        )

        self.assertEqual(
            mapping["source"],
            "generic",
        )

        self.assertIsNone(
            mapping["trust"]
        )

        self.assertIsNone(
            mapping[
                "catalog_mapping_id"
            ]
        )

        self.assertEqual(
            mapping["matched_codes"],
            [
                "temperature_offset",
            ],
        )

    def test_candidate_config_is_never_exported(
        self,
    ):
        result = build_mapping_diagnostics(
            ["1 (value: True)"],
            [
                candidate(
                    "switch",
                    1,
                )
            ],
        )

        serialized = repr(
            result
        )

        self.assertNotIn(
            "local_key",
            serialized,
        )

        self.assertNotIn(
            "secret",
            serialized,
        )

        self.assertNotIn(
            "private_config_value",
            serialized,
        )

        self.assertNotIn(
            "do-not-export",
            serialized,
        )

    def test_observed_dps_parser_ignores_invalid_values(
        self,
    ):
        result = build_mapping_diagnostics(
            [
                "1 (value: True)",
                "invalid",
                "32 (value: 21.0)",
                None,
                "103 (value: heat)",
            ],
            [],
        )

        self.assertEqual(
            result["observed_dps"],
            [
                1,
                32,
                103,
            ],
        )


if __name__ == "__main__":
    unittest.main()


class RuntimeMappingDiagnosticsTests(
    unittest.IsolatedAsyncioTestCase
):
    """Validate runtime resolver diagnostics behavior."""

    async def test_runtime_uses_stored_dps_and_catalog(
        self,
    ):
        from types import SimpleNamespace
        from unittest.mock import patch

        from custom_components.localtuya.const import (
            DATA_DEVICE_CATALOG,
            DOMAIN,
        )
        from custom_components.localtuya.diagnostics import (
            _async_device_mapping_diagnostics,
        )

        catalog = object()

        hass = SimpleNamespace(
            data={
                DOMAIN: {
                    DATA_DEVICE_CATALOG:
                        catalog,
                }
            }
        )

        device_config = {
            "friendly_name":
                "Thermostat",
            "product_key":
                "test-product",
            "dps_strings": [
                "1 (value: True)",
                "16 (value: 21)",
                "24 (value: 20.5)",
            ],
        }

        resolved = [
            candidate(
                "climate",
                1,
                source=(
                    MappingSource.CATALOG
                ),
                trust=(
                    MappingTrust.VERIFIED
                ),
                matched_codes=(
                    "catalog:test-map",
                ),
                referenced_dps=(
                    1,
                    16,
                    24,
                ),
            )
        ]

        with patch(
            (
                "custom_components.localtuya."
                "diagnostics."
                "resolve_entity_candidates"
            ),
            return_value=resolved,
        ) as resolver:
            result = await (
                _async_device_mapping_diagnostics(
                    hass,
                    "device-1",
                    device_config,
                )
            )

        self.assertEqual(
            result["observed_dps"],
            [
                1,
                16,
                24,
            ],
        )

        args = resolver.call_args

        mapper_device = args.args[0]
        detected_ids = args.args[2]

        self.assertEqual(
            mapper_device[
                "product_key"
            ],
            "test-product",
        )

        self.assertEqual(
            mapper_device[
                "name"
            ],
            "Thermostat",
        )

        self.assertEqual(
            detected_ids,
            {
                1,
                16,
                24,
            },
        )

        self.assertIs(
            args.kwargs[
                "catalog_client"
            ],
            catalog,
        )


    async def test_cloud_specification_failure_is_non_fatal(
        self,
    ):
        from types import SimpleNamespace
        from unittest.mock import patch

        from custom_components.localtuya.const import (
            DATA_CLOUD,
            DOMAIN,
        )
        from custom_components.localtuya.diagnostics import (
            _async_device_mapping_diagnostics,
        )

        class FailingCloud:
            device_list = {
                "device-1": {
                    "id": "device-1",
                    "name":
                        "Cloud Device",
                }
            }

            device_specifications = {}

            async def async_get_device_specification(
                self,
                device_id,
            ):
                raise ConnectionError(
                    "cloud unavailable"
                )

        hass = SimpleNamespace(
            data={
                DOMAIN: {
                    DATA_CLOUD:
                        FailingCloud(),
                }
            }
        )

        with patch(
            (
                "custom_components.localtuya."
                "diagnostics."
                "resolve_entity_candidates"
            ),
            return_value=[],
        ) as resolver:
            result = await (
                _async_device_mapping_diagnostics(
                    hass,
                    "device-1",
                    {
                        "dps_strings": [
                            "1 (value: True)",
                        ],
                    },
                )
            )

        self.assertEqual(
            result["observed_dps"],
            [1],
        )

        # Cloud failure did not stop the local resolver.
        resolver.assert_called_once()


    async def test_cached_cloud_specification_avoids_request(
        self,
    ):
        from types import SimpleNamespace
        from unittest.mock import AsyncMock, patch

        from custom_components.localtuya.const import (
            DATA_CLOUD,
            DOMAIN,
        )
        from custom_components.localtuya.diagnostics import (
            _async_device_mapping_diagnostics,
        )

        cached_spec = {
            "functions": [
                {
                    "dp_id": 1,
                    "code": "switch",
                    "type": "Boolean",
                    "values": "{}",
                }
            ]
        }

        cloud = SimpleNamespace(
            device_list={
                "device-1": {
                    "id": "device-1",
                }
            },
            device_specifications={
                "device-1":
                    cached_spec,
            },
            async_get_device_specification=(
                AsyncMock()
            ),
        )

        hass = SimpleNamespace(
            data={
                DOMAIN: {
                    DATA_CLOUD:
                        cloud,
                }
            }
        )

        with patch(
            (
                "custom_components.localtuya."
                "diagnostics."
                "resolve_entity_candidates"
            ),
            return_value=[],
        ) as resolver:
            await (
                _async_device_mapping_diagnostics(
                    hass,
                    "device-1",
                    {
                        "dps_strings": [
                            "1 (value: True)",
                        ],
                    },
                )
            )

        cloud.async_get_device_specification.assert_not_awaited()

        self.assertIs(
            resolver.call_args.args[1],
            cached_spec,
        )


class DeviceDiagnosticsIntegrationTests(
    unittest.IsolatedAsyncioTestCase
):
    """Test complete Home Assistant device diagnostics."""

    async def test_device_diagnostics_contains_mapping_and_redacts_network_data(
        self,
    ):
        from types import SimpleNamespace
        from unittest.mock import patch

        from homeassistant.const import (
            CONF_DEVICES,
        )

        from custom_components.localtuya.const import (
            DATA_CLOUD,
            DOMAIN,
        )
        from custom_components.localtuya.diagnostics import (
            async_get_device_diagnostics,
        )

        device_config = {
            "friendly_name":
                "Thermostat",
            "host":
                "192.168.50.123",
            "local_key":
                "very-secret-local-key",
            "dps_strings": [
                "1 (value: True)",
                "32 (value: 21.0)",
            ],
            "entities": [],
        }

        entry = SimpleNamespace(
            data={
                CONF_DEVICES: {
                    "device-1":
                        device_config,
                }
            }
        )

        cloud = SimpleNamespace(
            device_list={}
        )

        hass = SimpleNamespace(
            data={
                DOMAIN: {
                    DATA_CLOUD:
                        cloud,
                }
            }
        )

        device = SimpleNamespace(
            identifiers={
                (
                    DOMAIN,
                    "local_device-1",
                )
            }
        )

        mapping = {
            "observed_dps": [
                1,
                32,
            ],
            "candidates": [],
        }

        with patch(
            (
                "custom_components.localtuya."
                "diagnostics."
                "_async_device_mapping_diagnostics"
            ),
            return_value=mapping,
        ):
            result = await (
                async_get_device_diagnostics(
                    hass,
                    entry,
                    device,
                )
            )

        serialized = repr(
            result
        )

        self.assertEqual(
            result["mapping"],
            mapping,
        )

        self.assertNotIn(
            "very-secret-local-key",
            serialized,
        )

        self.assertNotIn(
            "192.168.50.123",
            serialized,
        )


    async def test_resolver_failure_is_non_fatal_and_message_is_hidden(
        self,
    ):
        from types import SimpleNamespace
        from unittest.mock import patch

        from homeassistant.const import (
            CONF_DEVICES,
        )

        from custom_components.localtuya.const import (
            DATA_CLOUD,
            DOMAIN,
        )
        from custom_components.localtuya.diagnostics import (
            async_get_device_diagnostics,
        )

        entry = SimpleNamespace(
            data={
                CONF_DEVICES: {
                    "device-1": {
                        "friendly_name":
                            "Thermostat",
                        "host":
                            "192.168.50.123",
                        "local_key":
                            "secret-key",
                        "dps_strings": [
                            "1 (value: True)",
                            "103 (value: heat)",
                        ],
                        "entities": [],
                    }
                }
            }
        )

        hass = SimpleNamespace(
            data={
                DOMAIN: {
                    DATA_CLOUD:
                        SimpleNamespace(
                            device_list={}
                        ),
                }
            }
        )

        device = SimpleNamespace(
            identifiers={
                (
                    DOMAIN,
                    "local_device-1",
                )
            }
        )

        with patch(
            (
                "custom_components.localtuya."
                "diagnostics."
                "_async_device_mapping_diagnostics"
            ),
            side_effect=RuntimeError(
                "secret-key at "
                "192.168.50.123"
            ),
        ):
            result = await (
                async_get_device_diagnostics(
                    hass,
                    entry,
                    device,
                )
            )

        self.assertEqual(
            result[
                "mapping"
            ][
                "observed_dps"
            ],
            [
                1,
                103,
            ],
        )

        self.assertEqual(
            result[
                "mapping"
            ][
                "resolver_error"
            ],
            "RuntimeError",
        )

        serialized = repr(
            result
        )

        self.assertNotIn(
            "secret-key",
            serialized,
        )

        self.assertNotIn(
            "192.168.50.123",
            serialized,
        )


    async def test_cloud_device_identifiers_are_redacted(
        self,
    ):
        from types import SimpleNamespace
        from unittest.mock import patch

        from homeassistant.const import (
            CONF_DEVICES,
        )

        from custom_components.localtuya.const import (
            DATA_CLOUD,
            DOMAIN,
        )
        from custom_components.localtuya.diagnostics import (
            async_get_device_diagnostics,
        )

        entry = SimpleNamespace(
            data={
                CONF_DEVICES: {
                    "device-1": {
                        "friendly_name":
                            "Thermostat",
                        "host":
                            "192.168.1.10",
                        "local_key":
                            "local-secret",
                        "dps_strings": [
                            "1 (value: True)",
                        ],
                        "entities": [],
                    }
                }
            }
        )

        cloud = SimpleNamespace(
            device_list={
                "device-1": {
                    "id":
                        "device-1",
                    "uuid":
                        "uuid-private",
                    "uid":
                        "uid-private",
                    "ip":
                        "10.20.30.40",
                    "name":
                        "Thermostat",
                    "product_id":
                        "safe-product-id",
                    "category":
                        "wk",
                }
            }
        )

        hass = SimpleNamespace(
            data={
                DOMAIN: {
                    DATA_CLOUD:
                        cloud,
                }
            }
        )

        device = SimpleNamespace(
            identifiers={
                (
                    DOMAIN,
                    "local_device-1",
                )
            }
        )

        with patch(
            (
                "custom_components.localtuya."
                "diagnostics."
                "_async_device_mapping_diagnostics"
            ),
            return_value={
                "observed_dps": [1],
                "candidates": [],
            },
        ):
            result = await (
                async_get_device_diagnostics(
                    hass,
                    entry,
                    device,
                )
            )

        serialized = repr(
            result
        )

        self.assertNotIn(
            "device-1",
            repr(
                result[
                    "device_cloud_info"
                ]
            ),
        )

        self.assertNotIn(
            "uuid-private",
            serialized,
        )

        self.assertNotIn(
            "uid-private",
            serialized,
        )

        self.assertNotIn(
            "10.20.30.40",
            serialized,
        )

        # Useful non-identifying product metadata remains.
        self.assertIn(
            "safe-product-id",
            serialized,
        )

        self.assertIn(
            "Thermostat",
            serialized,
        )


class DiagnosticsRedactionRegressionTests(
    unittest.TestCase
):
    """Ensure privacy redaction does not destroy useful DP metadata."""

    def test_entity_dp_id_is_not_globally_redacted(
        self,
    ):
        from homeassistant.helpers.redact import (
            async_redact_data,
        )

        from custom_components.localtuya.diagnostics import (
            TO_REDACT,
        )

        data = {
            "host":
                "192.168.1.50",
            "local_key":
                "secret",
            "entities": [
                {
                    "id": 32,
                    "platform":
                        "number",
                }
            ],
        }

        result = async_redact_data(
            data,
            TO_REDACT,
        )

        self.assertEqual(
            result[
                "entities"
            ][0][
                "id"
            ],
            32,
        )

        self.assertEqual(
            result[
                "host"
            ],
            "**REDACTED**",
        )

        self.assertEqual(
            result[
                "local_key"
            ],
            "**REDACTED**",
        )


class AdditionalDiagnosticsPrivacyTests(
    unittest.TestCase
):
    """Protect device and Cloud owner identifiers."""

    def test_device_id_is_globally_redacted(
        self,
    ):
        from homeassistant.helpers.redact import (
            async_redact_data,
        )

        from custom_components.localtuya.diagnostics import (
            TO_REDACT,
        )

        result = async_redact_data(
            {
                "device_id":
                    "private-device-id",
                "entities": [
                    {
                        "id": 32,
                        "platform":
                            "number",
                    }
                ],
            },
            TO_REDACT,
        )

        self.assertEqual(
            result["device_id"],
            "**REDACTED**",
        )

        # Entity DP IDs must remain useful.
        self.assertEqual(
            result["entities"][0]["id"],
            32,
        )


    def test_cloud_owner_id_is_redacted(
        self,
    ):
        from custom_components.localtuya.diagnostics import (
            _privacy_safe_cloud_device,
        )

        result = (
            _privacy_safe_cloud_device(
                {
                    "owner_id":
                        "private-owner",
                    "id":
                        "private-device",
                    "product_id":
                        "safe-product",
                    "category":
                        "wk",
                }
            )
        )

        self.assertEqual(
            result["owner_id"],
            "**REDACTED**",
        )

        self.assertEqual(
            result["id"],
            "**REDACTED**",
        )

        self.assertEqual(
            result["product_id"],
            "safe-product",
        )

        self.assertEqual(
            result["category"],
            "wk",
        )
