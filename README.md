# Window — Cabinet Hardware Constraint Engine

A deterministic constraint reasoning engine for cabinet hardware compatibility. Given customer requirements (cabinet type, door dimensions, application, brand preference), the engine evaluates all valid product combinations and returns ranked configurations with full explainability traces.

This is the reasoning layer of a three-tier architecture designed for multi-brand cabinet hardware distribution:

1. **Knowledge foundation** — product catalogs, compatibility data, pricing feeds
2. **Constraint reasoning engine** — deterministic solver that guarantees every recommendation is provably correct (this repo)
3. **Conversational layer** — LLM-powered interface for guided discovery and professional fast-track workflows

The recommended integration pattern is deterministic-first: preprocess inputs with rules and database lookups, retrieve relevant knowledge, generate via LLM where needed, then validate all outputs through the constraint engine. The engine acts as both the primary recommendation source and the safety net — no recommendation reaches the user without passing all constraints.

## Architecture

The project contains two engine implementations:

**`engine_v1/`** — The production constraint engine for concealed hinges (the first and most complete product family). Exhaustive search over pre-filtered hinge × plate pairs, evaluating 14 constraint rules per pair. Every evaluation produces a full rule trace (pass/fail, values compared, remediation suggestions) so the conversational layer can explain *why* a configuration was recommended or *why* it failed.

**`engine_v2/`** — Experimental multi-family prototype. A generic constraint solver framework with pluggable rules and product families. Supports single-product, paired-product, and N-candidate families through a unified solver architecture. Three product families prototyped (concealed hinges, drawer slides, LED lighting).

### Solver approaches

Three solver approaches have been prototyped and evaluated:

| Approach | Implementation | Best for |
|---|---|---|
| **V1 Paired** | `engine_v1/solver.py` | 2-product families (hinge + plate) with indexed pre-filtering |
| **V2 Flat N-Candidate** | `engine_v2/core/solver_n.py` | Any number of product roles — the recommended default |
| **V2 Staged Pipeline** | `engine_v2/core/solver_staged.py` | Large catalogs with clearly layered constraints (optimisation path) |

**Decision:** The flat N-candidate solver is the recommended production approach. It handles single-product (N=1), paired (N=2), and multi-product (N=3+) families with a single algorithm. The staged pipeline is retained as a documented optimisation path for when catalog sizes exceed performance requirements. See [ADR-001](documentation/docs/architecture/decisions/ADR-001-flat-n-candidate-solver.md) for the full rationale and [Solver Architecture Diagrams](documentation/docs/architecture/solver-architecture-diagrams.md) for visual flowcharts.

### V1 hinge engine flow

```
CustomerRequirements
    |
    v
Pre-filter hinges (indexed by application, cabinet type, brand)
    |
    v
For each filtered hinge x all plates:
    Evaluate all constraint rules -> RuleResults -> Configuration
    |
    v
Discard invalid configurations
    |
    v
Sort by price ASC, capacity DESC
    |
    v
Ranked list of valid configurations with full constraint traces
```

Current catalog: 53 hinges and 55 mounting plates across Blum, Grass, and Hafele, covering frameless and face-frame cabinets, full/half/inset overlay, 95-170 degree opening angles.

## Project Structure

