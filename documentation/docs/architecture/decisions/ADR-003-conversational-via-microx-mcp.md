# ADR-003: Conversational Layer via Micro-X MCP Server with Deterministic-First Guardrail

## Status

Proposed

## Context

The work brief targets a three-layer architecture: knowledge foundation + reasoning engine + conversational layer. Phases 1–3 of the [production roadmap](../../planning/PLAN-production-roadmap.md) deliver the engine and an API in front of it. The conversational layer has been referenced but not designed.

A conversational interface needs to interpret free-text user requests, drive the constraint engine, look up catalogue facts (distributor SKUs, prices, replacements, cross-family relationships) the engine doesn't model, answer free-text product questions from manuals, and carry conversational state across follow-up turns. Critically, it must **never invent compatibility verdicts** — those must come from the engine's `RuleResult` trace, not from LLM training data, both for correctness and for SOC 2 explainability.

Three components have non-overlapping responsibilities and need to compose cleanly:

| Component | Owns the truth about |
|---|---|
| Constraint engine (`engine_v1`, future `engine_v2`) | Whether a configuration is valid and why |
| Catalogue graph (Phase 4, see [Knowledge Graph Research](../../research/knowledge-graph-research.md)) | Distributor SKUs, prices, lifecycle, cross-family relationships |
| Vector store over docs | Free-text manuals and datasheets |

Two architectural questions follow from this:

1. **Who orchestrates?** A bespoke Python pipeline that hardcodes the call sequence, or an LLM agent that picks tools per turn?
2. **How do we prevent hallucinated compatibility?** The system must structurally prevent the LLM from improvising "yes this fits" answers.

The team already maintains the [Micro-X agent loop](https://github.com/StephenDenisEdwards/micro-x-agent-loop-python) — a multi-provider, MCP-based, streaming agent runtime with semantic model routing (Micro-X ADR-020), parallel tool execution, layered cost reduction (Micro-X ADR-012), `ask_user` human-in-the-loop (Micro-X ADR-017), SQLite session memory, and an HTTP/WebSocket API server. The orchestration substrate already exists.

## Decision

**Use Micro-X as the conversational orchestrator.** Build a single MCP server, `window`, that exposes the constraint engine, the catalogue graph, and document search as tools registered with Micro-X. Enforce a **deterministic-first guardrail** in two places: (1) the system prompt requires that any compatibility claim be backed by a `window.solve_configuration` call in the same conversation, and (2) only `solve_configuration` returns compatibility verdicts — graph tools return relationships and metadata, never "yes this fits."

The tool surface is fixed and small:

**Engine tools:**
- `window.solve_configuration` — find valid configurations, return rule trace
- `window.explain_rule` — explain why a rule fired, return remediation
- `window.list_required_inputs` — JSON Schema of `CustomerRequirements`

**Graph tools (Phase 3):**
- `window.graph_lookup_part` — entity-link free text to canonical part numbers
- `window.graph_distributors` — distributors, SKUs, prices for a part
- `window.graph_alternatives` — replacements, supersessions, same-series
- `window.graph_cross_family` — cross-family interactions (clearance, shared zones)

**Documentation tool:**
- `window.search_documentation` — vector RAG over manuals and datasheets

Phasing:

1. **Phase 1 (Weeks 1–2):** Engine tools only. Wraps `engine_v1.HingeConstraintEngine`. Working conversational configurator on Micro-X, no graph, no vector RAG.
2. **Phase 2 (Week 3):** Add `search_documentation` over a vector store of existing manuals.
3. **Phase 3 (Weeks 4–8):** Catalogue graph (Apache AGE on PostgreSQL) + four graph tools. Aligned with roadmap Phase 4.
4. **Phase 4 (Weeks 8–14):** `solve_configuration` dispatches to `engine_v2` family registry. Cross-family constraints feed back from graph traversals.

Full engineering specification — tool schemas, sequence flows, failure modes, testing strategy, cost profile — is in [DESIGN-conversational-integration.md](../../design/DESIGN-conversational-integration.md).

## Consequences

### What becomes easier

- **No agent runtime to build.** Micro-X provides streaming, multi-provider LLMs, parallel tool execution, clarifying questions (`ask_user`), session memory, cost controls, and an HTTP/WebSocket API server. The integration work is the MCP server, not the agent.
- **Tool API is reusable.** The same `window` MCP server is callable from Micro-X's REPL, the FastAPI server, scheduled jobs (Micro-X's broker), and any future MCP-aware client. No coupling between orchestrator and tools.
- **Cost is bounded by design.** Micro-X's semantic model routing sends configuration requests to capable models (Sonnet) and lookup follow-ups to cheap models (Haiku/local). Tool-search-on-demand keeps schema payloads small. Prompt caching covers the system prompt and the deterministic-first guardrail text.
- **Compatibility correctness is structurally guaranteed.** The LLM cannot return a "yes this fits" answer from the graph because the graph tool schemas don't expose one. The only path to a compatibility verdict is `solve_configuration`, and every such call produces a logged `RuleResult` trace.
- **SOC 2 explainability is free.** Every reply containing a compatibility claim has a corresponding tool call in Micro-X's session memory and api_payloads.jsonl. Audit is a database query.
- **Phasing is independent.** Each tool family ships separately. Engine tools alone (Phase 1) deliver a working product. Graph tools come online when the graph does, without changing the engine integration.
- **Multi-family expansion is accommodated.** When `engine_v2`'s family registry is ready, `solve_configuration` dispatches to it without changing the tool contract or the LLM's view of the system.

