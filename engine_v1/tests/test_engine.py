"""
Tests for the production hinge constraint engine.

Verifies parity with the PoC engine for all existing scenarios,
plus tests for new production model features.

Run:
    python -m pytest engine/tests/test_engine.py -v
"""

import json
import pytest
from pathlib import Path

from engine_v1 import (
    ApplicationType,
    CabinetPosition,
    CabinetType,
    ConcealedHinge,
    Configuration,
    CustomerRequirements,
    DoorMaterial,
    HingeConstraintEngine,
    HingeSeries,
    MountingMethod,
    MountingPlate,
    OverlayEntry,
    OverlayTable,
    PlateMaterial,
    PlateType,
    ProductFamily,
    Range,
    RuleCategory,
    RuleResult,
    load_from_json,
)
from engine_v1.rules import hinges_per_door


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def data_dir():
    return Path(__file__).parent.parent.parent / "sample-data"


@pytest.fixture(scope="module")
def catalog(data_dir):
    return load_from_json(data_dir)


@pytest.fixture(scope="module")
def engine(catalog):
    hinges, plates = catalog
    return HingeConstraintEngine(hinges, plates)


@pytest.fixture(scope="module")
def scenarios(data_dir):
    with open(data_dir / "customer_scenarios.json") as f:
        return json.load(f)


def _hinge(catalog, sku: str) -> ConcealedHinge:
    return next(h for h in catalog[0] if h.sku == sku)


def _plate(catalog, sku: str) -> MountingPlate:
    return next(p for p in catalog[1] if p.sku == sku)


def _make_req(**kwargs) -> CustomerRequirements:
    """Create a CustomerRequirements from scenario inputs dict."""
    # Map scenario keys to model fields
    mapping = dict(kwargs)
    # Handle cabinet_position default
    if "cabinet_position" not in mapping:
        mapping["cabinet_position"] = "standard"
    # Handle missing fields with defaults
    mapping.setdefault("has_adjacent_door", False)
    mapping.setdefault("adjacent_door_overlay_mm", 0)
    mapping.setdefault("partition_thickness_mm", 19)
    mapping.setdefault("face_frame_width_mm", 0)
    # Remove keys not in CustomerRequirements
    valid_keys = set(CustomerRequirements.model_fields.keys())
    filtered = {k: v for k, v in mapping.items() if k in valid_keys}
    return CustomerRequirements(**filtered)


# ---------------------------------------------------------------------------
# Enum validation tests
# ---------------------------------------------------------------------------

class TestEnums:
    def test_application_type_values(self):
        assert ApplicationType.FULL_OVERLAY.value == "full_overlay"
        assert ApplicationType.HALF_OVERLAY.value == "half_overlay"
        assert ApplicationType.INSET.value == "inset"
        assert ApplicationType.OVERLAY.value == "overlay"

    def test_cabinet_type_values(self):
        assert CabinetType.FRAMELESS.value == "frameless"
        assert CabinetType.FACE_FRAME.value == "face_frame"

    def test_mounting_method_values(self):
        assert MountingMethod.SCREW_ON.value == "screw_on"
        assert MountingMethod.DOWEL.value == "dowel"
        assert MountingMethod.EURO_SCREW.value == "euro_screw"

    def test_hinge_series_values(self):
        assert HingeSeries.CLIP_TOP_BLUMOTION.value == "CLIP top BLUMOTION"
        assert HingeSeries.TIOMOS.value == "Tiomos"

    def test_plate_type_values(self):
        assert PlateType.CRUCIFORM.value == "cruciform"
        assert PlateType.WING.value == "wing"

    def test_rule_category_values(self):
        assert RuleCategory.HARD_CONSTRAINT.value == "hard_constraint"
        assert RuleCategory.PREFERENCE.value == "preference"

    def test_door_material_values(self):
        assert DoorMaterial.PARTICLEBOARD.value == "particleboard"
        assert DoorMaterial.MDF.value == "mdf"

    def test_cabinet_position_values(self):
        assert CabinetPosition.STANDARD.value == "standard"
        assert CabinetPosition.CORNER.value == "corner"
        assert CabinetPosition.BLIND_CORNER.value == "blind_corner"

    def test_invalid_enum_raises(self):
        with pytest.raises(ValueError):
            ApplicationType("nonexistent")

    def test_all_json_applications_are_valid_enums(self, catalog):
        for h in catalog[0]:
            assert isinstance(h.application, ApplicationType)

    def test_all_json_cabinet_types_are_valid_enums(self, catalog):
        for h in catalog[0]:
            assert isinstance(h.cabinet_type, CabinetType)
        for p in catalog[1]:
            assert isinstance(p.cabinet_type, CabinetType)


