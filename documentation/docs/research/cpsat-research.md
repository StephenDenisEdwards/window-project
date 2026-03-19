# CP-SAT Research — Applicability to Window Constraint Engine

Research into whether Google OR-Tools CP-SAT is a suitable solver for the hinge constraint engine, either now or as the system scales to multi-family product configuration.

---

## 1. What is Google OR-Tools CP-SAT?

### Overview

CP-SAT (Constraint Programming — Satisfiability) is a constraint solver within Google's open-source [OR-Tools](https://developers.google.com/optimization) suite. It combines techniques from constraint programming (CP), Boolean satisfiability (SAT), and mixed-integer programming (MIP) into a single solver that accepts a declarative constraint model and finds solutions — or proves none exist.

**Core abstraction:** You define _variables_ with finite domains, _constraints_ over those variables, and optionally an _objective function_ to optimize. The solver explores the search space, pruning infeasible regions via constraint propagation, and returns valid assignments.

### Key Concepts

| Concept | Description |
|---------|-------------|
| **CpModel** | Container for variables, constraints, and objectives. You build the model programmatically in Python. |
| **IntVar** | Integer decision variable with a finite domain `[lb, ub]`. All variables must be integer — floats are scaled to integers (e.g., millimetres not metres). |
| **BoolVar** | Special case of IntVar with domain `{0, 1}`. Used heavily for "indicator" constraints (if X is selected, then Y must hold). |
| **Constraints** | Linear inequalities (`x + y <= 10`), element constraints (`allowed_values[index] == target`), boolean implications (`x.OnlyEnforceIf(b)`), table constraints (allowed tuples), all-different, circuit, etc. |
| **Objective** | Optional. Minimize/maximize a linear expression over variables. Without an objective, CP-SAT enumerates feasible solutions. |
| **CpSolver** | Executes the search. Returns status (`OPTIMAL`, `FEASIBLE`, `INFEASIBLE`, `MODEL_INVALID`). Can enumerate all solutions via a callback, or return the first/best within a time limit. |
| **Solution callbacks** | User-defined callbacks invoked each time a feasible solution is found. Used for enumerating all valid configurations. |
| **SearchStrategy** | Configurable: automatic (default), fixed variable ordering, or custom branching hints. |

### Architecture Under the Hood

CP-SAT is not a pure CP solver or a pure SAT solver. It is a **lazy clause generation** solver:

1. **SAT core** — The search backbone is a CDCL SAT solver (conflict-driven clause learning), the same algorithm family that powers modern SAT solvers like MiniSat and CaDiCaL.
2. **CP propagators** — Domain-specific propagators (for linear constraints, element constraints, table constraints, etc.) run during search to tighten variable domains. When a propagator detects infeasibility, it generates a _conflict clause_ that the SAT core learns, preventing the same dead end from being revisited.
3. **LP relaxation** — An embedded LP solver provides bounds and cuts, similar to MIP solvers. This tightens the objective bound and prunes the search.
4. **Parallelism** — CP-SAT runs multiple search strategies in parallel (portfolio approach). By default it uses all available CPU cores, each running a different heuristic. The first worker to find a proof of optimality terminates the others.

### Python API

```python
from ortools.sat.python import cp_model

model = cp_model.CpModel()

# Variables
x = model.NewIntVar(0, 10, 'x')
y = model.NewIntVar(0, 10, 'y')

# Constraints
model.Add(x + y <= 15)
model.Add(x != y)

# Objective (optional)
model.Maximize(x + 2 * y)

# Solve
solver = cp_model.CpSolver()
status = solver.Solve(model)

if status == cp_model.OPTIMAL:
    print(f"x={solver.Value(x)}, y={solver.Value(y)}")
```

### What CP-SAT Excels At

CP-SAT is purpose-built for **combinatorial optimization** problems where:

- There are many interdependent variables with finite domains
- Constraints create complex interactions between variables (not just pairwise filtering)
- The search space is exponential and brute force is infeasible
- You need provably optimal solutions or proof of infeasibility

Classic CP-SAT strengths:

| Problem Class | Why CP-SAT Fits |
|---------------|-----------------|
| **Job-shop scheduling** | Machines × jobs × time slots with no-overlap, precedence, and makespan minimization |
| **Vehicle routing** | Vehicles × stops × capacity × time windows — exponential assignments |
| **Bin packing** | Items × bins with capacity, weight, and compatibility constraints |
| **Nurse rostering** | Staff × shifts × skills × fairness — many interdependent soft/hard constraints |
| **Configuration (multi-way)** | Selecting components from N categories simultaneously where choices interact |