```
engine_v1/                         # Production constraint engine (Python 3.13, Pydantic v2)
├── models.py                   # Domain models: ConcealedHinge, MountingPlate, Configuration
├── enums.py                    # 10 enumeration types (no raw strings)
├── rules.py                    # 14 constraint rules (single source of truth)
├── solver.py                   # HingeConstraintEngine: pre-filter, evaluate, rank
├── loader.py                   # JSON data adapter
└── tests/
    └── test_engine.py          # 70+ tests including 7 customer scenarios

engine_v2/                      # Experimental multi-family prototype
├── core/
│   ├── models.py               # Base classes: Product, Requirements, NConfiguration
│   ├── solver.py               # Generic paired ConstraintSolver
│   ├── solver_n.py             # Flat N-candidate solver (recommended)
│   ├── solver_staged.py        # Staged pipeline solver (optimisation path)
│   ├── registry.py             # ProductFamilyRegistry
│   └── types.py                # Type aliases: NRuleFn, PreFilterFn, RankKeyFn
├── families/
│   ├── concealed_hinge/        # Hinge family on generic framework
│   ├── drawer_slide/           # Drawer slide prototype (single-product)
│   └── led_lighting/           # LED lighting prototype (3-candidate: bar + driver + dimmer)
└── tests/
    ├── test_generic_solver.py  # Generic solver tests
    ├── test_n_candidate.py     # 26 N-candidate tests
    └── test_staged.py          # 25 staged tests + 5 cross-solver consistency

sample-data/                    # Product catalog JSON
├── hinges.json                 # 53 concealed hinges
└── mounting_plates.json        # 55 mounting plates

catalogs/                       # Source PDF catalogs (Wurth Baer, Grass)

demo/                           # Interactive Jupyter notebooks
├── v1/
│   └── v1_hinge_constraint_demo.ipynb          # V1 paired engine walkthrough
├── v2-n-candidate/
│   ├── v2_drawer_slide_demo.ipynb              # N=1 drawer slides
│   ├── v2_hinge_n_candidate_demo.ipynb         # N=2 hinges on N-candidate solver
│   └── v2_n_candidate_demo.ipynb               # N=3 LED lighting
└── v2-staged-pipeline/
    └── v2_staged_pipeline_demo.ipynb           # Staged pipeline benchmarks

documentation/docs/             # Structured documentation
├── index.md                    # Central navigation hub
├── architecture/
│   ├── multi-family-architecture.md    # Generic vs independent engines, N-candidate vs staged
│   ├── solver-architecture-diagrams.md # Mermaid flowcharts for all three approaches
│   └── decisions/
│       ├── README.md                   # ADR index
│       └── ADR-001-flat-n-candidate-solver.md  # Solver approach decision
├── design/
│   ├── DESIGN-constraint-engine.md     # Core rules reference and architecture
│   └── DESIGN-domain-model.md          # Domain model design
├── planning/
│   ├── INDEX.md                        # Priority queue and status
│   ├── PLAN-production-roadmap.md      # Phased plan (PostgreSQL, FastAPI, rules-as-data)
│   └── PLAN-catalog-integration.md     # Data tiers, ingestion pipeline, known gaps
├── research/                           # Technology evaluations, market research
│   ├── README.md                       # Research index
│   └── *.md                            # 8 research documents
├── operations/                         # User-facing: setup, configuration
└── guides/
    └── documentation-guide.md          # Naming conventions, templates, indexes
```

## Constraint Rules

14 rules across 3 categories, defined in `engine_v1/rules.py`:

**Hard constraints** — brand lock (conditional, controlled by `brand_lock` flag), series compatibility, cabinet type match, overlay range, inset support, door thickness, door weight capacity, boring pattern, face frame overlay, adjacent door clearance, corner cabinet angle, mounting method compatibility, cup depth.

**Derived values** — hinge count from door height (2-5 hinges based on thresholds).

**Preferences** — soft-close (non-blocking).

Every rule returns structured results with rule ID, category, detail, compared values, and remediation suggestions. See [Constraint Engine Design](documentation/docs/design/DESIGN-constraint-engine.md) for full rule reference.

## Setup

```bash
pip install -r requirements.txt

# Run V1 engine tests (70+ tests)
pytest engine_v1/tests/ -v

# Run V2 engine tests (experimental)
pytest engine_v2/tests/ -v
```

## Demo Notebooks

Three interactive Jupyter notebooks demonstrate the constraint engine approaches:

### V1 Hinge Constraint Demo

`demo/v1/v1_hinge_constraint_demo.ipynb` — walkthrough of the production hinge engine:

1. **Catalog overview** — all hinges and mounting plates across Blum, Grass, and Hafele with product images
2. **Constraint rules** — the 14 rules the engine enforces and their categories
3. **Customer scenarios** — five real-world selection problems (standard kitchen, corner cabinet, tall pantry, adjacent doors, and a deliberate constraint violation)
4. **Constraint trace deep dive** — full rule-by-rule pass/fail trace showing exactly why a configuration was recommended
5. **Compatibility matrix** — exhaustive evaluation of all 2,915 hinge × plate pairs
6. **Price vs capacity analysis** — trade-offs across valid configurations
7. **Failure analysis** — how the engine explains why no solution exists and identifies the closest match
8. **Interactive explorer** — modify `CustomerRequirements` values and re-run to test your own scenarios

### V2 N-Candidate Demo

`demo/v2-n-candidate/v2_n_candidate_demo.ipynb` — flat N-candidate solver with LED lighting (bar + driver + dimmer):

- Cartesian product evaluation of all triples
- Solving scenarios, failure analysis, and closest-match identification
- Exhaustive evaluation matrix and failure breakdown by rule
- Scaling projections and benchmarks at increasing catalog sizes
- Redundancy analysis showing wasted work from unpruned invalid pairs

