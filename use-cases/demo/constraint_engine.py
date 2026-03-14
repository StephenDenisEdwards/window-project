"""
Window — Hinge Compatibility Constraint Engine (Demo)

Demonstrates deterministic constraint reasoning for hinge-to-mounting-plate
selection. Every recommendation is provably correct — no LLM inference involved.

Usage:
    python constraint_engine.py
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Domain models
# ---------------------------------------------------------------------------

@dataclass
class Hinge:
    sku: str
    brand: str
    series: str
    application: str
    opening_angle_deg: int
    cup_diameter_mm: int
    boring_pattern_mm: int
    door_thickness_min_mm: int
    door_thickness_max_mm: int
    max_door_weight_kg: float
    soft_close: bool
    mounting: str
    cabinet_type: str
    crank_mm: float
    compatible_mounting_plate_skus: list[str]
    price_usd: float
    cup_depth_mm: Optional[float] = None

    @property
    def effective_max_weight_kg(self) -> float:
        """Wide-angle hinges (>120°) are derated by 25% — rule R010."""
        if self.opening_angle_deg > 120:
            return self.max_door_weight_kg * 0.75
        return self.max_door_weight_kg


@dataclass
class MountingPlate:
    sku: str
    brand: str
    series: str
    plate_type: str
    mounting_method: str
    cabinet_type: str
    plate_height_mm: int
    compatible_hinge_series: list[str]
    overlay_range_mm: dict
    price_usd: float


@dataclass
class CustomerRequirements:
    cabinet_type: str                          # frameless | face_frame
    door_thickness_mm: float
    door_height_mm: float
    door_weight_kg: float
    application: str                           # full_overlay | half_overlay | inset
    desired_overlay_mm: float
    boring_pattern_mm: int
    soft_close: bool
    cabinet_position: str = "standard"         # standard | corner
    preferred_brand: Optional[str] = None
    has_adjacent_door: bool = False
    adjacent_door_overlay_mm: float = 0
    partition_thickness_mm: float = 19
    face_frame_width_mm: float = 0


# ---------------------------------------------------------------------------
# Constraint rule results
# ---------------------------------------------------------------------------

@dataclass
class RuleResult:
    rule_id: str
    rule_name: str
    passed: bool
    detail: str


@dataclass
class Configuration:
    hinge: Hinge
    plate: MountingPlate
    hinges_per_door: int
    total_weight_capacity_kg: float
    rule_results: list[RuleResult] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return all(r.passed for r in self.rule_results)

    @property
    def failed_rules(self) -> list[RuleResult]:
        return [r for r in self.rule_results if not r.passed]

    @property
    def total_price_usd(self) -> float:
        h_price = self.hinge.price_usd or 0
        p_price = self.plate.price_usd or 0
        if self.hinge.price_usd is None or self.plate.price_usd is None:
            return None
        return round((h_price + p_price) * self.hinges_per_door, 2)


# ---------------------------------------------------------------------------
# Constraint engine
# ---------------------------------------------------------------------------

class HingeConstraintEngine:

    def __init__(self, hinges: list[Hinge], plates: list[MountingPlate]):
        self.hinges = hinges
        self.plates = plates

    # -- Derived values -----------------------------------------------------

    @staticmethod
    def hinges_per_door(door_height_mm: float) -> int:
        """R008: hinge count derived from door height."""
        if door_height_mm <= 889:
            return 2
        if door_height_mm <= 1400:
            return 3
        if door_height_mm <= 1800:
            return 4
        return 5

    # -- Individual constraint checks ---------------------------------------

    def _check_brand_lock(self, h: Hinge, p: MountingPlate) -> RuleResult:
        ok = h.brand == p.brand
        return RuleResult("R001", "brand_lock", ok,
            f"Hinge brand '{h.brand}' {'==' if ok else '!='} plate brand '{p.brand}'")

    def _check_series_compat(self, h: Hinge, p: MountingPlate) -> RuleResult:
        ok = h.series in p.compatible_hinge_series
        return RuleResult("R002", "series_compatibility", ok,
            f"Hinge series '{h.series}' {'in' if ok else 'not in'} plate compatible series {p.compatible_hinge_series}")

    def _check_cabinet_type(self, h: Hinge, p: MountingPlate, req: CustomerRequirements) -> RuleResult:
        ok = h.cabinet_type == p.cabinet_type == req.cabinet_type
        return RuleResult("R003", "cabinet_type_match", ok,
            f"Cabinet type: hinge={h.cabinet_type}, plate={p.cabinet_type}, required={req.cabinet_type}")

    # Map application names to overlay_range_mm keys in the plate data
    APP_TO_OVERLAY_KEY = {
        "full_overlay": "full",
        "half_overlay": "half",
        "inset": "inset",
        "overlay": "full",
    }

    def _check_overlay_range(self, h: Hinge, p: MountingPlate, req: CustomerRequirements) -> RuleResult:
        app_key = self.APP_TO_OVERLAY_KEY.get(req.application, req.application)
        overlay_spec = p.overlay_range_mm.get(app_key)
        if overlay_spec is None or overlay_spec is False:
            return RuleResult("R004", "overlay_in_range", False,
                f"Plate {p.sku} does not support {req.application} application")
        if overlay_spec is True:  # inset — any overlay that's 0 is valid
            ok = True
            detail = f"Inset supported by plate {p.sku}"
        else:
            lo, hi = overlay_spec
            ok = lo <= req.desired_overlay_mm <= hi
            detail = f"Desired overlay {req.desired_overlay_mm}mm vs plate range [{lo}-{hi}]mm for {req.application}"
        return RuleResult("R004", "overlay_in_range", ok, detail)

    def _check_inset_support(self, h: Hinge, p: MountingPlate, req: CustomerRequirements) -> RuleResult:
        if req.application != "inset":
            return RuleResult("R005", "inset_support", True, "Not an inset application — skipped")
        ok = p.overlay_range_mm.get("inset", False) is not False
        return RuleResult("R005", "inset_support", ok,
            f"Plate {p.sku} {'supports' if ok else 'does not support'} inset")

    def _check_door_thickness(self, h: Hinge, req: CustomerRequirements) -> RuleResult:
        ok = h.door_thickness_min_mm <= req.door_thickness_mm <= h.door_thickness_max_mm
        return RuleResult("R006", "door_thickness_range", ok,
            f"Door {req.door_thickness_mm}mm vs hinge range [{h.door_thickness_min_mm}-{h.door_thickness_max_mm}]mm")

    def _check_weight(self, h: Hinge, req: CustomerRequirements, num_hinges: int) -> RuleResult:
        capacity = h.effective_max_weight_kg * num_hinges
        ok = req.door_weight_kg <= capacity
        detail = (f"Door {req.door_weight_kg}kg vs capacity {h.effective_max_weight_kg}kg x {num_hinges} "
                  f"= {capacity}kg")
        if h.opening_angle_deg > 120:
            detail += f" (derated from {h.max_door_weight_kg}kg for {h.opening_angle_deg}° angle)"
        return RuleResult("R007", "door_weight_limit", ok, detail)

    def _check_boring_pattern(self, h: Hinge, req: CustomerRequirements) -> RuleResult:
        ok = h.boring_pattern_mm == req.boring_pattern_mm
        return RuleResult("R009", "boring_pattern_match", ok,
            f"Hinge boring {h.boring_pattern_mm}mm vs required {req.boring_pattern_mm}mm")

    def _check_corner_angle(self, h: Hinge, req: CustomerRequirements) -> RuleResult:
        if req.cabinet_position != "corner":
            return RuleResult("R013", "corner_cabinet_angle", True, "Not a corner cabinet — skipped")
        ok = h.opening_angle_deg >= 155
        return RuleResult("R013", "corner_cabinet_angle", ok,
            f"Corner cabinet needs >=155°, hinge is {h.opening_angle_deg}°")

    def _check_adjacent_clearance(self, req: CustomerRequirements) -> RuleResult:
        if not req.has_adjacent_door:
            return RuleResult("R012", "adjacent_door_clearance", True, "No adjacent door — skipped")
        combined = req.desired_overlay_mm + req.adjacent_door_overlay_mm
        ok = combined <= req.partition_thickness_mm
        return RuleResult("R012", "adjacent_door_clearance", ok,
            f"Combined overlay {combined}mm vs partition {req.partition_thickness_mm}mm")

    def _check_face_frame_overlay(self, p: MountingPlate, req: CustomerRequirements) -> RuleResult:
        if p.cabinet_type != "face_frame":
            return RuleResult("R011", "face_frame_overlay", True, "Not face frame — skipped")
        limit = req.face_frame_width_mm - 3
        ok = req.desired_overlay_mm <= limit
        return RuleResult("R011", "face_frame_overlay", ok,
            f"Overlay {req.desired_overlay_mm}mm vs face frame limit {limit}mm (frame {req.face_frame_width_mm}mm - 3)")

    # Mounting method compatibility map:
    # screw_on hinges work with screw_on, euro_screw, and system_screw plates
    # dowel hinges work with dowel and system_screw plates
    MOUNTING_METHOD_COMPAT = {
        "screw_on": {"screw_on", "euro_screw", "system_screw"},
        "dowel": {"dowel", "system_screw"},
    }

    def _check_mounting_method(self, h: Hinge, p: MountingPlate) -> RuleResult:
        allowed = self.MOUNTING_METHOD_COMPAT.get(h.mounting, {h.mounting})
        ok = p.mounting_method in allowed
        return RuleResult("R014", "mounting_method_match", ok,
            f"Hinge mounting '{h.mounting}' vs plate '{p.mounting_method}'")

    def _check_cup_depth(self, h: Hinge, req: CustomerRequirements) -> RuleResult:
        """R015: door thickness must be at least cup_depth_mm + 2mm."""
        if h.cup_depth_mm is None:
            return RuleResult("R015", "cup_depth_door_thickness", True,
                "Cup depth not specified — skipped")
        min_thickness = h.cup_depth_mm + 2
        ok = req.door_thickness_mm >= min_thickness
        return RuleResult("R015", "cup_depth_door_thickness", ok,
            f"Door {req.door_thickness_mm}mm vs min {min_thickness}mm (cup depth {h.cup_depth_mm}mm + 2mm)")

    def _check_soft_close(self, h: Hinge, req: CustomerRequirements) -> RuleResult:
        if not req.soft_close:
            return RuleResult("PREF", "soft_close_preference", True, "Soft-close not required — any hinge OK")
        ok = h.soft_close
        return RuleResult("PREF", "soft_close_preference", ok,
            f"Soft-close required: hinge {'has' if ok else 'lacks'} soft-close")

    # -- Evaluate a single hinge+plate pair ---------------------------------

    def evaluate(self, h: Hinge, p: MountingPlate, req: CustomerRequirements) -> Configuration:
        num_hinges = self.hinges_per_door(req.door_height_mm)
        capacity = h.effective_max_weight_kg * num_hinges

        results = [
            self._check_brand_lock(h, p),
            self._check_series_compat(h, p),
            self._check_cabinet_type(h, p, req),
            self._check_overlay_range(h, p, req),
            self._check_inset_support(h, p, req),
            self._check_door_thickness(h, req),
            self._check_weight(h, req, num_hinges),
            self._check_boring_pattern(h, req),
            self._check_corner_angle(h, req),
            self._check_adjacent_clearance(req),
            self._check_face_frame_overlay(p, req),
            self._check_mounting_method(h, p),
            self._check_cup_depth(h, req),
            self._check_soft_close(h, req),
        ]

        return Configuration(
            hinge=h,
            plate=p,
            hinges_per_door=num_hinges,
            total_weight_capacity_kg=round(capacity, 2),
            rule_results=results,
        )

    # -- Find all valid configurations --------------------------------------

    def solve(self, req: CustomerRequirements) -> list[Configuration]:
        """Exhaustive search: evaluate every hinge × plate pair, return valid ones."""
        valid = []
        for h in self.hinges:
            # Quick pre-filters before evaluating all plates
            if req.preferred_brand and h.brand != req.preferred_brand:
                continue
            if h.application != req.application:
                continue
            if h.cabinet_type != req.cabinet_type:
                continue

            for p in self.plates:
                config = self.evaluate(h, p, req)
                if config.valid:
                    valid.append(config)

        # Sort by price (None last), then by weight capacity (descending)
        valid.sort(key=lambda c: (c.total_price_usd if c.total_price_usd is not None else float('inf'), -c.total_weight_capacity_kg))
        return valid

    def solve_with_explanation(self, req: CustomerRequirements) -> dict:
        """Solve and return a structured result with full reasoning trace."""
        solutions = self.solve(req)

        if not solutions:
            # Re-run without brand preference to check if that's the blocker
            if req.preferred_brand:
                req_any = CustomerRequirements(**{
                    **req.__dict__, "preferred_brand": None
                })
                alt_solutions = self.solve(req_any)
                if alt_solutions:
                    return {
                        "status": "no_solution_for_brand",
                        "message": f"No valid configuration found for {req.preferred_brand}. "
                                   f"{len(alt_solutions)} solution(s) available from other brands.",
                        "alternatives": [_format_solution(s) for s in alt_solutions[:3]],
                    }

            # Show why the best candidate failed
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
        best, fewest = None, 999
        req_no_brand = CustomerRequirements(**{**req.__dict__, "preferred_brand": None})
        for h in self.hinges:
            if h.application != req_no_brand.application:
                continue
            for p in self.plates:
                config = self.evaluate(h, p, req_no_brand)
                n_fail = len(config.failed_rules)
                if 0 < n_fail < fewest:
                    best, fewest = config, n_fail
        return best


def _format_solution(config: Configuration) -> dict:
    return {
        "hinge": {
            "sku": config.hinge.sku,
            "description": (f"{config.hinge.brand} {config.hinge.series} "
                           f"{config.hinge.opening_angle_deg}° {config.hinge.application}"),
            "soft_close": config.hinge.soft_close,
            "price_usd": config.hinge.price_usd,
        },
        "mounting_plate": {
            "sku": config.plate.sku,
            "description": (f"{config.plate.brand} {config.plate.series} "
                           f"{config.plate.plate_type} {config.plate.plate_height_mm}mm"),
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


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_catalog(data_dir: Path) -> tuple[list[Hinge], list[MountingPlate]]:
    with open(data_dir / "hinges.json") as f:
        raw_hinges = json.load(f)
    with open(data_dir / "mounting_plates.json") as f:
        raw_plates = json.load(f)

    hinges = [
        Hinge(
            sku=h["sku"], brand=h["brand"], series=h["series"],
            application=h["application"], opening_angle_deg=h["opening_angle_deg"],
            cup_diameter_mm=h["cup_diameter_mm"], boring_pattern_mm=h["boring_pattern_mm"],
            door_thickness_min_mm=h["door_thickness_min_mm"],
            door_thickness_max_mm=h["door_thickness_max_mm"],
            max_door_weight_kg=h["max_door_weight_kg"], soft_close=h["soft_close"],
            mounting=h["mounting"], cabinet_type=h["cabinet_type"],
            crank_mm=h["crank_mm"],
            compatible_mounting_plate_skus=h["compatible_mounting_plate_skus"],
            price_usd=h["price_usd"],
            cup_depth_mm=h.get("cup_depth_mm"),
        )
        for h in raw_hinges
    ]

    plates = [
        MountingPlate(
            sku=p["sku"], brand=p["brand"], series=p["series"],
            plate_type=p["type"], mounting_method=p["mounting_method"],
            cabinet_type=p["cabinet_type"], plate_height_mm=p["plate_height_mm"],
            compatible_hinge_series=p["compatible_hinge_series"],
            overlay_range_mm=p["overlay_range_mm"], price_usd=p["price_usd"],
        )
        for p in raw_plates
    ]

    return hinges, plates


# ---------------------------------------------------------------------------
# Demo scenarios
# ---------------------------------------------------------------------------

def run_demo():
    data_dir = Path(__file__).parent.parent / "sample-data"
    hinges, plates = load_catalog(data_dir)
    engine = HingeConstraintEngine(hinges, plates)

    scenarios = [
        (
            "Scenario 1: Standard kitchen remodel — Blum, full overlay, soft-close",
            CustomerRequirements(
                cabinet_type="frameless", door_thickness_mm=19, door_height_mm=720,
                door_weight_kg=5.2, application="full_overlay", desired_overlay_mm=16,
                boring_pattern_mm=45, soft_close=True, preferred_brand="Blum",
            ),
        ),
        (
            "Scenario 2: Corner cabinet — needs wide-angle hinge",
            CustomerRequirements(
                cabinet_type="frameless", door_thickness_mm=19, door_height_mm=800,
                door_weight_kg=4.0, application="full_overlay", desired_overlay_mm=16,
                boring_pattern_mm=45, soft_close=True, cabinet_position="corner",
            ),
        ),
        (
            "Scenario 3: Tall pantry door — 1600mm, heavy, Grass preferred",
            CustomerRequirements(
                cabinet_type="frameless", door_thickness_mm=22, door_height_mm=1600,
                door_weight_kg=14.0, application="full_overlay", desired_overlay_mm=16,
                boring_pattern_mm=45, soft_close=True, preferred_brand="Grass",
            ),
        ),
        (
            "Scenario 4: Adjacent doors sharing partition — half overlay",
            CustomerRequirements(
                cabinet_type="frameless", door_thickness_mm=19, door_height_mm=720,
                door_weight_kg=4.0, application="half_overlay", desired_overlay_mm=6,
                boring_pattern_mm=45, soft_close=True, preferred_brand="Blum",
                has_adjacent_door=True, adjacent_door_overlay_mm=6,
                partition_thickness_mm=19,
            ),
        ),
        (
            "Scenario 5: CONSTRAINT VIOLATION — heavy corner door (no valid solution)",
            CustomerRequirements(
                cabinet_type="frameless", door_thickness_mm=22, door_height_mm=900,
                door_weight_kg=12.0, application="full_overlay", desired_overlay_mm=16,
                boring_pattern_mm=45, soft_close=True, cabinet_position="corner",
                preferred_brand="Blum",
            ),
        ),
    ]

    for title, req in scenarios:
        print("=" * 80)
        print(f"  {title}")
        print("=" * 80)

        result = engine.solve_with_explanation(req)
        print(f"\nStatus: {result['status']}")
        print(f"Message: {result['message']}")

        if result["status"] == "solved":
            rec = result["recommended"]
            print(f"\n  Recommended:")
            print(f"    Hinge: {rec['hinge']['sku']} — {rec['hinge']['description']}")
            print(f"    Plate: {rec['mounting_plate']['sku']} — {rec['mounting_plate']['description']}")
            print(f"    Hinges per door: {rec['hinges_per_door']}")
            print(f"    Weight capacity: {rec['total_weight_capacity_kg']}kg")
            print(f"    Price per door: ${rec['total_price_per_door_usd']}")
            print(f"\n  Constraint trace:")
            for rule in rec["constraint_trace"]:
                icon = "PASS" if rule["passed"] else "FAIL"
                print(f"    [{icon}] {rule['rule']} {rule['name']}: {rule['detail']}")

            if result["alternatives"]:
                print(f"\n  + {len(result['alternatives'])} alternative(s) available")

        elif result["status"] == "no_solution":
            if result.get("closest_match"):
                cm = result["closest_match"]
                print(f"\n  Closest match: {cm['hinge']['sku']} + {cm['mounting_plate']['sku']}")
            print(f"\n  Failed rules:")
            for fr in result["failed_rules"]:
                print(f"    [FAIL] {fr['rule']} {fr['name']}: {fr['detail']}")

        elif result["status"] == "no_solution_for_brand":
            print(f"\n  Alternatives from other brands:")
            for alt in result["alternatives"]:
                print(f"    {alt['hinge']['sku']} — {alt['hinge']['description']} "
                      f"(${alt['total_price_per_door_usd']}/door)")

        print()


if __name__ == "__main__":
    run_demo()