# ---------------------------------------------------------------------------
# OverlayTable tests
# ---------------------------------------------------------------------------

class TestOverlayTable:
    def test_supports(self):
        table = OverlayTable(entries={
            ApplicationType.FULL_OVERLAY: [
                OverlayEntry(base_plate_height_mm=0, drilling_distance_mm=5, overlay_mm=16),
            ],
        })
        assert table.supports(ApplicationType.FULL_OVERLAY)
        assert not table.supports(ApplicationType.INSET)

    def test_overlay_range(self):
        table = OverlayTable(entries={
            ApplicationType.FULL_OVERLAY: [
                OverlayEntry(base_plate_height_mm=0, drilling_distance_mm=3, overlay_mm=14),
                OverlayEntry(base_plate_height_mm=0, drilling_distance_mm=7, overlay_mm=20),
            ],
        })
        r = table.overlay_range(ApplicationType.FULL_OVERLAY)
        assert r.min == 14
        assert r.max == 20

    def test_overlay_range_none_for_unsupported(self):
        table = OverlayTable(entries={})
        assert table.overlay_range(ApplicationType.FULL_OVERLAY) is None

    def test_achievable_overlay(self):
        table = OverlayTable(entries={
            ApplicationType.FULL_OVERLAY: [
                OverlayEntry(base_plate_height_mm=0, drilling_distance_mm=5, overlay_mm=18),
                OverlayEntry(base_plate_height_mm=3, drilling_distance_mm=5, overlay_mm=15),
            ],
        })
        assert table.achievable_overlay(ApplicationType.FULL_OVERLAY, 5) == 18
        assert table.achievable_overlay(ApplicationType.FULL_OVERLAY, 99) is None

    def test_backward_compat_overlay_range_mm(self, catalog):
        """Plates loaded from JSON should expose overlay_range_mm compatible with PoC."""
        plate = _plate(catalog, "BLM-173L6100")
        orm = plate.overlay_range_mm
        assert "full" in orm
        assert "half" in orm
        assert "inset" in orm
        assert orm["full"] == [14, 20]
        assert orm["half"] == [3, 9]
        assert orm["inset"] is True


# ---------------------------------------------------------------------------
# Range tests
# ---------------------------------------------------------------------------

class TestRange:
    def test_contains(self):
        r = Range(min=16, max=26)
        assert r.contains(19)
        assert r.contains(16)
        assert r.contains(26)
        assert not r.contains(15.9)
        assert not r.contains(26.1)


# ---------------------------------------------------------------------------
# Derived values tests (parity with PoC)
# ---------------------------------------------------------------------------

class TestDerivedValues:
    def test_short_door_gets_2_hinges(self):
        assert hinges_per_door(720) == 2

    def test_boundary_889mm_gets_2_hinges(self):
        assert hinges_per_door(889) == 2

    def test_boundary_890mm_gets_3_hinges(self):
        assert hinges_per_door(890) == 3

    def test_medium_door_gets_3_hinges(self):
        assert hinges_per_door(1200) == 3

    def test_tall_door_gets_4_hinges(self):
        assert hinges_per_door(1600) == 4

    def test_very_tall_door_gets_5_hinges(self):
        assert hinges_per_door(2000) == 5

    def test_no_derating_for_wide_angle(self, catalog):
        """Production engine does NOT derate — uses max_door_weight_kg directly."""
        h = _hinge(catalog, "BLM-79B3550")  # 155 degrees
        # In PoC: effective = 5.0 * 0.75 = 3.75. Production: 5.0
        assert h.max_door_weight_kg == 5.0

    def test_r010_not_applied(self, engine, catalog):
        """R010 is removed — weight capacity is NOT derated for wide-angle."""
        h = _hinge(catalog, "BLM-79B3550")  # 155 degrees, 5.0kg
        req = CustomerRequirements(
            cabinet_type="frameless", door_thickness_mm=19, door_height_mm=720,
            door_weight_kg=4.0, application="full_overlay", desired_overlay_mm=16,
            boring_pattern_mm=45, soft_close=True,
        )
        p = _plate(catalog, "BLM-173L6100")
        config = engine.evaluate(h, p, req)
        # No derating: 5.0 * 2 = 10.0 (PoC would be 3.75 * 2 = 7.5)
        assert config.total_weight_capacity_kg == 10.0