### V2 Staged Pipeline Demo

`demo/v2-staged-pipeline/v2_staged_pipeline_demo.ipynb` — staged pipeline solver with the same LED lighting data:

- Stage-by-stage visualisation with pruning rates
- Head-to-head benchmark against the flat solver
- Pruning rate analysis at different catalog sizes
- Discussion of stage ordering, cross-cutting constraints, and when staging is worth it

### Running the notebooks

**VS Code (easiest option):**

1. Install [Python](https://www.python.org/downloads/) and ensure it's on your PATH
2. Open this project folder in VS Code
3. Install the [Jupyter extension](https://marketplace.visualstudio.com/items?itemName=ms-toolsai.jupyter) (Extensions panel, search "Jupyter")
4. Install dependencies: `pip install -r requirements.txt`
5. Open any notebook in `demo/` — VS Code will prompt you to select a Python kernel
6. Click **Run All** or step through cells individually

**Command line (Jupyter):**

```bash
pip install -r requirements.txt
jupyter notebook demo/v1/v1_hinge_constraint_demo.ipynb
```

### Dependencies

The notebooks require the packages listed in `requirements.txt`:

- `pydantic` (>=2.0) — domain models and validation
- `ipykernel` / `jupyter` — notebook runtime

No additional packages beyond the standard library are needed. The engine itself only depends on Pydantic.

## Key Design Decisions

- **Products are facts, compatibility is derived** — no hand-maintained compatibility lists. Whether a hinge + plate pair works is computed by rules at query time.
- **Flat N-candidate as default solver** — one algorithm handles single-product (N=1), paired (N=2), and multi-product (N=3+) families. Staged pipeline reserved as an optimisation path. See [ADR-001](documentation/docs/architecture/decisions/ADR-001-flat-n-candidate-solver.md).
- **No implicit derating** — manufacturer's published weight ratings are used directly. The engine does not silently reduce ratings for wide opening angles or other factors. If derating is needed, it must be added as an explicit rule. See [Constraint Engine Design](documentation/docs/design/DESIGN-constraint-engine.md#design-principles) for rationale.
- **Full enum typing** — every constrained string field is an enum. No silent failures from typos.
- **Full rule tracing** — every evaluation records rule ID, category, detail, and remediation. Supports the "always correct and explainable" value proposition.
- **Separate identity from pricing** — canonical manufacturer part numbers with per-distributor SKU and pricing overlays.
- **Brand lock is a rule, not an assumption** — cross-brand hinge + plate pairing is controlled by the `brand_lock` flag on `CustomerRequirements` (default `True`). When disabled, R001 passes automatically and the trace records it. Brand policy is a configurable constraint, not a hardcoded architectural decision.

## Production Roadmap

The engine is functional but not production-ready. Key remaining work:

- **Data store** — migrate from flat JSON to PostgreSQL (recommended) via SQLite stepping stone
- **Rules as data** — convert simple predicate rules to JSON definitions; keep complex rules as Python callables
- **API layer** — FastAPI service exposing solve/evaluate/product endpoints
- **Plate indexing** — plates are not indexed; hinge-only rule caching not implemented
- **Brand-specific parameters** — hinge count thresholds differ by brand but aren't parameterised
- **Rule versioning** — no record of which rules were active for past recommendations
- **SOC 2 compliance** — encryption, audit logging, RBAC, per-brand data isolation
- **Multi-brand deployment** — per-brand catalogs, pricing feeds, and rule parameters
- **13 product families** — engine currently covers concealed hinges only; drawer slides, lift systems, handles, locks, lighting to follow

See [Production Roadmap](documentation/docs/planning/PLAN-production-roadmap.md) for the full phased plan, [Production Tooling](documentation/docs/research/production-tooling-research.md) for technology evaluation, and [Catalog Integration](documentation/docs/planning/PLAN-catalog-integration.md) for data ingestion strategy.

## Documentation

Full documentation lives in `documentation/docs/` — see [index.md](documentation/docs/index.md) for the navigation hub.

| Category | Contents |
|---|---|
| [Architecture](documentation/docs/architecture/) | Multi-family architecture, solver diagrams, ADRs |
| [Design](documentation/docs/design/) | Constraint engine design, domain model |
| [Planning](documentation/docs/planning/INDEX.md) | Production roadmap, catalog integration |
| [Research](documentation/docs/research/README.md) | Technology evaluations, market research (8 documents) |
| [Guides](documentation/docs/guides/) | Documentation guide, naming conventions |
