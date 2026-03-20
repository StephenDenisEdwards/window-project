"""Staged pipeline constraint solver.

Decomposes an N-candidate problem into sequential stages. Each stage
evaluates a subset of products, filters to valid combinations, and feeds
results into the next stage.

Example for LED lighting:
  Stage 1: light_bar × driver  →  electrical rules  →  valid pairs
  Stage 2: valid_pair × dimmer  →  dimming rules     →  valid triples

Trade-off: More complex to configure, but prunes aggressively between
stages. If Stage 1 eliminates 90% of pairs, Stage 2 evaluates 10× fewer
combinations than the flat N-candidate approach.

Key concept: each stage produces "partial configurations" — dicts of
{role: product} that grow as they pass through stages. A stage takes
the output of the previous stage and crosses it with one or more new
product roles.
"""

from itertools import product as cartesian_product
from typing import Any, Callable, Optional

from pydantic import BaseModel

from engine_v2.core.models import Product, Requirements, RuleCategory, RuleResult


class StagedConfiguration(BaseModel):
    """A configuration built up across pipeline stages.

    candidates accumulate as the config passes through stages.
    rule_results include traces from ALL stages, in order.
    """

    candidates: dict[str, Product]
    rule_results: list[RuleResult] = []
    derived: dict = {}

    @property
    def valid(self) -> bool:
        return all(r.passed for r in self.rule_results)

    @property
    def failed_rules(self) -> list[RuleResult]:
        return [r for r in self.rule_results if not r.passed]

    @property
    def passed_count(self) -> int:
        return sum(1 for r in self.rule_results if r.passed)

    @property
    def total_price_usd(self) -> Optional[float]:
        prices = [c.price_usd for c in self.candidates.values()]
        if any(p is None for p in prices):
            return None
        qty = self.derived.get("quantity", 1)
        return sum(prices) * qty  # type: ignore


# Rule function for staged solver — receives candidates accumulated so far
StagedRuleFn = Callable[[dict[str, Product], Requirements, dict], RuleResult]
StagedRankKeyFn = Callable[[StagedConfiguration], Any]
StagedDerivedFn = Callable[[Requirements], dict]
StagedPreFilterFn = Callable[[str, list[Product], Requirements], list[Product]]


class Stage:
    """One stage in the pipeline.

    A stage introduces one or more new product roles and evaluates
    rules that involve those roles (and any roles from prior stages).

    Attributes:
        name: Human-readable stage name (e.g., "electrical_compatibility")
        new_roles: Roles introduced at this stage (e.g., ["driver"])
        rules: Rules evaluated at this stage — they can reference any role
               from this stage or prior stages
        early_termination: Stop rule evaluation on first hard constraint failure
    """

    def __init__(
        self,
        name: str,
        new_roles: list[str],
        rules: list[StagedRuleFn],
        early_termination: bool = True,
    ):
        self.name = name
        self.new_roles = new_roles
        self.rules = rules
        self.early_termination = early_termination


class StagedFamilyConfig:
    """Configuration for a staged pipeline family.

    Instead of a flat list of rules, the family defines a sequence of stages.
    Each stage introduces new product roles and evaluates stage-specific rules.
    """

    def __init__(
        self,
        name: str,
        roles: list[tuple[str, type[Product]]],
        requirements_type: type[Requirements],
        stages: list[Stage],
        pre_filters: list[StagedPreFilterFn] | None = None,
        rank_key: StagedRankKeyFn | None = None,
        derived_values: StagedDerivedFn | None = None,
    ):
        self.name = name
        self.roles = roles
        self.requirements_type = requirements_type
        self.stages = stages
        self.pre_filters = pre_filters or []
        self.rank_key = rank_key or (lambda c: (0 if c.total_price_usd else 1, c.total_price_usd or 0))
        self.derived_values = derived_values or (lambda r: {})

        # Validate that every role is introduced by exactly one stage
        all_stage_roles = []
        for stage in stages:
            all_stage_roles.extend(stage.new_roles)
        role_names = [name for name, _ in roles]
        missing = set(role_names) - set(all_stage_roles)
        if missing:
            raise ValueError(f"Roles {missing} are not introduced by any stage")

    @property
    def role_names(self) -> list[str]:
        return [name for name, _ in self.roles]