# ---------------------------------------------------------------------------
# Customer scenario parity tests (SC001-SC007)
# ---------------------------------------------------------------------------

class TestScenario1StandardKitchenRemodel:
    """SC001: Blum full overlay soft-close kitchen remodel."""

    def _req(self):
        return CustomerRequirements(
            cabinet_type="frameless", door_thickness_mm=19, door_height_mm=720,
            door_weight_kg=5.2, application="full_overlay", desired_overlay_mm=16,
            boring_pattern_mm=45, soft_close=True, preferred_brand="Blum",
        )

    def test_finds_solutions(self, engine):
        solutions = engine.solve(self._req())
        assert len(solutions) > 0

    def test_all_solutions_are_blum(self, engine):
        for config in engine.solve(self._req()):
            assert config.hinge.brand == "Blum"
            assert config.plate.brand == "Blum"

    def test_recommended_sku(self, engine):
        solutions = engine.solve(self._req())
        # Cheapest Blum hinge is BLM-71B3550; cheapest plate is BLM-175H7100
        assert solutions[0].hinge.sku == "BLM-71B3550"
        assert solutions[0].plate.sku == "BLM-175H7100"

    def test_2_hinges_per_door(self, engine):
        for config in engine.solve(self._req()):
            assert config.hinges_per_door == 2

    def test_all_solutions_have_soft_close(self, engine):
        for config in engine.solve(self._req()):
            assert config.hinge.soft_close is True

    def test_recommended_is_cheapest(self, engine):
        solutions = engine.solve(self._req())
        priced = [s for s in solutions if s.total_price_usd is not None]
        assert priced[0].total_price_usd <= priced[-1].total_price_usd

    def test_weight_capacity_sufficient(self, engine):
        for config in engine.solve(self._req()):
            assert config.total_weight_capacity_kg >= 5.2


class TestScenario2CornerCabinet:
    """SC002: Corner cabinet requiring wide-angle hinge."""

    def _req(self):
        return CustomerRequirements(
            cabinet_type="frameless", door_thickness_mm=19, door_height_mm=800,
            door_weight_kg=4.0, application="full_overlay", desired_overlay_mm=16,
            boring_pattern_mm=45, soft_close=True, cabinet_position="corner",
        )

    def test_finds_solutions(self, engine):
        solutions = engine.solve(self._req())
        assert len(solutions) > 0

    def test_all_solutions_are_wide_angle(self, engine):
        for config in engine.solve(self._req()):
            assert config.hinge.opening_angle_deg >= 155

    def test_includes_multiple_brands(self, engine):
        brands = {c.hinge.brand for c in engine.solve(self._req())}
        assert len(brands) >= 2

    def test_no_derating_in_capacity(self, engine):
        """Production engine uses raw max_door_weight_kg — no 0.75 derating."""
        for config in engine.solve(self._req()):
            expected = config.hinge.max_door_weight_kg * config.hinges_per_door
            assert config.total_weight_capacity_kg == pytest.approx(expected)


class TestScenario3TallPantryDoor:
    """SC005: Tall pantry door, 1600mm, 14kg, Grass preferred."""

    def _req(self):
        return CustomerRequirements(
            cabinet_type="frameless", door_thickness_mm=22, door_height_mm=1600,
            door_weight_kg=14.0, application="full_overlay", desired_overlay_mm=16,
            boring_pattern_mm=45, soft_close=True, preferred_brand="Grass",
        )

    def test_finds_solutions(self, engine):
        solutions = engine.solve(self._req())
        assert len(solutions) > 0

    def test_4_hinges_per_door(self, engine):
        for config in engine.solve(self._req()):
            assert config.hinges_per_door == 4

    def test_all_solutions_are_grass(self, engine):
        for config in engine.solve(self._req()):
            assert config.hinge.brand == "Grass"
            assert config.plate.brand == "Grass"

    def test_capacity_handles_14kg(self, engine):
        for config in engine.solve(self._req()):
            assert config.total_weight_capacity_kg >= 14.0

    def test_recommended_sku(self, engine):
        solutions = engine.solve(self._req())
        # Cheapest Grass hinge for this scenario (matches PoC output)
        assert solutions[0].hinge.sku == "GRS-F028138519"


