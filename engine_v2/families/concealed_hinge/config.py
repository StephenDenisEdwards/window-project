"""Concealed hinge family registration for the N-candidate solver."""

from __future__ import annotations

from engine_v2.core.models import Product, Requirements
from engine_v2.core.solver_n import NFamilyConfig
from engine_v2.families.concealed_hinge.models import (
    Hinge,
    HingeRequirements,
    Plate,
)
from engine_v2.families.concealed_hinge.rules import RULES, hinges_per_door


# --- Pre-filters ---

def pre_filter_hinges(role: str, products: list[Product], req: Requirements) -> list[Product]:
    """Filter hinges by application, cabinet type, and brand. Pass plates through."""
    if role != "hinge":
        return products

    r = HingeRequirements.model_validate(req.model_dump())
    filtered = []
    for p in products:
        h = Hinge.model_validate(p.model_dump())
        if h.application.value != r.application.value:
            continue
        if h.cabinet_type != r.cabinet_type:
            continue
        if r.preferred_brand and h.brand != r.preferred_brand:
            continue
        filtered.append(p)
    return filtered


# --- Derived values ---

def compute_derived(req: Requirements) -> dict:
    r = HingeRequirements.model_validate(req.model_dump())
    num = hinges_per_door(r.door_height_mm)
    return {"hinges_per_door": num, "quantity": num}


# --- Ranking ---

def rank_config(config) -> tuple:
    price = config.total_price_usd
    h = config.candidates.get("hinge")
    num = config.derived.get("hinges_per_door", 2)
    capacity = h.max_door_weight_kg * num if isinstance(h, Hinge) else 0
    return (
        0 if price is not None else 1,
        price or 0,
        -capacity,
    )


# --- Config ---

HINGE_N_CONFIG = NFamilyConfig(
    name="concealed_hinge",
    roles=[
        ("hinge", Hinge),
        ("plate", Plate),
    ],
    requirements_type=HingeRequirements,
    rules=RULES,
    pre_filters=[pre_filter_hinges],
    rank_key=rank_config,
    derived_values=compute_derived,
    early_termination=True,
)
