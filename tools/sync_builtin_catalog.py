#!/usr/bin/env python3
"""Synchronize LocalTuya's bundled verified device catalog."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from urllib.request import urlopen


CURRENT_SCHEMA_VERSION = 2
SUPPORTED_SCHEMA_VERSIONS = {1, 2}

DEFAULT_SOURCE = (
    "https://raw.githubusercontent.com/"
    "MattiaFontana997/localtuya-device-catalog/"
    "main/catalog.json"
)

DEFAULT_OUTPUT = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "localtuya"
    / "builtin_catalog.json"
)


def load_source(source: str) -> dict:
    """Load catalog JSON from a local path or HTTP(S) URL."""
    if source.startswith(("http://", "https://")):
        with urlopen(source, timeout=15) as response:
            payload = response.read().decode("utf-8")
    else:
        payload = Path(source).read_text(encoding="utf-8")

    data = json.loads(payload)
    if not isinstance(data, dict):
        raise ValueError("Catalog root must be an object")

    if data.get("schema_version") not in SUPPORTED_SCHEMA_VERSIONS:
        raise ValueError("Unsupported catalog schema version")

    if not isinstance(data.get("mappings"), list):
        raise ValueError("Catalog mappings must be a list")

    return data


def _normalize_mapping(mapping: dict, schema_version: int) -> dict:
    """Normalize a V1/V2 source mapping to the bundled V2 representation."""
    normalized = copy.deepcopy(mapping)
    source_match = normalized.get("match")
    if not isinstance(source_match, dict):
        return normalized

    if schema_version == 1:
        product_id = source_match.get("product_id")
        product_ids = [product_id] if product_id else []
        optional_dps = []
    else:
        product_ids = source_match.get("product_ids", [])
        optional_dps = source_match.get("optional_dps", [])

    # Rebuild the selector rather than mutating it so snapshot output remains
    # byte-for-byte deterministic across a V1 -> V2 source transition.
    normalized["match"] = {
        "product_ids": sorted(product_ids),
        "category": source_match.get("category"),
        "required_dps": sorted(source_match.get("required_dps", [])),
        "optional_dps": sorted(optional_dps),
    }

    return normalized


def build_snapshot(catalog: dict) -> dict:
    """Build the V2 offline snapshot from physically verified mappings only."""
    schema_version = catalog["schema_version"]
    verified = []

    for mapping in catalog["mappings"]:
        if not isinstance(mapping, dict):
            continue
        if mapping.get("confidence") != "verified":
            continue
        verified.append(_normalize_mapping(mapping, schema_version))

    verified.sort(key=lambda mapping: str(mapping.get("id", "")))
    return {
        "schema_version": CURRENT_SCHEMA_VERSION,
        "mappings": verified,
    }


def serialize(payload: dict) -> str:
    """Serialize deterministically."""
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source",
        default=DEFAULT_SOURCE,
        help="Catalog JSON URL or local path",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
        help="Bundled catalog output path",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail if the bundled snapshot does not match the source catalog",
    )
    args = parser.parse_args()

    snapshot = build_snapshot(load_source(args.source))
    serialized = serialize(snapshot)
    output = Path(args.output)

    if args.check:
        if not output.exists():
            raise SystemExit("Bundled device catalog does not exist")
        if output.read_text(encoding="utf-8") != serialized:
            raise SystemExit("Bundled device catalog is out of date")
        print(
            "Bundled device catalog is current "
            f"({len(snapshot['mappings'])} verified mappings)"
        )
        return

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(serialized, encoding="utf-8")
    print(
        "Updated bundled device catalog: "
        f"{len(snapshot['mappings'])} verified mappings"
    )


if __name__ == "__main__":
    main()