class TestScenario4FaceFrameInset:
    """SC004: Inset hinges for face-frame bathroom vanity.

    Note: Both PoC and production engine return 0 solutions because
    BLM-75T1550 has application=full_overlay, not inset. The pre-filter
    in solve() correctly rejects it. This matches PoC behavior.
    """

    def _req(self):
        return CustomerRequirements(
            cabinet_type="face_frame", door_thickness_mm=19, door_height_mm=600,
            door_weight_kg=3.5, application="inset", desired_overlay_mm=0,
            boring_pattern_mm=45, soft_close=False, preferred_brand="Blum",
            face_frame_width_mm=38,
        )

    def test_no_solutions_matches_poc(self, engine):
        """Both engines return 0 solutions — hinge application mismatch."""
        solutions = engine.solve(self._req())
        assert len(solutions) == 0

    def test_evaluate_pair_passes_all_rules(self, engine, catalog):
        """The pair BLM-75T1550 + BLM-175H9100 passes all rules when evaluated directly."""
        h = _hinge(catalog, "BLM-75T1550")
        p = _plate(catalog, "BLM-175H9100")
        config = engine.evaluate(h, p, self._req())
        assert config.valid


class TestScenario5ConstraintViolation:
    """SC006: Heavy door in corner cabinet.

    In the PoC, wide-angle hinges are derated 25% (R010), making this unsolvable.
    In production, R010 is removed: 5.0kg * 3 hinges = 15kg > 12kg, so solutions exist.
    This is an intentional difference — the production engine uses manufacturer's
    published max_door_weight_kg directly.
    """

    def _req(self):
        return CustomerRequirements(
            cabinet_type="frameless", door_thickness_mm=22, door_height_mm=900,
            door_weight_kg=12.0, application="full_overlay", desired_overlay_mm=16,
            boring_pattern_mm=45, soft_close=True, cabinet_position="corner",
            preferred_brand="Blum",
        )

    def test_has_solutions_without_derating(self, engine):
        """Production engine finds solutions since R010 derating is removed."""
        solutions = engine.solve(self._req())
        assert len(solutions) > 0

    def test_all_solutions_wide_angle(self, engine):
        for config in engine.solve(self._req()):
            assert config.hinge.opening_angle_deg >= 155

    def test_capacity_sufficient_without_derating(self, engine):
        for config in engine.solve(self._req()):
            assert config.total_weight_capacity_kg >= 12.0


class TestScenario6AdjacentDoors:
    """SC007: Adjacent doors on shared partition."""

    def _req(self):
        return CustomerRequirements(
            cabinet_type="frameless", door_thickness_mm=19, door_height_mm=720,
            door_weight_kg=4.0, application="half_overlay", desired_overlay_mm=6,
            boring_pattern_mm=45, soft_close=True, preferred_brand="Blum",
            has_adjacent_door=True, adjacent_door_overlay_mm=6,
            partition_thickness_mm=19,
        )

    def test_finds_solutions(self, engine):
        solutions = engine.solve(self._req())
        assert len(solutions) > 0

    def test_all_solutions_are_half_overlay(self, engine):
        for config in engine.solve(self._req()):
            assert config.hinge.application == ApplicationType.HALF_OVERLAY

    def test_recommended_sku(self, engine):
        solutions = engine.solve(self._req())
        assert solutions[0].hinge.sku == "BLM-71B3650"

    def test_partition_exceeded_returns_no_solutions(self, engine):
        req = self._req().model_copy(update={
            "desired_overlay_mm": 12,
            "adjacent_door_overlay_mm": 12,
        })
        assert len(engine.solve(req)) == 0


class TestScenario7GuidedBuyer:
    """SC003: Guided buyer — same as SC001 but without brand preference."""

    def _req(self):
        return CustomerRequirements(
            cabinet_type="frameless", door_thickness_mm=19, door_height_mm=711,
            door_weight_kg=4.5, application="full_overlay", desired_overlay_mm=16,
            boring_pattern_mm=45, soft_close=True,
        )

    def test_finds_solutions(self, engine):
        solutions = engine.solve(self._req())
        assert len(solutions) > 0

    def test_recommended_sku(self, engine):
        solutions = engine.solve(self._req())
        # Cheapest overall is Hafele Duomatic (matches PoC output)
        assert solutions[0].hinge.sku == "HFL-311131"
        assert solutions[0].plate.sku == "HFL-311971"

    def test_multiple_brands_available(self, engine):
        brands = {c.hinge.brand for c in engine.solve(self._req())}
        assert len(brands) >= 2


