# Multi-Family Constraint Engine Architecture

The current engine handles one product family: concealed hinges paired with mounting plates. The Würth catalog covers 13 product families, each with different products, pairing logic, and constraint rules. This document evaluates two approaches for scaling the engine across all families.

## Product families and their constraint shapes

Not all families look alike. Understanding the variation is critical before choosing an architecture.

| Family | Candidate A | Candidate B | Key constraints | Pairing shape |
|---|---|---|---|---|
| Concealed hinges | Hinge | Mounting plate | Brand lock, series compat, overlay, weight, boring pattern, mounting method | A × B (pair) |
| Drawer slides | Slide | — (single product) | Load rating, extension type, cabinet depth, mounting method, soft-close | A only (single) |
| Lift systems | Lift mechanism | — (single product) | Spring force vs door weight balance, cabinet height, clearance | A only (single) |
| Handles/knobs | Handle | — (single product) | Bore spacing, finish, min door width, projection clearance | A only (single) |
| Locks | Lock cylinder | Lock body | Keying, backset distance, door thickness, material | A × B (pair) |
| Drawer systems | Drawer side | Drawer slide | Height compatibility, load rating, runner length | A × B (pair) |
| Shelf supports | Shelf pin | — (single product) | Hole diameter, shelf thickness, load rating | A only (single) |
| LED lighting | Light bar | Driver/transformer | Wattage, voltage, daisy-chain limits, dimming compatibility | A × B (pair) |
| Closet systems | Component | Rail/standard | Slot spacing, load rating, component width | A × B (pair) |
| Door dampers | Damper | — (single product) | Door weight range, mounting space, actuation force | A only (single) |
| Catches/latches | Catch | — (single product) | Pull force, mounting method, door thickness | A only (single) |
| Flap stays | Stay | — (single product) | Door weight, opening angle, cabinet depth | A only (single) |
| Connecting fittings | Fitting | — (single product) | Panel thickness, material, joint type | A only (single) |

**Key observations:**

1. **Not all families are pairs.** Drawer slides, handles, shelf supports are single-product selections filtered against requirements. Only ~5 of 13 families involve pairing two products.
2. **Requirements differ radically.** A hinge needs overlay, boring pattern, cup depth. A drawer slide needs cabinet depth, extension type, load rating. There is almost no overlap in requirement fields.
3. **Rule count varies.** Hinges have 14 rules. Handles might have 4. Lighting might have 8 with electrical safety constraints.
4. **Ranking criteria differ.** Hinges rank by price then capacity. Drawer slides might rank by extension type then price. Lighting ranks by lumen output then wattage efficiency.

## Option A: Generic solver with pluggable rule sets

### Concept

Extract the solver into a family-agnostic framework. Each product family registers:
- Its domain models (product types, requirements type)
- Its rule functions
- Its pre-filter indexes
- Its ranking criteria
- Whether it's a single-product or paired-product family

The solver doesn't know what a hinge is. It takes candidates, rules, and requirements, then evaluates and ranks.

### Architecture

```
engine_v2/
├── core/
│   ├── solver.py           # Generic ConstraintSolver — works on any product family
│   ├── models.py           # Base classes: Product, Requirements, RuleResult, Configuration
│   ├── registry.py         # ProductFamilyRegistry — registers families and their components
│   └── types.py            # Type aliases: RuleFn, PreFilterFn, RankKeyFn
├── families/
│   ├── concealed_hinge/
│   │   ├── models.py       # ConcealedHinge, MountingPlate, HingeRequirements
│   │   ├── rules.py        # 14 hinge-specific rules
│   │   ├── filters.py      # Brand/cabinet/application pre-filters
│   │   └── config.py       # Family registration: products, rules, ranking
│   ├── drawer_slide/
│   │   ├── models.py       # DrawerSlide, SlideRequirements
│   │   ├── rules.py        # Slide-specific rules
│   │   ├── filters.py      # Pre-filters
│   │   └── config.py       # Family registration
│   └── ...                 # One sub-package per family
└── __init__.py
```

### How it works

**1. Family registration**

Each family defines a `FamilyConfig` that tells the solver everything it needs:

```python
@dataclass
class FamilyConfig:
    name: str
    primary_type: type[Product]           # e.g., ConcealedHinge
    secondary_type: type[Product] | None  # e.g., MountingPlate (None for single-product families)
    requirements_type: type[Requirements] # e.g., HingeRequirements
    rules: list[RuleFn]                   # Ordered rule functions
    pre_filters: list[PreFilterFn]        # Functions that narrow candidates before evaluation
    rank_key: RankKeyFn                   # Sorting function for valid configurations
    derived_values: DerivedValuesFn       # e.g., hinges_per_door
```

