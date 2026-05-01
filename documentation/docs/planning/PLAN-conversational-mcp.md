# Plan: Conversational MCP Server (`window`)

Phased delivery plan for the conversational layer that exposes the constraint engine, catalogue graph, and document search to the [Micro-X agent loop](https://github.com/StephenDenisEdwards/micro-x-agent-loop-python) via a single MCP server.

**Status:** Phase 1 ready to start. Phases 2–4 sequenced behind their dependencies (vector store, catalogue graph, `engine_v2` family registry).

**Authoritative design:** [DESIGN-conversational-integration.md](../design/DESIGN-conversational-integration.md). Authoritative decision: [ADR-003](../architecture/decisions/ADR-003-conversational-via-microx-mcp.md).

---

## Overview

The `window` MCP server lives at `mcp_servers/python/window/` in this repository. It is registered with Micro-X via `config.json` like any other MCP server — Micro-X handles the agent loop, routing, parallel tool execution, session memory, and cost controls. This plan is just about the tool surface.

```
window-project/
└── mcp_servers/
    └── python/
        └── window/
            ├── pyproject.toml
            ├── README.md
            ├── main.py                    ← FastMCP entry point
            ├── tools/
            │   ├── __init__.py
            │   ├── solve.py               ← Phase 1
            │   ├── explain.py             ← Phase 1
            │   ├── inputs.py              ← Phase 1
            │   ├── docs.py                ← Phase 2
            │   └── graph.py               ← Phase 3
            └── tests/
                └── test_main.py
```

---

## Phase 1 — Engine tools (Weeks 1–2)

**Goal:** working conversational hinge configurator on Micro-X. No graph, no vector RAG.

### Deliverables

| Tool | Wraps | Status |
|---|---|---|
| `window.solve_configuration` | `engine_v1.HingeConstraintEngine.solve()` | New |
| `window.explain_rule` | `engine_v1.rules` registry + `RuleResult.remediation` | New |
| `window.list_required_inputs` | `CustomerRequirements.model_json_schema()` | New |

### Tasks

1. **Scaffold the MCP server** — `mcp_servers/python/window/{main.py, pyproject.toml, README.md}`. FastMCP entry point with three `@mcp.tool()` registrations.
2. **Wire to engine_v1** — load catalogue once at startup via `engine_v1.load_from_json`, hold a single `HingeConstraintEngine` instance, reuse across tool calls.
3. **Tool input/output contracts** — Pydantic models matching `CustomerRequirements`, `Configuration`, `RuleResult` exactly. Returns shaped for LLM consumption: top-N configurations, rejection summary, structured rule traces.
4. **System prompt contribution** — the deterministic-first guardrail text from [DESIGN §6.1](../design/DESIGN-conversational-integration.md). Returned via the MCP `instructions` capability so Micro-X folds it into the cached system prompt.
5. **Unit tests** — `tests/test_main.py` exercising each tool against the existing seven customer scenarios from `engine_v1/tests/test_engine.py`. Fast, no LLM in the loop.
6. **Micro-X registration** — add a `window` entry to the team Micro-X `config.json` documenting how to register this server.
7. **Smoke test** — run a scripted conversation through Micro-X end-to-end against the seven scenarios. Capture the api_payloads.jsonl trace as evidence.

### Acceptance criteria

- All seven scenarios in `engine_v1/tests/test_engine.py` reproducible via Micro-X conversational interaction.
- No compatibility claim appears in any reply without a corresponding `solve_configuration` tool call in the same session.
- Tool unit tests green; smoke conversation green.

### Dependencies

None. `engine_v1` is production-ready.

---

## Phase 2 — Documentation search (Week 3)

**Goal:** answer free-text installation and datasheet questions from existing manuals.

### Deliverables

| Tool | Wraps | Status |
|---|---|---|
| `window.search_documentation` | pgvector + embedding pipeline | New |

### Tasks

1. **Ingest existing PDFs** — manuals and datasheets in `sample-data/` get chunked, embedded, and stored. Use pgvector on the same PostgreSQL the catalogue will eventually live on (lower-risk than a dedicated store).
2. **Embedding pipeline** — small batched script, re-runnable. No live re-embedding loop in Phase 2.
3. **Tool input/output contract** — query string + optional product/doc-type filters → ranked chunks with citations.
4. **Tests** — golden Q&A pairs over the existing sample-data PDFs.

### Acceptance criteria

- "How do I install plate 175H7100?" returns the relevant manual section with citation.
- Out-of-scope queries return empty rather than fabricated answers.

### Dependencies

- PostgreSQL deployment (roadmap Phase 3 prerequisite).
- Decision on embedding model — defer to start of Phase 2.

---

## Phase 3 — Catalogue graph + graph tools (Weeks 4–8)

**Goal:** distributor lookup, lifecycle, cross-family relationships, and entity linking via the catalogue graph.

Aligned with Phase 4 of the [production roadmap](PLAN-production-roadmap.md) and the Phase 4 recommendation in [knowledge-graph-research.md](../research/knowledge-graph-research.md).

### Deliverables

| Tool | Wraps | Status |
|---|---|---|
| `window.graph_lookup_part` | Cypher entity-link template | New |
| `window.graph_distributors` | `DISTRIBUTED_AS` traversal | New |
| `window.graph_alternatives` | `REPLACED_BY`, `BACKWARDS_COMPATIBLE_WITH` traversals | New |
| `window.graph_cross_family` | `CONFLICTS_AT_ANGLE`, `REQUIRES_CLEARANCE_FROM`, etc. | New |

### Tasks

1. **Apache AGE deployment** — graph extension on the existing PostgreSQL instance.
2. **ETL** — manufacturer JSON in `sample-data/` → nodes (Hinge, Plate, Brand, Distributor, Application, CabinetType) and edges (`MANUFACTURED_BY`, `SERIES_COMPATIBLE_WITH`, `DISTRIBUTED_AS`, `SUPPORTS_APPLICATION`, `FITS_FRAME_TYPE`, `REPLACED_BY`).
3. **Cypher query templates** — one per tool, parameterised. The MCP server holds these; the LLM does not write Cypher.
4. **Tool input/output contracts** — see [DESIGN §4.2](../design/DESIGN-conversational-integration.md).
5. **Cross-family ETL extension** — once `engine_v2` LED lighting and drawer slide families have data, extend ETL to populate cross-family edges.
6. **Golden conversation tests** — three multi-turn scenarios:
   - Würth Baer vs Würth Louis pricing comparison
   - Discontinued Blum part replacement chain
   - AVENTOS clearance check against current hinge selection

### Acceptance criteria

- All three multi-turn scenarios end-to-end green via Micro-X.
- Compatibility claims still gated by `solve_configuration` (graph tools never assert "yes this fits").
- Graph and engine SKU lists stay in sync (cross-checked in CI).

### Dependencies

- PostgreSQL with Apache AGE.
- Manufacturer/distributor data normalised per [PLAN-catalog-integration.md](PLAN-catalog-integration.md).

---

## Phase 4 — Multi-family solve (Weeks 8–14)

**Goal:** `solve_configuration` dispatches across all product families (`engine_v2` family registry), with cross-family constraints derived from graph traversals feeding back into the solve.

### Deliverables

- `window.solve_configuration` extended to accept a `family` parameter or auto-detect from requirements.
- Cross-family constraint propagation — when the user asks for hinges + slides + lighting in the same cabinet, graph cross-family edges become solver inputs.

### Tasks

1. **Dispatch layer** — replace the direct `HingeConstraintEngine` call with `engine_v2.FamilyRegistry.solve(family, requirements)`.
2. **Multi-family request shape** — extend the input schema to support multiple families in one call, returning configurations per family plus inter-family compatibility.
3. **Graph-derived constraints** — translate `CONFLICTS_AT_ANGLE` and similar edges into runtime rule inputs.
4. **Golden tests** — three-family compound scenario (hinges + AVENTOS + LED) end-to-end.

### Acceptance criteria

- Multi-family scenarios in `engine_v2/tests/` reproducible via Micro-X.
- Inter-family conflicts surfaced in the rule trace, not silently dropped.

### Dependencies

- `engine_v2` family registry stable.
- Phase 3 catalogue graph populated.

---

## Out of scope for this plan

- The Micro-X agent runtime itself (already exists).
- The HTTP/WebSocket API (Micro-X provides this; roadmap Phase 3.1 covers wiring).
- Authentication and multi-tenant scoping — open question in [DESIGN §12](../design/DESIGN-conversational-integration.md).

---

## Risks

| Risk | Mitigation |
|---|---|
| Tool input/output schemas churn after Phase 1 | Get `CustomerRequirements`, `Configuration`, `RuleResult` shapes right *first*; everything downstream depends on them. |
| LLM violates deterministic-first guardrail | Adversarial prompt tests in CI; tool schemas asymmetric so the LLM cannot extract compatibility from graph tools. |
| Graph and engine drift | CI cross-check: every part in the engine catalogue has a graph node, every graph node has an engine record. |
| Latency creep with multiple tool calls per turn | Micro-X parallel tool execution covers most cases; cache solve results on `hash(requirements)` for follow-up turns. |
| Provider outage | Micro-X provider pool + same-family fallback (Micro-X ADR-021). |

---

## Related

- [DESIGN-conversational-integration.md](../design/DESIGN-conversational-integration.md)
- [ADR-003: Conversational layer via Micro-X MCP server](../architecture/decisions/ADR-003-conversational-via-microx-mcp.md)
- [Production Roadmap](PLAN-production-roadmap.md) — Phases 3 and 4 alignment
- [Catalog Integration](PLAN-catalog-integration.md) — distributor data feeding the graph
- [Knowledge Graph Research](../research/knowledge-graph-research.md) — Phase 3 graph adoption rationale
- [Graph RAG for the Product Catalogue](../guides/graph-rag-for-product-catalogue.md) — Phase 3 graph tutorial
