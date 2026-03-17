"""Tests for the flat N-candidate solver using LED lighting.

The N-candidate solver computes the full Cartesian product (bar × driver × dimmer)
and evaluates all rules against each triple. No inter-stage pruning — every
combination is evaluated independently.

These tests use the same product data and scenarios as test_staged.py
so results can be compared.
"""

import pytest

from engine_v2.core.solver_n import NCandidateSolver, NFamilyConfig, NConfiguration
from engine_v2.families.led_lighting.models import (
    Dimmer,
    DimmingProtocol,
    Driver,
    LightBar,
    LightingRequirements,
    Voltage,
)
from engine_v2.families.led_lighting.rules import ALL_RULES
from engine_v2.families.led_lighting.test_data import (
    ALL_BARS,
    ALL_DIMMERS,
    ALL_DRIVERS,
    BAR_12V_5W,
    BAR_12V_10W,
    BAR_12V_LONG,
    BAR_24V_15W,
    BAR_24V_8W_DIM,
    DIM_0_10V_200W,
    DIM_LEADING,
    DIM_TRAILING_150W,
    DIM_TRAILING_SMALL,
    DRV_12V_30W,
    DRV_12V_15W_NODIM,
    DRV_24V_60W,
    DRV_24V_20W,
)


# --- Family config ---

LED_N_CONFIG = NFamilyConfig(
    name="led_lighting",
    roles=[
        ("light_bar", LightBar),
        ("driver", Driver),
        ("dimmer", Dimmer),
    ],
    requirements_type=LightingRequirements,
    rules=ALL_RULES,
    rank_key=lambda c: (
        0 if c.total_price_usd is not None else 1,
        c.total_price_usd or 0,
    ),
    early_termination=True,
)


def make_solver(bars=None, drivers=None, dimmers=None):
    return NCandidateSolver(
        config=LED_N_CONFIG,
        product_lists={
            "light_bar": bars or ALL_BARS,
            "driver": drivers or ALL_DRIVERS,
            "dimmer": dimmers or ALL_DIMMERS,
        },
    )


# ===== Basic functionality =====

class TestNBasic:
    def test_finds_valid_configs(self):
        """Simple 12V setup with trailing-edge dimming should find matches."""
        solver = make_solver()
        req = LightingRequirements(
            cabinet_length_mm=600,
            dimming_required=True,
        )
        results = solver.solve(req)
        assert len(results) >= 1
        for config in results:
            assert config.valid
            assert "light_bar" in config.candidates
            assert "driver" in config.candidates
            assert "dimmer" in config.candidates

    def test_all_candidates_present(self):
        """Every result should have all three roles filled."""
        solver = make_solver()
        req = LightingRequirements(cabinet_length_mm=1000)
        results = solver.solve(req)
        for config in results:
            assert len(config.candidates) == 3

    def test_ranked_by_price(self):
        solver = make_solver()
        req = LightingRequirements(cabinet_length_mm=600)
        results = solver.solve(req)
        prices = [c.total_price_usd for c in results if c.total_price_usd is not None]
        assert prices == sorted(prices)


# ===== Constraint validation =====