**2. Generic solver**

```python
class ConstraintSolver:
    def solve(self, family: str, requirements: Requirements) -> list[Configuration]:
        config = registry.get(family)
        primaries = config.pre_filters(self.catalog[family], requirements)

        if config.secondary_type:
            # Paired family: evaluate A × B
            for a in primaries:
                for b in self.catalog[family + "_secondary"]:
                    configuration = self.evaluate(a, b, requirements, config.rules)
                    if configuration.valid:
                        results.append(configuration)
        else:
            # Single-product family: evaluate A against requirements
            for a in primaries:
                configuration = self.evaluate(a, None, requirements, config.rules)
                if configuration.valid:
                    results.append(configuration)

        return sorted(results, key=config.rank_key)
```

**3. Rules stay simple functions**

```python
# Hinge rule — same signature as today, just typed against base classes
def check_brand_lock(primary: Product, secondary: Product, req: Requirements, derived: dict) -> RuleResult:
    h, p = cast(ConcealedHinge, primary), cast(MountingPlate, secondary)
    # ... same logic as current R001
```

### Pros

- **One solver to maintain.** Bug fixes, optimizations (early termination, caching) apply to all families.
- **Consistent API.** The FastAPI layer exposes one `/solve` endpoint with a `family` parameter. The conversational layer uses the same interface regardless of product type.
- **Consistent tracing.** Every family produces `RuleResult` traces in the same format. The LLM explanation layer doesn't need family-specific formatting.
- **Easy to add families.** Adding drawer slides means writing models, rules, and a config — no solver changes.

### Cons

- **Forced abstraction.** The `Product` base class and `Requirements` base class need to be general enough for all families. This can lead to overly generic types that lose domain clarity.
- **Cast-heavy rule code.** Rules receive `Product` but need `ConcealedHinge`. Every rule function starts with a cast. Type safety is weaker than the current approach.
- **Paired vs single divergence.** The solver needs branching logic for paired vs single-product families. This is manageable but adds complexity.
- **Premature generalization risk.** We've only built one family. Designing the generic framework from one example risks getting the abstractions wrong. Drawer slides might not fit the mold we designed around hinges.
- **Ranking complexity.** Each family has different ranking criteria. The `rank_key` function works, but complex ranking (e.g., lighting systems with multi-objective optimization) may outgrow a simple sort key.

### Risk mitigation

The biggest risk is premature abstraction. Mitigation: build the framework with hinges and one new family (drawer slides), then validate that the abstractions hold before committing to them for all 13.

---

## Option B: Independent engines per family

### Concept

Each product family gets its own engine module — its own models, rules, solver, and loader. They share common infrastructure (RuleResult format, data loading patterns, API response format) but not a common solver.

### Architecture

```
engines/
├── common/
│   ├── models.py           # RuleResult, RuleCategory, ManufacturerProduct, DistributorSKU
│   ├── types.py            # Shared type aliases
│   └── loader.py           # Base JSON/DB loading utilities
├── concealed_hinge/
│   ├── models.py           # ConcealedHinge, MountingPlate, CustomerRequirements, Configuration
│   ├── rules.py            # 14 rules
│   ├── solver.py           # HingeConstraintEngine (current code, unchanged)
│   ├── loader.py           # Hinge-specific JSON adapter
│   └── tests/
├── drawer_slide/
│   ├── models.py           # DrawerSlide, SlideRequirements, SlideConfiguration
│   ├── rules.py            # Slide rules
│   ├── solver.py           # DrawerSlideEngine
│   ├── loader.py           # Slide-specific loader
│   └── tests/
└── ...
```

### How it works

Each engine is self-contained:

```python
class DrawerSlideEngine:
    def __init__(self, slides: list[DrawerSlide]):
        self.slides = slides
        self._load_index = ...

    def solve(self, req: SlideRequirements) -> list[SlideConfiguration]:
        # Family-specific logic — no need to fit a generic mold
        ...
```

The API layer provides the unified interface:

```python
@app.post("/solve/{family}")
def solve(family: str, requirements: dict):
    engine = engine_registry[family]
    return engine.solve(parse_requirements(family, requirements))
```

### Pros

- **Domain clarity.** `DrawerSlideEngine.solve(SlideRequirements)` is self-documenting. No casts, no generic types.
- **Independent evolution.** Each family's solver can be optimized for its specific constraint shape. Drawer slides don't need the paired-product loop. Lighting can use graph-based constraint propagation if needed.
- **No premature abstraction.** Each family is built based on its actual needs. Common patterns are extracted after they emerge naturally from 3-4 implementations.
- **Easier testing.** Each family has isolated tests that don't depend on a shared framework.
- **Lower risk.** If the lighting family needs a fundamentally different solving approach, it just builds its own solver. No framework changes needed.

