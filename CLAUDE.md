# CLAUDE.md — Project Context for AI Assistants

## Project

**window-project** — A deterministic constraint reasoning engine for cabinet hardware compatibility. Given customer requirements (cabinet type, door dimensions, application, brand), the engine evaluates all valid product combinations and returns ranked configurations with full explainability traces.

## Language & Layout

- **Python 3.14**, Pydantic v2
- Production engine: `engine_v1/`
- Experimental multi-family prototype: `engine_v2/`
- Product catalog: `sample-data/`
- Demo notebooks: `demo/`
- Documentation: `documentation/docs/`

## Key Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run V1 engine tests (70+ tests)
pytest engine_v1/tests/test_engine.py -v

# Run specific test categories
python -m pytest engine_v1/tests/ -k scenario       # 7 customer scenarios
python -m pytest engine_v1/tests/ -k "enum"          # enum validation
python -m pytest engine_v1/tests/ -k "prefilter"     # pre-filter verification

# Run V2 engine tests (experimental multi-family prototype)
pytest engine_v2/tests/ -v

# Launch web demo (all three families)
python -m uvicorn demo.app:app --reload
# Open http://localhost:8000
```

## Architecture Overview

**engine_v1/** — Production constraint engine for concealed hinges:
- `enums.py` — 11 enumeration types. Every constrained string field is an enum; no typos silently fail.
- `models.py` — Domain models: `ConcealedHinge`, `MountingPlate`, `CustomerRequirements`, `Configuration`, `RuleResult`. Products use canonical manufacturer part numbers with per-distributor SKU overlays (`DistributorSKU`).
- `rules.py` — 14 constraint rules (single source of truth). Each rule returns a `RuleResult` with pass/fail, detail, values compared, and remediation.
- `solver.py` — `HingeConstraintEngine`: pre-filters hinges via brand/cabinet-type/application indexes, evaluates all hinge×plate pairs against rules, returns valid configurations ranked by price ASC then capacity DESC.
- `loader.py` — Converts PoC JSON format from `sample-data/` into production Pydantic models.

**engine_v2/** — Experimental multi-family prototype (not production-ready):
- Generic `ConstraintSolver` with pluggable rules and `FamilyRegistry`
- `NCandidateSolver` — flat N-candidate solver (recommended default, ADR-001)
- `StagedPipelineSolver` — staged pipeline solver (optimisation path)
- Three prototype families: `concealed_hinge`, `drawer_slide`, `led_lighting`

### Key Files

| File | Purpose |
|------|---------|
| `engine_v1/solver.py` | Production hinge constraint engine |
| `engine_v1/rules.py` | 14 constraint rules (single source of truth) |
| `engine_v1/models.py` | Domain models (Pydantic v2) |
| `engine_v2/core/solver_n.py` | Flat N-candidate solver (recommended) |
| `engine_v2/core/solver_staged.py` | Staged pipeline solver (optimisation path) |
| `engine_v2/families/led_lighting/` | 3-candidate LED lighting prototype |

## Conventions

### Commit Messages

Use prefix style: `feat:`, `fix:`, `docs:`, `refactor:`, `chore:`, `test:`

### Code Style

- Type hints on all public functions
- `from __future__ import annotations` in every module
- Pydantic v2 for all domain models
- Every constrained string field must be an enum

### Testing

- V1 tests in `engine_v1/tests/` using pytest
- V2 tests in `engine_v2/tests/` using pytest
- Name test files `test_<module>.py`

## Key Design Decisions

- **Products are facts, compatibility is derived** — No hand-maintained compatibility lists; all compatibility computed at query time via rules.
- **Flat N-candidate as default solver** — One algorithm handles N=1 (single), N=2 (paired), N=3+ (multi-product) families. Staged pipeline reserved as optimisation path (ADR-001).
- **Brand lock is configurable** — `brand_lock` flag on `CustomerRequirements` controls R001; defaults to True.
- **No implicit derating** — Published manufacturer weight ratings used directly. Wide opening angles do NOT reduce capacity. If derating is needed, add an explicit rule.
- **Full rule tracing** — Every evaluation produces a complete trace: rule ID, category, detail, values compared, remediation suggestions.

## What NOT to Do

- Do not add dependencies without checking `requirements.txt` first
- Do not use `git add -A` — stage specific files only
- Do not skip pre-commit hooks (`--no-verify`)
- Do not commit `.env` files or secrets

## Rule Reference (rules.py)

Hard constraints: R001 brand lock, R002 series compatibility, R003 cabinet type match, R004 overlay in range, R005 inset support, R006 door thickness, R007 door weight, R009 boring pattern, R011 face frame overlay, R012 adjacent door clearance, R013 corner cabinet angle, R014 mounting method, R015 cup depth. Derived: R008 hinges per door. Preference: PREF soft close.

## Documentation

Full docs in `documentation/docs/`:
- `architecture/` — Multi-family architecture + ADRs
- `design/` — Constraint engine design, domain model
- `planning/` — Production roadmap, catalog integration
- `research/` — Technology evaluations, market research
- `guides/` — Documentation guide
- See [Documentation Guide](documentation/docs/guides/documentation-guide.md) for naming conventions and templates