### What becomes more difficult

- **Tool API is now load-bearing.** Both the agent today and any future orchestrator depend on the MCP tool contracts. Breaking changes are expensive. Phase 1 must get the input/output schemas right, especially `CustomerRequirements`, `Configuration`, and `RuleResult` shapes — these are the lingua franca.
- **The deterministic-first guardrail must be tested.** Adversarial prompt tests ("just confirm it fits", "skip the check") need to live in CI to catch regressions when prompt or tool descriptions change. The guardrail is design-enforced, not type-enforced — it relies on tool schemas being asymmetric.
- **Golden conversation tests are slow and expensive.** Verifying multi-turn behaviour end-to-end requires real LLM calls. These run nightly, not per-commit, and add an operational dependency on a cheap-but-not-free model.
- **A failure in any provider degrades the conversation.** Micro-X's provider pool and same-family fallback (Micro-X ADR-021) mitigate this, but the conversational layer's availability is now a function of LLM provider availability in a way the deterministic API isn't.
- **Conversational latency is variable.** Configuration turns may chain 3–4 tool calls and the LLM picks ordering per turn. A rigid pipeline would be faster and more predictable, but couldn't handle compound or follow-up questions naturally — that's the trade we're making.
- **Security posture for free-text input is broader.** The agent will accept arbitrary user prose. Prompt-injection vectors (especially via documents retrieved by `search_documentation`) need consideration. Mitigations: cited document chunks must be presented as untrusted data, and tool calls remain restricted to the fixed `window.*` surface — the LLM cannot escalate to arbitrary code execution.
- **Adoption commits the project to MCP.** If Micro-X is replaced in future, the tool definitions are MCP-shaped. This is a low risk because MCP is a cross-vendor protocol, but worth noting.

## Related

- [DESIGN-conversational-integration.md](../../design/DESIGN-conversational-integration.md) — full engineering specification
- [Graph RAG for the Product Catalogue](../../guides/graph-rag-for-product-catalogue.md) — tutorial on the graph layer
- [Knowledge Graph Research](../../research/knowledge-graph-research.md) — Phase 4 graph adoption recommendation
- [Window Tech Brief](../../research/window-tech-brief-research-report.md) — broader LLM integration patterns
- [Production Roadmap](../../planning/PLAN-production-roadmap.md) — Phase 3 (API) and Phase 4 (multi-family) alignment
- [ADR-001: Flat N-Candidate Solver](ADR-001-flat-n-candidate-solver.md) — the solver this MCP server wraps
- [ADR-002: LLM Agent Family Generation](ADR-002-llm-agent-family-generation.md) — separate LLM use case (code generation, not runtime conversation)
