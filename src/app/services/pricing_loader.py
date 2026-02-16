"""Load and slice product pricing data from Supabase via get_product_variants RPC."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from supabase import create_client

from ..config import settings

# ── Supabase client (singleton) ──────────────────────────────────────────────

@lru_cache(maxsize=1)
def _get_client():
    """Create and cache the Supabase client."""
    return create_client(settings.supabase_url, settings.supabase_key)


# ── Supabase product ID map ──────────────────────────────────────────────────
# Maps logical names used in the codebase to Supabase product table IDs.

_PRODUCT_IDS = {
    # Base pricing by size
    "r_blade_prices": 30,
    "r_shade_prices": 33,
    "r_breeze_prices": 34,
    # Color surcharges
    "r_blade_color": 20,
    "r_shade_color": 18,
    "r_breeze_color": 21,
    # Add-ons & surcharges
    "lights": 22,
    "fan_upgrade": 281,
    "heaters": 244,
    "motorized_shades": 28,
    "shade_install": 304,
    "privacy_wall_pricing": 32,
    "privacy_wall_surcharges": 19,
    "trim": 29,
    "electrical": 31,
    "installation": 14,
    "multibay_structural": 267,
    "structural_posts_beams": 261,
    "automation_controls": 269,
    "freight_logistics": 271,
    "labor_sitework": 272,
    "r_shade_support": 284,
}

# Map product_id to base pricing Supabase product ID
_BASE_PRICE_MAP: dict[str, int] = {
    "r_blade": _PRODUCT_IDS["r_blade_prices"],
    "r_breeze": _PRODUCT_IDS["r_breeze_prices"],
    "r_shade": _PRODUCT_IDS["r_shade_prices"],
}

# Map product_id to color surcharge Supabase product ID
_COLOR_SURCHARGE_MAP: dict[str, int] = {
    "r_blade": _PRODUCT_IDS["r_blade_color"],
    "r_breeze": _PRODUCT_IDS["r_breeze_color"],
    "r_shade": _PRODUCT_IDS["r_shade_color"],
}


# ── RPC helper ────────────────────────────────────────────────────────────────

_cache: dict[int, list[dict[str, Any]]] = {}


def _fetch_variants(product_id: int) -> list[dict[str, Any]]:
    """Fetch variants from Supabase RPC, with in-memory cache."""
    if product_id in _cache:
        return _cache[product_id]

    client = _get_client()
    resp = client.rpc("get_product_variants", {"p_product_id": product_id}).execute()
    rows = resp.data or []

    # The RPC returns composite objects — flatten them
    flattened: list[dict[str, Any]] = []
    for row in rows:
        if isinstance(row, dict) and "get_product_variants" in row:
            flattened.append(row["get_product_variants"])
        elif isinstance(row, dict):
            flattened.append(row)

    _cache[product_id] = flattened
    return flattened


def clear_cache() -> None:
    """Clear the in-memory pricing cache (useful for testing or reloads)."""
    _cache.clear()
    _get_client.cache_clear()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _clean_ft(val: Any) -> int | None:
    """Convert a dimension value like "16'" or 16 to int."""
    if val is None:
        return None
    s = str(val).replace("'", "").replace('"', "").strip()
    try:
        return int(float(s))
    except (ValueError, TypeError):
        return None


def _safe_float(val: Any) -> float | None:
    """Convert a value to float, returning None on failure."""
    if val is None or str(val).strip() in ("", "-"):
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


# ── Public API ────────────────────────────────────────────────────────────────

def get_base_pricing_table(product_id: str) -> list[dict[str, Any]]:
    """Return a clean pricing table [{width_ft, length_ft, sku, unit_price}, ...] for a product."""
    sb_id = _BASE_PRICE_MAP.get(product_id)
    if not sb_id:
        return []

    rows: list[dict[str, Any]] = []
    for v in _fetch_variants(sb_id):
        w = _clean_ft(v.get("width"))
        l = _clean_ft(v.get("length"))
        price = _safe_float(v.get("price"))
        sku = v.get("name", "")
        if w is not None and l is not None and price is not None and price > 0:
            rows.append({
                "width_ft": w,
                "length_ft": l,
                "sku": sku,
                "unit_price": round(price, 2),
            })
    return rows


def get_multibay_addons() -> list[dict[str, Any]]:
    """Return multi-bay structural add-on items."""
    items: list[dict[str, Any]] = []
    for v in _fetch_variants(_PRODUCT_IDS["multibay_structural"]):
        sku = v.get("name", "")
        val = _safe_float(v.get("value"))
        unit = v.get("pricing_unit_list", "")
        display = v.get("display_names") or v.get("model_name") or sku
        notes = v.get("notes", "") or ""
        if sku and val is not None:
            items.append({
                "sku": sku,
                "description": display,
                "unit_price": round(val, 2),
                "pricing_unit": unit,
                "notes": notes.strip(),
            })
    return items


def get_color_surcharges(product_id: str) -> list[dict[str, Any]]:
    """Return color/finish surcharge items for a product.

    Each item: {sku, display_name, color, applies_to, pricing_unit, value, notes}
    """
    sb_id = _COLOR_SURCHARGE_MAP.get(product_id)
    if not sb_id:
        return []

    items: list[dict[str, Any]] = []
    for v in _fetch_variants(sb_id):
        sku = v.get("name", "")
        val = _safe_float(v.get("value"))
        if sku and val is not None:
            items.append({
                "sku": sku,
                "display_name": v.get("display_names", ""),
                "color": v.get("color", ""),
                "applies_to": v.get("applies_to_list", ""),
                "pricing_unit": v.get("pricing_unit_list", ""),
                "value": val,
                "notes": (v.get("notes") or "").strip(),
            })
    return items


def get_lighting_fans(product_id: str) -> list[dict[str, Any]]:
    """Return lighting and fan items applicable to a product."""
    items: list[dict[str, Any]] = []
    pid_lower = product_id.lower().replace("_", "-")  # r_blade -> r-blade

    # Lights
    for v in _fetch_variants(_PRODUCT_IDS["lights"]):
        models = (v.get("model_name") or "").lower().replace("_", "-")
        if pid_lower in models or "all" in models or not models:
            sku = v.get("name", "")
            val = _safe_float(v.get("value"))
            if sku and val is not None:
                items.append({
                    "sku": sku,
                    "display_name": v.get("display_names", ""),
                    "unit_price": round(val, 2),
                    "pricing_unit": v.get("pricing_unit_list", "unit"),
                    "notes": (v.get("notes") or "").strip(),
                })

    # Fans
    for v in _fetch_variants(_PRODUCT_IDS["fan_upgrade"]):
        sku = v.get("name", "")
        val = _safe_float(v.get("value"))
        if sku and val is not None:
            items.append({
                "sku": sku,
                "display_name": v.get("display_names", ""),
                "unit_price": round(val, 2),
                "pricing_unit": v.get("pricing_unit_list", "each"),
                "notes": (v.get("notes") or "").strip(),
            })

    return items


def get_heater_items() -> list[dict[str, Any]]:
    """Return heater models, beams, and control panels from Heater Surcharges."""
    items: list[dict[str, Any]] = []
    for v in _fetch_variants(_PRODUCT_IDS["heaters"]):
        sku = v.get("name", "")
        val = _safe_float(v.get("value"))
        if sku and val is not None:
            items.append({
                "sku": sku,
                "display_name": v.get("display_names", ""),
                "brand": v.get("brand", ""),
                "unit_price": round(val, 2),
                "pricing_unit": v.get("pricing_unit_list", "unit"),
                "notes": (v.get("notes") or "").strip(),
            })
    return items


def get_shade_pricing_table() -> list[dict[str, Any]]:
    """Return motorized shade pricing [{width_ft, height_ft, sku, unit_price}, ...]."""
    rows: list[dict[str, Any]] = []
    for v in _fetch_variants(_PRODUCT_IDS["motorized_shades"]):
        w = _clean_ft(v.get("width"))
        h = _clean_ft(v.get("height"))
        price = _safe_float(v.get("price"))
        sku = v.get("name", "")
        if w is not None and h is not None and price is not None and price > 0:
            rows.append({
                "width_ft": w,
                "height_ft": h,
                "sku": sku,
                "unit_price": round(price, 2),
            })
    return rows


def get_shade_install_price() -> float:
    """Return per-shade installation price."""
    for v in _fetch_variants(_PRODUCT_IDS["shade_install"]):
        price = _safe_float(v.get("price"))
        if price and price > 0:
            return round(price, 2)
    return 1000.0  # fallback


def get_privacy_wall_pricing() -> list[dict[str, Any]]:
    """Return privacy wall base pricing [{width_ft, height_ft, sku, unit_price, style}, ...]."""
    rows: list[dict[str, Any]] = []
    for v in _fetch_variants(_PRODUCT_IDS["privacy_wall_pricing"]):
        sku = v.get("name", "")
        if not sku or "-SP-" not in sku:
            continue
        w = _clean_ft(v.get("width"))
        h = _clean_ft(v.get("height"))
        val = _safe_float(v.get("value"))
        if w is not None and h is not None and val is not None:
            rows.append({
                "width_ft": w,
                "height_ft": h,
                "sku": sku,
                "unit_price": round(val, 2),
                "style": "spaced",
            })
    return rows


def get_privacy_wall_surcharges() -> list[dict[str, Any]]:
    """Return privacy wall surcharge/add-on items."""
    items: list[dict[str, Any]] = []
    for v in _fetch_variants(_PRODUCT_IDS["privacy_wall_surcharges"]):
        sku = v.get("name", "")
        val = _safe_float(v.get("value"))
        if sku and val is not None:
            items.append({
                "sku": sku,
                "display_name": v.get("display_names", ""),
                "color": v.get("color", ""),
                "unit_price": round(val, 2),
                "pricing_unit": v.get("pricing_unit_list", "unit"),
                "notes": (v.get("notes") or "").strip(),
            })
    return items


def get_trim_items(product_id: str) -> list[dict[str, Any]]:
    """Return trim/architectural upgrade items applicable to a product."""
    items: list[dict[str, Any]] = []
    pid_lower = product_id.lower().replace("_", "-")

    for v in _fetch_variants(_PRODUCT_IDS["trim"]):
        models = (v.get("model_name") or "").lower().replace("_", "-")
        if pid_lower in models or "all" in models or not models:
            sku = v.get("name", "")
            val = _safe_float(v.get("value"))
            if sku and val is not None:
                items.append({
                    "sku": sku,
                    "display_name": v.get("display_names", ""),
                    "unit_price": round(val, 2),
                    "pricing_unit": v.get("pricing_unit_list", "unit"),
                })
    return items


def get_electrical_items() -> list[dict[str, Any]]:
    """Return electrical surcharge items [{name, unit_price, brand}, ...]."""
    items: list[dict[str, Any]] = []
    for v in _fetch_variants(_PRODUCT_IDS["electrical"]):
        name = v.get("name", "")
        price = _safe_float(v.get("price"))
        if name and price is not None and price > 0:
            items.append({
                "name": name,
                "unit_price": round(price, 2),
                "brand": v.get("brand", ""),
            })
    return items


def get_structural_items() -> list[dict[str, Any]]:
    """Return structural post/beam/header items."""
    items: list[dict[str, Any]] = []
    for v in _fetch_variants(_PRODUCT_IDS["structural_posts_beams"]):
        sku = v.get("name", "")
        val = _safe_float(v.get("value"))
        unit = v.get("pricing_unit_list", "")
        display = v.get("display_names") or v.get("model_name") or sku
        if sku and val is not None:
            items.append({
                "sku": sku,
                "description": display,
                "unit_price": round(val, 2),
                "pricing_unit": unit,
            })
    return items


def get_installation_items() -> list[dict[str, Any]]:
    """Return installation surcharge items by state."""
    items: list[dict[str, Any]] = []
    for v in _fetch_variants(_PRODUCT_IDS["installation"]):
        sku = v.get("name", "")
        price = _safe_float(v.get("price"))
        val = _safe_float(v.get("value"))
        if sku:
            items.append({
                "sku": sku,
                "display_name": v.get("display_names", ""),
                "model_name": v.get("model_name", ""),
                "min_price": round(price, 2) if price else 0,
                "rate_per_sqft": round(val, 2) if val else 0,
                "pricing_unit": v.get("pricing_unit_list", ""),
                "notes": (v.get("notes") or "").strip(),
            })
    return items
