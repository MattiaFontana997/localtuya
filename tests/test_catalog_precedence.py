"""Regression tests for catalog-first automatic mapping precedence."""

from types import SimpleNamespace

from custom_components.localtuya import mapping_resolver
from custom_components.localtuya.device_mapper import (
    EntityCandidate,
    MappingConfidence,
    MappingSource,
    MappingTrust,
)


def _candidate(platform, dp, config, *, referenced_dps=None):
    return EntityCandidate(
        platform=platform,
        primary_dp=dp,
        confidence=MappingConfidence.HIGH,
        config=dict(config),
        matched_codes=(f"generic:{platform}:{dp}",),
        referenced_dps=tuple(referenced_dps or (dp,)),
    )


class _CatalogClient:
    def __init__(self, match):
        self._match = match

    def match(self, _device, _available_dps):
        return self._match


def _catalog_match(*, confidence="verified", entities=(), required_dps=(1,)):
    return SimpleNamespace(
        source="remote",
        mapping_id="test-product",
        product_id="pid-test",
        confidence=confidence,
        entities=tuple(entities),
        required_dps=tuple(required_dps),
    )


def test_verified_catalog_is_authoritative_and_generic_only_fills_missing(monkeypatch):
    """Trusted catalog values win while useful generic fields can fill gaps."""
    generic_light = _candidate(
        "light",
        1,
        {
            "id": 1,
            "platform": "light",
            "friendly_name": "Generic light",
            "brightness_upper": 255,
            "color_temp": 2,
        },
        referenced_dps=(1, 2),
    )
    generic_extra = _candidate(
        "switch",
        3,
        {
            "id": 3,
            "platform": "switch",
            "friendly_name": "Generic extra switch",
        },
    )
    monkeypatch.setattr(
        mapping_resolver,
        "build_entity_candidates",
        lambda *_args, **_kwargs: [generic_light, generic_extra],
    )

    catalog = _CatalogClient(
        _catalog_match(
            confidence="verified",
            required_dps=(1,),
            entities=(
                {
                    "platform": "light",
                    "config": {
                        "id": 1,
                        "friendly_name": "Catalog light",
                        "brightness_upper": 1000,
                    },
                },
            ),
        )
    )

    result = mapping_resolver.resolve_entity_candidates(
        {"name": "Lamp", "product_id": "pid-test"},
        None,
        {1, 2, 3},
        catalog_client=catalog,
    )

    assert len(result) == 1
    candidate = result[0]
    assert candidate.platform == "light"
    assert candidate.primary_dp == 1
    assert candidate.config["friendly_name"] == "Catalog light"
    assert candidate.config["brightness_upper"] == 1000
    assert candidate.config["color_temp"] == 2
    assert candidate.source == MappingSource.CATALOG
    assert candidate.trust == MappingTrust.VERIFIED
    assert candidate.confidence == MappingConfidence.HIGH
    assert "catalog:test-product" in candidate.matched_codes


def test_community_catalog_is_also_authoritative(monkeypatch):
    """Community mappings define the automatic entity set just like verified ones."""
    generic = _candidate(
        "switch",
        1,
        {
            "id": 1,
            "platform": "switch",
            "friendly_name": "Generic switch",
            "restore_on_reconnect": True,
        },
    )
    monkeypatch.setattr(
        mapping_resolver,
        "build_entity_candidates",
        lambda *_args, **_kwargs: [generic],
    )

    catalog = _CatalogClient(
        _catalog_match(
            confidence="community",
            entities=(
                {
                    "platform": "switch",
                    "config": {
                        "id": 1,
                        "friendly_name": "Community switch",
                        "restore_on_reconnect": False,
                    },
                },
            ),
        )
    )

    result = mapping_resolver.resolve_entity_candidates(
        {"product_id": "pid-test"},
        None,
        {1},
        catalog_client=catalog,
    )

    assert len(result) == 1
    assert result[0].config["restore_on_reconnect"] is False
    assert result[0].source == MappingSource.CATALOG
    assert result[0].trust == MappingTrust.COMMUNITY
    assert result[0].confidence == MappingConfidence.HIGH


def test_experimental_catalog_does_not_silently_replace_generic(monkeypatch):
    """Experimental catalog knowledge remains conservative and reviewable."""
    generic = _candidate(
        "light",
        1,
        {
            "id": 1,
            "platform": "light",
            "friendly_name": "Generic light",
            "brightness_upper": 255,
        },
    )
    monkeypatch.setattr(
        mapping_resolver,
        "build_entity_candidates",
        lambda *_args, **_kwargs: [generic],
    )

    catalog = _CatalogClient(
        _catalog_match(
            confidence="experimental",
            entities=(
                {
                    "platform": "light",
                    "config": {
                        "id": 1,
                        "brightness_upper": 1000,
                    },
                    "override_keys": [],
                },
            ),
        )
    )

    result = mapping_resolver.resolve_entity_candidates(
        {"product_id": "pid-test"},
        None,
        {1},
        catalog_client=catalog,
    )

    assert len(result) == 1
    assert result[0].config["brightness_upper"] == 255
    assert result[0].source == MappingSource.GENERIC
    assert result[0].confidence == MappingConfidence.HIGH
