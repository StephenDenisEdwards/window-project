"""Tests for the staged pipeline solver using LED lighting.

The staged solver splits evaluation into two stages:
  Stage 1: light_bar × driver  →  electrical rules (LED001-003, 006-008)
  Stage 2: valid_pair × dimmer  →  dimming rules (LED004, 005, 009)

Invalid bar-driver pairs are pruned before dimmer evaluation, reducing
the total number of rule evaluations compared to the flat N-candidate
approach.

These tests use the same product data and scenarios as test_n_candidate.py
so results can be compared.
"""

import pytest

from engine_v2.core.solver_staged import StagedPipelineSolver, StagedFamilyConfig, Stage
from engine_v2.families.led_lighting.models import (
    Dimmer,
    Driver,
    LightBar,
    LightingRequirements,
    Voltage,
)
from engine_v2.families.led_lighting.rules import STAGE_1_RULES, STAGE_2_RULES
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


# --- Family config with two stages ---

LED_STAGED_CONFIG = StagedFamilyConfig(
    name="led_lighting_staged",
    roles=[
        ("light_bar", LightBar),
        ("driver", Driver),
        ("dimmer", Dimmer),
    ],
    requirements_type=LightingRequirements,
    stages=[
        Stage(
            name="electrical_compatibility",
            new_roles=["light_bar", "driver"],
            rules=STAGE_1_RULES,
            early_termination=True,
        ),
        Stage(
            name="dimming_compatibility",
            new_roles=["dimmer"],
            rules=STAGE_2_RULES,
            early_termination=True,
        ),
    ],
    rank_key=lambda c: (
        0 if c.total_price_usd is not None else 1,
        c.total_price_usd or 0,
    ),
)


def make_solver(bars=None, drivers=None, dimmers=None):
    return StagedPipelineSolver(
        config=LED_STAGED_CONFIG,
        product_lists={
            "light_bar": bars or ALL_BARS,
            "driver": drivers or ALL_DRIVERS,
            "dimmer": dimmers or ALL_DIMMERS,
        },
    )


# ===== Basic functionality =====

class TestStagedBasic:
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

    def test_rule_results_span_both_stages(self):
        """Valid configs should have rule results from both stages."""
        solver = make_solver()
        req = LightingRequirements(cabinet_length_mm=600)
        results = solver.solve(req)
        if results:
            # Should have rules from Stage 1 (LED001-003, 006-008) and Stage 2 (LED004, 005, 009)
            rule_ids = {r.rule_id for r in results[0].rule_results}
            assert "LED001" in rule_ids  # Stage 1
            assert "LED004" in rule_ids  # Stage 2


# ===== Stage pruning =====

class TestStagedPruning:
    def test_voltage_mismatch_pruned_at_stage_1(self):
        """12V bar + 24V driver should be pruned at Stage 1 — never reach Stage 2."""
        solver = make_solver(
            bars=[BAR_12V_5W],
            drivers=[DRV_24V_60W],
            dimmers=[DIM_0_10V_200W],
        )
        req = LightingRequirements(cabinet_length_mm=600)
        results = solver.solve(req)
        assert len(results) == 0

    def test_stage_1_prunes_before_stage_2(self):
        """Stage 1 should prune incompatible bar-driver pairs before dimmer evaluation.

        With 5 bars × 4 drivers = 20 pairs, many will fail voltage/connector checks.
        Stage 2 should see fewer than 20 × 4 dimmers = 80 combinations.
        (We can't directly observe the pruning count, but we can verify the result
        matches the N-candidate solver.)
        """
        from engine_v2.core.solver_n import NCandidateSolver, NFamilyConfig
        from engine_v2.families.led_lighting.rules import ALL_RULES

        n_config = NFamilyConfig(
            name="led_n",
            roles=[("light_bar", LightBar), ("driver", Driver), ("dimmer", Dimmer)],
            requirements_type=LightingRequirements,
            rules=ALL_RULES,
            early_termination=False,  # Disable to get full evaluation
        )
        n_solver = NCandidateSolver(
            config=n_config,
            product_lists={"light_bar": ALL_BARS, "driver": ALL_DRIVERS, "dimmer": ALL_DIMMERS},
        )
        staged_solver = make_solver()

        req = LightingRequirements(cabinet_length_mm=1000)

        n_results = n_solver.solve(req)
        staged_results = staged_solver.solve(req)

        # Both should find the same number of valid configurations
        assert len(n_results) == len(staged_results)

        # And the same products in the recommended config
        if n_results and staged_results:
            n_rec = {role: p.sku for role, p in n_results[0].candidates.items()}
            s_rec = {role: p.sku for role, p in staged_results[0].candidates.items()}
            assert n_rec == s_rec


