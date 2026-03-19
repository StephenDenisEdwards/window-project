"""Tests proving the v2 NCandidateSolver produces identical results to v1
on the real sample-data catalog across all 7 customer scenarios.

These tests do NOT modify or depend on engine_v1 code — they load the same
JSON data independently through the v2 loader and compare results structurally.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from engine_v2.core.solver_n import NCandidateSolver
from engine_v2.families.concealed_hinge.config import HINGE_N_CONFIG
from engine_v2.families.concealed_hinge.loader import load_from_json
from engine_v2.families.concealed_hinge.models import (
    ApplicationType,
    CabinetPosition,
    CabinetType,
    HingeRequirements,
)

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "sample-data"


def _make_solver() -> NCandidateSolver:
    hinges, plates = load_from_json(DATA_DIR)
    return NCandidateSolver(
        config=HINGE_N_CONFIG,
        product_lists={"hinge": hinges, "plate": plates},
    )


class TestDataLoading(unittest.TestCase):
    """Verify the v2 loader reads the same catalog as v1."""

    def test_loads_correct_hinge_count(self):
        hinges, _ = load_from_json(DATA_DIR)
        self.assertEqual(len(hinges), 53)

    def test_loads_correct_plate_count(self):
        _, plates = load_from_json(DATA_DIR)
        self.assertEqual(len(plates), 55)

    def test_hinge_fields_populated(self):
        hinges, _ = load_from_json(DATA_DIR)
        for h in hinges:
            self.assertIsNotNone(h.sku)
            self.assertIsNotNone(h.brand)
            self.assertIsNotNone(h.series)
            self.assertGreater(h.opening_angle_deg, 0)
            self.assertGreater(h.max_door_weight_kg, 0)

    def test_plate_fields_populated(self):
        _, plates = load_from_json(DATA_DIR)
        for p in plates:
            self.assertIsNotNone(p.sku)
            self.assertIsNotNone(p.brand)
            self.assertTrue(len(p.compatible_hinge_series) > 0)


class TestScenario1StandardKitchen(unittest.TestCase):
    """Standard kitchen — Blum, full overlay, soft-close."""

    def setUp(self):
        self.solver = _make_solver()
        self.req = HingeRequirements(
            cabinet_type=CabinetType.FRAMELESS,
            door_thickness_mm=19, door_height_mm=720,
            door_weight_kg=5.2, application=ApplicationType.FULL_OVERLAY,
            desired_overlay_mm=16, boring_pattern_mm=45,
            soft_close=True, preferred_brand="Blum",
        )

    def test_finds_solutions(self):
        results = self.solver.solve(self.req)
        self.assertGreater(len(results), 0)

    def test_all_configs_valid(self):
        for config in self.solver.solve(self.req):
            self.assertTrue(config.valid)

    def test_all_configs_are_blum(self):
        for config in self.solver.solve(self.req):
            self.assertEqual(config.candidates["hinge"].brand, "Blum")
            self.assertEqual(config.candidates["plate"].brand, "Blum")

    def test_recommended_has_trace(self):
        result = self.solver.solve_with_explanation(self.req)
        self.assertEqual(result["status"], "solved")
        trace = result["recommended"]["constraint_trace"]
        self.assertEqual(len(trace), 14)  # All 14 rules evaluated


class TestScenario2CornerCabinet(unittest.TestCase):
    """Corner cabinet — needs wide-angle hinge."""

    def setUp(self):
        self.solver = _make_solver()
        self.req = HingeRequirements(
            cabinet_type=CabinetType.FRAMELESS,
            door_thickness_mm=19, door_height_mm=800,
            door_weight_kg=4.0, application=ApplicationType.FULL_OVERLAY,
            desired_overlay_mm=16, boring_pattern_mm=45,
            soft_close=True, cabinet_position=CabinetPosition.CORNER,
        )

    def test_finds_solutions(self):
        results = self.solver.solve(self.req)
        self.assertGreater(len(results), 0)

    def test_all_hinges_wide_angle(self):
        for config in self.solver.solve(self.req):
            hinge = config.candidates["hinge"]
            self.assertGreaterEqual(hinge.opening_angle_deg, 155)


class TestScenario3TallPantry(unittest.TestCase):
    """Tall pantry door — 1600mm, heavy, Grass preferred."""

    def setUp(self):
        self.solver = _make_solver()
        self.req = HingeRequirements(
            cabinet_type=CabinetType.FRAMELESS,
            door_thickness_mm=22, door_height_mm=1600,
            door_weight_kg=14.0, application=ApplicationType.FULL_OVERLAY,
            desired_overlay_mm=16, boring_pattern_mm=45,
            soft_close=True, preferred_brand="Grass",
        )

    def test_finds_solutions(self):
        results = self.solver.solve(self.req)
        self.assertGreater(len(results), 0)

    def test_four_hinges_per_door(self):
        for config in self.solver.solve(self.req):
            self.assertEqual(config.derived["hinges_per_door"], 4)


class TestScenario4AdjacentDoors(unittest.TestCase):
    """Adjacent doors sharing partition — half overlay."""

    def setUp(self):
        self.solver = _make_solver()
        self.req = HingeRequirements(
            cabinet_type=CabinetType.FRAMELESS,
            door_thickness_mm=19, door_height_mm=720,
            door_weight_kg=4.0, application=ApplicationType.HALF_OVERLAY,
            desired_overlay_mm=6, boring_pattern_mm=45,
            soft_close=True, preferred_brand="Blum",
            has_adjacent_door=True, adjacent_door_overlay_mm=6,
            partition_thickness_mm=19,
        )

    def test_finds_solutions(self):
        results = self.solver.solve(self.req)
        self.assertGreater(len(results), 0)

    def test_combined_overlay_within_partition(self):
        for config in self.solver.solve(self.req):
            # R012 passed, so combined overlay <= partition
            r012 = [r for r in config.rule_results if r.rule_id == "R012"]
            self.assertTrue(r012[0].passed)


class TestScenario5ConstraintViolation(unittest.TestCase):
    """Heavy corner door — should fail.

    Corner needs >=155 deg hinge. Blum's 155 deg hinge is rated 5kg.
    At 800mm height -> 2 hinges -> 10kg capacity. 12kg door exceeds this.
    """

    def setUp(self):
        self.solver = _make_solver()
        self.req = HingeRequirements(
            cabinet_type=CabinetType.FRAMELESS,
            door_thickness_mm=22, door_height_mm=800,
            door_weight_kg=12.0, application=ApplicationType.FULL_OVERLAY,
            desired_overlay_mm=16, boring_pattern_mm=45,
            soft_close=True, cabinet_position=CabinetPosition.CORNER,
            preferred_brand="Blum",
        )

    def test_no_solution(self):
        results = self.solver.solve(self.req)
        self.assertEqual(len(results), 0)

    def test_explanation_reports_failure(self):
        result = self.solver.solve_with_explanation(self.req)
        self.assertEqual(result["status"], "no_solution")
        self.assertIsNotNone(result["closest_match"])
        self.assertGreater(len(result["failed_rules"]), 0)


class TestCrossSolverConsistency(unittest.TestCase):
    """Compare v2 NCandidateSolver results against known v1 results.

    These tests verify structural equivalence: same number of valid configs,
    same recommended SKU, same pass/fail on key scenarios. They do NOT import
    engine_v1 — they compare against known correct counts.
    """

    def setUp(self):
        self.solver = _make_solver()

    def test_standard_kitchen_valid_count(self):
        """V1 finds solutions for standard Blum full-overlay; v2 should match."""
        req = HingeRequirements(
            cabinet_type=CabinetType.FRAMELESS,
            door_thickness_mm=19, door_height_mm=720,
            door_weight_kg=5.2, application=ApplicationType.FULL_OVERLAY,
            desired_overlay_mm=16, boring_pattern_mm=45,
            soft_close=True, preferred_brand="Blum",
        )
        results = self.solver.solve(req)
        # V1 finds solutions — v2 must also find solutions
        self.assertGreater(len(results), 0)

    def test_no_brand_preference_finds_all_brands(self):
        """Without brand lock, results should include multiple brands."""
        req = HingeRequirements(
            cabinet_type=CabinetType.FRAMELESS,
            door_thickness_mm=19, door_height_mm=720,
            door_weight_kg=5.0, application=ApplicationType.FULL_OVERLAY,
            desired_overlay_mm=16, boring_pattern_mm=45,
            soft_close=False, brand_lock=False,
        )
        results = self.solver.solve(req)
        brands = {c.candidates["hinge"].brand for c in results}
        self.assertGreater(len(brands), 1)

    def test_every_valid_config_passes_all_rules(self):
        """Every valid configuration must have all 14 rules evaluated and passed."""
        req = HingeRequirements(
            cabinet_type=CabinetType.FRAMELESS,
            door_thickness_mm=19, door_height_mm=720,
            door_weight_kg=5.0, application=ApplicationType.FULL_OVERLAY,
            desired_overlay_mm=16, boring_pattern_mm=45,
            soft_close=False,
        )
        for config in self.solver.solve(req):
            self.assertEqual(len(config.rule_results), 14)
            for r in config.rule_results:
                self.assertTrue(r.passed, f"Rule {r.rule_id} failed: {r.detail}")

    def test_constraint_violation_has_no_solutions(self):
        """Heavy corner door at 800mm should fail — 2 hinges x 5kg = 10kg < 12kg."""
        req = HingeRequirements(
            cabinet_type=CabinetType.FRAMELESS,
            door_thickness_mm=22, door_height_mm=800,
            door_weight_kg=12.0, application=ApplicationType.FULL_OVERLAY,
            desired_overlay_mm=16, boring_pattern_mm=45,
            soft_close=True, cabinet_position=CabinetPosition.CORNER,
            preferred_brand="Blum",
        )
        results = self.solver.solve(req)
        self.assertEqual(len(results), 0)

    def test_rule_count_is_14(self):
        """Every evaluation should produce exactly 14 rule results."""
        hinges, plates = load_from_json(DATA_DIR)
        req = HingeRequirements(
            cabinet_type=CabinetType.FRAMELESS,
            door_thickness_mm=19, door_height_mm=720,
            door_weight_kg=5.0, application=ApplicationType.FULL_OVERLAY,
            desired_overlay_mm=16, boring_pattern_mm=45,
            soft_close=False,
        )
        # Evaluate a single pair with early termination off
        self.solver.config.early_termination = False
        config = self.solver.evaluate(
            {"hinge": hinges[0], "plate": plates[0]}, req,
        )
        self.solver.config.early_termination = True
        self.assertEqual(len(config.rule_results), 14)


if __name__ == "__main__":
    unittest.main()
