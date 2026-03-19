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

### Stage decomposition: what it requires and what can go wrong

Stage decomposition means manually deciding which products to evaluate together at each step and which rules belong to each step. For LED lighting, this looks like:

- **Stage 1:** Cross light bars × drivers, evaluate voltage/wattage/connector rules. Discard invalid pairs.
- **Stage 2:** Cross surviving pairs × dimmers, evaluate dimming protocol/wattage/voltage rules.

This split is hand-curated in `engine_v2/families/led_lighting/rules.py`:

```python
STAGE_1_RULES = [LED001, LED002, LED003, LED006, LED007, LED008]  # bar ↔ driver
STAGE_2_RULES = [LED004, LED005, LED009]                          # driver ↔ dimmer
```

The decisions a family author must make:

1. **Which roles go in which stage.** Light bar and driver go together in Stage 1 because most rules involve those two. If you put light bar and dimmer in Stage 1 instead, there is only one bar-dimmer rule (LED005), so Stage 1 barely prunes anything and you gain nothing.

2. **Which rules go in which stage.** A rule can only reference roles available at its stage or earlier. LED004 (driver-dimmer protocol match) cannot run in Stage 1 because the dimmer has not been introduced yet. Assign it to the wrong stage and you get a runtime KeyError.

3. **Stage ordering matters for performance.** The whole point is that Stage 1 prunes heavily so Stage 2 has fewer combinations. If Stage 1 rules are weak filters, the pipeline adds complexity with no benefit.

**What can go wrong:**

- **Correctness is harder to verify.** The flat solver evaluates every combination against every rule — nothing can slip through a pruning crack. The staged solver only evaluates later-stage rules against combinations that survived earlier stages. If a stage incorrectly prunes a valid combination (e.g., a rule is assigned to the wrong stage), the solver silently drops correct results.

- **Adding a rule requires a decomposition decision.** With the flat solver, new rules are appended to `ALL_RULES`. With the staged solver, the author must decide which stage the rule belongs to, verify that all referenced roles are available at that stage, and consider whether the new rule changes the optimal stage ordering.

- **`_best_failing` negates the performance gain on failure.** When no valid configuration exists, `solve_with_explanation` calls `_best_failing`, which evaluates the full Cartesian product with no pruning and no early termination to find the closest match. The no-solution case — often the most important for user experience — is actually slower than the flat solver because the staged work was wasted.

- **Loss of the full evaluation matrix.** The staged solver prunes invalid partials between stages, so downstream stages never see combinations that failed upstream. Analytics like "which rule fails most often across all combinations" require a separate exhaustive pass, which is what `_best_failing` already does internally.

### Recommendation for N-candidate families

**Default to the flat N-candidate solver** for correctness, simplicity, and easy configuration. If latency becomes a problem at catalog scale, optimize the flat solver first (pre-filtering, indexing) before introducing stage decomposition. This matches the pattern in `engine_v1/solver.py`, which uses flat evaluation with brand/cabinet-type/application indexes to reduce the candidate space before the Cartesian product.

Reserve the staged pipeline for families where: (a) catalogs are large enough that the Cartesian product is measurably slow, (b) constraints are clearly layered across roles, and (c) the performance gain justifies the configuration and correctness burden.

---

## Appendix: Plain-English Guide — Paired vs N-Candidate Solvers

### Why concealed hinges are a paired solver (not a triple)

At first glance, the hinge constraint engine seems to involve three things: a hinge, a mounting plate, and a cabinet door. But the cabinet/door is not a product the engine selects — it's the problem definition. The contractor is standing in front of a specific cabinet. They know the door thickness, height, weight, and what overlay they need. They need the engine to tell them which hinge and plate to buy.

This distinction — **products you search over** vs **the situation you're given** — is what determines the solver shape:

| Thing | What it is | Searched over? |
|---|---|---|
| Hinge | Product from the catalog | Yes — the engine picks this |
| Mounting plate | Product from the catalog | Yes — the engine picks this |
| Cabinet/door | The contractor's job site | No — this is fixed input |

The 14 constraint rules reflect this. Some check the hinge against the cabinet (`R006: is the door thick enough for this hinge?`). Some check the plate against the cabinet (`R004: does this plate achieve the desired overlay?`). Some check the hinge against the plate (`R002: are they from compatible series?`). But none of them *search* for the right cabinet — the cabinet is always a constant.

That's why it's a paired solver: **two product axes** (hinge × plate) evaluated against **one fixed input** (customer requirements).

This also explains why pre-filtering works so well on the hinge side. Rules like R006 (door thickness) and R009 (boring pattern) depend only on the hinge and the customer's requirements — the plate is irrelevant. These rules could be evaluated once per hinge and cached, rather than re-evaluated for every plate pairing. The plate doesn't change the answer.

### Why LED lighting needs a 3-candidate solver

LED lighting is fundamentally different. A contractor fitting under-cabinet lighting doesn't pick their own driver and dimmer — they need the engine to find all three:

| Thing | What it is | Searched over? |
|---|---|---|
| Light bar | Product from the catalog | Yes — the engine picks this |
| Driver (transformer) | Product from the catalog | Yes — the engine picks this |
| Dimmer switch | Product from the catalog | Yes — the engine picks this |
| Cabinet | The contractor's job site | No — this is fixed input |

The driver can't be collapsed into "requirements" because the contractor doesn't know which driver they need. They know their cabinet is 600mm long and they want dimming — the engine has to figure out which bar, which driver, and which dimmer work together.

