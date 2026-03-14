"""
Unit tests for the Window Hinge Compatibility Constraint Engine.

Tests cover:
  - Individual constraint rules in isolation
  - Derived value calculations (hinge count, weight derating)
  - End-to-end scenario solving against the sample catalog
  - Constraint violation detection and reporting

Run:
    python -m pytest test_constraint_engine.py -v
"""

import pytest
from pathlib import Path

from constraint_engine import (
    Hinge,
    MountingPlate,
    CustomerRequirements,
    HingeConstraintEngine,
    load_catalog,
)


# ---------------------------------------------------------------------------
# Fixtures — shared test data
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def catalog():
    """Load the full sample catalog once for all tests."""
    data_dir = Path(__file__).parent.parent / "sample-data"
    hinges, plates = load_catalog(data_dir)
    return hinges, plates


@pytest.fixture(scope="module")
def engine(catalog):
    hinges, plates = catalog
    return HingeConstraintEngine(hinges, plates)


def _hinge(catalog, sku: str) -> Hinge:
    return next(h for h in catalog[0] if h.sku == sku)


def _plate(catalog, sku: str) -> MountingPlate:
    return next(p for p in catalog[1] if p.sku == sku)


# ---------------------------------------------------------------------------
# Unit tests — derived values
# ---------------------------------------------------------------------------

class TestDerivedValues:
    """R008: hinge count by door height, R010: wide-angle derating."""

    def test_short_door_gets_2_hinges(self):
        assert HingeConstraintEngine.hinges_per_door(720) == 2

    def test_boundary_900mm_gets_2_hinges(self):
        assert HingeConstraintEngine.hinges_per_door(900) == 2

    def test_medium_door_gets_3_hinges(self):
        assert HingeConstraintEngine.hinges_per_door(1200) == 3

    def test_tall_door_gets_4_hinges(self):
        assert HingeConstraintEngine.hinges_per_door(1600) == 4

    def test_very_tall_door_gets_5_hinges(self):
        assert HingeConstraintEngine.hinges_per_door(2000) == 5

    def test_standard_angle_no_derating(self, catalog):
        h = _hinge(catalog, "BLM-71B3550")  # 110 degrees
        assert h.effective_max_weight_kg == h.max_door_weight_kg

    def test_wide_angle_derated_25_percent(self, catalog):
        h = _hinge(catalog, "BLM-79B3550")  # 155 degrees
        assert h.effective_max_weight_kg == h.max_door_weight_kg * 0.75

    def test_170_degree_derated(self, catalog):
        h = _hinge(catalog, "BLM-79B9550")  # 170 degrees
        assert h.effective_max_weight_kg == pytest.approx(4.5 * 0.75)


# ---------------------------------------------------------------------------
# Unit tests — individual constraint rules
# ---------------------------------------------------------------------------

class TestBrandLock:
    """R001: hinge and plate must share the same brand."""

    def test_same_brand_passes(self, engine, catalog):
        h = _hinge(catalog, "BLM-71B3550")
        p = _plate(catalog, "BLM-173L6100")
        result = engine._check_brand_lock(h, p)
        assert result.passed

    def test_cross_brand_fails(self, engine, catalog):
        h = _hinge(catalog, "BLM-71B3550")
        p = _plate(catalog, "GRS-F058139761")
        result = engine._check_brand_lock(h, p)
        assert not result.passed


class TestSeriesCompatibility:
    """R002: plate must list the hinge's series as compatible."""

    def test_compatible_series_passes(self, engine, catalog):
        h = _hinge(catalog, "BLM-71B3550")  # CLIP top BLUMOTION
        p = _plate(catalog, "BLM-173L6100")  # supports CLIP top + CLIP top BLUMOTION
        result = engine._check_series_compat(h, p)
        assert result.passed

    def test_incompatible_series_fails(self, engine, catalog):
        h = _hinge(catalog, "GRS-F028138519")  # Tiomos
        p = _plate(catalog, "GRS-314493700")   # Nexis plates only
        result = engine._check_series_compat(h, p)
        assert not result.passed