### Cons

- **Code duplication.** The solve → pre-filter → evaluate → rank → trace pattern will be repeated in each engine. Bug fixes and optimizations must be applied to each.
- **Inconsistency risk.** Without a shared framework, families may drift in how they handle tracing, error reporting, or ranking. Code review discipline is the only guard.
- **More code to maintain.** 13 engines × ~4 files each = ~52 files vs ~20 files for Option A.
- **API layer complexity.** The FastAPI endpoint needs a registry mapping family names to engines, and each engine returns a slightly different response shape (unless you enforce a common output format — which starts to look like Option A).
- **Optimization duplication.** Early termination, plate indexing, caching — these improvements need to be implemented in each engine separately.

### Risk mitigation

Extract a shared `solve_pairs()` and `solve_singles()` utility that provides the basic loop + trace + rank pattern. Families use these utilities but can override any step. This gives ~80% of Option A's code reuse without the full generic framework.

---

## Comparison matrix

| Criterion | Option A (Generic) | Option B (Independent) |
|---|---|---|
| **Code reuse** | High — one solver | Low — repeated per family |
| **Type safety** | Weaker — casts needed | Strong — concrete types |
| **Adding a new family** | Config + models + rules | Full engine + models + rules |
| **Optimization scope** | Global — fix once | Per-family — fix N times |
| **Abstraction risk** | High — designed from 1 example | Low — each family fits itself |
| **API consistency** | Built-in | Must be enforced |
| **Testing complexity** | Shared framework tests + family tests | Family tests only |
| **Time to first new family** | Higher (build framework first) | Lower (copy and adapt) |
| **Time to 13th family** | Lower (just config) | Higher (full engine each time) |
| **Flexibility for unusual families** | Constrained by framework | Unlimited |

## Recommendation

**Start with Option A, but keep it minimal.** Build the generic solver with just enough abstraction to handle paired and single-product families. Validate with concealed hinges (existing, proves backward compatibility) and drawer slides (new, proves the framework generalizes). If a third family doesn't fit, revisit.

The key discipline: don't over-abstract. The generic solver should be ~100 lines, not a framework. If a family needs something the framework can't do, let it override rather than expanding the framework.

See `engine_v2/` for the working prototype.

---

## The N-candidate problem

The initial prototype assumes at most two products per configuration (primary + secondary). This covers single-product families (drawer slides) and paired families (hinges + plates). But some families require three or more products evaluated together:

| Family | Candidate A | Candidate B | Candidate C | Evaluation shape |
|---|---|---|---|---|
| LED lighting | Light bar | Driver/transformer | Dimmer switch | A × B × C (triple) |
| Closet systems | Upright standard | Bracket | Shelf/rod | A × B × C (triple) |
| Drawer systems | Drawer side | Slide runner | Front fixing | A × B × C (triple) |
| Concealed hinges | Hinge | Mounting plate | — | A × B (pair) |
| Drawer slides | Slide | — | — | A (single) |

**The core tension:** the solver needs to handle 1, 2, or 3+ products without becoming a nested-loop factory. Two approaches:

### Approach 1: Flat N-candidate solver

Generalize `Configuration` from `(primary, secondary)` to a list of N candidates. The solver takes N product lists and evaluates their Cartesian product. Rules receive all N candidates.

```python
class NConfiguration(BaseModel):
    candidates: dict[str, Product]  # {"light_bar": ..., "driver": ..., "dimmer": ...}
    rule_results: list[RuleResult]
    derived: dict
```

**How it works:**
1. Family config declares N product roles: `[("light_bar", LightBar), ("driver", Driver), ("dimmer", Dimmer)]`
2. Solver computes Cartesian product of all role lists
3. Each combination is evaluated against all rules
4. Rules receive a `dict[str, Product]` and access candidates by role name

**Pros:**
- Conceptually simple — one evaluation loop, one rule signature, any number of products
- Rules see the full candidate set, so they can check any cross-product constraint
- No intermediate state to manage

**Cons:**
- **Combinatorial explosion.** 50 light bars × 20 drivers × 30 dimmers = 30,000 triples. With 8 rules each, that's 240,000 rule evaluations. Manageable but grows fast.
- **No pruning between roles.** An incompatible light bar × driver pair is re-evaluated with every dimmer, wasting work. Pre-filtering helps but can't eliminate all cross-product waste.
- **Rules must handle missing roles.** A 2-product family passes `None` for absent roles. N-candidate solves this with named roles but adds lookup overhead.