# ===== Constraint validation (same scenarios as N-candidate) =====

class TestStagedConstraints:
    def test_voltage_match_accepted(self):
        solver = make_solver(
            bars=[BAR_12V_5W],
            drivers=[DRV_12V_30W],
            dimmers=[DIM_TRAILING_150W],
        )
        req = LightingRequirements(cabinet_length_mm=600)
        results = solver.solve(req)
        assert len(results) == 1

    def test_wattage_overload_rejected(self):
        solver = make_solver(
            bars=[BAR_24V_15W],
            drivers=[DRV_24V_20W],
            dimmers=[DIM_TRAILING_150W],
        )
        req = LightingRequirements(cabinet_length_mm=1000, num_light_bars=3)
        results = solver.solve(req)
        assert len(results) == 0

    def test_bar_too_long_rejected(self):
        solver = make_solver(
            bars=[BAR_12V_LONG],
            drivers=[DRV_12V_30W],
            dimmers=[DIM_TRAILING_150W],
        )
        req = LightingRequirements(cabinet_length_mm=500)
        results = solver.solve(req)
        assert len(results) == 0

    def test_dimming_protocol_mismatch_rejected(self):
        solver = make_solver(
            bars=[BAR_12V_5W],
            drivers=[DRV_12V_30W],
            dimmers=[DIM_0_10V_200W],
        )
        req = LightingRequirements(cabinet_length_mm=600, dimming_required=True)
        results = solver.solve(req)
        assert len(results) == 0

    def test_dimming_protocol_match_accepted(self):
        solver = make_solver(
            bars=[BAR_12V_5W],
            drivers=[DRV_12V_30W],
            dimmers=[DIM_TRAILING_150W],
        )
        req = LightingRequirements(cabinet_length_mm=600, dimming_required=True)
        results = solver.solve(req)
        assert len(results) == 1

    def test_non_dimmable_driver_rejected(self):
        solver = make_solver(
            bars=[BAR_12V_5W],
            drivers=[DRV_12V_15W_NODIM],
            dimmers=[DIM_TRAILING_150W],
        )
        req = LightingRequirements(cabinet_length_mm=600, dimming_required=True)
        results = solver.solve(req)
        assert len(results) == 0

    def test_dimmer_voltage_incompatible_rejected(self):
        solver = make_solver(
            bars=[BAR_24V_8W_DIM],
            drivers=[DRV_24V_20W],
            dimmers=[DIM_TRAILING_SMALL],  # 12V only
        )
        req = LightingRequirements(cabinet_length_mm=600)
        results = solver.solve(req)
        assert len(results) == 0


# ===== Solve with explanation =====

class TestStagedExplanation:
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
            bars=[BAR_12V_LONG],
            drivers=[DRV_24V_60W],
            dimmers=[DIM_LEADING],
        )
        req = LightingRequirements(cabinet_length_mm=500)
        result = solver.solve_with_explanation(req)
        assert result["status"] == "no_solution"
        assert result["closest_match"] is not None
        assert len(result["failed_rules"]) > 0

    def test_constraint_trace_includes_both_stages(self):
        solver = make_solver()
        req = LightingRequirements(cabinet_length_mm=600)
        result = solver.solve_with_explanation(req)
        trace = result["recommended"]["constraint_trace"]
        rule_ids = {r["rule"] for r in trace}
        # Stage 1 rules
        assert "LED001" in rule_ids
        assert "LED003" in rule_ids
        # Stage 2 rules
        assert "LED004" in rule_ids
        assert "LED005" in rule_ids


