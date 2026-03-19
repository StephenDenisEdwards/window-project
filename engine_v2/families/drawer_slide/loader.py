"""Load sample-data/ JSON into v2 drawer slide models."""

from __future__ import annotations

import json
from pathlib import Path

from .models import (
    DrawerSlide,
    ExtensionType,
    SlideCloseType,
    SlideMountType,
)


def load_from_json(data_dir: Path) -> list[DrawerSlide]:
    """Load drawer slides from JSON file."""
    with open(data_dir / "drawer_slides.json") as f:
        raw_slides = json.load(f)

    return [
        DrawerSlide(
            sku=s["sku"],
            brand=s["brand"],
            price_usd=s.get("price_usd"),
            series=s["series"],
            slide_length_mm=s["slide_length_mm"],
            max_load_kg=s["max_load_kg"],
            extension_type=ExtensionType(s["extension_type"]),
            mount_type=SlideMountType(s["mount_type"]),
            close_type=SlideCloseType(s["close_type"]),
            requires_rear_bracket=s.get("requires_rear_bracket", False),
            min_cabinet_depth_mm=s.get("min_cabinet_depth_mm", 0),
            disconnect_feature=s.get("disconnect_feature", False),
        )
        for s in raw_slides
    ]
