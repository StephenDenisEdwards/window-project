"""Tests for drawer slide family on the N-candidate solver (N=1).

Proves the NCandidateSolver handles single-product families — no Cartesian
product, just filter each slide against requirements.
"""

from __future__ import annotations

import unittest

from engine_v2.core.solver_n import NCandidateSolver
from engine_v2.families.drawer_slide.config import SLIDE_N_CONFIG
from engine_v2.families.drawer_slide.models import (
    DrawerSlide,
    ExtensionType,
    SlideCloseType,
    SlideMountType,
    SlideRequirements,
)
from engine_v2.families.drawer_slide.test_data import (
    ALL_SLIDES,
    BLUM_SLIDE_FULL,
    BUDGET_SLIDE,
    CENTER_SLIDE,
    GRASS_SLIDE,
)


def _make_solver() -> NCandidateSolver:
    return NCandidateSolver(
        config=SLIDE_N_CONFIG,
        product_lists={"slide": list(ALL_SLIDES)},
    )


class TestBasicSolve(unittest.TestCase):
    """Standard drawer slide scenarios."""

    def setUp(self):
        self.solver = _make_solver()

    def test_finds_slides_for_standard_cabinet(self):
        req = SlideRequirements(cabinet_depth_mm=550, drawer_weight_kg=15.0)
        results = self.solver.solve(req)
        self.assertGreater(len(results), 0)

    def test_all_results_valid(self):
        req = SlideRequirements(cabinet_depth_mm=550, drawer_weight_kg=15.0)
        for config in self.solver.solve(req):
            self.assertTrue(config.valid)

    def test_single_candidate_per_config(self):
        """N=1 family: each config has exactly one product."""
        req = SlideRequirements(cabinet_depth_mm=550, drawer_weight_kg=15.0)
        for config in self.solver.solve(req):
            self.assertEqual(len(config.candidates), 1)
            self.assertIn("slide", config.candidates)

    def test_ranked_by_price(self):
        req = SlideRequirements(cabinet_depth_mm=550, drawer_weight_kg=10.0)
        results = self.solver.solve(req)
        prices = [c.total_price_usd for c in results if c.total_price_usd is not None]
        self.assertEqual(prices, sorted(prices))

    def test_all_rules_evaluated(self):
        """Every valid config should have all 8 rules evaluated."""
        req = SlideRequirements(cabinet_depth_mm=550, drawer_weight_kg=10.0)
        for config in self.solver.solve(req):
            self.assertEqual(len(config.rule_results), 8)


class TestConstraints(unittest.TestCase):
    """Individual constraint rule verification."""

    def setUp(self):
        self.solver = _make_solver()

    def test_load_capacity_eliminates_weak_slides(self):
        req = SlideRequirements(cabinet_depth_mm=550, drawer_weight_kg=42.0)
        results = self.solver.solve(req)
        for config in results:
            slide = config.candidates["slide"]
            self.assertGreaterEqual(slide.max_load_kg, 42.0)

    def test_cabinet_depth_too_shallow(self):
        req = SlideRequirements(cabinet_depth_mm=300, drawer_weight_kg=5.0)
        results = self.solver.solve(req)
        self.assertEqual(len(results), 0)

    def test_extension_type_filter(self):
        req = SlideRequirements(
            cabinet_depth_mm=550, drawer_weight_kg=10.0,
            extension_type=ExtensionType.FULL,
        )
        for config in self.solver.solve(req):
            slide = config.candidates["slide"]
            self.assertEqual(slide.extension_type, ExtensionType.FULL)

    def test_mount_type_filter(self):
        req = SlideRequirements(
            cabinet_depth_mm=550, drawer_weight_kg=10.0,
            mount_type=SlideMountType.UNDERMOUNT,
        )
        for config in self.solver.solve(req):
            slide = config.candidates["slide"]
            self.assertEqual(slide.mount_type, SlideMountType.UNDERMOUNT)

    def test_soft_close_preference(self):
        req = SlideRequirements(
            cabinet_depth_mm=550, drawer_weight_kg=10.0,
            soft_close=True,
        )
        for config in self.solver.solve(req):
            slide = config.candidates["slide"]
            self.assertEqual(slide.close_type, SlideCloseType.SOFT_CLOSE)

    def test_brand_preference(self):
        req = SlideRequirements(
            cabinet_depth_mm=550, drawer_weight_kg=10.0,
            preferred_brand="Blum",
        )
        for config in self.solver.solve(req):
            self.assertEqual(config.candidates["slide"].brand, "Blum")

    def test_disconnect_required(self):
        req = SlideRequirements(
            cabinet_depth_mm=550, drawer_weight_kg=10.0,
            disconnect_required=True,
        )
        for config in self.solver.solve(req):
            slide = config.candidates["slide"]
            self.assertTrue(slide.disconnect_feature)


class TestExplanation(unittest.TestCase):
    """solve_with_explanation output format."""

    def setUp(self):
        self.solver = _make_solver()

    def test_solved_has_expected_keys(self):
        req = SlideRequirements(cabinet_depth_mm=550, drawer_weight_kg=10.0)
        result = self.solver.solve_with_explanation(req)
        self.assertEqual(result["status"], "solved")
        self.assertIn("recommended", result)
        self.assertIn("alternatives", result)

    def test_no_solution_has_closest_match(self):
        req = SlideRequirements(cabinet_depth_mm=200, drawer_weight_kg=100)
        result = self.solver.solve_with_explanation(req)
        self.assertEqual(result["status"], "no_solution")
        self.assertIsNotNone(result["closest_match"])
        self.assertGreater(len(result["failed_rules"]), 0)

    def test_recommended_has_one_candidate(self):
        req = SlideRequirements(cabinet_depth_mm=550, drawer_weight_kg=10.0)
        result = self.solver.solve_with_explanation(req)
        candidates = result["recommended"]["candidates"]
        self.assertEqual(len(candidates), 1)
        self.assertIn("slide", candidates)

    def test_constraint_trace_has_8_rules(self):
        req = SlideRequirements(cabinet_depth_mm=550, drawer_weight_kg=10.0)
        result = self.solver.solve_with_explanation(req)
        trace = result["recommended"]["constraint_trace"]
        self.assertEqual(len(trace), 8)


if __name__ == "__main__":
    unittest.main()
