# ADR-001: Flat N-Candidate Solver as Default Production Solver

## Status

Accepted

## Context

Three solver approaches have been prototyped and benchmarked:

| Approach | Implementation | Demo |
|---|---|---|
| V1 Paired Solver | `engine_v1/solver.py` | `demo/v1/v1_hinge_constraint_demo.ipynb` |
| V2 Flat N-Candidate | `engine_v2/core/solver_n.py` | `demo/v2-n-candidate/v2_n_candidate_demo.ipynb` |
| V2 Staged Pipeline | `engine_v2/core/solver_staged.py` | `demo/v2-staged-pipeline/v2_staged_pipeline_demo.ipynb` |

See [Solver Architecture Diagrams](../solver-architecture-diagrams.md) for visual flowcharts of each approach and [Multi-Family Architecture](../multi-family-architecture.md) for the full architectural evaluation.

## Decision

Adopt the flat N-candidate solver as the single production solver. Keep the staged pipeline as a documented optimisation path, not the default.

---

## The recommendation

### Use one generic solver based on the flat N-candidate pattern

The flat N-candidate solver (`NCandidateSolver`) handles all three product family shapes with a single algorithm:

| Shape | Families | How it works |
|---|---|---|
| Single product | 8 of 13 families (drawer slides, handles, shelf supports, door dampers, catches/latches, flap stays, connecting fittings, lift systems) | Filter A against requirements (N=1) |
| Paired products | 3-4 families (concealed hinges, locks, drawer systems, closet systems) | Pre-filter + A x B (N=2) |
| N-candidate | 2-3 families (LED lighting, possibly closet systems, possibly drawer systems) | Pre-filter + full Cartesian product (N=3+) |

These are the same algorithm at different values of N. A single product family is N=1 (no Cartesian product, just filter). A paired family is N=2 (what the V1 hinge engine does today). A triple-product family is N=3 (what the flat N-candidate solver was built for). There is no architectural discontinuity between them.

### Do not adopt the staged pipeline as the default

The staged pipeline solver is well-built, tested (25 tests + 5 cross-solver consistency tests), and delivers real performance gains at scale. But the evidence does not support adopting it as the default approach.

---

## Evidence

### 1. Most product families are simple

The Würth catalog covers 13 product families. Their constraint shapes are documented in `documentation/docs/architecture/multi-family-architecture.md`:

- **8 of 13 are single-product families** — drawer slides, handles/knobs, shelf supports, door dampers, catches/latches, flap stays, connecting fittings, lift systems. These are filtered against requirements with no pairing at all.
- **3-4 are paired** — concealed hinges, locks, drawer systems, closet systems. These use A x B evaluation, identical to what the V1 engine does today.
- **Only 2-3 might need 3+ products** — LED lighting (bar + driver + dimmer), possibly closet systems (upright + bracket + shelf), possibly drawer systems (side + slide + front fixing).

The staged pipeline's pruning advantage only applies to the 3+ product families, which are a small minority. For single-product and paired families, the staged pipeline adds configuration complexity with no performance benefit.

### 2. Catalog sizes do not justify staged evaluation

Current and projected catalog sizes from `documentation/docs/planning/PLAN-catalog-integration.md` and the benchmark notebooks:

| Family | Current catalog | Projected full catalog | Combinations |
|---|---|---|---|
| Concealed hinges | 53 hinges x 55 plates | ~100 x ~80 | ~8,000 pairs |
| LED lighting | 5 bars x 4 drivers x 4 dimmers (prototype) | ~100 x ~40 x ~50 | ~200,000 triples |
| Drawer slides | Not yet built | ~50-100 products | ~100 (single, no pairing) |
| Handles/knobs | Not yet built | ~200-500 products | ~500 (single, no pairing) |

The V1 hinge engine solves 2,915 pairs x 14 rules in milliseconds. The flat N-candidate benchmark in `demo/v2-n-candidate/v2_n_candidate_demo.ipynb` shows 200,000 triples completing in under 500ms with early termination. These are well within acceptable API latency even without pruning.

The staged pipeline's performance advantage becomes meaningful at ~1M+ combinations. No product family in the Würth catalog is projected to reach that scale.

