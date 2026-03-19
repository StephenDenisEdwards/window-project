# Constraint Engine Design

A deterministic rule-based solver for hinge-to-mounting-plate compatibility in cabinetry. Given customer requirements, it evaluates all hinge × plate combinations against a set of constraints and returns valid, sorted configurations.

## File Layout

```
engine_v1/
├── __init__.py      # Package exports
├── enums.py         # All enumeration types
├── models.py        # Domain models (Pydantic v2)
├── rules.py         # Individual constraint rules
├── solver.py        # Main engine: solve / evaluate
├── loader.py        # JSON data adapter
└── tests/
    └── test_engine.py
```

## Core Data Models

### Product Identity

`ManufacturerProduct` is the base class. Each product has a canonical `manufacturer_part` (e.g. "71B3550"), a `manufacturer`, a `product_family`, and a list of `DistributorSKU` entries (per-brand SKUs with pricing). Pricing lives on the SKU, not the product.

### ConcealedHinge

Physical specs (`series`, `opening_angle_deg`, `cup_diameter_mm`, `cup_depth_mm`, `boring_pattern_mm`, `crank_mm`), a `door_thickness_range_mm: Range`, capacity (`max_door_weight_kg`), and capabilities (`soft_close`, `mounting_method`, `cabinet_type`, `application`).

### MountingPlate

Identity (`series`, `plate_type`), mounting (`mounting_method`, `cabinet_type`), dimensions (`plate_height_mm`, adjustments, `setback_mm`), compatibility (`compatible_hinge_series`), and overlay support via a structured `OverlayTable` (lookup by application type and drilling distance).

### CustomerRequirements

The input to the solver. Includes cabinet type, door dimensions/weight/material, application type, desired overlay, boring pattern, soft-close preference, cabinet position, optional brand/series preference, and adjacent-door parameters.

### Configuration (Output)

```
Configuration
├── hinge: ConcealedHinge
├── plate: MountingPlate
├── hinges_per_door: int          # derived from door height
├── total_weight_capacity_kg: float
└── rule_results: list[RuleResult]
```

Each `RuleResult` carries `rule_id`, `rule_name`, `passed`, `detail`, `category` (hard_constraint | soft_constraint | preference | derived), optional `values_compared`, and optional `remediation` suggestion.

## Constraint Rules

### Hard Constraints

| ID | Name | Logic |
|----|------|-------|
| R001 | Brand Lock | if brand_lock: hinge.brand == plate.brand (conditional, skipped when brand_lock=False) |
| R002 | Series Compatibility | hinge.series ∈ plate.compatible_hinge_series |
| R003 | Cabinet Type Match | hinge, plate, and requirements all agree on cabinet type |
| R004 | Overlay in Range | desired overlay within plate's range for the application type |
| R005 | Inset Support | if application is inset, plate must support it (conditional) |
| R006 | Door Thickness | door_thickness_mm within hinge's rated range |
| R007 | Door Weight | door_weight_kg ≤ max_door_weight_kg × num_hinges |
| R009 | Boring Pattern | cabinet boring pattern matches hinge boring pattern |
| R011 | Face Frame Overlay | if face_frame, overlay ≤ frame_width − 3mm (conditional) |
| R012 | Adjacent Door Clearance | if adjacent door, combined overlays fit partition (conditional) |
| R013 | Corner Cabinet Angle | corner cabinets need ≥155° opening angle (conditional) |
| R014 | Mounting Method | hinge mounting compatible with plate mounting per matrix |
| R015 | Cup Depth | door_thickness ≥ cup_depth + 2mm (conditional) |

### Derived

| ID | Name | Logic |
|----|------|-------|
| R008 | Hinges Per Door | ≤889mm→2, ≤1400mm→3, ≤1800mm→4, >1800mm→5 |

### Preference

| ID | Name | Logic |
|----|------|-------|
| PREF | Soft Close | if soft_close requested, hinge should have it (non-blocking) |

### Mounting Method Compatibility Matrix (R014)

| Hinge Method | Compatible Plate Methods |
|---|---|
| screw_on | screw_on, euro_screw, system_screw |
| dowel | dowel, system_screw |

## Engine Architecture

### HingeConstraintEngine

Initialized with lists of hinges and plates. On construction (`solver.py` lines 52–60), builds three `dict[str, list[ConcealedHinge]]` indexes:

- `_brand_index` — hinges keyed by `brand`
- `_cabinet_type_index` — hinges keyed by `cabinet_type`
- `_application_index` — hinges keyed by `application`

### Pre-filtering (`_pre_filter_hinges`, lines 82–97)

Given a `CustomerRequirements`, retrieves matching hinges from each index and intersects the sets. Application and cabinet type are always applied; brand is applied only if `preferred_brand` is set. This narrows the candidate hinges before the brute-force plate loop.

Plates are **not indexed** — every filtered hinge is evaluated against every plate (`solve()` line 105).

### Data Flow

```
CustomerRequirements
    │
    ▼
Pre-filter hinges (by application, cabinet type, optional brand)
    │
    ▼
For each filtered hinge × all plates:
    Evaluate all rules → RuleResults → Configuration
    │
    ▼
Discard invalid configurations (any hard constraint failed)
    │
    ▼
Sort valid configs by (price ASC, capacity DESC)
    │
    ▼
Sorted list[Configuration]
```

### Public API

**`evaluate(hinge, plate, requirements) → Configuration`**
Runs all rules for a single hinge+plate pair. Returns full Configuration with rule trace.

**`solve(requirements) → list[Configuration]`**
Exhaustive search over pre-filtered candidates. Returns sorted valid configurations.

