"""Test data for drawer slide family.

Synthetic fixtures — same products used in the old test_generic_solver.py tests.
"""

from engine_v2.families.drawer_slide.models import (
    DrawerSlide,
    ExtensionType,
    SlideCloseType,
    SlideMountType,
)

BLUM_SLIDE_FULL = DrawerSlide(
    sku="563H5330B",
    brand="Blum",
    price_usd=45.00,
    series="TANDEM plus BLUMOTION",
    slide_length_mm=533,
    max_load_kg=30,
    extension_type=ExtensionType.FULL,
    mount_type=SlideMountType.UNDERMOUNT,
    close_type=SlideCloseType.SOFT_CLOSE,
    requires_rear_bracket=True,
    min_cabinet_depth_mm=10,
    disconnect_feature=True,
)

GRASS_SLIDE = DrawerSlide(
    sku="DWD-XP-533",
    brand="Grass",
    price_usd=35.00,
    series="Dynapro",
    slide_length_mm=500,
    max_load_kg=40,
    extension_type=ExtensionType.FULL,
    mount_type=SlideMountType.UNDERMOUNT,
    close_type=SlideCloseType.SOFT_CLOSE,
    requires_rear_bracket=False,
    min_cabinet_depth_mm=0,
    disconnect_feature=True,
)

BUDGET_SLIDE = DrawerSlide(
    sku="KV-8400-18",
    brand="KV",
    price_usd=8.00,
    series="8400",
    slide_length_mm=450,
    max_load_kg=45,
    extension_type=ExtensionType.THREE_QUARTER,
    mount_type=SlideMountType.SIDE_MOUNT,
    close_type=SlideCloseType.STANDARD,
    requires_rear_bracket=False,
    min_cabinet_depth_mm=0,
    disconnect_feature=False,
)

CENTER_SLIDE = DrawerSlide(
    sku="KV-CM-450",
    brand="KV",
    price_usd=6.00,
    series="Center Mount",
    slide_length_mm=450,
    max_load_kg=15,
    extension_type=ExtensionType.THREE_QUARTER,
    mount_type=SlideMountType.CENTER_MOUNT,
    close_type=SlideCloseType.SELF_CLOSE,
    requires_rear_bracket=False,
    min_cabinet_depth_mm=0,
    disconnect_feature=False,
)

ALL_SLIDES = [BLUM_SLIDE_FULL, GRASS_SLIDE, BUDGET_SLIDE, CENTER_SLIDE]
