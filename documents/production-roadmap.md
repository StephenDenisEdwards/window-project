# Production Roadmap — From PoC to Production Constraint Engine

## Current State

The engine has moved beyond the original single-file PoC into a modular production codebase (`engine/`). Completed work:

- Pydantic v2 domain models with full enum typing (no raw strings)
- Rules extracted to standalone functions in `rules.py` with a `RULES` list
- Structured `OverlayTable` (BPH × DD lookup) replacing flat `[min, max]` ranges
- R010 (wide-angle derating) removed — uses manufacturer's published ratings directly
- `ManufacturerProduct` base class with `DistributorSKU` overlay for SKU identity
- `RuleResult` extended with `category`, `values_compared`, and `remediation`
- Indexed pre-filtering on hinges (by brand, cabinet type, application)
- 70+ tests including 7 customer scenarios
- Original single-file demo removed

Still in place from the PoC: flat JSON data files, in-memory loading, brute-force plate scanning, single-threaded execution, no API layer.

This document evaluates what remains to meet the work brief requirements: a production-grade, multi-brand constraint reasoning engine deployed as part of a three-layer architecture (knowledge foundation + reasoning engine + conversational layer) with SOC 2 compliance.

---

## Phase 1: Engine Architecture (Weeks 3–4)

### 1.1 Separate rules from code

**Problem:** Every rule is a Python function in `engine/rules.py`. Adding a rule means writing code, deploying a new version, and hoping you didn't break something. The brief says Würth has 13 product families — each will have its own constraint rules. Hardcoded methods won't scale.

**Target:** Rules defined as data, evaluated by a generic engine.

```
# Instead of this (current — engine/rules.py):
def check_door_thickness(h, p, req, num_hinges):
    ok = h.door_thickness_range_mm.contains(req.door_thickness_mm)
    ...

# Move to this:
{
  "id": "R006",
  "type": "range_check",
  "field": "door_thickness_mm",
  "min_ref": "hinge.door_thickness_min_mm",
  "max_ref": "hinge.door_thickness_max_mm",
  "input_ref": "requirements.door_thickness_mm"
}
```

**Design decision:** How expressive should the rule language be? Options:
- **Simple DSL** (comparisons, range checks, lookups) — covers ~80% of current rules, easy to validate
- **Expression evaluator** (e.g., `eval` with sandboxing, or a custom AST) — covers all rules including computed ones like R010 derating
- **Full CSP solver** (OR-Tools, Z3) — overkill for this problem size, but future-proofs for complex multi-product configurations

**Recommendation:** Start with a typed rule DSL covering the common patterns (equality, range, lookup, conditional). Add an escape hatch for Python callables for complex rules (weight derating, overlay calculations). Avoid a full solver — the search space is manageable with indexed lookups.

### ~~1.2 Remove R010 (wide-angle derating)~~ DONE

R010 removed. `max_door_weight_kg` is used directly in R007.

### 1.3 Overlay calculation — accept drilling distance

**Problem:** The PoC stores overlay ranges as simple `[min, max]` per plate. In reality, achievable overlay is a function of base plate height (BPH) AND drilling distance (DD). The catalogs publish full lookup tables for this. Using a single range is a simplification that can recommend configurations that don't actually achieve the desired overlay at the customer's specific drilling distance.

**Target:** Store full overlay lookup tables (BPH × DD → overlay) per plate. Accept `drilling_distance_mm` as a customer input. Calculate exact achievable overlay at evaluation time.

**UX implication:** Professional contractors know their drilling distance. Guided discovery users don't — the system should default to the most common value (typically 5–6mm) for the guided path.

### 1.4 Brand-specific rule parameters

**Problem:** The PoC uses a single `hinges_per_door` table. Grass Tiomos uses ≤889mm=2, Blum uses ≤900mm=2. The weight capacity tables, reveal calculations, and overlay formulas all differ between brands.

**Target:** Rule parameters keyed by brand/series. The engine loads the appropriate parameter set based on the hinge being evaluated.

