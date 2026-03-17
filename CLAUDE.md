# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Cabinet hardware constraint engine that determines valid hinge + mounting plate combinations given customer requirements (cabinet type, door dimensions, application, brand). Returns ranked configurations with full explainability traces. Deterministic-first: no recommendation reaches the user without passing all constraint validation.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run all tests (70 tests)
pytest engine/tests/test_engine.py -v

# Run specific test categories
python -m pytest engine/tests/ -k scenario       # 7 customer scenarios
python -m pytest engine/tests/ -k "enum"          # enum validation
python -m pytest engine/tests/ -k "prefilter"     # pre-filter verification

# Run engine_v2 tests (experimental multi-family prototype)
pytest engine_v2/tests/ -v

# Launch demo notebook
jupyter notebook demo/constraint_engine_demo.ipynb
```

## Architecture

**engine/** — Production constraint engine (Python 3.13, Pydantic v2):
- `enums.py` — 10 enumeration types (ApplicationType, CabinetType, HingeSeries, etc.). Every constrained string field is an enum; no typos silently fail.
- `models.py` — Domain models: `ConcealedHinge`, `MountingPlate`, `CustomerRequirements`, `Configuration`, `RuleResult`. Products use canonical manufacturer part numbers with per-distributor SKU overlays (`DistributorSKU`).
- `rules.py` — 14 constraint rules (single source of truth). 10 hard constraints, 1 derived (hinge count from door height), 1 preference (soft-close). Each rule returns a `RuleResult` with pass/fail, detail, values compared, and remediation.
- `solver.py` — `HingeConstraintEngine`: pre-filters hinges via brand/cabinet-type/application indexes, evaluates all hinge×plate pairs against rules, returns valid configurations ranked by price ASC then capacity DESC.
- `loader.py` — Converts PoC JSON format from `sample-data/` into production Pydantic models.

**engine_v2/** — Experimental multi-family prototype (not production-ready):
- Generic `ConstraintSolver` with pluggable rules and `ProductFamilyRegistry`
- Three prototype families: `concealed_hinge`, `drawer_slide`, `led_lighting`
- Supports single-product families, N-candidate solvers, and staged evaluation

**sample-data/** — Product catalog: 53 hinges and 55 mounting plates (Blum, Grass, Hafele) in JSON.

**documents/** — Design specs and research (14 markdown files). Key references:
- `constraint-engine-design.md` — Core rules reference and architecture
- `multi-family-architecture.md` — Engine v2 design
- `production-roadmap.md` — Phased production plan (PostgreSQL, FastAPI, rules-as-data)

## Key Design Decisions

- **Products are facts, compatibility is derived** — No hand-maintained compatibility lists; all compatibility computed at query time via rules.
- **Brand lock is configurable** — `brand_lock` flag on `CustomerRequirements` controls R001; defaults to True.
- **No implicit derating** — Published manufacturer weight ratings used directly. Wide opening angles do NOT reduce capacity. If derating is needed, add an explicit rule.
- **Full rule tracing** — Every evaluation produces a complete trace: rule ID, category, detail, values compared, remediation suggestions.

## Rule Reference (rules.py)

Hard constraints: R001 brand lock, R002 series compatibility, R003 cabinet type match, R004 overlay in range, R005 inset support, R006 door thickness, R007 door weight, R009 boring pattern, R011 face frame overlay, R012 adjacent door clearance, R013 corner cabinet angle, R014 mounting method, R015 cup depth. Derived: R008 hinges per door. Preference: PREF soft close.