The constraint relationships show why this can't be reduced to a paired problem:

```
Bar ↔ Driver:    Voltage must match, wattage within capacity, connector compatible
Driver ↔ Dimmer: Dimming protocol must match, voltage compatible
Bar ↔ Dimmer:    Total wattage within dimmer's range
Bar ↔ Cabinet:   Bar length must fit (fixed input, like hinges)
```

There are **three cross-product axes** between catalog products (bar×driver, driver×dimmer, bar×dimmer), not just one. A rule like LED005 (dimmer wattage) needs to see the light bar and the dimmer but doesn't care about the driver. There's no way to express this in a paired `(primary, secondary)` model — which product is primary?

This is the problem the N-candidate solver was built for. Instead of `(hinge, plate)`, it uses `candidates: dict[str, Product]` so any rule can reach any product by role name:

```python
# Hinge rule — knows exactly what it's looking at
def check_series_compat(hinge, plate, req, num_hinges):
    return plate.series in hinge.compatible_series

# LED rule — reaches across roles freely
def check_dimmer_wattage(candidates, req, derived):
    bar = candidates["light_bar"]     # skips the driver entirely
    dimmer = candidates["dimmer"]
    return bar.wattage <= dimmer.max_wattage
```

### The general principle

The number of candidate products determines the solver shape. The customer's situation (cabinet dimensions, preferences, job site constraints) is always fixed input, regardless of how many fields it has:

| Candidates to search | Solver shape | Example families |
|---|---|---|
| 1 product | Filter against requirements | Drawer slides, handles, shelf supports |
| 2 products | A × B pairs | Concealed hinges, locks |
| 3+ products | A × B × C Cartesian product | LED lighting, closet systems |

A single-product family is just N=1 (no Cartesian product). A paired family is N=2. A triple is N=3. The algorithm is the same — the N-candidate solver handles all three shapes uniformly.

### Why staged decomposition is tempting but usually not worth it

The staged pipeline solver splits a 3-product problem into sequential stages. Instead of evaluating every bar × driver × dimmer triple, it evaluates bar × driver pairs first, throws away the failures, and only then brings in dimmers. This means less work — but it comes with real costs.

**The benefit is straightforward.** At full catalog scale (100 bars × 40 drivers × 50 dimmers = 200,000 triples), the flat solver evaluates all 200,000. The staged solver evaluates 4,000 bar-driver pairs first. If 80% fail (voltage mismatches, connector incompatibilities), only 800 pairs survive. Stage 2 evaluates 800 × 50 = 40,000 triples. Total: 44,000 evaluations instead of 200,000. That's a real saving.

**But someone has to decide how to split it.** With the flat solver, you write rules and add them to a list. With the staged solver, the family author must decide:

- Which products go in which stage? (Bar + driver in Stage 1, dimmer in Stage 2)
- Which rules go in which stage? (Voltage rules in Stage 1, dimming protocol rules in Stage 2)
- What order should stages run in? (The most restrictive stage should come first for maximum pruning)

These are optimisation decisions that have nothing to do with the domain. A domain expert thinks "voltage must match" — they don't think "and this check should happen in Stage 1 before dimmers are introduced." Staging leaks solver implementation concerns into domain modelling.

**Getting it wrong is silent.** If a rule is assigned to the wrong stage — say a rule that needs the dimmer is put in Stage 1, where no dimmer exists yet — that's a runtime error, and you'll catch it immediately. The dangerous case is subtler: if Stage 1 prunes a bar-driver pair that *looks* invalid at Stage 1 but *would have been* valid once paired with a specific dimmer in Stage 2, that valid configuration is silently lost. The solver doesn't report it as missing because it never evaluates it.

The flat solver can't have this problem. It evaluates every combination against every rule. If a valid configuration exists, the flat solver will find it. No pruning cracks for results to fall through.

**Adding a rule gets harder.** Flat solver: append to the rule list. Staged solver: decide which stage it belongs to, verify all the products it references are available at that stage, consider whether it changes which stage should come first. Every new rule is a decomposition decision, not just a domain decision.

**Failure analysis throws away the benefit.** When no valid configuration exists, the engine needs to find the *closest* match — the combination that fails the fewest rules — so the conversational layer can explain why. To find it, the solver must evaluate the full Cartesian product with no pruning (because the closest match might have been pruned). So the no-solution case — often the most important for user experience — does the same work as the flat solver, plus the wasted work from the initial staged attempt.

**Not all families decompose cleanly.** LED lighting works well for staging because bar ↔ dimmer has almost no direct constraints — most constraints are bar ↔ driver or driver ↔ dimmer. But imagine a family where every product constrains every other product equally. There's no clean split. Every stage ordering leaves substantial cross-cutting constraints for later stages, and the pruning benefit shrinks toward zero while the configuration complexity remains.

**The bottom line:** staged decomposition is a performance optimisation, not an architectural improvement. It makes the solver faster at the cost of making it harder to configure, harder to verify, and harder to extend. It should only be adopted when all three conditions are met:

1. The flat solver is *measurably* too slow (not theoretically — actually measured against latency requirements)
2. Constraints are clearly layered across product roles (some pairs have many rules, others have few)
3. The pruning rate is high enough (>50%) that the staged solver is meaningfully faster, even accounting for the failure analysis path that gets no benefit

In this project, the flat solver handles 200,000 triples in under 500ms. No product family currently justifies staging.
