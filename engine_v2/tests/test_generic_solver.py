"""Tests for the generic multi-family constraint solver.

Proves that the same ConstraintSolver handles two fundamentally different
product families:
  1. Concealed hinges — paired products (hinge × plate), 10 rules
  2. Drawer slides — single product, 8 rules

Neither family required changes to the solver.
"""

import pytest

# Register families
import engine_v2.families.concealed_hinge  # noqa: F401
import engine_v2.families.drawer_slide  # noqa: F401

from engine_v2.core import ConstraintSolver, registry
from engine_v2.families.concealed_hinge.models import (
    ApplicationType,
    CabinetPosition,
    CabinetType,
    Hinge,
    HingeRequirements,
    HingeSeries,
    MountingMethod,
    Plate,
    Range,
)
from engine_v2.families.drawer_slide.models import (
    DrawerSlide,
    ExtensionType,
    SlideCloseType,
    SlideMountType,
    SlideRequirements,
)


# ===== Test data =====

BLUM_HINGE = Hinge(
    sku="71B3550",
    brand="Blum",
    price_usd=5.50,
    series=HingeSeries.CLIP_TOP_BLUMOTION,
    application=ApplicationType.FULL_OVERLAY,
    opening_angle_deg=110,
    boring_pattern_mm=45,
    door_thickness_range_mm=Range(min=16, max=24),
    max_door_weight_kg=8.0,
    soft_close=True,
    mounting_method=MountingMethod.SCREW_ON,
    cabinet_type=CabinetType.FRAMELESS,
)

BLUM_PLATE = Plate(
    sku="175H7100",
    brand="Blum",
    price_usd=2.00,
    series="CLIP",
    compatible_hinge_series=[HingeSeries.CLIP_TOP_BLUMOTION, HingeSeries.CLIP_TOP],
    mounting_method=MountingMethod.SCREW_ON,
    cabinet_type=CabinetType.FRAMELESS,
    overlay_min_mm=10,
    overlay_max_mm=22,
)

GRASS_HINGE = Hinge(
    sku="T_FULL_110_SC",
    brand="Grass",
    price_usd=6.00,
    series=HingeSeries.TIOMOS,
    application=ApplicationType.FULL_OVERLAY,
    opening_angle_deg=110,
    boring_pattern_mm=45,
    door_thickness_range_mm=Range(min=16, max=24),
    max_door_weight_kg=10.0,
    soft_close=True,
    mounting_method=MountingMethod.SCREW_ON,
    cabinet_type=CabinetType.FRAMELESS,
)