```python
HINGES_PER_DOOR = {
    "Blum": {900: 2, 1400: 3, 1800: 4},
    "Grass/Tiomos": {889: 2, 1422: 3, 2134: 4},
    "Grass/Nexis": {889: 2, 1422: 3, 2134: 4},
    "default": {889: 2, 1400: 3, 1800: 4},
}
```

### 1.5 Indexed pre-filtering — PARTIALLY DONE

Hinge indexes are built at init (by brand, cabinet type, application). Remaining work:

- **Plate indexes not yet implemented** — plates are still scanned linearly. Indexing by `compatible_hinge_series` and `cabinet_type` would cut the inner loop.
- **No short-circuiting** — `evaluate()` runs all rules even after the first failure. Needed for `solve_with_explanation()` but wasteful for `solve()`.
- **No hinge-only rule caching** — rules like R006 (door thickness) and R009 (boring pattern) depend only on hinge + requirements, not the plate, but are re-evaluated per plate pairing.

---

## Phase 2: Data Architecture (Weeks 3–5)

### 2.1 Replace JSON files with a proper data store

**Problem:** Flat JSON files work for 108 products. They don't work for thousands of SKUs that change when catalogs update, prices change, or products are discontinued. No versioning, no audit trail, no concurrent access.

**Options:**
- **PostgreSQL with JSONB columns** — structured core fields, flexible extension via JSONB for brand-specific attributes. Good fit for SOC 2 (encryption at rest, RBAC, audit logging). Recommended.
- **DynamoDB** — if going AWS serverless. Single-table design maps well to the product + rule model. But overlay lookup tables are awkward in key-value.
- **SQLite per brand** — simple, file-based, easy to version. Works for the Weeks 3–6 build. But no concurrent access, no audit logging.

**Recommendation:** PostgreSQL. The SOC 2 requirement and multi-brand isolation make a proper relational database the right call from day one.

### 2.2 Catalog ingestion pipeline

**Problem:** The PoC loaded data by hand-editing JSON files and running extraction scripts against PDFs. Production needs a repeatable pipeline that can ingest catalog updates without engineering effort.

**Target pipeline:**

```
Source data (PDF, CSV, API)
  → Parser (per-format, per-brand)
  → Normalisation (canonical units, field mapping)
  → Validation (required fields, range checks, referential integrity)
  → Staging (human review for new/changed products)
  → Production (versioned, auditable)
```

**Key lessons from our extraction:**
- Würth Baer catalogs are PDFs with extractable text — PyMuPDF works. But page layouts vary and require per-section parsing logic.
- Manufacturer catalogs (Grass, Blum) have better-structured data but different formats from each other.
- Prices are not in catalogs — they come from Würth's ERP/ordering system via a separate feed.
- The internal sales process document (covering 13 product families) is the most valuable source and its format is unknown.

### 2.3 Compatibility matrix — derive, don't maintain

**Problem:** The PoC stores `compatible_mounting_plate_skus` as a hand-maintained list on each hinge. This breaks whenever a plate is added or a series changes. During our expansion, 41 plates were orphaned because the lists weren't updated.

**Target:** Compute compatibility at query time using the rules (R001 brand lock, R002 series compatibility, R003 cabinet type, R014 mounting method). Don't store it — derive it. The `compatible_mounting_plate_skus` field becomes unnecessary.

This also makes the engine self-consistent: if a rule changes, compatibility changes automatically. No more orphaned plates.

### 2.4 Price integration

**Problem:** Only 34% of hinges and 22% of plates have prices. The PoC scraped retail prices from third-party sites. Production needs Würth's actual distributor pricing, which varies by brand, customer tier, and volume.

**Target:** Price as a separate data feed, not embedded in product data. The engine evaluates constraint satisfaction without prices; pricing is applied as a post-filter/sort layer. This keeps the engine correct regardless of pricing data availability.

---

## Phase 3: Production Hardening (Weeks 5–7)

### 3.1 API layer

**Problem:** The PoC is a Python module called directly. The conversational layer needs an API.