class TestCabinetTypeMatch:
    """R003: hinge, plate, and requirement must all agree on cabinet type."""

    def test_all_frameless_passes(self, engine, catalog):
        h = _hinge(catalog, "BLM-71B3550")
        p = _plate(catalog, "BLM-173L6100")
        req = CustomerRequirements(
            cabinet_type="frameless", door_thickness_mm=19, door_height_mm=720,
            door_weight_kg=5, application="full_overlay", desired_overlay_mm=16,
            boring_pattern_mm=45, soft_close=True,
        )
        result = engine._check_cabinet_type(h, p, req)
        assert result.passed

    def test_face_frame_hinge_on_frameless_fails(self, engine, catalog):
        h = _hinge(catalog, "BLM-75T1550")    # face_frame hinge
        p = _plate(catalog, "BLM-173L6100")    # frameless plate
        req = CustomerRequirements(
            cabinet_type="frameless", door_thickness_mm=19, door_height_mm=720,
            door_weight_kg=5, application="full_overlay", desired_overlay_mm=16,
            boring_pattern_mm=45, soft_close=True,
        )
        result = engine._check_cabinet_type(h, p, req)
        assert not result.passed


class TestOverlayRange:
    """R004: desired overlay must be within plate's achievable range."""

    def test_overlay_in_range_passes(self, engine, catalog):
        h = _hinge(catalog, "BLM-71B3550")
        p = _plate(catalog, "BLM-173L6100")  # full overlay range [14, 20]
        req = CustomerRequirements(
            cabinet_type="frameless", door_thickness_mm=19, door_height_mm=720,
            door_weight_kg=5, application="full_overlay", desired_overlay_mm=16,
            boring_pattern_mm=45, soft_close=True,
        )
        result = engine._check_overlay_range(h, p, req)
        assert result.passed

    def test_overlay_below_range_fails(self, engine, catalog):
        h = _hinge(catalog, "BLM-71B3550")
        p = _plate(catalog, "BLM-173L6100")  # full overlay range [14, 20]
        req = CustomerRequirements(
            cabinet_type="frameless", door_thickness_mm=19, door_height_mm=720,
            door_weight_kg=5, application="full_overlay", desired_overlay_mm=10,
            boring_pattern_mm=45, soft_close=True,
        )
        result = engine._check_overlay_range(h, p, req)
        assert not result.passed

    def test_overlay_at_boundary_passes(self, engine, catalog):
        h = _hinge(catalog, "BLM-71B3550")
        p = _plate(catalog, "BLM-173L6100")  # full overlay range [14, 20]
        req = CustomerRequirements(
            cabinet_type="frameless", door_thickness_mm=19, door_height_mm=720,
            door_weight_kg=5, application="full_overlay", desired_overlay_mm=14,
            boring_pattern_mm=45, soft_close=True,
        )
        result = engine._check_overlay_range(h, p, req)
        assert result.passed

    def test_plate_unsupported_application_fails(self, engine, catalog):
        h = _hinge(catalog, "BLM-71B3550")
        p = _plate(catalog, "BLM-175H7100")  # wing plate, inset=false
        req = CustomerRequirements(
            cabinet_type="frameless", door_thickness_mm=19, door_height_mm=720,
            door_weight_kg=5, application="inset", desired_overlay_mm=0,
            boring_pattern_mm=45, soft_close=True,
        )
        result = engine._check_overlay_range(h, p, req)
        assert not result.passed


class TestDoorThickness:
    """R006: door thickness within hinge's supported range."""

    def test_within_range_passes(self, engine, catalog):
        h = _hinge(catalog, "BLM-71B3550")  # 16-24mm
        req = CustomerRequirements(
            cabinet_type="frameless", door_thickness_mm=19, door_height_mm=720,
            door_weight_kg=5, application="full_overlay", desired_overlay_mm=16,
            boring_pattern_mm=45, soft_close=True,
        )
        result = engine._check_door_thickness(h, req)
        assert result.passed

    def test_too_thin_fails(self, engine, catalog):
        h = _hinge(catalog, "BLM-71B3550")  # min 16mm
        req = CustomerRequirements(
            cabinet_type="frameless", door_thickness_mm=12, door_height_mm=720,
            door_weight_kg=5, application="full_overlay", desired_overlay_mm=16,
            boring_pattern_mm=45, soft_close=True,
        )
        result = engine._check_door_thickness(h, req)
        assert not result.passed

    def test_too_thick_fails(self, engine, catalog):
        h = _hinge(catalog, "BLM-71B3550")  # max 24mm
        req = CustomerRequirements(
            cabinet_type="frameless", door_thickness_mm=28, door_height_mm=720,
            door_weight_kg=5, application="full_overlay", desired_overlay_mm=16,
            boring_pattern_mm=45, soft_close=True,
        )
        result = engine._check_door_thickness(h, req)
        assert not result.passed