### 3. Correctness is the core product promise

From `CLAUDE.md`:

> *"Deterministic-first: no recommendation reaches the user without passing all constraint validation."*

The flat solver evaluates every combination against every rule. Nothing can slip through a pruning crack. The staged solver requires hand-curating which rules belong to which stage, and incorrect assignment silently drops valid results. From `documentation/docs/architecture/multi-family-architecture.md`:

> *"If a stage incorrectly prunes a valid combination (e.g., a rule is assigned to the wrong stage), the solver silently drops correct results."*

For a system whose core promise is provable correctness, exhaustive evaluation is a feature. The flat solver's simplicity means fewer opportunities for configuration errors, and its exhaustive evaluation means the full constraint space is always explored.

### 4. The existing documentation already recommends this

From `documentation/docs/architecture/multi-family-architecture.md` (line 396):

> *"Default to the flat N-candidate solver for correctness, simplicity, and easy configuration. If latency becomes a problem at catalog scale, optimize the flat solver first (pre-filtering, indexing) before introducing stage decomposition."*

> *"Reserve the staged pipeline for families where: (a) catalogs are large enough that the Cartesian product is measurably slow, (b) constraints are clearly layered across roles, and (c) the performance gain justifies the configuration and correctness burden."*

This recommendation is consistent with the V1 engine's design, which uses flat evaluation with indexed pre-filtering rather than staged pruning.

### 5. Failure analysis negates the staged advantage

When no valid configuration exists, both solvers must evaluate the full Cartesian product to find the closest match. From `documentation/docs/architecture/multi-family-architecture.md`:

> *"`_best_failing` negates the performance gain on failure. When no valid configuration exists, `solve_with_explanation` calls `_best_failing`, which evaluates the full Cartesian product with no pruning and no early termination to find the closest match."*

The no-solution case — often the most important for user experience, since it's where the engine explains *why* — gets no benefit from staged evaluation. The staged work is wasted.

### 6. The real bottlenecks are not the solver algorithm

The production roadmap (`documentation/docs/planning/PLAN-production-roadmap.md`) and catalog integration plan (`documentation/docs/planning/PLAN-catalog-integration.md`) identify the actual gates to scaling:

1. **The internal sales process document** — covers all 13 product families, not yet available. Without it, each new family requires from-scratch SME discovery.
2. **Data completeness** — overlay lookup tables, authoritative weight capacities, and Würth ERP pricing are all incomplete or missing.
3. **Infrastructure** — PostgreSQL migration, ingestion pipeline, FastAPI layer, SOC 2 controls.

The solver algorithm choice is irrelevant until these gates are cleared. Engineering effort is better spent on data architecture and the API layer than on solver optimisation for a problem that doesn't yet exist at scale.

---

## What this means in practice

### For new product families

When adding a new product family, the author:

1. Defines domain models (products + requirements) as Pydantic types
2. Writes constraint rules as functions with the standard `(candidates, requirements, derived) -> RuleResult` signature
3. Registers the family with an `NFamilyConfig` specifying roles, rules, pre-filters, and ranking
4. Writes golden scenario tests

No stage decomposition decisions. No rule-to-stage assignment. No ordering analysis. One flat rule list.

### For the V1 hinge engine

The V1 hinge engine (`engine_v1/solver.py`) remains the production implementation for concealed hinges. It is a specialised N=2 solver with indexed pre-filtering that has been validated with 70+ tests and 7 customer scenarios. There is no reason to rewrite it.

When the generic `NCandidateSolver` is promoted to production, the hinge family can be migrated to it (the V2 prototype already demonstrates this), but this is not urgent and should be driven by operational simplification, not solver architecture concerns.

### For the staged pipeline

The staged pipeline solver remains in the codebase as `engine_v2/core/solver_staged.py` with its full test suite. It is a valid optimisation for families that meet all three criteria:

1. **Catalog size** — the Cartesian product is measurably slow (>500ms) after pre-filtering and indexing
2. **Layered constraints** — constraints between roles are clearly separable into stages (e.g., LED lighting where bar-dimmer has no direct constraints)
3. **Justified complexity** — the performance gain outweighs the configuration and correctness burden

