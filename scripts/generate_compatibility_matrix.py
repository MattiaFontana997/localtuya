#!/usr/bin/env python3
"""Generate the public LocalTuya real-device compatibility matrix."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from custom_components.localtuya.compatibility_matrix import (
    build_compatibility_matrix,
    records_from_catalog,
)


def _load(path: Path) -> dict:
    if not path.exists():
        return {"mappings": []}
    return json.loads(path.read_text(encoding="utf-8"))


def _markdown(rows: list[dict]) -> str:
    lines = [
        "# LocalTuya Compatibility Matrix",
        "",
        "This file is generated from catalog mappings that contain explicit real-device compatibility evidence.",
        "`verified` means hardware-tested; catalog confidence alone is not sufficient.",
        "",
        "| Product ID | Category | Protocol | Transport | Mapping | Status | HA | LocalTuya | Tested at |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    if not rows:
        lines.append("| _No hardware evidence recorded yet_ | | | | | | | | |")
    for row in rows:
        lines.append(
            "| {product_id} | {category} | {protocol} | {transport} | {mapping_id} | {status} | {home_assistant} | {localtuya} | {tested_at} |".format(
                **{
                    key: str(row.get(key) or "—").replace("|", "\\|")
                    for key in (
                        "product_id",
                        "category",
                        "protocol",
                        "transport",
                        "mapping_id",
                        "status",
                        "home_assistant",
                        "localtuya",
                        "tested_at",
                    )
                }
            )
        )
    lines.extend(
        [
            "",
            "## Status semantics",
            "",
            "- **verified** — explicit real-hardware evidence exists for this product/protocol/transport record.",
            "- **community** — catalog/community evidence exists, but hardware verification is incomplete or absent.",
            "- **experimental** — preliminary compatibility only.",
            "",
            "No Device ID, IP address, local key, account identifier, token, MAC address, or user-friendly device name is stored here.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--catalog",
        default="custom_components/localtuya/builtin_catalog.json",
    )
    parser.add_argument(
        "--json-out",
        default="docs/compatibility_matrix.json",
    )
    parser.add_argument(
        "--markdown-out",
        default="docs/COMPATIBILITY_MATRIX.md",
    )
    args = parser.parse_args()

    catalog = _load(Path(args.catalog))
    rows = build_compatibility_matrix(records_from_catalog(catalog))

    json_out = Path(args.json_out)
    markdown_out = Path(args.markdown_out)
    json_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(
        json.dumps({"schema_version": 1, "products": rows}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    markdown_out.write_text(_markdown(rows), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
