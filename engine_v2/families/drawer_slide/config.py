"""Drawer slide family — N-candidate solver configuration.

Single-product family: N=1, one role ("slide"), no Cartesian product.
"""

from __future__ import annotations

from engine_v2.core.models import Product, Requirements
from engine_v2.core.solver_n import NFamilyConfig
from engine_v2.families.drawer_slide.models import (
    DrawerSlide,
    SlideRequirements,
)
from engine_v2.families.drawer_slide.rules import RULES


# --- Pre-filters ---

def pre_filter_slides(role: str, products: list[Product], req: Requirements) -> list[Product]:
    """Filter slides by brand preference and mount type."""
    if role != "slide":
        return products

    r = SlideRequirements.model_validate(req.model_dump())
    filtered = products

    if r.preferred_brand:
        filtered = [p for p in filtered if p.brand == r.preferred_brand]

    if r.mount_type is not None:
        filtered = [
            p for p in filtered
            if isinstance(p, DrawerSlide) and p.mount_type == r.mount_type
        ]

    return filtered


# --- Ranking ---

def rank_config(config) -> tuple:
    price = config.total_price_usd
    slide = config.candidates.get("slide")
    capacity = slide.max_load_kg if isinstance(slide, DrawerSlide) else 0
    return (
        0 if price is not None else 1,
        price or 0,
        -capacity,
    )


# --- Config ---

SLIDE_N_CONFIG = NFamilyConfig(
    name="drawer_slide",
    roles=[
        ("slide", DrawerSlide),
    ],
    requirements_type=SlideRequirements,
    rules=RULES,
    pre_filters=[pre_filter_slides],
    rank_key=rank_config,
    early_termination=True,
)
