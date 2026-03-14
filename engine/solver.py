"""
Production constraint engine with indexed pre-filtering.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Optional

from .models import (
    ConcealedHinge,
    Configuration,
    CustomerRequirements,
    MountingPlate,
    RuleResult,
)
from .rules import RULES, hinges_per_door


def _format_solution(config: Configuration) -> dict:
    """Format a configuration for the solve_with_explanation output (PoC compatible)."""
    return {
        "hinge": {
            "sku": config.hinge.sku,
            "description": (f"{config.hinge.brand} {config.hinge.series.value} "
                           f"{config.hinge.opening_angle_deg}° {config.hinge.application.value}"),
            "soft_close": config.hinge.soft_close,
            "price_usd": config.hinge.price_usd,
        },
        "mounting_plate": {
            "sku": config.plate.sku,
            "description": (f"{config.plate.brand} {config.plate.series} "
                           f"{config.plate.plate_type.value} {config.plate.plate_height_mm}mm"),
            "price_usd": config.plate.price_usd,
        },
        "hinges_per_door": config.hinges_per_door,
        "total_weight_capacity_kg": config.total_weight_capacity_kg,
        "total_price_per_door_usd": config.total_price_usd,
        "constraint_trace": [
            {"rule": r.rule_id, "name": r.rule_name, "passed": r.passed, "detail": r.detail}
            for r in config.rule_results
        ],
    }


class HingeConstraintEngine:

    def __init__(self, hinges: list[ConcealedHinge], plates: list[MountingPlate]):
        self.hinges = hinges
        self.plates = plates

        # Build indexes for pre-filtering
        self._brand_index: dict[str, list[ConcealedHinge]] = defaultdict(list)
        self._cabinet_type_index: dict[str, list[ConcealedHinge]] = defaultdict(list)
        self._application_index: dict[str, list[ConcealedHinge]] = defaultdict(list)

        for h in hinges:
            self._brand_index[h.brand].append(h)
            self._cabinet_type_index[h.cabinet_type.value].append(h)
            self._application_index[h.application.value].append(h)

    @staticmethod
    def hinges_per_door(door_height_mm: float) -> int:
        return hinges_per_door(door_height_mm)

    def evaluate(self, h: ConcealedHinge, p: MountingPlate, req: CustomerRequirements) -> Configuration:
        """Evaluate a single hinge+plate pair against all rules."""
        num_hinges = hinges_per_door(req.door_height_mm)
        # No derating — use max_door_weight_kg directly
        capacity = h.max_door_weight_kg * num_hinges

        results = [rule(h, p, req, num_hinges) for rule in RULES]

        return Configuration(
            hinge=h,
            plate=p,
            hinges_per_door=num_hinges,
            total_weight_capacity_kg=round(capacity, 2),
            rule_results=results,
        )

    def _pre_filter_hinges(self, req: CustomerRequirements) -> list[ConcealedHinge]:
        """Use indexes to narrow down candidate hinges."""
        # Start with application filter (always applied)
        candidates = set(id(h) for h in self._application_index.get(req.application.value, []))

        # Cabinet type filter
        cabinet_ids = set(id(h) for h in self._cabinet_type_index.get(req.cabinet_type.value, []))
        candidates &= cabinet_ids

        # Brand filter (optional)
        if req.preferred_brand:
            brand_ids = set(id(h) for h in self._brand_index.get(req.preferred_brand, []))
            candidates &= brand_ids

        # Return the actual hinge objects
        return [h for h in self.hinges if id(h) in candidates]

    def solve(self, req: CustomerRequirements) -> list[Configuration]:
        """Find all valid hinge+plate configurations, sorted by price then capacity."""
        valid = []
        filtered_hinges = self._pre_filter_hinges(req)

        for h in filtered_hinges:
            for p in self.plates:
                config = self.evaluate(h, p, req)
                if config.valid:
                    valid.append(config)

        valid.sort(key=lambda c: (
            c.total_price_usd if c.total_price_usd is not None else float('inf'),
            -c.total_weight_capacity_kg,
        ))
        return valid

    def solve_with_explanation(self, req: CustomerRequirements) -> dict:
        """Solve and return structured result with full reasoning trace (PoC compatible)."""
        solutions = self.solve(req)

        if not solutions:
            # Re-run without brand preference
            if req.preferred_brand:
                req_any = req.model_copy(update={"preferred_brand": None})
                alt_solutions = self.solve(req_any)
                if alt_solutions:
                    return {
                        "status": "no_solution_for_brand",
                        "message": f"No valid configuration found for {req.preferred_brand}. "
                                   f"{len(alt_solutions)} solution(s) available from other brands.",
                        "alternatives": [_format_solution(s) for s in alt_solutions[:3]],
                    }

            best_fail = self._best_failing(req)
            return {
                "status": "no_solution",
                "message": "No valid hinge + mounting plate configuration satisfies all constraints.",
                "closest_match": _format_solution(best_fail) if best_fail else None,
                "failed_rules": [
                    {"rule": r.rule_id, "name": r.rule_name, "detail": r.detail}
                    for r in (best_fail.failed_rules if best_fail else [])
                ],
            }

        return {
            "status": "solved",
            "message": f"Found {len(solutions)} valid configuration(s).",
            "recommended": _format_solution(solutions[0]),
            "alternatives": [_format_solution(s) for s in solutions[1:4]],
        }

    def _best_failing(self, req: CustomerRequirements) -> Optional[Configuration]:
        """Find the configuration with the fewest constraint violations."""
        best: Optional[Configuration] = None
        fewest = 999
        req_no_brand = req.model_copy(update={"preferred_brand": None})

        # Only check hinges matching the application
        for h in self._application_index.get(req_no_brand.application.value, []):
            for p in self.plates:
                config = self.evaluate(h, p, req_no_brand)
                n_fail = len(config.failed_rules)
                if 0 < n_fail < fewest:
                    best, fewest = config, n_fail
        return best