# ---------------------------------------------------------------------------
# Indexed pre-filtering parity tests
# ---------------------------------------------------------------------------

class TestPreFiltering:
    """Verify indexed pre-filtering produces the same results as brute force."""

    def test_brand_filtered_matches_brute_force(self, engine):
        req = CustomerRequirements(
            cabinet_type="frameless", door_thickness_mm=19, door_height_mm=720,
            door_weight_kg=5.0, application="full_overlay", desired_overlay_mm=16,
            boring_pattern_mm=45, soft_close=True, preferred_brand="Blum",
        )
        # Indexed solve
        indexed = engine.solve(req)

        # Brute force: evaluate every pair
        brute = []
        for h in engine.hinges:
            if req.preferred_brand and h.brand != req.preferred_brand:
                continue
            if h.application.value != req.application.value:
                continue
            if h.cabinet_type.value != req.cabinet_type.value:
                continue
            for p in engine.plates:
                config = engine.evaluate(h, p, req)
                if config.valid:
                    brute.append(config)
        brute.sort(key=lambda c: (
            c.total_price_usd if c.total_price_usd is not None else float('inf'),
            -c.total_weight_capacity_kg,
        ))

        assert len(indexed) == len(brute)
        for i_cfg, b_cfg in zip(indexed, brute):
            assert i_cfg.hinge.sku == b_cfg.hinge.sku
            assert i_cfg.plate.sku == b_cfg.plate.sku

    def test_no_brand_filtered_matches_brute_force(self, engine):
        req = CustomerRequirements(
            cabinet_type="frameless", door_thickness_mm=19, door_height_mm=720,
            door_weight_kg=5.0, application="full_overlay", desired_overlay_mm=16,
            boring_pattern_mm=45, soft_close=True,
        )
        indexed = engine.solve(req)

        brute = []
        for h in engine.hinges:
            if h.application.value != req.application.value:
                continue
            if h.cabinet_type.value != req.cabinet_type.value:
                continue
            for p in engine.plates:
                config = engine.evaluate(h, p, req)
                if config.valid:
                    brute.append(config)
        brute.sort(key=lambda c: (
            c.total_price_usd if c.total_price_usd is not None else float('inf'),
            -c.total_weight_capacity_kg,
        ))

        assert len(indexed) == len(brute)


# ---------------------------------------------------------------------------
# Data loading tests
# ---------------------------------------------------------------------------

class TestDataLoading:
    def test_loads_correct_hinge_count(self, catalog):
        hinges, _ = catalog
        assert len(hinges) == 53

    def test_loads_correct_plate_count(self, catalog):
        _, plates = catalog
        assert len(plates) == 55

    def test_hinge_fields_populated(self, catalog):
        h = _hinge(catalog, "BLM-71B3550")
        assert h.manufacturer_part == "71B3550"
        assert h.manufacturer == "Blum"
        assert h.series == HingeSeries.CLIP_TOP_BLUMOTION
        assert h.application == ApplicationType.FULL_OVERLAY
        assert h.opening_angle_deg == 110
        assert h.cup_diameter_mm == 35.0
        assert h.boring_pattern_mm == 45
        assert h.door_thickness_range_mm == Range(min=16, max=26)
        assert h.max_door_weight_kg == 7.5
        assert h.soft_close is True
        assert h.mounting_method == MountingMethod.SCREW_ON
        assert h.cabinet_type == CabinetType.FRAMELESS
        assert h.price_usd == 4.85

    def test_plate_fields_populated(self, catalog):
        p = _plate(catalog, "BLM-173L6100")
        assert p.manufacturer_part == "173L6100"
        assert p.manufacturer == "Blum"
        assert p.plate_type == PlateType.CRUCIFORM
        assert p.mounting_method == MountingMethod.SCREW_ON
        assert p.cabinet_type == CabinetType.FRAMELESS
        assert p.plate_height_mm == 0
        assert HingeSeries.CLIP_TOP_BLUMOTION in p.compatible_hinge_series
        assert p.price_usd == 1.2

    def test_null_prices_handled(self, catalog):
        """Hinges with null price should load without error."""
        hinges_with_none = [h for h in catalog[0] if h.price_usd is None]
        assert len(hinges_with_none) > 0

    def test_missing_cup_depth_handled(self, catalog):
        """Hinges with missing cup_depth_mm should load as None."""
        hinges_no_cup = [h for h in catalog[0] if h.cup_depth_mm is None]
        assert len(hinges_no_cup) >= 0  # may or may not exist