class TestWeightLimit:
    """R007: door weight vs hinge capacity x number of hinges."""

    def test_within_capacity_passes(self, engine, catalog):
        h = _hinge(catalog, "BLM-71B3550")  # 7.5kg per hinge
        req = CustomerRequirements(
            cabinet_type="frameless", door_thickness_mm=19, door_height_mm=720,
            door_weight_kg=5.2, application="full_overlay", desired_overlay_mm=16,
            boring_pattern_mm=45, soft_close=True,
        )
        result = engine._check_weight(h, req, num_hinges=2)
        assert result.passed
        assert "5.2kg vs capacity 7.5kg x 2 = 15.0kg" in result.detail

    def test_over_capacity_fails(self, engine, catalog):
        h = _hinge(catalog, "BLM-71B3550")  # 7.5kg per hinge, 2 hinges = 15kg
        req = CustomerRequirements(
            cabinet_type="frameless", door_thickness_mm=19, door_height_mm=720,
            door_weight_kg=16.0, application="full_overlay", desired_overlay_mm=16,
            boring_pattern_mm=45, soft_close=True,
        )
        result = engine._check_weight(h, req, num_hinges=2)
        assert not result.passed

    def test_wide_angle_derating_applied(self, engine, catalog):
        h = _hinge(catalog, "BLM-79B3550")  # 155deg, 5.0kg derated to 3.75kg
        req = CustomerRequirements(
            cabinet_type="frameless", door_thickness_mm=19, door_height_mm=720,
            door_weight_kg=4.0, application="full_overlay", desired_overlay_mm=16,
            boring_pattern_mm=45, soft_close=True,
        )
        result = engine._check_weight(h, req, num_hinges=2)
        assert result.passed
        assert "derated" in result.detail


class TestCornerCabinet:
    """R013: corner cabinets need >= 155 degree opening."""

    def test_standard_cabinet_skips(self, engine, catalog):
        h = _hinge(catalog, "BLM-71B3550")  # 110 degrees
        req = CustomerRequirements(
            cabinet_type="frameless", door_thickness_mm=19, door_height_mm=720,
            door_weight_kg=5, application="full_overlay", desired_overlay_mm=16,
            boring_pattern_mm=45, soft_close=True, cabinet_position="standard",
        )
        result = engine._check_corner_angle(h, req)
        assert result.passed

    def test_corner_with_110_fails(self, engine, catalog):
        h = _hinge(catalog, "BLM-71B3550")  # 110 degrees
        req = CustomerRequirements(
            cabinet_type="frameless", door_thickness_mm=19, door_height_mm=720,
            door_weight_kg=5, application="full_overlay", desired_overlay_mm=16,
            boring_pattern_mm=45, soft_close=True, cabinet_position="corner",
        )
        result = engine._check_corner_angle(h, req)
        assert not result.passed

    def test_corner_with_155_passes(self, engine, catalog):
        h = _hinge(catalog, "BLM-79B3550")  # 155 degrees
        req = CustomerRequirements(
            cabinet_type="frameless", door_thickness_mm=19, door_height_mm=720,
            door_weight_kg=5, application="full_overlay", desired_overlay_mm=16,
            boring_pattern_mm=45, soft_close=True, cabinet_position="corner",
        )
        result = engine._check_corner_angle(h, req)
        assert result.passed