**`solve_with_explanation(requirements) → dict`**
High-level API for conversational interfaces. Returns `{"status", "message", "recommended", "alternatives"}`. Status is one of `"solved"`, `"no_solution"`, or `"no_solution_for_brand"`. On failure with a brand preference, retries without brand. Falls back to `_best_failing()` to show the closest match with violation details.

## How Rules Are Applied

The solver and rules are decoupled through a single interface: the `RULES` list.

### The coupling point

`solver.py` line 72 is the only place the engine touches rules:

```python
results = [rule(h, p, req, num_hinges) for rule in RULES]
```

The engine iterates `RULES`, calls each entry with `(hinge, plate, requirements, num_hinges)`, and collects the `RuleResult` objects. It does not know what rules exist, what they check, or how many there are. A `Configuration` is valid when `all(r.passed for r in rule_results)`.

### Rule contract

Every rule is a callable with this signature:

```python
(ConcealedHinge, MountingPlate, CustomerRequirements, int) -> RuleResult
```

Currently all rules are Python functions in `rules.py`, registered by appending to `RULES`. The engine does not import individual rule functions — it only imports the list.

### Implication for rules-as-data

Because the solver only depends on `RULES` being a list of callables, a JSON rule loader would not require any changes to the solver. The loader would read rule definitions from a JSON file, construct callables (either by interpreting simple predicates or by dispatching to named Python functions for complex logic), and produce the same `list[RuleFn]` that the solver already consumes.

### Adding a new rule

Currently: write a function in `rules.py`, append it to `RULES`, deploy. No solver changes needed.

### Rule maintenance risks

- **Magic numbers buried in code** — `3mm` (R011), `2mm` (R015), `155°` (R013), height thresholds (R008) are domain constants that a product expert can't review without reading Python.
- **Mounting method matrix is hardcoded** — `MOUNTING_METHOD_COMPAT` dict. New mounting methods (e.g. INSERTA, already in the enum) silently fall back to exact-match instead of failing visibly.
- **Brand-specific parameters aren't parameterised** — R008 height thresholds differ by brand. The function accepts optional thresholds but they're never passed — `DEFAULT_HEIGHT_THRESHOLDS` is always used.
- **No rule versioning** — if a rule changes, there's no record of what was in effect when past recommendations were made.
- **No coverage check for new enum values** — adding a new `CabinetPosition` doesn't flag which rules need updating.

## Design Principles

1. **Products are facts, compatibility is derived** — No hand-maintained compatibility lists. Whether a hinge+plate pair works is computed by rules.
2. **Enumerate all constrained strings** — Every meaningful string field is an Enum. No silent failures from typos.
3. **Full rule tracing** — Every evaluation records rule ID, category, detail, and remediation. Supports explainability.
4. **No implicit derating** — Manufacturer's published `max_door_weight_kg` is used directly. The engine does not silently reduce weight ratings based on opening angle or other factors. In practice, a hinge rated for 80 kg at 90° may support less at wider angles (e.g. 170°) due to increased lever stress, but applying such derating factors automatically would embed assumptions that vary by product and manufacturer. If wide-angle derating is needed in the future, it should be added as an explicit, traceable rule — not baked into the weight comparison silently.
5. **Separate identity from presentation** — `manufacturer_part` (canonical) vs `distributor_skus` (per-retailer pricing).
6. **Brand lock is a rule, not an assumption** — Cross-brand hinge+plate pairing is controlled by the `brand_lock` flag on `CustomerRequirements` (defaults to `True`). When disabled, R001 passes automatically and the constraint trace records "Brand lock not required." This keeps brand policy as a configurable constraint rather than a hardcoded architectural assumption — different distributors or use cases may or may not require same-brand pairing.

## Data Loading

`loader.py` provides `load_from_json(data_dir)` which reads the JSON catalog (`hinges.json`, `mounting_plates.json`) and converts to domain models. Handles mapping overlay dicts to `OverlayTable`, thickness min/max to `Range`, and string enums to typed enums.

## Scalability Limitations

The engine uses an **O(H × P × R) brute-force search** where H = number of pre-filtered hinges, P = number of mounting plates, and R = number of constraint rules. This represents three nested loops:

```
for each hinge in filtered_hinges:        # H iterations
    for each plate in all_plates:          # P iterations
        for each rule in RULES:            # R iterations
            evaluate rule(hinge, plate, requirements)
```

Every hinge is paired with every plate, and every rule is run against every pair — no early exit. The total number of rule evaluations is H × P × R. With the current catalog (53 hinges, 55 plates, 14 rules) this is ~40,810 evaluations and completes in milliseconds, but the design has structural limits worth noting.

**No short-circuiting** — `evaluate()` runs all rules even after the first failure. This is intentional for `solve_with_explanation()` which needs the full trace, but `solve()` only needs to know whether a config is valid. Most combinations fail on R001 (brand lock, when enabled) or R002 (series compatibility), so short-circuiting would eliminate the majority of work.

**Plates are not indexed** — Hinges are indexed by brand, cabinet type, and application at init time, but plates are scanned linearly. Indexing plates by `compatible_hinge_series` or `cabinet_type` would cut the inner loop.

**No hinge-only rule caching** — Rules like R006 (door thickness) and R009 (boring pattern) depend only on the hinge and requirements, not the plate. These are re-evaluated for every plate pairing of the same hinge.

**Single-threaded, in-memory** — All products are loaded into lists. No database backing, no parallelism, no pagination.

**Practical impact** — Cabinetry hardware catalogs are bounded. Even 500 hinges × 500 plates × 14 rules is ~3.5M evaluations, which Python handles in seconds. These limitations only matter if scaling catalog size significantly, increasing request throughput, or both.
