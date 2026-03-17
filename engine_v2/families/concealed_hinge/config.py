"""Concealed hinge family registration."""

from engine_v2.core.models import Product, Requirements
from engine_v2.core.registry import FamilyConfig, registry
from engine_v2.families.concealed_hinge.models import (
    CabinetType,
    Hinge,
    HingeRequirements,
    Plate,
)
from engine_v2.families.concealed_hinge.rules import RULES


# --- Pre-filters ---

def filter_by_brand(products: list[Product], req: Requirements) -> list[Product]:
    r = HingeRequirements.model_validate(req.model_dump())
    if not r.preferred_brand:
        return products
    return [p for p in products if p.brand == r.preferred_brand]


def filter_by_cabinet_type(products: list[Product], req: Requirements) -> list[Product]:
    r = HingeRequirements.model_validate(req.model_dump())
    return [p for p in products if isinstance(p, Hinge) and p.cabinet_type == r.cabinet_type]


def filter_by_application(products: list[Product], req: Requirements) -> list[Product]:
    r = HingeRequirements.model_validate(req.model_dump())
    return [p for p in products if isinstance(p, Hinge) and p.application == r.application]


# --- Derived values ---

_HEIGHT_THRESHOLDS = [(889, 2), (1400, 3), (1800, 4)]


def compute_derived(req: Requirements) -> dict:
    r = HingeRequirements.model_validate(req.model_dump())
    num_hinges = 5  # default for very tall doors
    for threshold, count in _HEIGHT_THRESHOLDS:
        if r.door_height_mm <= threshold:
            num_hinges = count
            break
    return {"hinges_per_door": num_hinges, "quantity": num_hinges}


# --- Ranking ---

def rank_hinge_config(config) -> tuple:
    price = config.total_price_usd
    # Derive capacity from primary
    h = config.primary
    num = config.derived.get("hinges_per_door", 2)
    capacity = h.max_door_weight_kg * num if isinstance(h, Hinge) else 0
    return (
        0 if price is not None else 1,  # priced first
        price or 0,                      # cheapest first
        -capacity,                       # highest capacity first (tiebreaker)
    )


# --- Registration ---

def register():
    registry.register(FamilyConfig(
        name="concealed_hinge",
        primary_type=Hinge,
        secondary_type=Plate,
        requirements_type=HingeRequirements,
        rules=RULES,
        pre_filters=[filter_by_brand, filter_by_cabinet_type, filter_by_application],
        rank_key=rank_hinge_config,
        derived_values=compute_derived,
        early_termination=True,
    ))
