# ADR-004: Hinge-count derivation as a standalone module, not embedded in the engine

## Status

Accepted

## Context

The constraint engine needs to know **how many hinges a door requires**. The manufacturer
catalogs publish this as a **"Number of Hinges per Door" load chart** keyed by series — a 2-D
lookup of `(door height, door weight) → hinge count`. Two of these charts (Grass TIOMOS, Grass
NEXIS) are now extracted, human-verified, and stored in a unified schema in
`design-scratch/build/load_charts.json`.

A prior analysis ([ENGINE_V2_FIT.md §7](../../../../design-scratch/ENGINE_V2_FIT.md)) established
that hinge count is a **derived output**, not a weight pass/fail constraint: you *solve for* the
count from the chart, you don't check a fixed count. The engine's current `compute_derived()` hook
already produces a `hinges_per_door` value — but from a hard-coded height-only table, and the
standalone weight rule (`R007`) uses a wrong per-hinge-kilogram model.

The question this ADR settles: **does the load-chart derivation live inside the engine, or as a
separate component?**

Key observation: the derivation is a **pure function** — `(series, door_height, door_weight) →
hinge_count` over the load-chart data. It has **no dependency on the constraint solver**: no
candidate products, no rules, no pairing. Nothing forces it into the engine.

## Decision

**Build the hinge-count derivation as a standalone, self-contained module over `load_charts.json`,
separate from the constraint engine. The engine consumes it through a thin derived-values hook.**

- The module exposes a pure lookup, roughly `hinge_count(series, door_height, door_weight) → int`
  (plus an "off the chart → infeasible" signal), implementing the verified rule: *smallest hinge
  count whose `max_door_height` AND `max_weight` both cover the door*.
- The module owns all load-chart concerns: reading `load_charts.json`, the metric/imperial unit
  handling, and keying by `brand`+`series`.
- The engine's `compute_derived()` for the concealed-hinge family becomes a **thin adapter** that
  calls the module and stuffs the result into the derived values (which then drive quantity →
  price/BOM, ranking, and the demoted `R007` boundary check).
- The derivation does **not** live in `engine_v3`; `engine_v3` depends on it, not the reverse.

```
load-chart module  ──(pure lookup over load_charts.json)──►  hinge_count(series, h, w)
        ▲                                                          ▲
        │ imports                                                  │ thin call
   UI / standalone "how many hinges?"            engine_v3 compute_derived() hook
```

## Consequences

**Easier:**

- **Testable in isolation.** The module is unit-tested directly against the charts' printed worked
  examples (e.g. NEXIS `56″ × 19 lb → 3 hinges`) — no engine setup, same verification discipline
  used to extract and verify the charts.
- **Two consumers, one source.** Both the engine *and* the UI/standalone queries ("this door needs
  3 hinges") use the same lookup. Embedding it in the engine would serve only the engine.
- **Ships independently.** The derivation (and a UI "how many hinges?" feature) can be built and
  verified now, without waiting for the `engine_v3` scaffolding.
- **Decoupled from the data shape.** Chart-reading logic lives in one place; the engine just calls
  `hinge_count(...)` and is insulated from the `load_charts.json` schema.
- **Sharpens the engine.** `R007` collapses from a (wrongly modelled) per-hinge-weight rule into a
  derivation + a thin boundary check, and the count becomes weight-aware instead of height-only.

**More difficult / trade-offs:**

- One more module and dependency edge to maintain; the engine must call out rather than own the logic.
- The module's `series` keys must stay aligned with the product records' `series` values (the
  brand+series join). Mismatches surface as "no chart for this series."
- Load coverage is currently **Grass only** — Blum/Salice charts are still in *Data Sourcing
  Required*. The module must degrade gracefully (return "unknown / data not available") for series
  with no chart, consistent with the "missing data is marked, not invented" principle.

## References

- `design-scratch/ENGINE_V2_FIT.md` §7 — hinge count is a derived output, not a weight pass/fail
- `design-scratch/build/load_charts.json` — the verified TIOMOS + NEXIS load charts (unified schema)
- `design-scratch/EXTRACTION_STATUS.md` — extraction status; the Data Sourcing Required registry
- [ADR-001](ADR-001-flat-n-candidate-solver.md) — the engine framework this derivation feeds