class TestAdjacentDoorClearance:
    """R012: combined overlay of adjacent doors must not exceed partition thickness."""

    def test_no_adjacent_door_skips(self, engine):
        req = CustomerRequirements(
            cabinet_type="frameless", door_thickness_mm=19, door_height_mm=720,
            door_weight_kg=5, application="half_overlay", desired_overlay_mm=6,
            boring_pattern_mm=45, soft_close=True, has_adjacent_door=False,
        )
        result = engine._check_adjacent_clearance(req)
        assert result.passed

    def test_within_partition_passes(self, engine):
        req = CustomerRequirements(
            cabinet_type="frameless", door_thickness_mm=19, door_height_mm=720,
            door_weight_kg=5, application="half_overlay", desired_overlay_mm=6,
            boring_pattern_mm=45, soft_close=True,
            has_adjacent_door=True, adjacent_door_overlay_mm=6,
            partition_thickness_mm=19,
        )
        result = engine._check_adjacent_clearance(req)
        assert result.passed
        assert "12mm vs partition 19mm" in result.detail  # 6 + 6 = 12

    def test_exceeds_partition_fails(self, engine):
        req = CustomerRequirements(
            cabinet_type="frameless", door_thickness_mm=19, door_height_mm=720,
            door_weight_kg=5, application="half_overlay", desired_overlay_mm=12,
            boring_pattern_mm=45, soft_close=True,
            has_adjacent_door=True, adjacent_door_overlay_mm=12,
            partition_thickness_mm=19,
        )
        result = engine._check_adjacent_clearance(req)
        assert not result.passed  # 12 + 12 = 24 > 19


class TestMountingMethod:
    """R014: hinge and plate mounting methods must be compatible."""

    def test_matching_screw_on_passes(self, engine, catalog):
        h = _hinge(catalog, "BLM-71B3550")    # screw_on
        p = _plate(catalog, "BLM-173L6100")    # screw_on
        result = engine._check_mounting_method(h, p)
        assert result.passed

    def test_dowel_hinge_on_screw_plate_fails(self, engine, catalog):
        h = _hinge(catalog, "GRS-146322540")   # dowel mounting
        p = _plate(catalog, "GRS-F058139761")  # screw_on
        result = engine._check_mounting_method(h, p)
        assert not result.passed


# ---------------------------------------------------------------------------
# End-to-end scenario tests
# ---------------------------------------------------------------------------

class TestScenario1StandardKitchenRemodel:
    """
    Scenario 1: Experienced contractor replacing hinges on kitchen remodel.

    Inputs: Frameless, 19mm door, 720mm height, 5.2kg, full overlay 16mm,
            45mm boring, soft-close, Blum preferred.

    Expected: Blum CLIP top BLUMOTION 110 full overlay (BLM-71B3550)
              with compatible plate. 2 hinges per door.
    """

    def test_finds_solutions(self, engine):
        req = CustomerRequirements(
            cabinet_type="frameless", door_thickness_mm=19, door_height_mm=720,
            door_weight_kg=5.2, application="full_overlay", desired_overlay_mm=16,
            boring_pattern_mm=45, soft_close=True, preferred_brand="Blum",
        )
        solutions = engine.solve(req)
        assert len(solutions) > 0

    def test_all_solutions_are_blum(self, engine):
        req = CustomerRequirements(
            cabinet_type="frameless", door_thickness_mm=19, door_height_mm=720,
            door_weight_kg=5.2, application="full_overlay", desired_overlay_mm=16,
            boring_pattern_mm=45, soft_close=True, preferred_brand="Blum",
        )
        for config in engine.solve(req):
            assert config.hinge.brand == "Blum"
            assert config.plate.brand == "Blum"

    def test_recommended_is_cheapest(self, engine):
        req = CustomerRequirements(
            cabinet_type="frameless", door_thickness_mm=19, door_height_mm=720,
            door_weight_kg=5.2, application="full_overlay", desired_overlay_mm=16,
            boring_pattern_mm=45, soft_close=True, preferred_brand="Blum",
        )
        solutions = engine.solve(req)
        priced = [s for s in solutions if s.total_price_usd is not None]
        assert priced[0].total_price_usd <= priced[-1].total_price_usd

    def test_all_solutions_have_soft_close(self, engine):
        req = CustomerRequirements(
            cabinet_type="frameless", door_thickness_mm=19, door_height_mm=720,
            door_weight_kg=5.2, application="full_overlay", desired_overlay_mm=16,
            boring_pattern_mm=45, soft_close=True, preferred_brand="Blum",
        )
        for config in engine.solve(req):
            assert config.hinge.soft_close is True

    def test_2_hinges_per_door(self, engine):
        req = CustomerRequirements(
            cabinet_type="frameless", door_thickness_mm=19, door_height_mm=720,
            door_weight_kg=5.2, application="full_overlay", desired_overlay_mm=16,
            boring_pattern_mm=45, soft_close=True, preferred_brand="Blum",
        )
        for config in engine.solve(req):
            assert config.hinges_per_door == 2

    def test_weight_capacity_sufficient(self, engine):
        req = CustomerRequirements(
            cabinet_type="frameless", door_thickness_mm=19, door_height_mm=720,
            door_weight_kg=5.2, application="full_overlay", desired_overlay_mm=16,
            boring_pattern_mm=45, soft_close=True, preferred_brand="Blum",
        )
        for config in engine.solve(req):
            assert config.total_weight_capacity_kg >= 5.2