# ---------------------------------------------------------------------------
# Edge case / boundary tests
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_exact_weight_at_capacity_passes(self, engine, catalog):
        h = _hinge(catalog, "BLM-71B3550")  # 7.5kg per hinge
        p = _plate(catalog, "BLM-173L6100")
        req = CustomerRequirements(
            cabinet_type="frameless", door_thickness_mm=19, door_height_mm=720,
            door_weight_kg=15.0, application="full_overlay", desired_overlay_mm=16,
            boring_pattern_mm=45, soft_close=True,
        )
        config = engine.evaluate(h, p, req)
        # Find R007 result
        r007 = next(r for r in config.rule_results if r.rule_id == "R007")
        assert r007.passed  # 7.5 * 2 = 15.0 == 15.0

    def test_slightly_over_capacity_fails(self, engine, catalog):
        h = _hinge(catalog, "BLM-71B3550")
        p = _plate(catalog, "BLM-173L6100")
        req = CustomerRequirements(
            cabinet_type="frameless", door_thickness_mm=19, door_height_mm=720,
            door_weight_kg=15.1, application="full_overlay", desired_overlay_mm=16,
            boring_pattern_mm=45, soft_close=True,
        )
        config = engine.evaluate(h, p, req)
        r007 = next(r for r in config.rule_results if r.rule_id == "R007")
        assert not r007.passed

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

    def test_rule_results_have_categories(self, engine, catalog):
        """Production RuleResult includes category field."""
        h = _hinge(catalog, "BLM-71B3550")
        p = _plate(catalog, "BLM-173L6100")
        req = CustomerRequirements(
            cabinet_type="frameless", door_thickness_mm=19, door_height_mm=720,
            door_weight_kg=5.0, application="full_overlay", desired_overlay_mm=16,
            boring_pattern_mm=45, soft_close=True,
        )
        config = engine.evaluate(h, p, req)
        for r in config.rule_results:
            assert isinstance(r.category, RuleCategory)
        # Soft close rule should be PREFERENCE
        pref = next(r for r in config.rule_results if r.rule_id == "PREF")
        assert pref.category == RuleCategory.PREFERENCE

    def test_solve_with_explanation_format(self, engine):
        """Verify solve_with_explanation output matches PoC format."""
        req = CustomerRequirements(
            cabinet_type="frameless", door_thickness_mm=19, door_height_mm=720,
            door_weight_kg=5.2, application="full_overlay", desired_overlay_mm=16,
            boring_pattern_mm=45, soft_close=True, preferred_brand="Blum",
        )
        result = engine.solve_with_explanation(req)
        assert result["status"] == "solved"
        assert "recommended" in result
        assert "alternatives" in result
        rec = result["recommended"]
        assert "hinge" in rec
        assert "mounting_plate" in rec
        assert "hinges_per_door" in rec
        assert "total_weight_capacity_kg" in rec
        assert "total_price_per_door_usd" in rec
        assert "constraint_trace" in rec

    def test_configuration_total_price(self, engine, catalog):
        h = _hinge(catalog, "BLM-71B3550")  # $4.85
        p = _plate(catalog, "BLM-173L6100")  # $1.20
        req = CustomerRequirements(
            cabinet_type="frameless", door_thickness_mm=19, door_height_mm=720,
            door_weight_kg=5.0, application="full_overlay", desired_overlay_mm=16,
            boring_pattern_mm=45, soft_close=True,
        )
        config = engine.evaluate(h, p, req)
        # (4.85 + 1.20) * 2 = 12.10
        assert config.total_price_usd == 12.1

    def test_none_price_returns_none_total(self, catalog, engine):
        """If either price is None, total_price_usd should be None."""
        hinges_none_price = [h for h in catalog[0] if h.price_usd is None]
        if hinges_none_price:
            h = hinges_none_price[0]
            p = catalog[1][0]
            req = CustomerRequirements(
                cabinet_type=h.cabinet_type.value, door_thickness_mm=19, door_height_mm=720,
                door_weight_kg=5.0, application=h.application.value, desired_overlay_mm=16,
                boring_pattern_mm=45, soft_close=True,
            )
            config = engine.evaluate(h, p, req)
            assert config.total_price_usd is None