class StagedPipelineSolver:
    """Solver that evaluates products through a multi-stage pipeline.

    Each stage:
      1. Takes partial configurations from the previous stage (or empty for Stage 1)
      2. Crosses them with new product role(s) introduced at this stage
      3. Evaluates stage-specific rules
      4. Filters to valid-so-far configurations
      5. Passes valid configs to the next stage

    This means invalid combinations are pruned early — Stage 2 never
    sees pairs that failed Stage 1.

    Usage:
        solver = StagedPipelineSolver(
            config=led_lighting_staged_config,
            product_lists={
                "light_bar": [bar1, bar2, ...],
                "driver": [drv1, drv2, ...],
                "dimmer": [dim1, dim2, ...],
            }
        )
        results = solver.solve(requirements)
    """

    def __init__(self, config: StagedFamilyConfig, product_lists: dict[str, list[Product]]):
        self.config = config
        self.product_lists = product_lists

        for role_name, _ in config.roles:
            if role_name not in product_lists:
                raise ValueError(f"Missing product list for role {role_name!r}")

    def _apply_pre_filters(self, req: Requirements) -> dict[str, list[Product]]:
        filtered = dict(self.product_lists)
        for filt in self.config.pre_filters:
            for role_name in self.config.role_names:
                filtered[role_name] = filt(role_name, filtered[role_name], req)
        return filtered

    def _evaluate_stage(
        self,
        stage: Stage,
        candidates: dict[str, Product],
        req: Requirements,
        derived: dict,
    ) -> list[RuleResult]:
        """Evaluate a single stage's rules against the current candidate set."""
        results: list[RuleResult] = []
        for rule in stage.rules:
            result = rule(candidates, req, derived)
            results.append(result)
            if (
                stage.early_termination
                and not result.passed
                and result.category == RuleCategory.HARD_CONSTRAINT
            ):
                break
        return results

    def solve(self, req: Requirements) -> list[StagedConfiguration]:
        """Run the full pipeline and return valid configurations."""
        filtered = self._apply_pre_filters(req)
        derived = self.config.derived_values(req)

        # Start with empty partial configurations
        partials: list[StagedConfiguration] = [
            StagedConfiguration(candidates={}, derived=derived)
        ]

        for stage in self.config.stages:
            next_partials: list[StagedConfiguration] = []

            # Get product lists for the new roles in this stage
            new_role_lists = [filtered[role] for role in stage.new_roles]

            for partial in partials:
                # Cross the existing partial config with all combos of new roles
                for new_combo in cartesian_product(*new_role_lists):
                    # Build the expanded candidate set
                    expanded = dict(partial.candidates)
                    for role_name, product in zip(stage.new_roles, new_combo):
                        expanded[role_name] = product

                    # Evaluate this stage's rules
                    stage_results = self._evaluate_stage(stage, expanded, req, derived)

                    # Carry forward rule results from previous stages
                    all_results = list(partial.rule_results) + stage_results

                    new_config = StagedConfiguration(
                        candidates=expanded,
                        rule_results=all_results,
                        derived=derived,
                    )

                    # Only pass valid-so-far configs to next stage
                    if all(r.passed for r in stage_results):
                        next_partials.append(new_config)

            partials = next_partials

            # If no configs survived this stage, stop early
            if not partials:
                break

        return sorted(partials, key=self.config.rank_key)

    def solve_with_explanation(self, req: Requirements) -> dict:
        """Solve and return structured results with per-stage traces."""
        valid = self.solve(req)

        if valid:
            recommended = valid[0]
            return {
                "status": "solved",
                "message": f"Found {len(valid)} valid configuration(s)",
                "recommended": self._config_to_dict(recommended),
                "alternatives": [self._config_to_dict(c) for c in valid[1:]],
            }

        closest = self._best_failing(req)
        return {
            "status": "no_solution",
            "message": "No valid configuration exists for these requirements",
            "closest_match": self._config_to_dict(closest) if closest else None,
            "failed_rules": [
                {"rule": r.rule_id, "name": r.rule_name, "detail": r.detail, "remediation": r.remediation}
                for r in (closest.failed_rules if closest else [])
            ],
        }

    def _best_failing(self, req: Requirements) -> Optional[StagedConfiguration]:
        """Find the combination that passes the most rules across all stages.

        Unlike solve(), this does NOT prune between stages — it evaluates
        every combination through every stage to find the closest match.
        """
        filtered = self._apply_pre_filters(req)
        derived = self.config.derived_values(req)

        best: Optional[StagedConfiguration] = None
        best_count = -1

        # Build all role lists in stage order
        all_role_names: list[str] = []
        all_role_lists: list[list[Product]] = []
        all_rules: list[StagedRuleFn] = []

        for stage in self.config.stages:
            for role in stage.new_roles:
                all_role_names.append(role)
                all_role_lists.append(filtered[role])
            all_rules.extend(stage.rules)

        # Evaluate full Cartesian product (no pruning)
        for combo in cartesian_product(*all_role_lists):
            candidates = dict(zip(all_role_names, combo))
            results = []
            for rule in all_rules:
                results.append(rule(candidates, req, derived))

            config = StagedConfiguration(
                candidates=candidates,
                rule_results=results,
                derived=derived,
            )
            if config.passed_count > best_count:
                best = config
                best_count = config.passed_count

        return best

    @staticmethod
    def _config_to_dict(config: StagedConfiguration) -> dict:
        return {
            "candidates": {role: p.model_dump() for role, p in config.candidates.items()},
            "derived": config.derived,
            "total_price_usd": config.total_price_usd,
            "valid": config.valid,
            "constraint_trace": [
                {
                    "rule": r.rule_id,
                    "name": r.rule_name,
                    "passed": r.passed,
                    "detail": r.detail,
                    "category": r.category.value,
                    "remediation": r.remediation,
                }
                for r in config.rule_results
            ],
        }