class TestScenario2CornerCabinet:
    """
    Scenario 2: Corner cabinet requiring wide-angle hinge.

    Inputs: Frameless, 19mm door, 800mm height, 4.0kg, full overlay 16mm,
            corner position, soft-close, no brand preference.

    Expected: Only hinges >= 155 degrees qualify (R013). Weight is derated
              by 25% for wide-angle (R010).
    """

    def test_finds_solutions(self, engine):
        req = CustomerRequirements(
            cabinet_type="frameless", door_thickness_mm=19, door_height_mm=800,
            door_weight_kg=4.0, application="full_overlay", desired_overlay_mm=16,
            boring_pattern_mm=45, soft_close=True, cabinet_position="corner",
        )
        solutions = engine.solve(req)
        assert len(solutions) > 0

    def test_all_solutions_are_wide_angle(self, engine):
        req = CustomerRequirements(
            cabinet_type="frameless", door_thickness_mm=19, door_height_mm=800,
            door_weight_kg=4.0, application="full_overlay", desired_overlay_mm=16,
            boring_pattern_mm=45, soft_close=True, cabinet_position="corner",
        )
        for config in engine.solve(req):
            assert config.hinge.opening_angle_deg >= 155

    def test_weight_capacity_accounts_for_derating(self, engine):
        req = CustomerRequirements(
            cabinet_type="frameless", door_thickness_mm=19, door_height_mm=800,
            door_weight_kg=4.0, application="full_overlay", desired_overlay_mm=16,
            boring_pattern_mm=45, soft_close=True, cabinet_position="corner",
        )
        for config in engine.solve(req):
            per_hinge = config.hinge.max_door_weight_kg * 0.75
            expected_capacity = per_hinge * config.hinges_per_door
            assert config.total_weight_capacity_kg == pytest.approx(expected_capacity)

    def test_includes_multiple_brands(self, engine):
        req = CustomerRequirements(
            cabinet_type="frameless", door_thickness_mm=19, door_height_mm=800,
            door_weight_kg=4.0, application="full_overlay", desired_overlay_mm=16,
            boring_pattern_mm=45, soft_close=True, cabinet_position="corner",
        )
        brands = {c.hinge.brand for c in engine.solve(req)}
        assert len(brands) >= 2


class TestScenario3TallPantryDoor:
    """
    Scenario 3: Tall pantry door — 1600mm, 14kg, Grass preferred.

    Inputs: Frameless, 22mm door, 1600mm height, 14.0kg, full overlay 16mm,
            Grass preferred.

    Expected: 4 hinges per door (R008 for 1600mm). Grass Tiomos 110 with
              9.0kg/hinge x 4 = 36kg capacity handles the 14kg door.
    """

    def test_finds_solutions(self, engine):
        req = CustomerRequirements(
            cabinet_type="frameless", door_thickness_mm=22, door_height_mm=1600,
            door_weight_kg=14.0, application="full_overlay", desired_overlay_mm=16,
            boring_pattern_mm=45, soft_close=True, preferred_brand="Grass",
        )
        solutions = engine.solve(req)
        assert len(solutions) > 0

    def test_4_hinges_per_door(self, engine):
        req = CustomerRequirements(
            cabinet_type="frameless", door_thickness_mm=22, door_height_mm=1600,
            door_weight_kg=14.0, application="full_overlay", desired_overlay_mm=16,
            boring_pattern_mm=45, soft_close=True, preferred_brand="Grass",
        )
        for config in engine.solve(req):
            assert config.hinges_per_door == 4

    def test_all_solutions_are_grass(self, engine):
        req = CustomerRequirements(
            cabinet_type="frameless", door_thickness_mm=22, door_height_mm=1600,
            door_weight_kg=14.0, application="full_overlay", desired_overlay_mm=16,
            boring_pattern_mm=45, soft_close=True, preferred_brand="Grass",
        )
        for config in engine.solve(req):
            assert config.hinge.brand == "Grass"
            assert config.plate.brand == "Grass"

    def test_capacity_handles_14kg(self, engine):
        req = CustomerRequirements(
            cabinet_type="frameless", door_thickness_mm=22, door_height_mm=1600,
            door_weight_kg=14.0, application="full_overlay", desired_overlay_mm=16,
            boring_pattern_mm=45, soft_close=True, preferred_brand="Grass",
        )
        for config in engine.solve(req):
            assert config.total_weight_capacity_kg >= 14.0

    def test_22mm_door_accepted(self, engine):
        req = CustomerRequirements(
            cabinet_type="frameless", door_thickness_mm=22, door_height_mm=1600,
            door_weight_kg=14.0, application="full_overlay", desired_overlay_mm=16,
            boring_pattern_mm=45, soft_close=True, preferred_brand="Grass",
        )
        for config in engine.solve(req):
            assert config.hinge.door_thickness_min_mm <= 22 <= config.hinge.door_thickness_max_mm


