#!/usr/bin/env python3
"""Synchronize LocalTuya's bundled verified device catalog."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.request import urlopen


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
    if source.startswith(
        ("http://", "https://")
    ):
        with urlopen(
            source,
            timeout=15,
        ) as response:
            payload = response.read().decode(
                "utf-8"
            )
    else:
        payload = Path(
            source
        ).read_text(
            encoding="utf-8"
        )

    data = json.loads(
        payload
    )

    if not isinstance(
        data,
        dict,
    ):
        raise ValueError(
            "Catalog root must be an object"
        )

    if (
        data.get("schema_version")
        != 1
    ):
        raise ValueError(
            "Unsupported catalog schema version"
        )

    mappings = data.get(
        "mappings"
    )

    if not isinstance(
        mappings,
        list,
    ):
        raise ValueError(
            "Catalog mappings must be a list"
        )

    return data


def build_snapshot(
    catalog: dict,
) -> dict:
    """Build the offline snapshot from physically verified mappings only."""
    verified = []

    for mapping in catalog[
        "mappings"
    ]:
        if not isinstance(
            mapping,
            dict,
        ):
            continue

        if (
            mapping.get(
                "confidence"
            )
            != "verified"
        ):
            continue

        verified.append(
            mapping
        )

    verified.sort(
        key=lambda mapping: str(
            mapping.get(
                "id",
                "",
            )
        )
    )

    return {
        "schema_version": 1,
        "mappings": verified,
    }


def serialize(
    payload: dict,
) -> str:
    """Serialize deterministically."""
    return (
        json.dumps(
            payload,
            indent=2,
            ensure_ascii=False,
        )
        + "\n"
    )


def main() -> None:
    parser = (
        argparse.ArgumentParser()
    )

    parser.add_argument(
        "--source",
        default=DEFAULT_SOURCE,
        help=(
            "Catalog JSON URL or local path"
        ),
    )

    parser.add_argument(
        "--output",
        default=str(
            DEFAULT_OUTPUT
        ),
        help=(
            "Bundled catalog output path"
        ),
    )

    parser.add_argument(
        "--check",
        action="store_true",
        help=(
            "Fail if the bundled snapshot "
            "does not match the source catalog"
        ),
    )

    args = parser.parse_args()

    source_catalog = load_source(
        args.source
    )

    snapshot = build_snapshot(
        source_catalog
    )

    serialized = serialize(
        snapshot
    )

    output = Path(
        args.output
    )

    if args.check:
        if not output.exists():
            raise SystemExit(
                "Bundled device catalog "
                "does not exist"
            )

        current = (
            output.read_text(
                encoding="utf-8"
            )
        )

        if current != serialized:
            raise SystemExit(
                "Bundled device catalog "
                "is out of date"
            )

        print(
            "Bundled device catalog is current "
            f"({len(snapshot['mappings'])} verified mappings)"
        )

        return

    output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output.write_text(
        serialized,
        encoding="utf-8",
    )

    print(
        "Updated bundled device catalog: "
        f"{len(snapshot['mappings'])} verified mappings"
    )


if __name__ == "__main__":
    main()
