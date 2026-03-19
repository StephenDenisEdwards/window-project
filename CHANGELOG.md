# Changelog

All notable changes to the Window constraint engine are documented here, grouped by feature area.

## 2026-03-19

### Architecture
- **Solver approach recommendation** — Documented decision to adopt flat N-candidate solver as the default production solver (ADR-001). Staged pipeline retained as optimisation path.
- **Solver architecture diagrams** — Added Mermaid flowcharts comparing V1 paired, V2 flat N-candidate, and V2 staged pipeline solvers
- **Documentation restructure** — Migrated from flat `documents/` to structured `documentation/docs/` with architecture, design, research, planning, operations, and guides categories

### Docs
- Added plain-English appendices explaining paired vs N-candidate solvers and stage decomposition trade-offs
- Renamed demo notebooks with `v1_`/`v2_` prefixes to clarify which engine they reference
- Updated README to reflect multi-family architecture, all demo notebooks, and full documentation index
- Added CONTRIBUTING.md and CHANGELOG.md

## 2026-03-17

### Features
- **LED rules performance** — Fixed LED lighting rule evaluation and documented stage decomposition trade-offs
- **Staged pipeline limitations** — Documented when staged evaluation negates its performance benefit

## 2026-03-14

### Features
- **Multi-family prototype** — Added `engine_v2/` with generic `ConstraintSolver`, `NCandidateSolver`, and `StagedPipelineSolver`
- **LED lighting family** — Prototyped 3-candidate solver (light bar + driver + dimmer) with 9 constraint rules
- **Drawer slide family** — Prototyped single-product solver skeleton
- **Concealed hinge family** — Ported hinge engine to generic framework for validation
- **Brand lock made conditional** — `brand_lock` flag on `CustomerRequirements` controls R001 (default `True`)

### Docs
- Added multi-family architecture evaluation (generic vs independent engines)
- Added competitive landscape research
- Added constraint-based vs rules-based comparison with Tacton deep dive
- Added CLAUDE.md for Claude Code onboarding context

## 2026-03-10

### Docs
- Added CP-SAT and knowledge graph research documents
- Added catalog integration documentation covering three data tiers and ingestion pipeline

## 2026-03-07

### Features
- **Production constraint engine** — Modular `engine_v1/` package with Pydantic v2 models, 14 constraint rules, indexed pre-filtering, and full rule tracing
- **70+ tests** — Including 7 customer scenarios (standard kitchen, corner cabinet, tall pantry, adjacent doors, constraint violations)
- **Demo notebook** — Interactive walkthrough covering catalog overview, constraint traces, compatibility matrix, failure analysis, and interactive explorer

### Architecture
- Pydantic v2 domain models with full enum typing
- Rules extracted to standalone functions in `rules.py` with `RULES` list
- `ManufacturerProduct` base class with `DistributorSKU` overlay for SKU identity
- `RuleResult` with category, values_compared, and remediation
- Indexed pre-filtering on hinges (brand, cabinet type, application)
- R010 (wide-angle derating) removed — uses manufacturer's published ratings directly

### Docs
- Constraint engine design document with full rule reference
- Production roadmap (phased plan from PoC to production)
- Domain model documentation
- Data extraction evaluation
- Production tooling research