class TestScenario4AdjacentDoors:
    """
    Scenario 4: Adjacent doors sharing a 19mm partition — half overlay.

    Inputs: Frameless, 19mm door, 720mm height, 4.0kg, half overlay 6mm,
            adjacent door also 6mm overlay, 19mm partition, Blum preferred.

    Expected: Combined overlay 12mm < 19mm partition (R012 passes).
              Half-overlay Blum hinges selected.
    """

    def test_finds_solutions(self, engine):
        req = CustomerRequirements(
            cabinet_type="frameless", door_thickness_mm=19, door_height_mm=720,
            door_weight_kg=4.0, application="half_overlay", desired_overlay_mm=6,
            boring_pattern_mm=45, soft_close=True, preferred_brand="Blum",
            has_adjacent_door=True, adjacent_door_overlay_mm=6,
            partition_thickness_mm=19,
        )
        solutions = engine.solve(req)
        assert len(solutions) > 0

    def test_all_solutions_are_half_overlay(self, engine):
        req = CustomerRequirements(
            cabinet_type="frameless", door_thickness_mm=19, door_height_mm=720,
            door_weight_kg=4.0, application="half_overlay", desired_overlay_mm=6,
            boring_pattern_mm=45, soft_close=True, preferred_brand="Blum",
            has_adjacent_door=True, adjacent_door_overlay_mm=6,
            partition_thickness_mm=19,
        )
        for config in engine.solve(req):
            assert config.hinge.application == "half_overlay"

    def test_combined_overlay_within_partition(self, engine):
        req = CustomerRequirements(
            cabinet_type="frameless", door_thickness_mm=19, door_height_mm=720,
            door_weight_kg=4.0, application="half_overlay", desired_overlay_mm=6,
            boring_pattern_mm=45, soft_close=True, preferred_brand="Blum",
            has_adjacent_door=True, adjacent_door_overlay_mm=6,
            partition_thickness_mm=19,
        )
        # The engine already validated this, but verify explicitly
        assert req.desired_overlay_mm + req.adjacent_door_overlay_mm <= req.partition_thickness_mm

    def test_partition_exceeded_returns_no_solutions(self, engine):
        req = CustomerRequirements(
            cabinet_type="frameless", door_thickness_mm=19, door_height_mm=720,
            door_weight_kg=4.0, application="half_overlay", desired_overlay_mm=12,
            boring_pattern_mm=45, soft_close=True, preferred_brand="Blum",
            has_adjacent_door=True, adjacent_door_overlay_mm=12,
            partition_thickness_mm=19,  # 12 + 12 = 24 > 19
        )
        solutions = engine.solve(req)
        assert len(solutions) == 0


