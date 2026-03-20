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
├── enums.py                    # 11 enumeration types (no raw strings)
├── rules.py                    # 14 constraint rules (single source of truth)
├── solver.py                   # HingeConstraintEngine: pre-filter, evaluate, rank
├── loader.py                   # JSON data adapter
└── tests/
    └── test_engine.py          # 70+ tests including 7 customer scenarios

engine_v2/                      # Multi-family N-candidate solver
├── core/
│   ├── models.py               # Base classes: Product, Requirements, NConfiguration
│   ├── solver_n.py             # Flat N-candidate solver (recommended)
│   ├── solver_staged.py        # Staged pipeline solver (optimisation path)
│   ├── solver.py               # Legacy paired solver
│   ├── registry.py             # FamilyRegistry
│   └── types.py                # Type aliases: NRuleFn, PreFilterFn, RankKeyFn
├── families/
│   ├── concealed_hinge/        # N=2: hinge + plate (real catalog, 14 rules)
│   │   ├── models.py, rules.py, config.py, loader.py
│   ├── drawer_slide/           # N=1: single product (synthetic, 8 rules)
│   │   ├── models.py, rules.py, config.py, loader.py, test_data.py
│   └── led_lighting/           # N=3: bar + driver + dimmer (synthetic, 9 rules)
│       ├── models.py, rules.py, config.py, loader.py, test_data.py
└── tests/
    ├── test_hinge_n_candidate.py   # 21 tests — real catalog, 5 customer scenarios
    ├── test_slide_n_candidate.py   # 16 tests — drawer slide scenarios
    ├── test_n_candidate.py         # 26 tests — LED lighting N-candidate
    └── test_staged.py              # 25 + 5 cross-solver consistency tests

sample-data/                    # Product catalog JSON (all families)
├── hinges.json                 # 53 concealed hinges (real catalog)
├── mounting_plates.json        # 55 mounting plates (real catalog)
├── light_bars.json             # 5 LED light bars (synthetic)
├── drivers.json                # 4 LED drivers (synthetic)
├── dimmers.json                # 4 LED dimmers (synthetic)
└── drawer_slides.json          # 4 drawer slides (synthetic)

catalogs/                       # Source PDF catalogs (Wurth Baer, Grass)

demo/                           # Web demo + Jupyter notebooks
├── app.py                      # FastAPI backend — all three families
├── index.html                  # Browser UI — forms, results, constraint traces
├── v1/                         # V1 dedicated hinge engine notebooks
├── v2-n-candidate/             # N-candidate solver notebooks (N=1, N=2, N=3)
└── v2-staged-pipeline/         # Staged pipeline solver notebooks

documentation/docs/             # Structured documentation
├── index.md                    # Central navigation hub
├── architecture/
│   ├── multi-family-architecture.md    # Generic vs independent engines, N-candidate vs staged
│   ├── solver-architecture-diagrams.md # Mermaid flowcharts for all three approaches
│   └── decisions/
│       └── ADR-001-flat-n-candidate-solver.md  # Solver approach decision
├── design/
│   ├── DESIGN-constraint-engine.md     # Core rules reference and architecture
│   ├── DESIGN-n-candidate-families.md  # All three families: data, rules, topology
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

### Prerequisites

- **Python 3.14+**

### Install dependencies

```bash
pip install -r requirements.txt
```

This installs: `pydantic` (v2), `pytest`, `ipykernel`, `jupyter`, `fastapi`, `uvicorn`.

### Run tests

```bash
# V1 engine tests (70+ tests)
pytest engine_v1/tests/ -v

# V2 engine tests (experimental)
pytest engine_v2/tests/ -v

# Specific test categories
pytest engine_v1/tests/ -k scenario       # 7 customer scenarios
pytest engine_v1/tests/ -k "enum"          # enum validation
pytest engine_v1/tests/ -k "prefilter"     # pre-filter verification
```

## Demos

### Web Demo

The fastest way to see the engine in action. All three product families in a browser UI — no notebooks, no kernel setup.

```bash
python -m uvicorn demo.app:app --reload
```

Open **http://localhost:8000**. Three tabs:

- **Concealed Hinges** (N=2) — 53 hinges × 55 plates, 14 rules, real catalog data
- **Drawer Slides** (N=1) — 4 slides, 8 rules, synthetic data
- **LED Lighting** (N=3) — 5 bars × 4 drivers × 4 dimmers, 9 rules, synthetic data

Select a scenario from the **examples dropdown** (4-6 per family, including impossible scenarios that demonstrate failure analysis), then **Solve**. Results show ranked configurations with expandable constraint traces (pass/fail per rule, remediation suggestions).

Works in GitHub Codespaces — click **Code → Codespaces → Create codespace**, then run the same commands in the terminal.

#### API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/` | GET | Web UI |
| `/api/families` | GET | List all families with JSON schemas |
| `/api/examples/{family}` | GET | Named example scenarios |
| `/api/solve/{family}` | POST | Solve and return ranked configurations with traces |

### Jupyter Notebooks

Interactive notebooks for exploring each engine and solver in depth. Each notebook is self-contained — it locates the project root automatically, loads the catalog data, and runs the solver.

#### Running the notebooks

