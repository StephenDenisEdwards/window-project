"""Flat N-candidate constraint solver.

Generalizes the paired solver to handle any number of product roles.
The solver computes the Cartesian product of all role lists and evaluates
each combination against all rules.

Example: LED lighting has 3 roles (light_bar, driver, dimmer).
The solver evaluates every (light_bar, driver, dimmer) triple.

Trade-off: Simple and flexible, but O(A × B × C × rules) with no
inter-role pruning. Works well for small catalogs or when all products
constrain each other.
"""

from itertools import product as cartesian_product
from typing import Any, Callable, Optional

from pydantic import BaseModel

from engine_v2.core.models import Product, Requirements, RuleCategory, RuleResult


class NConfiguration(BaseModel):
    """A configuration of N products, one per role.

    Unlike Configuration (primary/secondary), this stores products by
    role name so rules can access them semantically:
        config.candidates["light_bar"]
        config.candidates["driver"]
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


# Type aliases for N-candidate solver
# Rules receive candidates as dict[str, Product] instead of (primary, secondary)
NRuleFn = Callable[[dict[str, Product], Requirements, dict], RuleResult]
NRankKeyFn = Callable[[NConfiguration], Any]
NDerivedFn = Callable[[Requirements], dict]
NPreFilterFn = Callable[[str, list[Product], Requirements], list[Product]]


class NFamilyConfig:
    """Configuration for an N-candidate product family.

    roles: Ordered list of (role_name, product_type) tuples.
           Example: [("light_bar", LightBar), ("driver", Driver), ("dimmer", Dimmer)]
    """

    def __init__(
        self,
        name: str,
        roles: list[tuple[str, type[Product]]],
        requirements_type: type[Requirements],
        rules: list[NRuleFn],
        pre_filters: list[NPreFilterFn] | None = None,
        rank_key: NRankKeyFn | None = None,
        derived_values: NDerivedFn | None = None,
        early_termination: bool = True,
    ):
        self.name = name
        self.roles = roles
        self.requirements_type = requirements_type
        self.rules = rules
        self.pre_filters = pre_filters or []
        self.rank_key = rank_key or (lambda c: (0 if c.total_price_usd else 1, c.total_price_usd or 0))
        self.derived_values = derived_values or (lambda r: {})
        self.early_termination = early_termination

    @property
    def role_names(self) -> list[str]:
        return [name for name, _ in self.roles]


class NCandidateSolver:
    """Solver that handles any number of product roles.

    Usage:
        solver = NCandidateSolver(
            config=led_lighting_config,
            product_lists={
                "light_bar": [bar1, bar2, ...],
                "driver": [drv1, drv2, ...],
                "dimmer": [dim1, dim2, ...],
            }
        )
        results = solver.solve(requirements)
    """

    def __init__(self, config: NFamilyConfig, product_lists: dict[str, list[Product]]):
        self.config = config
        self.product_lists = product_lists

        # Validate that all roles have product lists
        for role_name, _ in config.roles:
            if role_name not in product_lists:
                raise ValueError(f"Missing product list for role {role_name!r}")

    def evaluate(
        self,
        candidates: dict[str, Product],
        req: Requirements,
    ) -> NConfiguration:
        """Evaluate a single N-candidate combination against all rules."""
        derived = self.config.derived_values(req)
        results: list[RuleResult] = []

        for rule in self.config.rules:
            result = rule(candidates, req, derived)
            results.append(result)

            if (
                self.config.early_termination
                and not result.passed
                and result.category == RuleCategory.HARD_CONSTRAINT
            ):
                break

        return NConfiguration(
            candidates=candidates,
            rule_results=results,
            derived=derived,
        )

    def _apply_pre_filters(self, req: Requirements) -> dict[str, list[Product]]:
        """Apply pre-filters to each role's product list."""
        filtered = dict(self.product_lists)
        for filt in self.config.pre_filters:
            for role_name in self.config.role_names:
                filtered[role_name] = filt(role_name, filtered[role_name], req)
        return filtered

    def solve(self, req: Requirements) -> list[NConfiguration]:
        """Find all valid N-candidate configurations.

        Computes the Cartesian product of all role lists and evaluates
        each combination. For 3 roles with 50, 20, 30 products:
        50 × 20 × 30 = 30,000 evaluations.
        """
        filtered = self._apply_pre_filters(req)
        role_names = self.config.role_names
        role_lists = [filtered[name] for name in role_names]

        valid: list[NConfiguration] = []

        for combo in cartesian_product(*role_lists):
            candidates = dict(zip(role_names, combo))
            config = self.evaluate(candidates, req)
            if config.valid:
                valid.append(config)

        return sorted(valid, key=self.config.rank_key)

    def solve_with_explanation(self, req: Requirements) -> dict:
        """Solve and return structured results with traces."""
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

    def _best_failing(self, req: Requirements) -> Optional[NConfiguration]:
        """Find the combination that passes the most rules."""
        saved = self.config.early_termination
        self.config.early_termination = False

        best: Optional[NConfiguration] = None
        best_count = -1

        filtered = self._apply_pre_filters(req)
        role_names = self.config.role_names
        role_lists = [filtered[name] for name in role_names]

        for combo in cartesian_product(*role_lists):
            candidates = dict(zip(role_names, combo))
            config = self.evaluate(candidates, req)
            if config.passed_count > best_count:
                best = config
                best_count = config.passed_count

        self.config.early_termination = saved
        return best

    @staticmethod
    def _config_to_dict(config: NConfiguration) -> dict:
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
