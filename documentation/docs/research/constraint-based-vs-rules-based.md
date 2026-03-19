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

You could add 500 new hinges from a new manufacturer tomorrow and **not change a single rule**. The solver evaluates every candidate against the same constraints and derives compatibility from product attributes. This is the same architectural insight that let Siemens Energy replace thousands of if-then rules with a few hundred constraints (see `competitive-landscape.md`, Appendix A.2).

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

If the v2 multi-family architecture eventually produces search spaces where exhaustive evaluation becomes impractical, migrating to a CSP solver (Google OR-Tools CP-SAT is already being researched — see `cpsat-research.md`) would preserve all existing constraint logic while replacing only the solver strategy.

---

## Limitations of the Staged Pipeline

The current staged pipeline (pre-filter → exhaustive evaluate all pairs → filter valid → rank) is the right choice at current scale. These are the known limitations that would drive a future migration to CSP propagation:

### 1. Combinatorial Explosion

53 hinges x 55 plates = 2,915 pairs — trivial. But the roadmap calls for 13+ product families with thousands of products each. Cross-family configurations (hinge + plate + mounting screw + bumper) could produce millions of combinations. Exhaustive evaluation of every candidate against every rule does not scale to that.

| Scenario | Combinations | Rule Checks (14 rules) | Feasibility |
|----------|-------------|----------------------|-------------|
| Current (hinges only) | 2,915 | ~40,000 | Milliseconds |
| 3 families, 200 products each | 8,000,000 | ~112,000,000 | Seconds — borderline |
| 13 families, cross-family pairing | 100,000,000+ | 1,000,000,000+ | Impractical |

### 2. No Constraint Propagation

A CSP solver can narrow the solution space incrementally: *"Given what you've told me so far, only Blum and Grass are still possible."* The staged pipeline cannot — it requires all inputs before it runs, then evaluates everything from scratch. This means the conversational layer cannot progressively narrow options as the customer provides information mid-conversation. Every interaction is a full re-solve.

### 3. Redundant Computation

The v1 engine evaluates all 14 rules on every pair, even if it fails brand lock on rule 1 — that's 13 wasted rule checks per obviously-invalid pair. The v2 engine adds early termination (stop after first hard constraint failure), which helps but doesn't eliminate the root problem: a CSP solver with propagation would never generate the invalid pair in the first place.

**Example at current scale:**
- 53 hinges x 55 plates = 2,915 pairs
- Only ~200 pass brand lock (R001) — the remaining ~2,700 pairs are cross-brand and guaranteed to fail
- Without early termination: 2,700 x 14 = 37,800 wasted rule checks
- With early termination: 2,700 x 1 = 2,700 wasted rule checks (better, but still evaluated)
- With propagation: 0 — cross-brand pairs are never constructed

### 4. No Native Optimization

The pipeline finds all valid solutions, then sorts by price/capacity. It cannot express *"find the cheapest valid configuration"* as an optimization objective that guides the search. A CSP solver can minimize/maximize objectives natively, potentially finding the optimum without evaluating every candidate.

This matters for scenarios like: *"Find the cheapest configuration across all brands that supports a 25kg door with soft-close"* — the exhaustive pipeline must find all valid solutions first, then pick the cheapest. A CSP solver can prune entire branches of the search space that are provably more expensive than the current best.

### 5. No Incremental Solving

Every query is independent — no state is preserved between solves. If a customer asks *"What about 19mm doors instead of 18mm?"*, the engine re-evaluates everything from scratch rather than incrementally updating the previous result. At current scale this is instant, but it is architecturally wasteful and becomes a bottleneck in interactive sessions with large catalogs.

### 6. Cross-Family Constraints Are Hard

The pipeline handles one family at a time. Constraints that span families are difficult to express:

- *"The drawer slides must support the weight of a drawer whose front is hung on these hinges"*
- *"The lift system and the hinge system cannot both be installed on the same door"*
- *"The handle length must not interfere with the hinge cup boring position"*

These cross-family constraints require orchestrating multiple independent pipeline runs and correlating results manually. A CSP solver handles this naturally — all variables from all families exist in the same constraint model.

### When to Migrate

These limitations do not affect the current system. The pragmatic path:

1. **Now:** Keep exhaustive evaluation. It runs in milliseconds, provides complete explainability traces (including for failures), and is trivially simple to debug and extend.
2. **Trigger:** When either (a) catalog size makes exhaustive evaluation measurably slow, or (b) cross-family constraints require unified solving across product families.
3. **Migration:** Swap in CP-SAT as the solver behind the same constraint interface. The constraint definitions (property-level predicates in `rules.py`) remain unchanged — only the evaluation strategy changes. See `cpsat-research.md` for the CP-SAT evaluation.