The common thread: **the combinatorial explosion of joint assignments across multiple variable groups**, where constraint propagation prunes the space orders of magnitude faster than enumeration.

---

## 2. Suitability for the Current Hinge Constraint Engine

### Current Problem Structure

The engine solves a **pairwise product compatibility** problem:

- **Input:** `CustomerRequirements` (cabinet type, door dimensions, application, overlay, etc.)
- **Decision:** Select one `ConcealedHinge` and one `MountingPlate` from catalogs of 53 and 55 items respectively
- **Constraints:** 14 rules (13 hard constraints + 1 preference), each evaluating attributes of the hinge, plate, and requirements independently
- **Output:** All valid (hinge, plate) pairs, ranked by price then capacity

The search space is `53 × 55 = 2,915` pairs. After indexed pre-filtering by application, cabinet type, and brand, this drops to roughly 100–300 pairs. Each evaluation runs 14 predicate checks. Total work: ~4,000–40,000 simple comparisons, completing in single-digit milliseconds.

### Why CP-SAT Is Not the Right Fit Today

The hinge engine's problem structure is fundamentally different from the problems CP-SAT is designed to solve.

#### 2.1 No combinatorial explosion

CP-SAT's value proposition is pruning exponentially large search spaces. The hinge engine has two decision variables (hinge, plate) with a cross-product of ~3,000 — trivially enumerable. There is no exponential blowup to prune.

For comparison, a nurse rostering problem with 50 nurses × 30 days × 3 shifts = 3^1500 possible assignments. _That_ is where CP-SAT shines. The hinge engine is 10+ orders of magnitude smaller.

#### 2.2 Independent constraints, no propagation benefit