**When to use:** When all N products interact with each other (every product constrains every other product) and the catalog is small enough that the Cartesian product is tractable.

### Approach 2: Staged pipeline solver

Decompose the N-candidate problem into sequential stages. Each stage evaluates a subset of candidates, filters to valid combinations, then passes them to the next stage.

```
Stage 1: light_bar × driver → evaluate electrical rules → valid pairs
Stage 2: valid_pair × dimmer → evaluate dimming rules → valid triples
```

**How it works:**
1. Family config declares stages: `[Stage("electrical", ["light_bar", "driver"], electrical_rules), Stage("dimming", ["_prev", "dimmer"], dimming_rules)]`
2. Solver runs Stage 1, collects valid pairs
3. Stage 2 takes each valid pair and crosses it with dimmers
4. Each stage has its own rules — rules only see the candidates relevant to that stage

**Pros:**
- **Early pruning.** If 50 light bars × 20 drivers = 1,000 pairs but only 80 are electrically valid, Stage 2 evaluates 80 × 30 = 2,400 triples instead of 30,000.
- **Natural rule grouping.** Electrical safety rules don't need to know about dimming. Dimming rules don't need to check voltage matching. Each stage is focused.
- **Scales better.** Adding a 4th product (e.g., mounting clip) is just another stage, not another nested loop dimension.
- **Reusable stages.** The "electrical compatibility" stage could be shared across LED lighting and under-cabinet lighting families.

**Cons:**
- **Stage ordering matters.** If a dimmer constrains which drivers are valid (e.g., trailing-edge vs leading-edge), putting driver × dimmer in Stage 2 means you can't prune drivers in Stage 1. Wrong ordering wastes work.
- **Cross-stage constraints are awkward.** If a rule needs to see the light bar AND the dimmer (skipping the driver), it doesn't fit cleanly into either stage. You'd need a final "cross-cutting" stage.
- **More complex configuration.** Family authors must think about stage decomposition, not just "here are my rules."

**When to use:** When constraints are layered (some products constrain each other but not all), catalogs are large, and early pruning is important for performance.

### Comparison: N-candidate vs Staged

| Criterion | Flat N-candidate | Staged pipeline |
|---|---|---|
| **Simplicity** | Simpler — one loop, one rule signature | More complex — stages, ordering |
| **Performance** | O(A × B × C × rules) | O(A × B × rules₁) + O(valid_AB × C × rules₂) |
| **Pruning** | Pre-filters only | Inter-stage pruning |
| **Rule clarity** | Rules see everything (can be noisy) | Rules see only their stage's candidates |
| **Adding products** | Add to Cartesian product (exponential) | Add a stage (linear) |
| **Cross-cutting constraints** | Natural (rules see all candidates) | Awkward (need cross-cutting stage) |
| **Catalog size sensitivity** | High — full Cartesian product | Lower — pruning reduces later stages |

### LED lighting example (used in both prototypes)

A cabinet LED lighting system consists of three components that must be compatible:

**Light bar** — the LED strip or bar mounted inside the cabinet
- Wattage (power consumption)
- Voltage (12V or 24V DC)
- Length (must fit cabinet)
- Lumen output (brightness)
- Dimmable (yes/no)
- Connector type

**Driver (transformer)** — converts mains AC to the LED's DC voltage
- Output voltage (must match light bar)
- Max wattage (must exceed total light bar wattage with headroom)
- Output channels (how many light bars one driver can power)
- Dimmable (yes/no — must match if dimming desired)
- Dimming protocol (trailing-edge, leading-edge, 0-10V, DALI)

**Dimmer switch** — controls brightness (optional, only if dimming desired)
- Dimming protocol (must match driver)
- Max wattage (must exceed total system wattage)
- Voltage compatibility

**Constraint relationships:**
```
Light bar ←→ Driver:    Voltage match, wattage capacity, connector
Light bar ←→ Dimmer:    (no direct constraints)
Driver    ←→ Dimmer:    Dimming protocol match, wattage capacity
All three:              Total system wattage under dimmer limit
```

This is why staged works well here: light bar × driver constraints are independent of the dimmer, so Stage 1 can prune aggressively before dimmer evaluation.

See `engine_v2/core/solver_n.py` for the flat N-candidate prototype and `engine_v2/core/solver_staged.py` for the staged pipeline prototype. Both are tested with LED lighting in `engine_v2/tests/test_n_candidate.py` and `engine_v2/tests/test_staged.py`.
