"""Tests for the generic paired constraint solver (drawer slides).

The concealed hinge family has migrated to the N-candidate solver — see
test_hinge_n_candidate.py. This file tests the paired ConstraintSolver
with the drawer slide family (single-product, N=1).
"""

import pytest

# Register drawer slide family
import engine_v2.families.drawer_slide  # noqa: F401

from engine_v2.core import ConstraintSolver, registry
from engine_v2.families.drawer_slide.models import (
    DrawerSlide,
    ExtensionType,
    SlideCloseType,
    SlideMountType,
    SlideRequirements,
)


# ===== Test data =====

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


# ===== Registry tests =====

class TestRegistry:
    def test_slide_family_registered(self):
        families = registry.list_families()
        assert "drawer_slide" in families

    def test_slide_family_is_single(self):
        config = registry.get("drawer_slide")
        assert config.secondary_type is None

    def test_unknown_family_raises(self):
        with pytest.raises(KeyError, match="Unknown product family"):
            registry.get("nonexistent_family")


# ===== Drawer slide tests (single-product family) =====

class TestSlideFamily:
    def setup_method(self):
        self.solver = ConstraintSolver(
            family="drawer_slide",
            primaries=[BLUM_SLIDE_FULL, GRASS_SLIDE, BUDGET_SLIDE, CENTER_SLIDE],
        )

    def test_standard_solve_finds_slides(self):
        req = SlideRequirements(
            cabinet_depth_mm=550,
            drawer_weight_kg=15.0,
        )
        results = self.solver.solve(req)
        assert len(results) >= 1
        for config in results:
            assert config.valid
            assert config.secondary is None  # Single-product family

    def test_load_capacity_eliminates_weak_slides(self):
        req = SlideRequirements(
            cabinet_depth_mm=550,
            drawer_weight_kg=42.0,  # Only Grass (40kg) and Budget (45kg) might work
        )
        results = self.solver.solve(req)
        # Center mount (15kg) and Blum (30kg) should be eliminated
        for config in results:
            slide = DrawerSlide.model_validate(config.primary.model_dump())
            assert slide.max_load_kg >= 42.0

    def test_cabinet_depth_too_shallow(self):
        req = SlideRequirements(
            cabinet_depth_mm=300,  # Too shallow for 450mm+ slides
            drawer_weight_kg=5.0,
        )
        results = self.solver.solve(req)
        assert len(results) == 0

    def test_extension_type_filter(self):
        req = SlideRequirements(
            cabinet_depth_mm=550,
            drawer_weight_kg=10.0,
            extension_type=ExtensionType.FULL,
        )
        results = self.solver.solve(req)
        for config in results:
            slide = DrawerSlide.model_validate(config.primary.model_dump())
            assert slide.extension_type == ExtensionType.FULL

    def test_mount_type_filter(self):
        req = SlideRequirements(
            cabinet_depth_mm=550,
            drawer_weight_kg=10.0,
            mount_type=SlideMountType.UNDERMOUNT,
        )
        results = self.solver.solve(req)
        for config in results:
            slide = DrawerSlide.model_validate(config.primary.model_dump())
            assert slide.mount_type == SlideMountType.UNDERMOUNT

    def test_soft_close_preference(self):
        req = SlideRequirements(
            cabinet_depth_mm=550,
            drawer_weight_kg=10.0,
            soft_close=True,
        )
        results = self.solver.solve(req)
        for config in results:
            slide = DrawerSlide.model_validate(config.primary.model_dump())
            assert slide.close_type == SlideCloseType.SOFT_CLOSE

    def test_brand_preference(self):
        req = SlideRequirements(
            cabinet_depth_mm=550,
            drawer_weight_kg=10.0,
            preferred_brand="Blum",
        )
        results = self.solver.solve(req)
        for config in results:
            assert config.primary.brand == "Blum"

    def test_solve_with_explanation_no_solution(self):
        req = SlideRequirements(
            cabinet_depth_mm=200,  # Way too shallow
            drawer_weight_kg=100,  # Way too heavy
        )
        result = self.solver.solve_with_explanation(req)
        assert result["status"] == "no_solution"
        assert len(result["failed_rules"]) > 0

    def test_solve_with_explanation_solved(self):
        req = SlideRequirements(
            cabinet_depth_mm=550,
            drawer_weight_kg=10.0,
        )
        result = self.solver.solve_with_explanation(req)
        assert result["status"] == "solved"
        assert result["recommended"]["secondary"] is None  # No paired product

    def test_ranked_by_price(self):
        req = SlideRequirements(
            cabinet_depth_mm=550,
            drawer_weight_kg=10.0,
        )
        results = self.solver.solve(req)
        prices = [c.total_price_usd for c in results if c.total_price_usd is not None]
        assert prices == sorted(prices)

    def test_disconnect_required(self):
        req = SlideRequirements(
            cabinet_depth_mm=550,
            drawer_weight_kg=10.0,
            disconnect_required=True,
        )
        results = self.solver.solve(req)
        for config in results:
            slide = DrawerSlide.model_validate(config.primary.model_dump())
            assert slide.disconnect_feature