```bash
pip install -r requirements.txt
jupyter notebook
```

Then open any notebook from the `demo/` folder in the Jupyter file browser.

> **VS Code / Codespaces**: open any `.ipynb` file directly — VS Code's built-in notebook editor will prompt you to select a Python kernel. Choose the environment where you ran `pip install`.

#### V1 — Production Hinge Engine

| Notebook | Description |
|---|---|
| [`demo/v1/v1_hinge_constraint_demo.ipynb`](demo/v1/v1_hinge_constraint_demo.ipynb) | Full walkthrough of the V1 concealed hinge engine. Loads 53 hinges × 55 plates from the real catalog. Covers: catalog overview with product images, all 14 constraint rules, 5 customer scenarios (standard kitchen, corner cabinet, tall pantry, adjacent doors, deliberate constraint violation), full constraint trace deep dive, exhaustive compatibility matrix, price vs capacity analysis, failure analysis with closest-match identification and remediation suggestions, and an interactive explorer cell for testing custom requirements. |

#### V2 — N-Candidate Solver (Flat)

The recommended solver approach. One algorithm handles any number of product roles.

| Notebook | N | Description |
|---|---|---|
| [`demo/v2-n-candidate/v2_drawer_slide_demo.ipynb`](demo/v2-n-candidate/v2_drawer_slide_demo.ipynb) | 1 | **Single-product family (drawer slides).** The simplest case — no Cartesian product, each slide evaluated individually against requirements. Shows catalog listing, three scenarios (standard kitchen drawer, heavy-duty 42kg, impossible shallow cabinet), and exhaustive evaluation of all slides against all 8 rules. |
| [`demo/v2-n-candidate/v2_hinge_n_candidate_demo.ipynb`](demo/v2-n-candidate/v2_hinge_n_candidate_demo.ipynb) | 2 | **Paired-product family (concealed hinges).** Same real catalog as V1 (53 hinges × 55 plates = 2,915 pairs, 14 rules) but solved through the generic N-candidate solver. 5 customer scenarios, full constraint traces, all valid configurations for open requirements, pre-filter impact analysis, and performance benchmarks. |
| [`demo/v2-n-candidate/v2_n_candidate_demo.ipynb`](demo/v2-n-candidate/v2_n_candidate_demo.ipynb) | 3 | **Triple-product family (LED lighting).** 5 light bars × 4 drivers × 4 dimmers, 9 rules. Covers: product catalog, solving with dimming requirements, failure analysis for impossible scenarios, exhaustive evaluation matrix with failure breakdown by rule, scaling projections from prototype to full catalog sizes (up to 200 × 80 × 100 = 1.6M combinations), synthetic data benchmarks, and quantitative redundancy analysis showing wasted work from the flat approach. |

#### V2 — Staged Pipeline Solver

An optimisation over the flat N-candidate approach that prunes invalid partial combinations between stages.

| Notebook | Description |
|---|---|
| [`demo/v2-staged-pipeline/v2_staged_pipeline_demo.ipynb`](demo/v2-staged-pipeline/v2_staged_pipeline_demo.ipynb) | **Staged pipeline vs flat N-candidate comparison.** Uses LED lighting (same data as above) split into two stages: Stage 1 evaluates bar × driver electrical compatibility (6 rules), prunes failures, then Stage 2 crosses survivors with dimmers for dimming compatibility (3 rules). Includes: stage-by-stage trace with pruning visualization, scenario solving (identical results to flat), failure analysis, head-to-head benchmarks at 5 catalog scales (up to 200 × 80 × 100), pruning rate analysis, and discussion of stage ordering and cross-cutting constraints. |

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
- **API layer** — demo FastAPI app exists (`demo/app.py`); production API needs auth, logging, product CRUD endpoints
- **Plate indexing** — plates are not indexed; hinge-only rule caching not implemented
- **Brand-specific parameters** — hinge count thresholds differ by brand but aren't parameterised
- **Rule versioning** — no record of which rules were active for past recommendations
- **SOC 2 compliance** — encryption, audit logging, RBAC, per-brand data isolation
- **Multi-brand deployment** — per-brand catalogs, pricing feeds, and rule parameters
- **13 product families** — three prototyped (concealed hinges, drawer slides, LED lighting); remaining 10 need the internal sales process document

See [Production Roadmap](documentation/docs/planning/PLAN-production-roadmap.md) for the full phased plan, [Production Tooling](documentation/docs/research/production-tooling-research.md) for technology evaluation, and [Catalog Integration](documentation/docs/planning/PLAN-catalog-integration.md) for data ingestion strategy.

## Documentation

Full documentation lives in `documentation/docs/` — see [index.md](documentation/docs/index.md) for the navigation hub.

| Category | Contents |
|---|---|
| [Architecture](documentation/docs/architecture/) | Multi-family architecture, solver diagrams, ADRs |
| [Design](documentation/docs/design/) | Constraint engine design, N-candidate families reference, domain model |
| [Planning](documentation/docs/planning/INDEX.md) | Production roadmap, catalog integration |
| [Research](documentation/docs/research/README.md) | Technology evaluations, market research (8 documents) |
| [Guides](documentation/docs/guides/) | Documentation guide, naming conventions |