The 14 rules are **independent predicates** — each examines only attributes of the hinge, plate, and requirements. No rule's outcome affects another rule's evaluation. This means constraint propagation (CP-SAT's primary acceleration mechanism) has nothing to propagate. The solver would degenerate to brute-force enumeration with overhead.

Constraint propagation is powerful when tightening one variable's domain cascades through interconnected constraints to tighten others. Example: in scheduling, assigning a job to time slot 3 propagates to exclude slot 3 from conflicting jobs, which propagates further. In the hinge engine, knowing that R001 (brand lock) passes tells you nothing about R007 (weight capacity) — they examine different attributes.

#### 2.3 Enumeration vs. optimization

The engine needs **all valid configurations** with full rule traces, not just the optimal one. CP-SAT can enumerate solutions via callbacks, but this is not its natural mode — it is optimized for finding one optimal solution quickly. Solution enumeration in CP-SAT carries overhead (callback dispatch, model state management) that exceeds the cost of a simple Python loop over 3,000 pairs.

#### 2.4 Full rule tracing is essential

Every configuration must include a `RuleResult` for every rule — even passing rules — with human-readable detail, compared values, and remediation suggestions. This tracing is the engine's core value proposition for the conversational AI layer. CP-SAT provides infeasibility certificates (unsatisfiable cores), not per-rule explanations with domain-specific remediation text. Bolting explainability onto a CP-SAT model would require re-evaluating all rules after solving — negating the solver's benefit entirely.

#### 2.5 "Best failing" requires violation counting

When no solution exists, the engine finds the configuration with the fewest violations (`_best_failing`). CP-SAT can handle soft constraints via penalty terms, but its "closest infeasible" is an optimization over penalty weights — not a transparent count of discrete rule violations with per-rule explanations. The current approach is simpler and more explainable.

#### 2.6 Performance overhead

OR-Tools CP-SAT has non-trivial model construction and solver startup costs (~5–50ms depending on model complexity). The current engine solves in <5ms. Introducing CP-SAT would likely increase solve time by 5–20×, with no correctness or functionality benefit.

### Assessment Summary

| Criterion | Current Engine | CP-SAT |
|-----------|---------------|--------|
| Correctness | All constraints evaluated, deterministic | Equivalent, but must mirror rules in model |
| Solve time | <5ms | ~20–100ms (model build + solve + trace) |
| Explainability | Full per-rule trace with remediation | Requires separate post-solve evaluation |
| All-solutions enumeration | Natural (loop) | Callback overhead |
| Best-failing analysis | Count violations, return closest | Soft-constraint penalties, less transparent |
| Code complexity | ~160 lines (solver.py) | ~300+ lines (model construction + mapping + callbacks + post-processing) |
| Dependencies | Zero (pure Python + Pydantic) | ortools (~150MB, C++ bindings, platform-specific wheels) |
| Maintainability | Rules are Python functions, testable individually | Constraints are model builder calls, harder to test in isolation |

**Verdict for the current system:** CP-SAT is not suitable. It would add complexity, dependencies, and latency without improving correctness, performance, or explainability. The problem is a small, flat, pairwise filter — not a combinatorial optimization.

---

## 3. Future Phases Where CP-SAT Becomes Relevant

### 3.1 Multi-Family Cabinet Configuration (Phase 4)

The production roadmap targets 13 product families. A full cabinet specification would require simultaneously selecting:

- Concealed hinges (per door)
- Mounting plates (per hinge)
- Drawer slides (per drawer)
- Lift system (if applicable)
- Handles (per door/drawer)
- Lighting (if applicable)
- Drivers/power supplies (for lighting)

With 6 product families × ~50 options each, the naive cross-product is `50^6 = 15.6 billion` — well beyond brute-force. Critically, these choices **interact**:

- Hinge opening angle may conflict with lift system clearance (AVENTOS HK-XS requires clearance that a 170° hinge violates)
- Drawer slide mounting competes for cabinet interior space with hinge boring
- Lighting drivers require specific mounting zones that may overlap with plate positions
- Handle placement affects door balance, which affects hinge weight requirements

These are exactly the multi-way interdependent constraints where CP-SAT's propagation delivers orders-of-magnitude speedup over enumeration.

### 3.2 Multi-Door Optimization

A kitchen with 20 cabinet doors where the contractor wants to minimize total cost while maintaining brand consistency where possible, but allowing brand mixing if a door's requirements can't be met by the preferred brand. This is a constrained optimization problem across 20 coupled decisions — natural CP-SAT territory.

### 3.3 Project-Level Bill of Materials

Optimizing a complete kitchen project across all cabinets: volume pricing thresholds (buy 50+ of the same hinge for a discount), inventory availability (prefer in-stock items), delivery consolidation (fewer distinct SKUs = simpler logistics). This is a global optimization over many local decisions — exactly what CP-SAT is built for.

---

## 4. Why Not Start with CP-SAT Now?

If multi-family configuration is the ultimate goal, there is a reasonable argument for building on CP-SAT from the start to avoid a future rewrite. This section evaluates that argument honestly.

### 4.1 The case for starting now

- **Avoid a rewrite.** If multi-family is the destination, building brute-force now means discarding it later.
- **Build expertise early.** CP-SAT has a learning curve — better to climb it on a simple problem than under Phase 4 pressure.
- **The model grows incrementally.** Start with 2 variables (hinge, plate), add drawer slides as a third, lift systems as a fourth.

### 4.2 Why it doesn't hold up

#### CP-SAT does not replace the current engine — it sits alongside it

The engine's core value isn't solving. It's **explainability**. Every query returns full rule traces with human-readable detail, compared values, and remediation suggestions. The conversational AI layer depends on this entirely.

CP-SAT can tell you _that_ a configuration is valid or infeasible. It cannot tell you _why_ in domain-specific language — which rules passed, what values were compared, or what the user should change.

Even with CP-SAT handling the solve, you still need:

- The rule functions (for per-rule tracing)
- The evaluation loop (for explanation output)
- The `_best_failing` logic (for "no solution" diagnostics)

This means **two representations of every constraint** must be maintained — one as a CP-SAT model element, one as a Python rule function. They must stay in sync. That is a real, ongoing maintenance cost with no current benefit.

#### The cross-family constraints don't exist yet

The 2-variable CP-SAT model for hinges teaches almost nothing about the future 6-variable model. The hard part of Phase 4 isn't "how do I use CP-SAT" — it's "what are the cross-family constraints between hinges and AVENTOS lift systems?" Those constraints don't exist in the codebase or catalogs yet. Nobody has defined them.

The CP-SAT model built today would be substantially rewritten when those interactions are discovered. Starting with CP-SAT now optimizes for a future that can't yet be defined.

#### The 2-variable model doesn't exercise CP-SAT's strengths

Running CP-SAT on 2 variables with independent constraints is like testing a Formula 1 engine by driving it around a parking lot. You learn the API, but you learn nothing about its behavior under the conditions that actually matter — large search spaces, deep constraint propagation, parallel portfolio search. The experience gained is superficial.

#### The dependency cost is front-loaded, the benefit is back-loaded

OR-Tools adds ~150MB of platform-specific C++ bindings. This means:

- CI/CD pipeline must build/test against a specific platform wheel
- Deployment artifacts grow significantly
- Platform compatibility constraints (ARM vs x86, Linux vs macOS)
- Version pinning against a Google release schedule

These costs start immediately. The benefit starts at Phase 4 — which may be 6–12 months away, or may not arrive at all if business priorities shift.

### 4.3 Verdict

Starting with CP-SAT now trades **certain complexity today** for **uncertain benefit later**, against a problem whose shape is not yet known. The current engine is correct, fast, explainable, and simple. The right time to introduce CP-SAT is when the first concrete cross-family constraint is identified — not before.

---

## 5. Recommended Architecture for Phase 4: Hybrid Coordination

When multi-family configuration does arrive, the right approach is not replacing the per-family engines with CP-SAT. It is adding CP-SAT as a **coordination layer above them**.

### 5.1 Architecture

```
┌─────────────────────────────────────────────────┐
│              CP-SAT Coordination Layer           │
│  (cross-family constraints, global optimization) │
└────────┬──────────┬──────────┬──────────┬───────┘
         │          │          │          │
    ┌────▼───┐ ┌────▼───┐ ┌───▼────┐ ┌───▼────┐
    │ Hinge  │ │ Drawer │ │  Lift  │ │ Handle │
    │ Engine │ │ Slide  │ │ System │ │ Engine │
    │        │ │ Engine │ │ Engine │ │        │
    └────────┘ └────────┘ └────────┘ └────────┘
    (pairwise,  (pairwise,  (pairwise,  (pairwise,
     explainable) explainable) explainable) explainable)
```

### 5.2 How It Works

1. **Each product family has its own constraint engine** — identical in architecture to the current hinge engine. Pairwise evaluation, full rule tracing, explainability, `_best_failing` diagnostics. These are fast, simple, and independently testable.

2. **CP-SAT sits above**, selecting one valid configuration per family such that cross-family constraints are satisfied and a global objective (total cost, brand consistency, delivery consolidation) is optimized.

3. **CP-SAT variables** are not raw products — they are indices into each family engine's valid configuration list. The per-family engines pre-compute valid options; CP-SAT selects among them.

4. **Explainability is preserved.** Each family engine provides its full rule trace. CP-SAT adds cross-family constraint explanations ("AVENTOS HK-XS requires ≥40mm clearance from hinge cup; selected hinge provides 45mm — OK"). The conversational layer gets both per-family and cross-family traces.

### 5.3 Why This Works Better Than CP-SAT Everywhere

| Concern | CP-SAT Everywhere | Hybrid |
|---------|-------------------|--------|
| Explainability | Must duplicate all rules for tracing | Per-family engines handle tracing natively |
| Constraint sync | Two representations of every rule | Cross-family constraints exist only in CP-SAT |
| Testing | One monolithic model, hard to test rules in isolation | Per-family engines tested independently |
| Performance | Model construction overhead on every query, even single-family | CP-SAT only invoked for multi-family queries |
| Incremental adoption | All-or-nothing rewrite | Add families one at a time, CP-SAT layer added when ≥2 families interact |
| Single-family queries | Still pays CP-SAT overhead | Falls through to fast per-family engine |

### 5.4 CP-SAT Model Sketch for Coordination

```python
from ortools.sat.python import cp_model

# Each family engine has pre-computed valid configurations
hinge_configs = hinge_engine.solve(req.hinge_requirements)    # list[Configuration]
slide_configs = slide_engine.solve(req.slide_requirements)    # list[Configuration]
lift_configs = lift_engine.solve(req.lift_requirements)        # list[Configuration]

model = cp_model.CpModel()

# Decision: which valid config to pick from each family
hinge_idx = model.NewIntVar(0, len(hinge_configs) - 1, 'hinge_config')
slide_idx = model.NewIntVar(0, len(slide_configs) - 1, 'slide_config')
lift_idx = model.NewIntVar(0, len(lift_configs) - 1, 'lift_config')

# Cross-family constraint: AVENTOS clearance vs hinge opening angle
# Pre-compute which (hinge_config, lift_config) pairs are jointly feasible
allowed_hinge_lift = []
for hi, hc in enumerate(hinge_configs):
    for li, lc in enumerate(lift_configs):
        if hc.hinge.opening_angle_deg <= lc.lift.max_adjacent_angle_deg:
            allowed_hinge_lift.append((hi, li))
model.AddAllowedAssignments([hinge_idx, lift_idx], allowed_hinge_lift)

# Cross-family constraint: drawer slide depth vs hinge cup protrusion
allowed_hinge_slide = []
for hi, hc in enumerate(hinge_configs):
    for si, sc in enumerate(slide_configs):
        if hc.hinge.cup_protrusion_mm + sc.slide.min_clearance_mm <= req.cabinet_depth_mm:
            allowed_hinge_slide.append((hi, si))
model.AddAllowedAssignments([hinge_idx, slide_idx], allowed_hinge_slide)

# Global objective: minimize total project cost
hinge_costs = [int(hc.total_price_usd * 100) for hc in hinge_configs]
slide_costs = [int(sc.total_price_usd * 100) for sc in slide_configs]
lift_costs = [int(lc.total_price_usd * 100) for lc in lift_configs]

h_cost = model.NewIntVar(0, max(hinge_costs), 'h_cost')
s_cost = model.NewIntVar(0, max(slide_costs), 's_cost')
l_cost = model.NewIntVar(0, max(lift_costs), 'l_cost')
model.AddElement(hinge_idx, hinge_costs, h_cost)
model.AddElement(slide_idx, slide_costs, s_cost)
model.AddElement(lift_idx, lift_costs, l_cost)

model.Minimize(h_cost + s_cost + l_cost)

# Solve
solver = cp_model.CpSolver()
status = solver.Solve(model)
```

### 5.5 When to Build This

The trigger is **the first concrete cross-family constraint**. When someone can write down "product X from family A conflicts with product Y from family B under condition Z" with specific attribute values, that is the moment to:

1. Build the second family engine (e.g., drawer slides) following the hinge engine pattern
2. Add the CP-SAT coordination layer with the identified cross-family constraint
3. Test with real product data

Until that constraint is identified and validated against manufacturer specifications, any CP-SAT model would be speculative.

---

## 6. Alternative Approaches Evaluated

### 6.1 Current Approach: Indexed Brute Force (Recommended for Now)

**How it works:** Pre-filter hinges by application, cabinet type, and brand using hash indexes. Evaluate all remaining (hinge × plate) pairs through 14 rules. Return all valid configurations sorted by price.

**Strengths:** Simple, fast (<5ms), fully explainable, zero dependencies, easy to test and modify. Rules are plain Python functions.

**Weaknesses:** O(H × P × R) — scales linearly with catalog size. At 10,000 hinges × 10,000 plates, this would take ~1 second. Unlikely to be a problem for concealed hinges, but could matter for multi-family expansion.

**Verdict:** The right approach for the current problem and foreseeable single-family use.

### 6.2 python-constraint2

A pure Python CSP library using backtracking search with arc consistency.

**How it maps to the hinge problem:**
```python
from constraint import Problem
p = Problem()
p.addVariable("hinge", hinges)
p.addVariable("plate", plates)
p.addConstraint(lambda h, p: h.brand == p.brand, ["hinge", "plate"])
# ... 13 more constraints
solutions = p.getSolutions()
```

**Why not:** Backtracking with 2 variables is strictly slower than direct enumeration. The library adds overhead for domain management and constraint checking that doesn't pay off until variables number in the dozens. No optimization support. No parallel search. Would be 2–5× slower than the current approach.

### 6.3 Microsoft Z3 (SMT Solver)

Z3 is a theorem prover for Satisfiability Modulo Theories — it answers "does a satisfying assignment exist?" for logical formulas over integers, reals, bitvectors, arrays, etc.

**Why not:** Z3 reasons over abstract mathematical domains, not finite product catalogs. The question "enumerate all valid (hinge, plate) pairs from these specific JSON products" is unnatural in Z3. You'd encode each product as a set of integer constants and ask Z3 to find assignments — but Z3's strength is infinite domains and complex theories (nonlinear arithmetic, quantifiers), not "pick from a list." The model would be awkward and slower than direct evaluation.

Z3 would become relevant if the constraints involved complex mathematical relationships (e.g., "is there any door dimension where no hinge exists?") rather than evaluating known products against known requirements.

### 6.4 MiniZinc

A high-level constraint modeling language that compiles to multiple solver backends (Gecode, Chuffed, OR-Tools, etc.).

**Strengths:** Clean declarative syntax, solver-independent, good for prototyping constraint models.

**Why not:** Subprocess invocation overhead (shell out to `minizinc` binary) adds 50–500ms per solve. The data marshalling (Python objects → MiniZinc data → solve → parse output) is complex. Would need a parallel rule-trace evaluation pass. The abstraction doesn't pay off for 14 independent predicates.

**When it would fit:** If multi-family configuration models need to be developed and tested rapidly, MiniZinc's declarative syntax makes it easy to prototype different constraint formulations before committing to a CP-SAT implementation.

### 6.5 Rules-as-Data (JSON Rule Definitions)

Not a solver, but an architectural pattern already identified in the production roadmap. Simple predicates (equality, range, set membership) are defined as JSON; complex rules remain Python callables.

**Why it matters:** This is the highest-value improvement to the constraint system that doesn't involve adopting a solver. It enables rule versioning, non-developer editing, A/B testing, and database storage — all without adding a dependency or changing performance characteristics.

### 6.6 Progressive Domain Reduction (CPQ Pattern)

Borrowed from enterprise Configure-Price-Quote systems. As the user makes each selection in the conversational UI, propagate that choice to filter remaining valid options. The engine already does this via `_pre_filter_hinges()`.

**How to extend:** Build an API that accepts partial requirements and returns valid remaining values for unfilled fields. E.g., after selecting "frameless" + "full overlay", return only the overlay ranges, brands, and series that have at least one valid configuration. This is achievable with the current indexed approach — no solver needed.

### Comparison Matrix

| Approach | Solve Time | Explainability | All Solutions | Dependencies | Complexity | When to Use |
|----------|-----------|----------------|---------------|-------------|------------|-------------|
| **Indexed brute force** | <5ms | Full trace | Natural | None | Low | Now (2-variable pairwise) |
| **CP-SAT** | 20–100ms | Requires post-processing | Callback | ortools (150MB) | High | Multi-family coordination (6+ variables) |
| **python-constraint2** | 5–15ms | Manual | Built-in | Small | Medium | Never (strictly worse at current scale) |
| **Z3** | 50–200ms | Unsat core only | Awkward | z3-solver (100MB) | High | Mathematical constraint verification |
| **MiniZinc** | 100–500ms | None | Built-in | External binary | Medium | Rapid model prototyping |
| **Rules-as-data** | <5ms | Full trace | Natural | None | Low | Now (maintainability improvement) |
| **Progressive reduction** | <5ms | Full trace | N/A (guided) | None | Low | Now (conversational UX) |

---

## 7. CP-SAT Prototype Specification

Despite CP-SAT not being the right tool for the current problem, a working prototype has value for three reasons:

1. **Validates the assessment** — proves concretely that CP-SAT adds overhead without benefit at current scale
2. **Establishes the pattern** — when multi-family coordination arrives, the prototype provides a template for encoding product constraints
3. **Benchmarks** — provides hard numbers for solve time, model construction, and memory usage vs. the current approach

### 7.1 Prototype Scope

Build a CP-SAT model that mirrors the current engine's behavior for a single `CustomerRequirements` query. The prototype must:

- Accept the same `CustomerRequirements` input
- Load the same `hinges.json` and `mounting_plates.json` data
- Enforce the same 13 hard constraints
- Find all valid (hinge, plate) configurations
- Sort by price then capacity
- Run alongside the current engine for comparison

The prototype does NOT need to:

- Replace the current engine
- Provide full rule tracing (this proves the explainability limitation)
- Handle `_best_failing` analysis
- Match the `solve_with_explanation()` output format

### 7.2 Model Design

#### Decision Variables

```python
model = cp_model.CpModel()

# Which hinge index (0..N-1) is selected
hinge_idx = model.NewIntVar(0, len(hinges) - 1, 'hinge')

# Which plate index (0..M-1) is selected
plate_idx = model.NewIntVar(0, len(plates) - 1, 'plate')
```

#### Encoding Product Attributes as Arrays

CP-SAT operates on integers, so product attributes must be encoded as integer arrays indexed by the decision variables:

```python
# Brand encoded as integer (Blum=0, Grass=1, Hafele=2)
brand_map = {"Blum": 0, "Grass": 1, "Hafele": 2}
hinge_brands = [brand_map[h.brand] for h in hinges]
plate_brands = [brand_map[p.brand] for p in plates]

# Series encoded as integer
series_map = {s: i for i, s in enumerate(all_series)}
hinge_series_ids = [series_map[h.series.value] for h in hinges]

# Numeric attributes used directly (scaled to integers where needed)
hinge_max_weight_kg_x10 = [int(h.max_door_weight_kg * 10) for h in hinges]
hinge_opening_angles = [h.opening_angle_deg for h in hinges]
hinge_boring_patterns = [h.boring_pattern_mm for h in hinges]
# ... etc for all attributes referenced by rules
```

#### Constraint Encoding (Rule by Rule)

**R001 — Brand Lock** (hinge brand == plate brand):
```python
hinge_brand = model.NewIntVar(0, max_brand, 'hinge_brand')
plate_brand = model.NewIntVar(0, max_brand, 'plate_brand')
model.AddElement(hinge_idx, hinge_brands, hinge_brand)
model.AddElement(plate_idx, plate_brands, plate_brand)
model.Add(hinge_brand == plate_brand)
```

**R002 — Series Compatibility** (hinge series in plate's compatible list):
```python
# Pre-compute allowed (hinge_idx, plate_idx) tuples
allowed_series_pairs = []
for hi, h in enumerate(hinges):
    for pi, p in enumerate(plates):
        if h.series.value in [s.value for s in p.compatible_hinge_series]:
            allowed_series_pairs.append((hi, pi))
model.AddAllowedAssignments([hinge_idx, plate_idx], allowed_series_pairs)
```

**R003 — Cabinet Type Match** (all three must agree):
```python
# Pre-filter: only allow hinges/plates matching req.cabinet_type
valid_hinge_indices = [i for i, h in enumerate(hinges)
                       if h.cabinet_type == req.cabinet_type]
valid_plate_indices = [i for i, p in enumerate(plates)
                       if p.cabinet_type == req.cabinet_type]
model.AddAllowedAssignments([hinge_idx], [(i,) for i in valid_hinge_indices])
model.AddAllowedAssignments([plate_idx], [(i,) for i in valid_plate_indices])
```

**R004 — Overlay in Range** (desired overlay within plate's achievable range):
```python
# Pre-compute which plates support the required overlay
valid_overlay_plates = []
for pi, p in enumerate(plates):
    overlay_spec = p.overlay_range_mm.get(app_key)
    if overlay_spec is True:  # inset
        valid_overlay_plates.append(pi)
    elif overlay_spec and overlay_spec[0] <= req.desired_overlay_mm <= overlay_spec[1]:
        valid_overlay_plates.append(pi)
model.AddAllowedAssignments([plate_idx], [(pi,) for pi in valid_overlay_plates])
```

**R006 — Door Thickness** (within hinge range):
```python
valid_thickness_hinges = [i for i, h in enumerate(hinges)
                          if h.door_thickness_range_mm.contains(req.door_thickness_mm)]
model.AddAllowedAssignments([hinge_idx], [(i,) for i in valid_thickness_hinges])
```

**R007 — Door Weight** (weight ≤ capacity × num_hinges):
```python
num_hinges = hinges_per_door(req.door_height_mm)
valid_weight_hinges = [i for i, h in enumerate(hinges)
                       if req.door_weight_kg <= h.max_door_weight_kg * num_hinges]
model.AddAllowedAssignments([hinge_idx], [(i,) for i in valid_weight_hinges])
```

**R009, R011, R012, R013, R014, R015** — Similar pattern: pre-compute valid indices, add as allowed assignments.

**PREF — Soft Close** (preference, not hard constraint):
```python
# Encode as objective bonus, not a constraint
has_soft_close = [int(h.soft_close) for h in hinges]
sc_var = model.NewIntVar(0, 1, 'soft_close')
model.AddElement(hinge_idx, has_soft_close, sc_var)
# Add to objective with small weight if req.soft_close
```

#### Objective Function

```python
# Price minimization (scale to cents to keep integer)
hinge_prices_cents = [int((h.price_usd or 9999) * 100) for h in hinges]
plate_prices_cents = [int((p.price_usd or 9999) * 100) for p in plates]

h_price = model.NewIntVar(0, 999900, 'h_price')
p_price = model.NewIntVar(0, 999900, 'p_price')
model.AddElement(hinge_idx, hinge_prices_cents, h_price)
model.AddElement(plate_idx, plate_prices_cents, p_price)

total_price = model.NewIntVar(0, 1999800, 'total')
model.Add(total_price == h_price * num_hinges + p_price)

model.Minimize(total_price)
```

#### Solution Enumeration

```python
class SolutionCollector(cp_model.CpSolverSolutionCallback):
    def __init__(self, hinge_idx, plate_idx, hinges, plates):
        super().__init__()
        self._hinge_idx = hinge_idx
        self._plate_idx = plate_idx
        self._hinges = hinges
        self._plates = plates
        self.solutions = []

    def on_solution_callback(self):
        hi = self.Value(self._hinge_idx)
        pi = self.Value(self._plate_idx)
        self.solutions.append((self._hinges[hi], self._plates[pi]))

solver = cp_model.CpSolver()
solver.parameters.enumerate_all_solutions = True
collector = SolutionCollector(hinge_idx, plate_idx, hinges, plates)
status = solver.Solve(model, collector)
```

### 7.3 Implementation Plan

| Step | Task | Effort |
|------|------|--------|
| 1 | Add `ortools` to `requirements.txt` | Minutes |
| 2 | Create `engine/cpsat_solver.py` with `CpSatHingeEngine` class | 2–3 hours |
| 3 | Implement model construction with all 14 rules encoded | Core of step 2 |
| 4 | Implement `SolutionCollector` callback | Included in step 2 |
| 5 | Create `engine/tests/test_cpsat.py` — run same 7 customer scenarios, assert identical results to current engine | 1–2 hours |
| 6 | Add benchmark comparing solve times | 1 hour |
| 7 | Document findings in results section of this document | 1 hour |

### 7.4 File Structure

```
engine/
├── cpsat_solver.py          # CpSatHingeEngine class
├── tests/
│   ├── test_engine.py       # Existing tests
│   └── test_cpsat.py        # CP-SAT comparison tests
```

### 7.5 Expected Outcomes

| Metric | Current Engine | CP-SAT Prototype (Expected) |
|--------|---------------|----------------------------|
| Solve time (typical query) | 1–5ms | 15–80ms |
| Model construction time | N/A | 5–20ms |
| Solution correctness | Baseline | Identical (validated by tests) |
| Memory usage | ~1MB (product data) | ~5–10MB (ortools overhead) |
| All-solutions enumeration | Built-in | Callback-based, slower |
| Rule trace output | Full | Not available (requires separate pass) |
| Package size | 0 (pure Python) | ~150MB (ortools wheel) |

### 7.6 Prototype API

```python
class CpSatHingeEngine:
    """CP-SAT based solver for comparison with HingeConstraintEngine."""

    def __init__(self, hinges: list[ConcealedHinge], plates: list[MountingPlate]):
        """Pre-compute attribute arrays for model construction."""

    def solve(self, req: CustomerRequirements) -> list[tuple[ConcealedHinge, MountingPlate]]:
        """Find all valid (hinge, plate) pairs using CP-SAT.

        Returns pairs sorted by price (ascending), then weight capacity (descending).
        Does NOT include rule traces — this is a known limitation of the CP-SAT approach.
        """

    def solve_optimal(self, req: CustomerRequirements) -> tuple[ConcealedHinge, MountingPlate] | None:
        """Find the single lowest-price valid configuration.

        This is where CP-SAT would shine if the search space were larger —
        finding optimal without enumerating all solutions.
        """
```

---

## 8. Conclusions

### For the current system

Do not adopt CP-SAT. The hinge engine is a small pairwise filter with independent predicates. The indexed brute-force approach is correct, fast (<5ms), fully explainable, and has zero dependencies. The highest-value near-term improvements are **rules-as-data** and **progressive domain reduction** — neither requires a solver.

### For multi-family configuration (Phase 4+)

Adopt CP-SAT as a **coordination layer** above per-family engines, not as a replacement for them. Each family keeps its own explainable constraint engine. CP-SAT handles cross-family constraints and global optimization. This preserves explainability, enables incremental adoption, and puts CP-SAT where it adds genuine value.

### Why not start with CP-SAT now

Starting with CP-SAT today trades certain complexity for uncertain benefit. The cross-family constraints that would justify CP-SAT don't exist yet — they haven't been identified, let alone validated against manufacturer specifications. The 2-variable hinge model doesn't exercise CP-SAT's strengths and would be substantially rewritten when real cross-family interactions are discovered. The right trigger is the first concrete cross-family constraint, not anticipation of one.

### The prototype

Build it anyway (~4–6 hours). It provides concrete benchmarks for stakeholder conversations, establishes the encoding pattern for future use, and validates this assessment with hard numbers rather than theory.

---

## Relationship to Other Research

- **Production tooling research** (`production-tooling-research.md`) — independently concluded CSP solvers are not warranted at current scale; this document provides the detailed technical rationale and future architecture
- **Knowledge graph research** (`knowledge-graph-research.md`) — similar conclusion: not warranted now, revisit at Phase 4 for cross-family relationship traversal
- **Constraint engine design** (`constraint-engine-design.md`) — the "products are facts, compatibility is derived" principle is preserved by the hybrid architecture; CP-SAT derives cross-family compatibility at query time rather than materialising it
- **Production roadmap** (`production-roadmap.md`) — Phase 4 (multi-family expansion) is the identified trigger for CP-SAT adoption