The trigger to adopt it would be: measured API latency exceeding requirements at real catalog scale, after pre-filtering and early termination have been tried first.

---

## Optimisation path (if needed)

If the flat solver becomes too slow for a specific family at production catalog scale, the optimisation sequence is:

1. **Pre-filtering** — indexed lookups to narrow candidates before the Cartesian product (already proven in V1 hinge engine)
2. **Early termination** — stop evaluating rules on first hard constraint failure (already implemented in `NCandidateSolver`)
3. **Hinge-only rule caching** — rules that depend only on one product + requirements (not the pairing) can be evaluated once and cached. Identified as remaining work in `documentation/docs/planning/PLAN-production-roadmap.md` Phase 1.5.
4. **Staged pipeline** — decompose into stages with inter-stage pruning. Only after steps 1-3 are insufficient.

This sequence is ordered by increasing complexity and decreasing certainty of benefit. Each step should be measured before proceeding to the next.

---

## Appendix: Plain-English Guide — Why "Flat N-Candidate" Covers Everything

### Products vs requirements: the key distinction

Every product family involves two kinds of things:

1. **Products** — items from the catalog that the engine selects. The contractor buys these.
2. **Requirements** — the contractor's situation (cabinet dimensions, door weight, preferences). These are fixed input.

The number of *products* determines the solver shape. Requirements can have dozens of fields — that doesn't make the solver more complex, because requirements don't vary during a solve.

**Concealed hinges — 2 products:**

The contractor knows their cabinet. They need the engine to pick a hinge and a plate.

| Thing | Product or requirement? |
|---|---|
| Hinge | Product (searched over) |
| Mounting plate | Product (searched over) |
| Door thickness, weight, height | Requirements (fixed) |
| Cabinet type, overlay, boring pattern | Requirements (fixed) |

The engine searches hinge × plate pairs. The cabinet/door is the problem definition, not a candidate.

**LED lighting — 3 products:**

The contractor knows their cabinet. They need the engine to pick a light bar, a driver, *and* a dimmer.

| Thing | Product or requirement? |
|---|---|
| Light bar | Product (searched over) |
| Driver | Product (searched over) |
| Dimmer | Product (searched over) |
| Cabinet length, dimming preference | Requirements (fixed) |

The driver can't be treated as a requirement because the contractor doesn't know which driver they need — that's what the engine solves. The engine searches bar × driver × dimmer triples.

**Drawer slides — 1 product:**

The contractor knows their cabinet depth and load needs. They need the engine to pick a slide.

| Thing | Product or requirement? |
|---|---|
| Drawer slide | Product (searched over) |
| Cabinet depth, load, extension type | Requirements (fixed) |

No pairing at all — just filter slides against requirements.

### Why one solver handles all three

These are all the same algorithm at different values of N:

- **N=1:** For each slide, evaluate rules → filter → rank
- **N=2:** For each hinge × plate, evaluate rules → filter → rank
- **N=3:** For each bar × driver × dimmer, evaluate rules → filter → rank

The flat N-candidate solver uses `candidates: dict[str, Product]` instead of fixed `(hinge, plate)` slots, so it handles N=1, N=2, and N=3 without any structural change. Rules access products by role name (`candidates["light_bar"]`) rather than by position (`primary`, `secondary`).

This is why we don't need a different solver architecture for different families — just a different N, different product types, and different rules.

---

## References

- `documentation/docs/architecture/multi-family-architecture.md` — Full evaluation of generic vs independent engines, flat vs staged solvers
- `documentation/docs/architecture/solver-architecture-diagrams.md` — Mermaid flowcharts comparing all three approaches
- `documentation/docs/planning/PLAN-production-roadmap.md` — Phased plan from PoC to production
- `documentation/docs/planning/PLAN-catalog-integration.md` — Data completeness, ingestion pipeline, known gaps
- `demo/v1/v1_hinge_constraint_demo.ipynb` — V1 paired solver demonstration
- `demo/v2-n-candidate/v2_n_candidate_demo.ipynb` — Flat N-candidate benchmarks and scaling analysis
- `demo/v2-staged-pipeline/v2_staged_pipeline_demo.ipynb` — Staged pipeline benchmarks and pruning analysis
