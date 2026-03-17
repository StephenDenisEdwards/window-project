"""Drawer slide family registration."""

from engine_v2.core.models import Product, Requirements
from engine_v2.core.registry import FamilyConfig, registry
from engine_v2.families.drawer_slide.models import (
    DrawerSlide,
    SlideRequirements,
    SlideMountType,
)
from engine_v2.families.drawer_slide.rules import RULES


# --- Pre-filters ---

def filter_by_brand(products: list[Product], req: Requirements) -> list[Product]:
    if not req.preferred_brand:
        return products
    return [p for p in products if p.brand == req.preferred_brand]


def filter_by_mount_type(products: list[Product], req: Requirements) -> list[Product]:
    r = SlideRequirements.model_validate(req.model_dump())
    if r.mount_type is None:
        return products
    return [p for p in products if isinstance(p, DrawerSlide) and p.mount_type == r.mount_type]


# --- Ranking ---

def rank_slide_config(config) -> tuple:
    price = config.total_price_usd
    slide = config.primary
    capacity = slide.max_load_kg if isinstance(slide, DrawerSlide) else 0
    return (
        0 if price is not None else 1,  # priced first
        price or 0,                      # cheapest first
        -capacity,                       # highest capacity first (tiebreaker)
    )


# --- Registration ---

def register():
    registry.register(FamilyConfig(
        name="drawer_slide",
        primary_type=DrawerSlide,
        secondary_type=None,  # Single-product family — no pairing
        requirements_type=SlideRequirements,
        rules=RULES,
        pre_filters=[filter_by_brand, filter_by_mount_type],
        rank_key=rank_slide_config,
        early_termination=True,
    ))
