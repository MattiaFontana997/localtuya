"""Privacy-safe real-device compatibility matrix for LocalTuya.

The matrix deliberately separates catalog confidence from hardware evidence.
A catalog mapping may be authoritative for matching purposes, but the public
compatibility status is ``verified`` only when a real-device validation record
exists. Device IDs, hosts, local keys and account identifiers are never part of
this model.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable


@dataclass(slots=True, frozen=True)
class CompatibilityRecord:
    """One product-level compatibility observation."""

    product_id: str
    category: str
    protocol: str
    mapping_id: str
    confidence: str
    hardware_tested: bool
    transport: str
    home_assistant: str | None = None
    localtuya: str | None = None
    tested_at: str | None = None

    def public_dict(self) -> dict[str, Any]:
        """Return the intentionally identifier-free public representation."""
        data = asdict(self)
        confidence = str(self.confidence or "experimental").lower()
        if confidence == "verified" and not self.hardware_tested:
            confidence = "community"
        if confidence not in {"experimental", "community", "verified"}:
            confidence = "experimental"
        data["status"] = confidence
        data.pop("confidence", None)
        return data


def build_compatibility_matrix(
    records: Iterable[CompatibilityRecord],
) -> list[dict[str, Any]]:
    """Build deterministic public compatibility rows.

    Duplicate evidence is collapsed by product/protocol/transport/mapping. When
    duplicate rows differ, the strongest hardware-backed status wins, followed
    by the most recent row order-independent lexical representation. This keeps
    generated documentation deterministic in CI.
    """
    rank = {"experimental": 0, "community": 1, "verified": 2}
    unique: dict[tuple[str, str, str, str], dict[str, Any]] = {}

    for record in records:
        row = record.public_dict()
        product_id = str(row.get("product_id") or "").strip()
        if not product_id:
            continue
        row["product_id"] = product_id
        row["category"] = str(row.get("category") or "").strip()
        row["protocol"] = str(row.get("protocol") or "unknown").strip() or "unknown"
        row["mapping_id"] = str(row.get("mapping_id") or "").strip()
        transport = str(row.get("transport") or "direct").strip()
        if transport not in {"direct", "gateway_child"}:
            transport = "direct"
        row["transport"] = transport

        key = (
            row["product_id"],
            row["protocol"],
            row["transport"],
            row["mapping_id"],
        )
        current = unique.get(key)
        if current is None:
            unique[key] = row
            continue
        current_rank = rank.get(str(current.get("status")), 0)
        new_rank = rank.get(str(row.get("status")), 0)
        if new_rank > current_rank:
            unique[key] = row
        elif new_rank == current_rank and repr(sorted(row.items())) > repr(sorted(current.items())):
            unique[key] = row

    return sorted(
        unique.values(),
        key=lambda item: (
            str(item.get("product_id") or ""),
            str(item.get("protocol") or ""),
            str(item.get("transport") or ""),
            str(item.get("mapping_id") or ""),
        ),
    )


def records_from_catalog(catalog: dict[str, Any]) -> list[CompatibilityRecord]:
    """Extract matrix evidence from catalog mappings carrying compatibility data."""
    result: list[CompatibilityRecord] = []
    mappings = catalog.get("mappings", []) if isinstance(catalog, dict) else []
    if not isinstance(mappings, list):
        return result

    for mapping in mappings:
        if not isinstance(mapping, dict):
            continue
        match = mapping.get("match")
        compatibility = mapping.get("compatibility")
        if not isinstance(match, dict) or not isinstance(compatibility, dict):
            continue
        product_ids = match.get("product_ids", [])
        if not isinstance(product_ids, list):
            continue

        protocols = compatibility.get("protocols", ["unknown"])
        if isinstance(protocols, str):
            protocols = [protocols]
        if not isinstance(protocols, list) or not protocols:
            protocols = ["unknown"]

        for product_id in product_ids:
            product_id = str(product_id or "").strip()
            if not product_id:
                continue
            for protocol in protocols:
                result.append(
                    CompatibilityRecord(
                        product_id=product_id,
                        category=str(match.get("category") or ""),
                        protocol=str(protocol or "unknown"),
                        mapping_id=str(mapping.get("id") or ""),
                        confidence=str(mapping.get("confidence") or "experimental"),
                        hardware_tested=bool(compatibility.get("hardware_tested", False)),
                        transport=str(compatibility.get("transport") or "direct"),
                        home_assistant=(
                            str(compatibility["home_assistant"])
                            if compatibility.get("home_assistant")
                            else None
                        ),
                        localtuya=(
                            str(compatibility["localtuya"])
                            if compatibility.get("localtuya")
                            else None
                        ),
                        tested_at=(
                            str(compatibility["tested_at"])
                            if compatibility.get("tested_at")
                            else None
                        ),
                    )
                )
    return result
