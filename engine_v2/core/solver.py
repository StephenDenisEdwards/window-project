"""Generic constraint solver — works on any registered product family."""

from typing import Optional

from engine_v2.core.models import Configuration, Product, Requirements, RuleCategory, RuleResult
from engine_v2.core.registry import FamilyConfig, FamilyRegistry, registry


class ConstraintSolver:
    """Family-agnostic constraint solver.

    Loads products, applies pre-filters, evaluates rules, and returns
    ranked configurations. Doesn't know what a hinge or drawer slide is.
    """

    def __init__(
        self,
        family: str,
        primaries: list[Product],
        secondaries: list[Product] | None = None,
        reg: FamilyRegistry | None = None,
    ):
        self._registry = reg or registry
        self._config = self._registry.get(family)
        self.primaries = primaries
        self.secondaries = secondaries or []

        if self._config.secondary_type and not self.secondaries:
            raise ValueError(
                f"Family {family!r} requires secondary products "
                f"({self._config.secondary_type.__name__}) but none were provided"
            )

    @property
    def family_config(self) -> FamilyConfig:
        return self._config

    def evaluate(
        self,
        primary: Product,
        secondary: Optional[Product],
        req: Requirements,
    ) -> Configuration:
        """Evaluate a single candidate against all rules."""
        derived = self._config.derived_values(req)
        results: list[RuleResult] = []

        for rule in self._config.rules:
            result = rule(primary, secondary, req, derived)
            results.append(result)

            # Early termination: skip remaining rules if a hard constraint failed
            if (
                self._config.early_termination
                and not result.passed
                and result.category == RuleCategory.HARD_CONSTRAINT
            ):
                break

        return Configuration(
            primary=primary,
            secondary=secondary,
            rule_results=results,
            derived=derived,
        )

    def _apply_pre_filters(self, req: Requirements) -> list[Product]:
        """Apply all registered pre-filters to narrow primary candidates."""
        candidates = self.primaries
        for filt in self._config.pre_filters:
            candidates = filt(candidates, req)
        return candidates

    def solve(self, req: Requirements) -> list[Configuration]:
        """Find all valid configurations, ranked by the family's ranking criteria."""
        filtered = self._apply_pre_filters(req)
        valid: list[Configuration] = []

        if self._config.secondary_type:
            # Paired family: evaluate primary × secondary
            for a in filtered:
                for b in self.secondaries:
                    config = self.evaluate(a, b, req)
                    if config.valid:
                        valid.append(config)
        else:
            # Single-product family: evaluate primary only
            for a in filtered:
                config = self.evaluate(a, None, req)
                if config.valid:
                    valid.append(config)

        return sorted(valid, key=self._config.rank_key)

    def solve_with_explanation(self, req: Requirements) -> dict:
        """Solve and return structured results with status, recommendations, and traces."""
        valid = self.solve(req)

        if valid:
            recommended = valid[0]
            return {
                "status": "solved",
                "message": f"Found {len(valid)} valid configuration(s)",
                "recommended": self._config_to_dict(recommended),
                "alternatives": [self._config_to_dict(c) for c in valid[1:]],
            }

        # No solution — find closest match
        closest = self._best_failing(req)
        result = {
            "status": "no_solution",
            "message": "No valid configuration exists for these requirements",
            "closest_match": self._config_to_dict(closest) if closest else None,
            "failed_rules": [],
        }
        if closest:
            result["failed_rules"] = [
                {
                    "rule": r.rule_id,
                    "name": r.rule_name,
                    "detail": r.detail,
                    "remediation": r.remediation,
                }
                for r in closest.failed_rules
            ]
        return result

    def _best_failing(self, req: Requirements) -> Optional[Configuration]:
        """Find the configuration that passes the most rules (closest to valid)."""
        # Temporarily disable early termination to get full traces
        saved = self._config.early_termination
        self._config.early_termination = False

        best: Optional[Configuration] = None
        best_count = -1

        filtered = self._apply_pre_filters(req)

        if self._config.secondary_type:
            for a in filtered:
                for b in self.secondaries:
                    config = self.evaluate(a, b, req)
                    if config.passed_count > best_count:
                        best = config
                        best_count = config.passed_count
        else:
            for a in filtered:
                config = self.evaluate(a, None, req)
                if config.passed_count > best_count:
                    best = config
                    best_count = config.passed_count

        self._config.early_termination = saved
        return best

    @staticmethod
    def _config_to_dict(config: Configuration) -> dict:
        return {
            "primary": config.primary.model_dump(),
            "secondary": config.secondary.model_dump() if config.secondary else None,
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
