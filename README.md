# Window — Cabinet Hardware Constraint Engine

A deterministic constraint reasoning engine for cabinet hinge-to-mounting-plate compatibility. Given customer requirements (cabinet type, door dimensions, application, brand preference), the engine evaluates all valid hinge + plate combinations and returns ranked configurations with full explainability traces.

This is the reasoning layer of a three-tier architecture designed for multi-brand cabinet hardware distribution:

1. **Knowledge foundation** — product catalogs, compatibility data, pricing feeds
2. **Constraint reasoning engine** — deterministic solver that guarantees every recommendation is provably correct (this repo)
3. **Conversational layer** — LLM-powered interface for guided discovery and professional fast-track workflows

The recommended integration pattern is deterministic-first: preprocess inputs with rules and database lookups, retrieve relevant knowledge, generate via LLM where needed, then validate all outputs through the constraint engine. The engine acts as both the primary recommendation source and the safety net — no recommendation reaches the user without passing all constraints.

## Architecture

The engine does an exhaustive search over pre-filtered hinge x plate pairs, evaluating 14 constraint rules per pair. Every evaluation produces a full rule trace (pass/fail, values compared, remediation suggestions) so the conversational layer can explain *why* a configuration was recommended or *why* it failed.

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
engine/                     # Production constraint engine
├── models.py               # Domain models (Pydantic v2)
├── enums.py                # Enumeration types
├── rules.py                # Constraint rules (single source of truth)
├── solver.py               # Engine: solve / evaluate
├── loader.py               # JSON data adapter
└── tests/
    └── test_engine.py      # 70+ tests including 7 customer scenarios
sample-data/                # Product catalog JSON
├── hinges.json
└── mounting_plates.json
catalogs/                   # Source PDF catalogs (Wurth Baer, Grass)
demo/                       # Demo notebook
└── constraint_engine_demo.ipynb
documents/                 # Design docs, roadmap, research
├── constraint-engine-design.md
├── production-roadmap.md
├── production-tooling-research.md
├── domain-model.md
├── evaluation.md
├── data-extraction-evaluation.md
└── window-tech-brief-research-report.md
```

## Constraint Rules

14 rules across 3 categories, defined in `engine/rules.py`:

**Hard constraints** — brand lock (conditional, controlled by `brand_lock` flag), series compatibility, cabinet type match, overlay range, inset support, door thickness, door weight capacity, boring pattern, face frame overlay, adjacent door clearance, corner cabinet angle, mounting method compatibility, cup depth.

**Derived values** — hinge count from door height (2-5 hinges based on thresholds).

**Preferences** — soft-close (non-blocking).

Every rule returns structured results with rule ID, category, detail, compared values, and remediation suggestions. See `documents/constraint-engine-design.md` for full rule reference.

## Setup

```bash
pip install -r requirements.txt
pytest engine/tests/
```

## Demo Notebook

`demo/constraint_engine_demo.ipynb` is an interactive walkthrough of the constraint engine. It covers:

1. **Catalog overview** — all hinges and mounting plates across Blum, Grass, and Hafele with product images
2. **Constraint rules** — the 14 rules the engine enforces and their categories
3. **Customer scenarios** — five real-world selection problems (standard kitchen, corner cabinet, tall pantry, adjacent doors, and a deliberate constraint violation)
4. **Constraint trace deep dive** — full rule-by-rule pass/fail trace showing exactly why a configuration was recommended
5. **Compatibility matrix** — exhaustive evaluation of all 2,915 hinge × plate pairs
6. **Price vs capacity analysis** — trade-offs across valid configurations
7. **Failure analysis** — how the engine explains why no solution exists and identifies the closest match
8. **Interactive explorer** — modify `CustomerRequirements` values and re-run to test your own scenarios

### Running the notebook

**VS Code (easiest option):**

1. Install [Python](https://www.python.org/downloads/) and ensure it's on your PATH
2. Open this project folder in VS Code
3. Install the [Jupyter extension](https://marketplace.visualstudio.com/items?itemName=ms-toolsai.jupyter) (Extensions panel, search "Jupyter")
4. Install dependencies: `pip install -r requirements.txt`
5. Open `demo/constraint_engine_demo.ipynb` — VS Code will prompt you to select a Python kernel
6. Click **Run All** or step through cells individually

**Command line (Jupyter):**

```bash
pip install -r requirements.txt
jupyter notebook demo/constraint_engine_demo.ipynb
```

### Dependencies

The notebook requires the packages listed in `requirements.txt`:

- `pydantic` (>=2.0) — domain models and validation
- `ipykernel` / `jupyter` — notebook runtime

No additional packages beyond the standard library are needed. The engine itself only depends on Pydantic.

## Key Design Decisions

- **Products are facts, compatibility is derived** — no hand-maintained compatibility lists. Whether a hinge + plate pair works is computed by rules at query time.
- **No implicit derating** — manufacturer's published weight ratings are used directly. The engine does not silently reduce ratings for wide opening angles or other factors. If derating is needed, it must be added as an explicit rule. See [constraint-engine-design.md](documents/constraint-engine-design.md#design-principles) for rationale.
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

See `documents/production-roadmap.md` for the full phased plan and `documents/production-tooling-research.md` for technology evaluation.