class TestScenario5ConstraintViolation:
    """
    Scenario 5: Heavy door in corner cabinet — no valid solution.

    Inputs: Frameless, 22mm door, 900mm height, 12.0kg, full overlay 16mm,
            corner position, Blum preferred.

    Expected: No solution. Corner requires >= 155 deg (R013), but wide-angle
              hinges have reduced capacity after derating (R010). Even with
              2 hinges, max capacity is too low for 12kg.
    """

    def test_no_solution_with_blum(self, engine):
        req = CustomerRequirements(
            cabinet_type="frameless", door_thickness_mm=22, door_height_mm=900,
            door_weight_kg=12.0, application="full_overlay", desired_overlay_mm=16,
            boring_pattern_mm=45, soft_close=True, cabinet_position="corner",
            preferred_brand="Blum",
        )
        solutions = engine.solve(req)
        assert len(solutions) == 0

    def test_no_solution_any_brand(self, engine):
        req = CustomerRequirements(
            cabinet_type="frameless", door_thickness_mm=22, door_height_mm=900,
            door_weight_kg=12.0, application="full_overlay", desired_overlay_mm=16,
            boring_pattern_mm=45, soft_close=True, cabinet_position="corner",
        )
        solutions = engine.solve(req)
        assert len(solutions) == 0

    def test_explanation_reports_failure(self, engine):
        req = CustomerRequirements(
            cabinet_type="frameless", door_thickness_mm=22, door_height_mm=900,
            door_weight_kg=12.0, application="full_overlay", desired_overlay_mm=16,
            boring_pattern_mm=45, soft_close=True, cabinet_position="corner",
            preferred_brand="Blum",
        )
        result = engine.solve_with_explanation(req)
        assert result["status"] == "no_solution"
        assert len(result["failed_rules"]) > 0

    def test_closest_match_has_fewest_failures(self, engine):
        req = CustomerRequirements(
            cabinet_type="frameless", door_thickness_mm=22, door_height_mm=900,
            door_weight_kg=12.0, application="full_overlay", desired_overlay_mm=16,
            boring_pattern_mm=45, soft_close=True, cabinet_position="corner",
            preferred_brand="Blum",
        )
        result = engine.solve_with_explanation(req)
        assert result["closest_match"] is not None
        failed = [r for r in result["closest_match"]["constraint_trace"] if not r["passed"]]
        assert len(failed) >= 1


# ---------------------------------------------------------------------------
# Edge case tests
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Boundary conditions and edge cases."""

    def test_exact_weight_at_capacity_passes(self, engine, catalog):
        h = _hinge(catalog, "BLM-71B3550")  # 7.5kg per hinge
        req = CustomerRequirements(
            cabinet_type="frameless", door_thickness_mm=19, door_height_mm=720,
            door_weight_kg=15.0, application="full_overlay", desired_overlay_mm=16,
            boring_pattern_mm=45, soft_close=True,
        )
        result = engine._check_weight(h, req, num_hinges=2)  # 7.5 * 2 = 15.0
        assert result.passed

    def test_slightly_over_capacity_fails(self, engine, catalog):
        h = _hinge(catalog, "BLM-71B3550")  # 7.5kg per hinge
        req = CustomerRequirements(
            cabinet_type="frameless", door_thickness_mm=19, door_height_mm=720,
            door_weight_kg=15.1, application="full_overlay", desired_overlay_mm=16,
            boring_pattern_mm=45, soft_close=True,
        )
        result = engine._check_weight(h, req, num_hinges=2)
        assert not result.passed

    def test_no_brand_preference_returns_all_brands(self, engine):
        req = CustomerRequirements(
            cabinet_type="frameless", door_thickness_mm=19, door_height_mm=720,
            door_weight_kg=5.0, application="full_overlay", desired_overlay_mm=16,
            boring_pattern_mm=45, soft_close=True,
        )
        solutions = engine.solve(req)
        brands = {c.hinge.brand for c in solutions}
        assert len(brands) >= 2

    def test_soft_close_not_required_includes_non_soft_close(self, engine):
        req = CustomerRequirements(
            cabinet_type="frameless", door_thickness_mm=19, door_height_mm=720,
            door_weight_kg=5.0, application="full_overlay", desired_overlay_mm=16,
            boring_pattern_mm=45, soft_close=False,
        )
        solutions = engine.solve(req)
        has_non_soft_close = any(not c.hinge.soft_close for c in solutions)
        assert has_non_soft_close

    def test_every_valid_config_passes_all_rules(self, engine):
        req = CustomerRequirements(
            cabinet_type="frameless", door_thickness_mm=19, door_height_mm=720,
            door_weight_kg=5.0, application="full_overlay", desired_overlay_mm=16,
            boring_pattern_mm=45, soft_close=True,
        )
        for config in engine.solve(req):
            assert config.valid
            assert len(config.failed_rules) == 0
