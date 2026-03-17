# Constraint-Based vs Rules-Based Systems

## The Difference

### Rules-Based

Rules-based systems encode compatibility as explicit if-then statements that reference specific products or product combinations:

```
IF hinge_series == "CLIP top" AND cabinet_type == "frameless" AND overlay >= 3 AND overlay <= 18
THEN plate "174H7100" is compatible
```

You write a rule for every valid combination. 50 hinges x 55 plates = potentially thousands of hand-maintained rules. Add a new product? Write new rules. Change a spec? Find and update every rule that touches it.

**Characteristics:**
- Rules reference specific products or product groups
- Compatibility is manually maintained as explicit lookup tables or decision trees
- Adding a product requires writing new rules
- Changing a spec requires finding and updating every rule that references it
- Rigid input ordering — rules are typically evaluated in a fixed sequence
- Scale linearly (or worse) with catalog size

### Constraint-Based

Constraint-based systems define properties that must hold true, and let a solver figure out which combinations satisfy them:

```
hinge.brand == plate.brand
hinge.series IN plate.compatible_series
overlay BETWEEN plate.overlay_min AND plate.overlay_max
door_weight <= hinge.capacity * num_hinges
```

Add a new product? Just add its data — the constraints derive compatibility automatically. The rules don't reference specific products at all.

**Characteristics:**
- Rules are property-level predicates — they never mention a specific SKU or part number
- Compatibility is derived at query time from product attributes
- Adding a product requires only adding its data, not updating logic
- Rules are independent of catalog size
- Input order doesn't matter — constraints hold true regardless of evaluation sequence
- Scale with the number of constraint dimensions, not the number of products

### Side-by-Side Comparison

| Aspect | Rules-Based | Constraint-Based |
|--------|------------|-----------------|
| What a rule says | "Product A works with Product B" | "These properties must match" |
| Maintenance | High — hard-coded many-to-many relationships | Low — logic reused across all SKUs |
| New product onboarding | Write new rules per product | Add product data only |
| Catalog growth impact | More products = more rules | More products = same rules |
| User input flexibility | Rigid forced paths | Any input order |
| Portfolio coverage | Often limited to subsets | Full coverage with fewer constraints |
| Explainability | "Rule 47 said no" | "Brand mismatch: hinge is Blum, plate is Grass" |

---

## Which One Is This Project?

**This project is constraint-based.** None of the 14 rules in `engine/rules.py` mention a specific SKU, part number, or product. They are all property-level predicates:

| Rule | What it checks | Products referenced |
|------|---------------|-------------------|
| `check_brand_lock` (R001) | `h.brand == p.brand` | None — works for any hinge and any plate |
| `check_series_compat` (R002) | `h.series in p.compatible_series` | None — works for any series |
| `check_cabinet_type` (R003) | `h.cabinet_type == p.cabinet_type == req.cabinet_type` | None |
| `check_overlay_range` (R004) | `lo <= req.desired_overlay_mm <= hi` | None — works for any overlay table |
| `check_door_thickness` (R006) | `h.door_thickness_range_mm.contains(req.door_thickness_mm)` | None |
| `check_weight` (R007) | `req.door_weight_kg <= h.max_door_weight_kg * num_hinges` | None |
| `check_boring_pattern` (R009) | `h.boring_pattern_mm == req.boring_pattern_mm` | None |
| `check_corner_angle` (R013) | `h.opening_angle_deg >= 155` (if corner) | None |
| `check_mounting_method` (R014) | `p.mounting_method in COMPAT[h.mounting_method]` | None |
| `check_cup_depth` (R015) | `req.door_thickness_mm >= h.cup_depth_mm + 2` | None |

You could add 500 new hinges from a new manufacturer tomorrow and **not change a single rule**. The solver evaluates every candidate against the same constraints and derives compatibility from product attributes. This is the same architectural insight that let Siemens Energy replace thousands of if-then rules with a few hundred constraints (see `documents/competitive-landscape.md`, Appendix A.2).

The engine currently has 14 rules covering 2,915 hinge x plate pairs (53 hinges x 55 plates). Those same 14 rules will work unchanged as the catalog grows to thousands of products across multiple manufacturers.

---

## Solver Strategy: Exhaustive Evaluation vs CSP Propagation

There are two ways to execute a constraint-based system:

### Exhaustive Evaluation (This Project)

Evaluate every candidate pair against all constraints. Collect results. Filter to valid. Rank.

```
for each hinge in filtered_hinges:
    for each plate in all_plates:
        evaluate all 14 rules
        if all pass: add to valid list
sort valid by price, capacity
```

**Strengths:**
- Simple to implement and reason about
- Full explainability — every pair gets a complete rule-by-rule trace, including failures
- No solver complexity — pure Python, no external dependencies beyond Pydantic
- "Closest match" analysis is trivial — the failing configurations are already evaluated

**Practical at current scale:** 53 hinges x 55 plates = 2,915 evaluations x 14 rules = ~40,000 rule checks per solve. Runs in milliseconds.

### CSP Propagation + Search (Tacton, OR-Tools CP-SAT)

Define variables (product attributes), domains (possible values), and constraints. The solver narrows domains through propagation (eliminating values that would violate constraints) and uses backtracking search to find valid assignments.

```
variables: hinge_brand, plate_brand, overlay, weight_capacity, ...
domains:   {Blum, Grass, Hafele}, {Blum, Grass, Hafele}, [0..25], ...
constraints: hinge_brand == plate_brand, overlay in plate_range, ...
solver.propagate() -> narrowed domains
solver.search() -> valid assignments
```

**Strengths:**
- Scales to enormous search spaces (millions+ combinations)
- Propagation prunes invalid regions without evaluating them
- Can optimize (minimize price, maximize capacity) natively
- Handles complex interdependencies efficiently

**When it becomes necessary:** When the search space grows to the point where exhaustive evaluation is too slow — likely when the engine covers 13+ product families with potentially millions of cross-family combinations.

### Where This Project Sits

The engine is **constraint-based in design** (property-level predicates, no product-specific rules, data/logic separation) but uses **exhaustive evaluation as its solver strategy**. This is the right choice at current scale — it's simpler, provides complete explainability traces, and runs fast enough.

If the v2 multi-family architecture eventually produces search spaces where exhaustive evaluation becomes impractical, migrating to a CSP solver (Google OR-Tools CP-SAT is already being researched — see `documents/cpsat-research.md`) would preserve all existing constraint logic while replacing only the solver strategy.
