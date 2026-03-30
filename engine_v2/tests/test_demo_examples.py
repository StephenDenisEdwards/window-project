"""Tests for every preset example in the web demo (demo/app.py).

Each test class corresponds to one preset scenario from the EXAMPLES dict
in the demo app. Tests exercise solve_with_explanation() and verify status,
structure, and key domain invariants.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from engine_v2.core.solver_n import NCandidateSolver
from engine_v2.families.concealed_hinge.config import HINGE_N_CONFIG
from engine_v2.families.concealed_hinge.loader import load_from_json as load_hinges
from engine_v2.families.concealed_hinge.models import (
    ApplicationType,
    CabinetPosition,
    CabinetType,
    HingeRequirements,
)
from engine_v2.families.drawer_slide.config import SLIDE_N_CONFIG
from engine_v2.families.drawer_slide.loader import load_from_json as load_slides
from engine_v2.families.drawer_slide.models import (
    ExtensionType,
    SlideMountType,
    SlideRequirements,
)
from engine_v2.families.led_lighting.config import LED_N_CONFIG
from engine_v2.families.led_lighting.loader import load_from_json as load_led
from engine_v2.families.led_lighting.models import LightingRequirements

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "sample-data"


# ── Shared helpers ────────────────────────────────────────────────────

def _hinge_solver() -> NCandidateSolver:
    hinges, plates = load_hinges(DATA_DIR)
    return NCandidateSolver(
        config=HINGE_N_CONFIG,
        product_lists={"hinge": hinges, "plate": plates},
    )


def _slide_solver() -> NCandidateSolver:
    slides = load_slides(DATA_DIR)
    return NCandidateSolver(
        config=SLIDE_N_CONFIG,
        product_lists={"slide": slides},
    )


def _led_solver() -> NCandidateSolver:
    bars, drivers, dimmers = load_led(DATA_DIR)
    return NCandidateSolver(
        config=LED_N_CONFIG,
        product_lists={"light_bar": bars, "driver": drivers, "dimmer": dimmers},
    )


def _assert_solved(test: unittest.TestCase, result: dict) -> None:
    """Common assertions for a successful solve."""
    test.assertEqual(result["status"], "solved")
    test.assertIn("recommended", result)
    test.assertIsNotNone(result["recommended"])
    test.assertIn("alternatives", result)
    test.assertIn("constraint_trace", result["recommended"])
    for rule in result["recommended"]["constraint_trace"]:
        test.assertTrue(rule["passed"], f"Rule {rule['rule']} failed: {rule['detail']}")


def _assert_no_solution(test: unittest.TestCase, result: dict) -> None:
    """Common assertions for a no-solution result."""
    test.assertEqual(result["status"], "no_solution")
    test.assertIn("closest_match", result)
    test.assertIsNotNone(result["closest_match"])
    test.assertIn("failed_rules", result)
    test.assertGreater(len(result["failed_rules"]), 0)


# ── Concealed Hinge examples ─────────────────────────────────────────

class TestHingeExample1StandardKitchen(unittest.TestCase):
    """Preset: Standard kitchen — Blum, full overlay."""

    def setUp(self):
        self.solver = _hinge_solver()
        self.req = HingeRequirements(
            cabinet_type=CabinetType.FRAMELESS,
            door_thickness_mm=19, door_height_mm=720,
            door_weight_kg=5.2, application=ApplicationType.FULL_OVERLAY,
            desired_overlay_mm=16, boring_pattern_mm=45,
            soft_close=True, preferred_brand="Blum",
        )

    def test_solves_successfully(self):
        result = self.solver.solve_with_explanation(self.req)
        _assert_solved(self, result)

    def test_all_products_are_blum(self):
        result = self.solver.solve_with_explanation(self.req)
        candidates = result["recommended"]["candidates"]
        self.assertEqual(candidates["hinge"]["brand"], "Blum")
        self.assertEqual(candidates["plate"]["brand"], "Blum")

    def test_has_14_rules_in_trace(self):
        result = self.solver.solve_with_explanation(self.req)
        self.assertEqual(len(result["recommended"]["constraint_trace"]), 14)


class TestHingeExample2CornerCabinet(unittest.TestCase):
    """Preset: Corner cabinet — wide-angle hinge needed."""

    def setUp(self):
        self.solver = _hinge_solver()
        self.req = HingeRequirements(
            cabinet_type=CabinetType.FRAMELESS,
            door_thickness_mm=19, door_height_mm=800,
            door_weight_kg=4.0, application=ApplicationType.FULL_OVERLAY,
            desired_overlay_mm=16, boring_pattern_mm=45,
            soft_close=True, cabinet_position=CabinetPosition.CORNER,
        )

    def test_solves_successfully(self):
        result = self.solver.solve_with_explanation(self.req)
        _assert_solved(self, result)

    def test_recommended_hinge_is_wide_angle(self):
        results = self.solver.solve(self.req)
        for config in results:
            self.assertGreaterEqual(config.candidates["hinge"].opening_angle_deg, 155)


class TestHingeExample3TallPantry(unittest.TestCase):
    """Preset: Tall pantry — 1600mm, heavy, Grass."""

    def setUp(self):
        self.solver = _hinge_solver()
        self.req = HingeRequirements(
            cabinet_type=CabinetType.FRAMELESS,
            door_thickness_mm=22, door_height_mm=1600,
            door_weight_kg=14.0, application=ApplicationType.FULL_OVERLAY,
            desired_overlay_mm=16, boring_pattern_mm=45,
            soft_close=True, preferred_brand="Grass",
        )

    def test_solves_successfully(self):
        result = self.solver.solve_with_explanation(self.req)
        _assert_solved(self, result)

    def test_four_hinges_per_door(self):
        results = self.solver.solve(self.req)
        for config in results:
            self.assertEqual(config.derived["hinges_per_door"], 4)

    def test_all_products_are_grass(self):
        result = self.solver.solve_with_explanation(self.req)
        candidates = result["recommended"]["candidates"]
        self.assertEqual(candidates["hinge"]["brand"], "Grass")
        self.assertEqual(candidates["plate"]["brand"], "Grass")


class TestHingeExample4AdjacentDoors(unittest.TestCase):
    """Preset: Adjacent doors — half overlay, shared partition."""

    def setUp(self):
        self.solver = _hinge_solver()
        self.req = HingeRequirements(
            cabinet_type=CabinetType.FRAMELESS,
            door_thickness_mm=19, door_height_mm=720,
            door_weight_kg=4.0, application=ApplicationType.HALF_OVERLAY,
            desired_overlay_mm=6, boring_pattern_mm=45,
            soft_close=True, preferred_brand="Blum",
            has_adjacent_door=True, adjacent_door_overlay_mm=6,
            partition_thickness_mm=19,
        )

    def test_solves_successfully(self):
        result = self.solver.solve_with_explanation(self.req)
        _assert_solved(self, result)

    def test_r012_adjacent_door_clearance_passes(self):
        results = self.solver.solve(self.req)
        for config in results:
            r012 = [r for r in config.rule_results if r.rule_id == "R012"]
            self.assertTrue(len(r012) > 0, "R012 should be evaluated")
            self.assertTrue(r012[0].passed, "R012 should pass — combined overlay fits partition")


class TestHingeExample5ImpossibleHeavyCorner(unittest.TestCase):
    """Preset: IMPOSSIBLE — heavy corner door (Blum, 12kg)."""

    def setUp(self):
        self.solver = _hinge_solver()
        self.req = HingeRequirements(
            cabinet_type=CabinetType.FRAMELESS,
            door_thickness_mm=22, door_height_mm=800,
            door_weight_kg=12.0, application=ApplicationType.FULL_OVERLAY,
            desired_overlay_mm=16, boring_pattern_mm=45,
            soft_close=True, cabinet_position=CabinetPosition.CORNER,
            preferred_brand="Blum",
        )

    def test_no_solution(self):
        result = self.solver.solve_with_explanation(self.req)
        _assert_no_solution(self, result)

    def test_closest_match_provided(self):
        result = self.solver.solve_with_explanation(self.req)
        self.assertIn("candidates", result["closest_match"])


class TestHingeExample6AllBrands(unittest.TestCase):
    """Preset: All brands — no preference, no soft-close."""

    def setUp(self):
        self.solver = _hinge_solver()
        self.req = HingeRequirements(
            cabinet_type=CabinetType.FRAMELESS,
            door_thickness_mm=19, door_height_mm=720,
            door_weight_kg=5.0, application=ApplicationType.FULL_OVERLAY,
            desired_overlay_mm=16, boring_pattern_mm=45,
            soft_close=False,
        )

    def test_solves_successfully(self):
        result = self.solver.solve_with_explanation(self.req)
        _assert_solved(self, result)

    def test_multiple_brands_in_results(self):
        results = self.solver.solve(self.req)
        brands = {c.candidates["hinge"].brand for c in results}
        self.assertGreater(len(brands), 1, "Without brand lock, multiple brands expected")

    def test_has_alternatives(self):
        result = self.solver.solve_with_explanation(self.req)
        self.assertGreater(len(result["alternatives"]), 0)


# ── Drawer Slide examples ────────────────────────────────────────────

class TestSlideExample1StandardKitchenDrawer(unittest.TestCase):
    """Preset: Standard kitchen drawer."""

    def setUp(self):
        self.solver = _slide_solver()
        self.req = SlideRequirements(
            cabinet_depth_mm=550, drawer_weight_kg=15.0,
        )

    def test_solves_successfully(self):
        result = self.solver.solve_with_explanation(self.req)
        _assert_solved(self, result)

    def test_single_candidate_per_config(self):
        results = self.solver.solve(self.req)
        for config in results:
            self.assertEqual(len(config.candidates), 1)
            self.assertIn("slide", config.candidates)

    def test_all_slides_handle_load(self):
        results = self.solver.solve(self.req)
        for config in results:
            self.assertGreaterEqual(config.candidates["slide"].max_load_kg, 15.0)


class TestSlideExample2HeavyDuty(unittest.TestCase):
    """Preset: Heavy-duty — 42kg load."""

    def setUp(self):
        self.solver = _slide_solver()
        self.req = SlideRequirements(
            cabinet_depth_mm=550, drawer_weight_kg=42.0,
        )

    def test_solves_successfully(self):
        result = self.solver.solve_with_explanation(self.req)
        _assert_solved(self, result)

    def test_all_slides_rated_for_42kg(self):
        results = self.solver.solve(self.req)
        for config in results:
            self.assertGreaterEqual(config.candidates["slide"].max_load_kg, 42.0)


class TestSlideExample3BlumUndermount(unittest.TestCase):
    """Preset: Blum undermount, soft-close, full extension."""

    def setUp(self):
        self.solver = _slide_solver()
        self.req = SlideRequirements(
            cabinet_depth_mm=550, drawer_weight_kg=20.0,
            extension_type=ExtensionType.FULL,
            mount_type=SlideMountType.UNDERMOUNT,
            soft_close=True, preferred_brand="Blum",
        )

    def test_solves_successfully(self):
        result = self.solver.solve_with_explanation(self.req)
        _assert_solved(self, result)

    def test_recommended_is_blum_undermount_full(self):
        result = self.solver.solve_with_explanation(self.req)
        slide = result["recommended"]["candidates"]["slide"]
        self.assertEqual(slide["brand"], "Blum")


class TestSlideExample4ImpossibleShallowCabinet(unittest.TestCase):
    """Preset: IMPOSSIBLE — cabinet too shallow."""

    def setUp(self):
        self.solver = _slide_solver()
        self.req = SlideRequirements(
            cabinet_depth_mm=300, drawer_weight_kg=5.0,
        )

    def test_no_solution(self):
        result = self.solver.solve_with_explanation(self.req)
        _assert_no_solution(self, result)


# ── LED Lighting examples ────────────────────────────────────────────

class TestLedExample1CabinetWithDimming(unittest.TestCase):
    """Preset: 600mm cabinet with dimming."""

    def setUp(self):
        self.solver = _led_solver()
        self.req = LightingRequirements(
            cabinet_length_mm=600, dimming_required=True, min_lumen_output=300,
        )

    def test_solves_successfully(self):
        result = self.solver.solve_with_explanation(self.req)
        _assert_solved(self, result)

    def test_recommended_has_three_candidates(self):
        result = self.solver.solve_with_explanation(self.req)
        candidates = result["recommended"]["candidates"]
        self.assertEqual(len(candidates), 3)
        self.assertIn("light_bar", candidates)
        self.assertIn("driver", candidates)
        self.assertIn("dimmer", candidates)

    def test_light_bar_fits_cabinet(self):
        results = self.solver.solve(self.req)
        for config in results:
            bar = config.candidates["light_bar"]
            self.assertLessEqual(bar.length_mm, 600)

    def test_brightness_meets_requirement(self):
        results = self.solver.solve(self.req)
        for config in results:
            bar = config.candidates["light_bar"]
            self.assertGreaterEqual(bar.lumen_output, 300)


class TestLedExample2LargeCabinetNoDimming(unittest.TestCase):
    """Preset: Large cabinet, no dimming."""

    def setUp(self):
        self.solver = _led_solver()
        self.req = LightingRequirements(
            cabinet_length_mm=900, dimming_required=False,
        )

    def test_solves_successfully(self):
        result = self.solver.solve_with_explanation(self.req)
        _assert_solved(self, result)

    def test_light_bar_fits_cabinet(self):
        results = self.solver.solve(self.req)
        for config in results:
            bar = config.candidates["light_bar"]
            self.assertLessEqual(bar.length_mm, 900)


class TestLedExample3HighBrightnessDimming(unittest.TestCase):
    """Preset: High brightness, dimming required.

    No bar in the sample catalog reaches 1000 lm with dimming at 800mm,
    so this is effectively an impossible scenario (like the other IMPOSSIBLE
    presets). The demo uses it to show failure explanation for brightness.
    """

    def setUp(self):
        self.solver = _led_solver()
        self.req = LightingRequirements(
            cabinet_length_mm=800, dimming_required=True, min_lumen_output=1000,
        )

    def test_no_solution(self):
        result = self.solver.solve_with_explanation(self.req)
        _assert_no_solution(self, result)

    def test_brightness_is_blocking_rule(self):
        result = self.solver.solve_with_explanation(self.req)
        failed_rule_ids = [r["rule"] for r in result["failed_rules"]]
        # LED007 = brightness check (bar output < required lumens)
        self.assertIn("LED007", failed_rule_ids,
                      "Brightness rule should be among failed constraints")


class TestLedExample4ImpossibleSmallCabinet(unittest.TestCase):
    """Preset: IMPOSSIBLE — cabinet too small (200mm)."""

    def setUp(self):
        self.solver = _led_solver()
        self.req = LightingRequirements(
            cabinet_length_mm=200, dimming_required=True, min_lumen_output=300,
        )

    def test_no_solution(self):
        result = self.solver.solve_with_explanation(self.req)
        _assert_no_solution(self, result)


if __name__ == "__main__":
    unittest.main()