GRASS_PLATE = Plate(
    sku="F060073293",
    brand="Grass",
    price_usd=2.50,
    series="Tiomos",
    compatible_hinge_series=[HingeSeries.TIOMOS],
    mounting_method=MountingMethod.SCREW_ON,
    cabinet_type=CabinetType.FRAMELESS,
    overlay_min_mm=12,
    overlay_max_mm=21,
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


# ===== Registry tests =====

class TestRegistry:
    def test_both_families_registered(self):
        families = registry.list_families()
        assert "concealed_hinge" in families
        assert "drawer_slide" in families

    def test_hinge_family_is_paired(self):
        config = registry.get("concealed_hinge")
        assert config.secondary_type is not None

    def test_slide_family_is_single(self):
        config = registry.get("drawer_slide")
        assert config.secondary_type is None

    def test_unknown_family_raises(self):
        with pytest.raises(KeyError, match="Unknown product family"):
            registry.get("nonexistent_family")


# ===== Concealed hinge tests (paired family) =====

class TestHingeFamily:
    def setup_method(self):
        self.solver = ConstraintSolver(
            family="concealed_hinge",
            primaries=[BLUM_HINGE, GRASS_HINGE],
            secondaries=[BLUM_PLATE, GRASS_PLATE],
        )

    def test_standard_solve_finds_valid_configs(self):
        req = HingeRequirements(
            cabinet_type=CabinetType.FRAMELESS,
            door_thickness_mm=19,
            door_height_mm=720,
            door_weight_kg=5.0,
            application=ApplicationType.FULL_OVERLAY,
            desired_overlay_mm=16,
            boring_pattern_mm=45,
            soft_close=True,
        )
        results = self.solver.solve(req)
        assert len(results) >= 1
        for config in results:
            assert config.valid

    def test_brand_lock_prevents_cross_brand(self):
        """Blum hinge + Grass plate should fail R001."""
        req = HingeRequirements(
            cabinet_type=CabinetType.FRAMELESS,
            door_thickness_mm=19,
            door_height_mm=720,
            door_weight_kg=5.0,
            application=ApplicationType.FULL_OVERLAY,
            desired_overlay_mm=16,
            boring_pattern_mm=45,
            soft_close=False,
        )
        config = self.solver.evaluate(BLUM_HINGE, GRASS_PLATE, req)
        assert not config.valid
        assert config.rule_results[0].rule_id == "R001"
        assert not config.rule_results[0].passed

    def test_early_termination_stops_on_brand_fail(self):
        """With early termination, brand lock failure should skip remaining rules."""
        req = HingeRequirements(
            cabinet_type=CabinetType.FRAMELESS,
            door_thickness_mm=19,
            door_height_mm=720,
            door_weight_kg=5.0,
            application=ApplicationType.FULL_OVERLAY,
            desired_overlay_mm=16,
            boring_pattern_mm=45,
            soft_close=False,
        )
        config = self.solver.evaluate(BLUM_HINGE, GRASS_PLATE, req)
        # Should have stopped after R001 (brand_lock) failed
        assert len(config.rule_results) == 1

    def test_brand_preference_filters(self):
        req = HingeRequirements(
            cabinet_type=CabinetType.FRAMELESS,
            door_thickness_mm=19,
            door_height_mm=720,
            door_weight_kg=5.0,
            application=ApplicationType.FULL_OVERLAY,
            desired_overlay_mm=16,
            boring_pattern_mm=45,
            soft_close=True,
            preferred_brand="Blum",
        )
        results = self.solver.solve(req)
        for config in results:
            assert config.primary.brand == "Blum"

    def test_solve_with_explanation_returns_structure(self):
        req = HingeRequirements(
            cabinet_type=CabinetType.FRAMELESS,
            door_thickness_mm=19,
            door_height_mm=720,
            door_weight_kg=5.0,
            application=ApplicationType.FULL_OVERLAY,
            desired_overlay_mm=16,
            boring_pattern_mm=45,
            soft_close=True,
        )
        result = self.solver.solve_with_explanation(req)
        assert result["status"] == "solved"
        assert "recommended" in result
        assert "alternatives" in result
        assert "constraint_trace" in result["recommended"]

    def test_weight_over_capacity_fails(self):
        req = HingeRequirements(
            cabinet_type=CabinetType.FRAMELESS,
            door_thickness_mm=19,
            door_height_mm=720,
            door_weight_kg=50.0,  # Way too heavy
            application=ApplicationType.FULL_OVERLAY,
            desired_overlay_mm=16,
            boring_pattern_mm=45,
            soft_close=False,
        )
        results = self.solver.solve(req)
        assert len(results) == 0

    def test_corner_cabinet_requires_wide_angle(self):
        req = HingeRequirements(
            cabinet_type=CabinetType.FRAMELESS,
            door_thickness_mm=19,
            door_height_mm=720,
            door_weight_kg=5.0,
            application=ApplicationType.FULL_OVERLAY,
            desired_overlay_mm=16,
            boring_pattern_mm=45,
            soft_close=False,
            cabinet_position=CabinetPosition.CORNER,
        )
        # Both test hinges are 110° — should fail R013 (need >= 155°)
        results = self.solver.solve(req)
        assert len(results) == 0

    def test_hinge_count_derived_from_height(self):
        req = HingeRequirements(
            cabinet_type=CabinetType.FRAMELESS,
            door_thickness_mm=19,
            door_height_mm=1600,  # Tall door — should need 4 hinges
            door_weight_kg=5.0,
            application=ApplicationType.FULL_OVERLAY,
            desired_overlay_mm=16,
            boring_pattern_mm=45,
            soft_close=True,
        )
        results = self.solver.solve(req)
        if results:
            assert results[0].derived["hinges_per_door"] == 4


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


# ===== Cross-family tests =====

class TestCrossFamilyConsistency:
    """Verify that the generic solver produces consistent output regardless of family."""

    def test_solve_with_explanation_has_same_keys(self):
        hinge_solver = ConstraintSolver(
            family="concealed_hinge",
            primaries=[BLUM_HINGE],
            secondaries=[BLUM_PLATE],
        )
        slide_solver = ConstraintSolver(
            family="drawer_slide",
            primaries=[BLUM_SLIDE_FULL],
        )

        hinge_result = hinge_solver.solve_with_explanation(HingeRequirements(
            cabinet_type=CabinetType.FRAMELESS, door_thickness_mm=19,
            door_height_mm=720, door_weight_kg=5.0,
            application=ApplicationType.FULL_OVERLAY, desired_overlay_mm=16,
            boring_pattern_mm=45, soft_close=True,
        ))
        slide_result = slide_solver.solve_with_explanation(SlideRequirements(
            cabinet_depth_mm=550, drawer_weight_kg=10.0,
        ))

        # Both should have the same top-level keys
        assert set(hinge_result.keys()) == set(slide_result.keys())

    def test_constraint_trace_format_consistent(self):
        hinge_solver = ConstraintSolver(
            family="concealed_hinge",
            primaries=[BLUM_HINGE],
            secondaries=[BLUM_PLATE],
        )
        slide_solver = ConstraintSolver(
            family="drawer_slide",
            primaries=[BLUM_SLIDE_FULL],
        )

        hinge_result = hinge_solver.solve_with_explanation(HingeRequirements(
            cabinet_type=CabinetType.FRAMELESS, door_thickness_mm=19,
            door_height_mm=720, door_weight_kg=5.0,
            application=ApplicationType.FULL_OVERLAY, desired_overlay_mm=16,
            boring_pattern_mm=45, soft_close=True,
        ))
        slide_result = slide_solver.solve_with_explanation(SlideRequirements(
            cabinet_depth_mm=550, drawer_weight_kg=10.0,
        ))

        # Both traces should have the same fields per rule
        hinge_trace = hinge_result["recommended"]["constraint_trace"]
        slide_trace = slide_result["recommended"]["constraint_trace"]
        assert set(hinge_trace[0].keys()) == set(slide_trace[0].keys())

    def test_no_solution_format_consistent(self):
        hinge_solver = ConstraintSolver(
            family="concealed_hinge",
            primaries=[BLUM_HINGE],
            secondaries=[BLUM_PLATE],
        )
        slide_solver = ConstraintSolver(
            family="drawer_slide",
            primaries=[BLUM_SLIDE_FULL],
        )

        # Both should fail
        hinge_result = hinge_solver.solve_with_explanation(HingeRequirements(
            cabinet_type=CabinetType.FRAMELESS, door_thickness_mm=19,
            door_height_mm=720, door_weight_kg=5.0,
            application=ApplicationType.FULL_OVERLAY, desired_overlay_mm=16,
            boring_pattern_mm=45, soft_close=False,
            cabinet_position=CabinetPosition.CORNER,  # 110° hinge can't do corner
        ))
        slide_result = slide_solver.solve_with_explanation(SlideRequirements(
            cabinet_depth_mm=200, drawer_weight_kg=100,  # Impossible
        ))

        assert hinge_result["status"] == "no_solution"
        assert slide_result["status"] == "no_solution"
        assert set(hinge_result.keys()) == set(slide_result.keys())
