"""Product-specific extensions for Tuya devices.

Generic Cloud metadata should remain the primary source of entity mappings.
This module is only for device behaviour that has been verified for a
specific Tuya product but is not exposed by the Cloud specification.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .const import (
    CONF_HVAC_MODE_DP,
    CONF_HVAC_MODE_SET,
)


@dataclass(frozen=True, slots=True)
class ProductEntityOverride:
    """One product-specific extension to a generic entity candidate."""

    platform: str
    primary_dp: int
    required_dps: tuple[int, ...]
    config_updates: tuple[tuple[str, Any], ...]


# Keep this registry deliberately narrow.
#
# wxmbjwpt8yea7bag
#   Cloud category: wk
#   Product: Room thermostat
#
# Verified LAN DPS:
#   103 = heatcool_heat / heatcool_cool / heatcool_heatcool
#
# DP3 is intentionally NOT mapped here yet. It has been observed as
# "cool", but the complete action value set has not been established.
_PRODUCT_OVERRIDES: dict[
    str,
    tuple[ProductEntityOverride, ...],
] = {
    "wxmbjwpt8yea7bag": (
        ProductEntityOverride(
            platform="climate",
            primary_dp=1,
            required_dps=(103,),
            config_updates=(
                (
                    CONF_HVAC_MODE_DP,
                    103,
                ),
                (
                    CONF_HVAC_MODE_SET,
                    "heatcool_heat/heatcool_cool/heatcool_heatcool",
                ),
            ),
        ),
    ),
}


def get_product_entity_overrides(
    device: dict[str, Any],
) -> tuple[ProductEntityOverride, ...]:
    """Return verified overrides for a Tuya product."""
    product_id = None

    for key in (
        "product_id",
        "productId",
        "product_key",
        "productKey",
    ):
        value = device.get(key)

        if value:
            product_id = str(value).strip()
            break

    if not product_id:
        return ()

    return _PRODUCT_OVERRIDES.get(
        product_id,
        (),
    )
