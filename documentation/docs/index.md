# Window — Constraint Engine Documentation

Central navigation hub for all project documentation.

## Architecture

- [Multi-Family Architecture](architecture/multi-family-architecture.md) — Generic vs independent engines, N-candidate vs staged, plain-English appendices
- [Solver Architecture Diagrams](architecture/solver-architecture-diagrams.md) — Mermaid flowcharts comparing all three solver approaches
- [Architecture Decision Records](architecture/decisions/README.md) — Index of all ADRs

## Design

- [Constraint Engine Design](design/DESIGN-constraint-engine.md) — Core rules reference, architecture, design principles
- [Domain Model](design/DESIGN-domain-model.md) — Product and configuration domain model

## Planning

- [Planning Index](planning/INDEX.md) — Prioritised work queue and plan status
- [Production Roadmap](planning/PLAN-production-roadmap.md) — Phased plan from PoC to production
- [Catalog Integration](planning/PLAN-catalog-integration.md) — Data tiers, ingestion pipeline, known gaps

## Research

- [Research Index](research/README.md) — All studies and evaluations
- [Constraint-Based vs Rules-Based](research/constraint-based-vs-rules-based.md) — Approach comparison with Tacton deep dive
- [Competitive Landscape](research/competitive-landscape.md) — Market research for cabinet hardware configuration

## Demo Notebooks

- `demo/v1_hinge_constraint_demo.ipynb` — V1 paired engine walkthrough (concealed hinges)
- `demo/v2_n_candidate_demo.ipynb` — Flat N-candidate benchmarks (LED lighting)
- `demo/v2_staged_pipeline_demo.ipynb` — Staged pipeline benchmarks and pruning analysis

## Document Map

```mermaid
graph TD
    INDEX[index.md] --> ARCH[Architecture]
    INDEX --> DESIGN[Design]
    INDEX --> PLAN[Planning]
    INDEX --> RESEARCH[Research]

    ARCH --> MFA[Multi-Family Architecture]
    ARCH --> DIAGRAMS[Solver Diagrams]
    ARCH --> ADR[ADR Index]
    ADR --> ADR001[ADR-001: Flat N-Candidate Solver]

    DESIGN --> CE[Constraint Engine Design]
    DESIGN --> DM[Domain Model]

    PLAN --> ROADMAP[Production Roadmap]
    PLAN --> CATALOG[Catalog Integration]

    RESEARCH --> CBVR[Constraint vs Rules]
    RESEARCH --> CPSAT[CP-SAT Research]
    RESEARCH --> KG[Knowledge Graph]
    RESEARCH --> COMP[Competitive Landscape]
    RESEARCH --> TOOLS[Production Tooling]
```