# ===== Stage configuration validation =====

class TestStagedConfig:
    def test_missing_role_in_stages_raises(self):
        """If a role isn't introduced by any stage, config should error."""
        with pytest.raises(ValueError, match="not introduced by any stage"):
            StagedFamilyConfig(
                name="bad",
                roles=[
                    ("light_bar", LightBar),
                    ("driver", Driver),
                    ("dimmer", Dimmer),
                ],
                requirements_type=LightingRequirements,
                stages=[
                    Stage(name="stage1", new_roles=["light_bar", "driver"], rules=[]),
                    # dimmer is missing from all stages
                ],
            )

    def test_missing_product_list_raises(self):
        """If a role's product list is missing, solver should error."""
        with pytest.raises(ValueError, match="Missing product list"):
            StagedPipelineSolver(
                config=LED_STAGED_CONFIG,
                product_lists={
                    "light_bar": ALL_BARS,
                    "driver": ALL_DRIVERS,
                    # "dimmer" missing
                },
            )


# ===== Cross-solver consistency =====

class TestCrossSolverConsistency:
    """Verify that N-candidate and staged solvers produce identical results."""

    def _make_both_solvers(self, bars=None, drivers=None, dimmers=None):
        from engine_v2.core.solver_n import NCandidateSolver, NFamilyConfig
        from engine_v2.families.led_lighting.rules import ALL_RULES

        products = {
            "light_bar": bars or ALL_BARS,
            "driver": drivers or ALL_DRIVERS,
            "dimmer": dimmers or ALL_DIMMERS,
        }

        n_config = NFamilyConfig(
            name="led_n",
            roles=[("light_bar", LightBar), ("driver", Driver), ("dimmer", Dimmer)],
            requirements_type=LightingRequirements,
            rules=ALL_RULES,
            early_termination=False,
        )
        n_solver = NCandidateSolver(config=n_config, product_lists=dict(products))
        staged_solver = make_solver(**{
            "bars": products["light_bar"],
            "drivers": products["driver"],
            "dimmers": products["dimmer"],
        })
        return n_solver, staged_solver

    def test_same_valid_count_simple(self):
        n_solver, staged_solver = self._make_both_solvers(
            bars=[BAR_12V_5W],
            drivers=[DRV_12V_30W],
            dimmers=[DIM_TRAILING_150W],
        )
        req = LightingRequirements(cabinet_length_mm=600)
        assert len(n_solver.solve(req)) == len(staged_solver.solve(req))

    def test_same_valid_count_full_catalog(self):
        n_solver, staged_solver = self._make_both_solvers()
        req = LightingRequirements(cabinet_length_mm=1000)
        n_results = n_solver.solve(req)
        staged_results = staged_solver.solve(req)
        assert len(n_results) == len(staged_results)

    def test_same_valid_count_dimming_required(self):
        n_solver, staged_solver = self._make_both_solvers()
        req = LightingRequirements(cabinet_length_mm=600, dimming_required=True)
        assert len(n_solver.solve(req)) == len(staged_solver.solve(req))

    def test_same_recommended_sku(self):
        n_solver, staged_solver = self._make_both_solvers()
        req = LightingRequirements(cabinet_length_mm=600)
        n_results = n_solver.solve(req)
        staged_results = staged_solver.solve(req)
        if n_results and staged_results:
            n_skus = sorted(p.sku for p in n_results[0].candidates.values())
            s_skus = sorted(p.sku for p in staged_results[0].candidates.values())
            assert n_skus == s_skus

    def test_no_solution_both_agree(self):
        n_solver, staged_solver = self._make_both_solvers(
            bars=[BAR_12V_LONG],
            drivers=[DRV_24V_60W],
            dimmers=[DIM_LEADING],
        )
        req = LightingRequirements(cabinet_length_mm=500)
        n_result = n_solver.solve_with_explanation(req)
        s_result = staged_solver.solve_with_explanation(req)
        assert n_result["status"] == "no_solution"
        assert s_result["status"] == "no_solution"