**Target:** REST or GraphQL API with:
- `POST /solve` — accept customer requirements, return ranked configurations
- `GET /products/{sku}` — product detail with images
- `GET /rules` — current rule set (for transparency/debugging)
- `POST /evaluate` — evaluate a specific hinge + plate pair (for the pro fast-track)

**Framework:** FastAPI is the natural choice — Python-first (matching the brief), async, auto-generated OpenAPI docs, and good typing support.

### ~~3.2 Constraint trace as a first-class output~~ DONE

`RuleResult` now includes `rule_id`, `rule_name`, `category` (hard_constraint | soft_constraint | preference | derived), `passed`, `detail`, `values_compared`, and `remediation`.

### 3.3 Testing strategy

**Problem:** The PoC has 61 unit tests that verify internal consistency. They don't verify domain correctness — they test that the code does what the code says, not that the code says the right thing.

**Production testing needs three layers:**

1. **Unit tests** (current) — rule logic works correctly given inputs
2. **Integration tests against known-good configurations** — the 7 customer scenarios in `engine/tests/test_engine.py` verify the engine recommends correct configurations. These are the "golden tests" that prove domain correctness.
3. **Regression tests on catalog changes** — when a product is added, updated, or discontinued, verify that existing valid configurations aren't broken and new products are reachable.
4. **SME validation suite** — a set of real-world configurations validated by a domain expert (Würth sales rep or experienced installer). This is the ultimate correctness check and should be built during Week 1–2 discovery.

### 3.4 Error handling and observability

**Problem:** The PoC silently skips rules when data is missing (`cup_depth_mm is None → skip`). In production, missing data should be tracked and flagged.

**Target:**
- Every rule evaluation logged with inputs, outputs, and timing
- Missing data fields flagged in a product health dashboard (not silently skipped)
- Query latency tracked (p50, p95, p99)
- Alert on rule evaluation errors or unexpected None values

### 3.5 Remove the demo scaffolding — PARTIALLY DONE

The original single-file demo (`demo/`) has been removed. Remaining items:

| PoC pattern | Status |
|-------------|--------|
| `compatible_mounting_plate_skus` maintained by hand | **Done** — compatibility derived from rules at query time |
| `effective_max_weight_kg` applies derating in the model | **Done** — R010 removed, uses published weight directly |
| Hardcoded rule methods on engine class | **Done** — standalone functions in `rules.py` with `RULES` list |
| `load_catalog()` reads JSON files on every call | Remaining — no startup caching or refresh |
| `price_usd` embedded in product data | Remaining — no separate pricing feed |
| Brute-force plate scanning | Remaining — plates not indexed |
| `run_demo()` with hardcoded scenarios | Remaining — no API endpoints yet |

---

## Phase 4: Multi-Brand and Multi-Product (Weeks 8–14)

### 4.1 Brand isolation

**Problem:** The PoC loads all products into one engine instance. The brief requires client-isolated environments and deployment across three brands.

**Target:** Per-brand configuration:
- Brand-specific product catalogs
- Brand-specific rule parameters (hinges-per-door thresholds, overlay formulas)
- Brand-specific pricing feeds
- Shared rule engine code, different data

**Architecture options:**
- **Separate deployments per brand** — simplest isolation, easiest SOC 2 compliance, but higher operational overhead
- **Multi-tenant with logical isolation** — one deployment, brand resolved from request context. Lower cost, but SOC 2 audit gets more complex
- **Hybrid** — shared engine service, per-brand data stores

### 4.2 Extending to the remaining 12 product families

The brief says: "If we get hinges right, every other product category in the catalog becomes a fast follow-on."

This is optimistic. Each product family has its own constraint space:

| Product family | Constraint type | Similarity to hinges |
|---------------|-----------------|---------------------|
| Drawer slides | Length × cabinet depth × weight | Similar — dimensional + weight |
| Lift systems (AVENTOS) | Door height × weight × power factor | Different — uses power factor calculation, not simple weight |
| Handles/knobs | Aesthetic, bore spacing | Much simpler — fewer hard constraints |
| Locks | Backset × door thickness | Simpler |
| Lighting | Voltage × length × driver compatibility | Different constraint domain |