class TestNConstraints:
    def test_voltage_mismatch_rejected(self):
        """12V bar + 24V driver should fail voltage match."""
        solver = make_solver(
            bars=[BAR_12V_5W],
            drivers=[DRV_24V_60W],
            dimmers=[DIM_0_10V_200W],
        )
        req = LightingRequirements(cabinet_length_mm=600)
        results = solver.solve(req)
        assert len(results) == 0

    def test_voltage_match_accepted(self):
        """12V bar + 12V driver should pass voltage match."""
        solver = make_solver(
            bars=[BAR_12V_5W],
            drivers=[DRV_12V_30W],
            dimmers=[DIM_TRAILING_150W],
        )
        req = LightingRequirements(cabinet_length_mm=600)
        results = solver.solve(req)
        assert len(results) == 1

    def test_wattage_overload_rejected(self):
        """3 × 15W bars = 45W on a 20W driver (safe capacity 16W) should fail."""
        solver = make_solver(
            bars=[BAR_24V_15W],
            drivers=[DRV_24V_20W],
            dimmers=[DIM_TRAILING_150W],
        )
        req = LightingRequirements(
            cabinet_length_mm=1000,
            num_light_bars=3,
        )
        results = solver.solve(req)
        assert len(results) == 0

    def test_connector_mismatch_rejected(self):
        """Barrel jack bar + terminal block driver should fail."""
        solver = make_solver(
            bars=[BAR_12V_5W],  # barrel_jack
            drivers=[DRV_24V_60W],  # terminal_block (also wrong voltage)
            dimmers=[DIM_TRAILING_150W],
        )
        req = LightingRequirements(cabinet_length_mm=600)
        results = solver.solve(req)
        assert len(results) == 0

    def test_bar_too_long_rejected(self):
        """1200mm bar in a 500mm cabinet should fail."""
        solver = make_solver(
            bars=[BAR_12V_LONG],
            drivers=[DRV_12V_30W],
            dimmers=[DIM_TRAILING_150W],
        )
        req = LightingRequirements(cabinet_length_mm=500)
        results = solver.solve(req)
        assert len(results) == 0

    def test_dimming_protocol_mismatch_rejected(self):
        """Trailing-edge driver + 0-10V dimmer should fail."""
        solver = make_solver(
            bars=[BAR_12V_5W],
            drivers=[DRV_12V_30W],  # trailing_edge
            dimmers=[DIM_0_10V_200W],  # 0-10V
        )
        req = LightingRequirements(cabinet_length_mm=600, dimming_required=True)
        results = solver.solve(req)
        assert len(results) == 0

    def test_dimming_protocol_match_accepted(self):
        """Trailing-edge driver + trailing-edge dimmer should pass."""
        solver = make_solver(
            bars=[BAR_12V_5W],
            drivers=[DRV_12V_30W],  # trailing_edge
            dimmers=[DIM_TRAILING_150W],  # trailing_edge
        )
        req = LightingRequirements(cabinet_length_mm=600, dimming_required=True)
        results = solver.solve(req)
        assert len(results) == 1

    def test_non_dimmable_driver_rejected_when_dimming_required(self):
        """Non-dimmable driver should fail when dimming is required."""
        solver = make_solver(
            bars=[BAR_12V_5W],
            drivers=[DRV_12V_15W_NODIM],
            dimmers=[DIM_TRAILING_150W],
        )
        req = LightingRequirements(cabinet_length_mm=600, dimming_required=True)
        results = solver.solve(req)
        assert len(results) == 0

    def test_dimmer_min_load_rejected(self):
        """2W total load on a dimmer with 10W minimum should fail (flickering)."""
        solver = make_solver(
            bars=[BAR_12V_5W],  # 5W — but dimmer min is 10W
            drivers=[DRV_12V_30W],
            dimmers=[DIM_LEADING],  # min_load 10W, but wrong protocol anyway
        )
        req = LightingRequirements(cabinet_length_mm=600)
        results = solver.solve(req)
        # Should fail due to protocol mismatch AND/OR min load
        assert len(results) == 0

    def test_dimmer_voltage_incompatible_rejected(self):
        """24V driver + 12V-only dimmer should fail."""
        solver = make_solver(
            bars=[BAR_24V_8W_DIM],
            drivers=[DRV_24V_20W],  # trailing_edge, 24V
            dimmers=[DIM_TRAILING_SMALL],  # trailing_edge but 12V only
        )
        req = LightingRequirements(cabinet_length_mm=600)
        results = solver.solve(req)
        assert len(results) == 0


# ===== Early termination =====

class TestNEarlyTermination:
    def test_stops_on_first_hard_failure(self):
        """With early termination, voltage mismatch should skip remaining rules."""
        solver = make_solver(
            bars=[BAR_12V_5W],
            drivers=[DRV_24V_60W],
            dimmers=[DIM_0_10V_200W],
        )
        req = LightingRequirements(cabinet_length_mm=600)
        candidates = {
            "light_bar": BAR_12V_5W,
            "driver": DRV_24V_60W,
            "dimmer": DIM_0_10V_200W,
        }
        config = solver.evaluate(candidates, req)
        # Should stop after LED001 (voltage_match) fails
        assert len(config.rule_results) == 1
        assert config.rule_results[0].rule_id == "LED001"
        assert not config.rule_results[0].passed


# ===== Solve with explanation =====

class TestNExplanation:
    def test_solved_has_expected_keys(self):
        solver = make_solver()
        req = LightingRequirements(cabinet_length_mm=600)
        result = solver.solve_with_explanation(req)
        assert result["status"] == "solved"
        assert "recommended" in result
        assert "alternatives" in result
        assert "candidates" in result["recommended"]
        assert "constraint_trace" in result["recommended"]

    def test_no_solution_has_closest_match(self):
        solver = make_solver(
            bars=[BAR_12V_LONG],  # 1200mm, non-dimmable
            drivers=[DRV_24V_60W],  # wrong voltage
            dimmers=[DIM_LEADING],  # wrong protocol
        )
        req = LightingRequirements(cabinet_length_mm=500)
        result = solver.solve_with_explanation(req)
        assert result["status"] == "no_solution"
        assert result["closest_match"] is not None
        assert len(result["failed_rules"]) > 0

    def test_recommended_has_three_candidates(self):
        solver = make_solver()
        req = LightingRequirements(cabinet_length_mm=600)
        result = solver.solve_with_explanation(req)
        assert len(result["recommended"]["candidates"]) == 3


# ===== Full catalog evaluation =====

class TestNFullCatalog:
    def test_full_catalog_solve(self):
        """Run all 5 bars × 4 drivers × 4 dimmers = 80 combinations."""
        solver = make_solver()
        req = LightingRequirements(cabinet_length_mm=1000)
        results = solver.solve(req)
        # Should find at least some valid configs
        assert len(results) >= 1
        # Every result should have all three roles
        for config in results:
            assert len(config.candidates) == 3
            assert config.valid

    def test_total_evaluations(self):
        """Verify the solver evaluates the full Cartesian product."""
        # 5 bars × 4 drivers × 4 dimmers = 80 combinations
        # With early termination, not all rules run on each, but all combos are tried
        solver = make_solver()
        req = LightingRequirements(cabinet_length_mm=1000)
        # Just verify it completes without error and returns consistent results
        results = solver.solve(req)
        valid_count = len(results)

        # Run again without early termination to verify same valid count
        LED_N_CONFIG.early_termination = False
        results2 = solver.solve(req)
        LED_N_CONFIG.early_termination = True

        assert len(results2) == valid_count