**What carries across:** The engine architecture (data-driven rules, indexed search, constraint trace output), the API layer, the testing framework, the catalog ingestion pipeline.

**What doesn't carry across:** The specific rules, the domain models, the overlay/weight/angle calculations, and critically the SME knowledge for each family.

**Recommendation:** Design the engine with a generic `ProductFamily` abstraction from the start. Each family defines its own models, rules, and derived values. The engine provides the evaluation framework. But budget real time for each new family — "fast follow-on" is credible for drawer slides (similar constraint space) but not for lighting (different domain entirely).

### 4.3 SKU identity across brands

**Problem discovered during extraction:** The same Blum hinge has different distributor SKUs at different Würth brands (e.g., `BP71B3550` at Würth Baer). If Würth Louis uses a different prefix, the knowledge layer needs a canonical product model with per-brand mappings.

**Target:** A canonical product ID (manufacturer part number) with brand-specific SKU mappings:

```
canonical: "71B3550" (Blum manufacturer part)
├── wurth_baer: "BP71B3550"
├── wurth_louis: "WL71B3550"  (hypothetical)
└── wurth_wood: "WW71B3550"   (hypothetical)
```

---

## Phase 5: SOC 2 and Production Deployment (Ongoing)

### 5.1 SOC 2 controls needed from day one

The brief specifies SOC 2 from day one. For the constraint engine specifically:

- **Encryption at rest:** Product data, rule definitions, and query logs encrypted in the database
- **Encryption in transit:** TLS on all API endpoints
- **Audit logging:** Every rule evaluation logged with timestamp, inputs, results (not just the recommendation — the full trace)
- **RBAC:** Separate roles for rule authoring, product data updates, API access, and dashboard viewing
- **Data deletion:** On contract termination, all brand-specific product data and query logs must be deletable. This requires per-brand data isolation in the database schema.

### 5.2 Deployment pipeline

```
Code change → CI (lint, type check, unit tests)
  → Integration tests (golden scenarios)
  → Staging (brand-specific data, full evaluation suite)
  → Production (blue-green or canary)
```

**Catalog update pipeline (separate from code):**
```
New catalog data → Ingestion pipeline
  → Validation (schema, referential integrity)
  → Diff report (new/changed/removed products)
  → Human review + SME sign-off
  → Deploy to production (no code change needed)
```

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Internal sales document is incomplete or messy | High | High | Budget Week 1–2 for SME interviews alongside document review |
| Overlay simplification causes incorrect recommendations | Medium | High | Implement full BPH × DD lookup tables in Phase 1 |
| ~~R010 double-derating ships to production~~ | ~~High~~ | ~~Medium~~ | **RESOLVED** — R010 removed |
| Third brand has incompatible data format | Medium | Medium | Design ingestion pipeline with per-brand parsers from the start |
| 13 product families take longer than expected | High | Medium | Prioritise families by commercial value, not engineering ease |
| Price data unavailable or stale | Medium | Low | Engine works without prices — pricing is a sort layer, not a constraint |
| Edge cases discovered in production | Certain | Variable | Build an SME feedback loop into the dashboard — flag uncertain recommendations for human review |

---

## Summary

The engine has progressed from a single-file PoC to a modular, typed codebase with structured rule output, enum safety, and hinge-side indexing. The remaining gap to production is:

1. **Data architecture** — moving from flat JSON to a proper data store with versioning, validation, and audit trails
2. **Rule abstraction** — rules are now standalone functions (not class methods), but still Python code, not data-driven definitions
3. **Data completeness** — getting the internal sales process document, manufacturer spec sheets, and SME validation that catalogs alone can't provide
4. **Operational infrastructure** — API layer, catalog update pipeline, SOC 2 controls
5. **Search efficiency** — plate indexing, short-circuiting for `solve()`, hinge-only rule caching

The constraint engine itself is currently ~800 lines of Python across 6 modules. The surrounding infrastructure — ingestion, validation, API, testing, deployment, monitoring — is where the bulk of the remaining engineering effort goes.
