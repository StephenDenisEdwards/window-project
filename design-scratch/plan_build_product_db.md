# PLAN — Building the Structured Product Database

> Status: **Draft — iterating.** This is the build plan; the analysis it rests on is
> [`incremental_design_wurth.md`](incremental_design_wurth.md). Section references
> (§3.1, §4, §6, §8, §9) point into that analysis doc.
>
> Goal in one line: **turn the four catalog PDFs into a structured product database
> (plus linked prose) that the eval-set queries can be answered from, with correct part
> numbers and page citations.**
>
> Date: 2026-06-06

---

## 1. Goal (refined)

The analysis doc's target architecture is: *extract a structured product database from
the PDFs, query it directly where possible, and keep unstructured prose as text linked
by part number.* Refinements that make it plan-ready:

**1. The "database" is a small set of typed, linked stores — not one table.**
- **Products** — one canonical record per real product, keyed on the **manufacturer
  part-number core** (§3.1). Carries identity (brand, series, family), the distributor
  SKU(s) that map to it, and typed spec fields.
- **Family schemas** — every product belongs to a family (`concealed_hinge`,
  `baseplate`, `lift_system`, `lid_stay`, …); each family defines its own typed fields
  (§4 #7). Shared identity columns, family-specific spec columns.
- **Relationships** — explicit compatibility/companion links between products
  (hinge → baseplate, hinge → soft-close adapter, lift → cover/arm sets), each carrying
  the **condition that gates it** ("for 170° hinges", "*requires 85° clip").
- **Text store** — the genuinely unstructured prose (application notes, install
  guidance, qualitative "for use with…" conditions) as chunks **linked to products /
  families by part number**, not flattened into columns.

**2. Provenance is per-field and first-class.** Because two sources can disagree (§4 #8),
a field is not just a value — it is `{value, source, page, raw_text}`. This is what lets
the merge apply precedence (manufacturer-wins-for-specs) and lets every answer cite.

**3. Keep raw *and* normalized.** Store the raw extracted token next to the normalized
typed value (`"Up to 7/8″ (22mm)"` → `{max_overlay_mm: 22}`). Lets us audit extraction
and re-normalize later without re-extracting.

**4. Never invent missing data — mark it for human resolution.** Where a value isn't in
the catalog (load rating absent from distributor tables; price anywhere), the field is
explicitly `null/unknown` — never guessed. But "missing" is not inert: every gap becomes
a **first-class, tracked record** in a gaps queue (see below) so a human can later supply
or confirm the value. "Never invent" stands; "mark and resolve" is how gaps get closed.

**5. Scope is incremental — structure the high-value regular data first.** First
iteration targets the **concealed-hinge tables (Würth Section B) + the Grass
load/geometry charts**, joined. The Section C long tail starts as text-with-metadata and
is promoted into structured form only where the eval set shows it's needed.

**6. "Done" is eval-driven, per iteration.** An iteration is done when the §9 walkthrough
queries it targets are answerable **from the database**, returning the correct part
number(s) with page citations — measured against the eval set (§8), not by gut feel.

### Gaps & exceptions queue

The DB build produces, as a deliverable, a **gaps/exceptions queue** — the worklist of
everything a human needs to resolve. It is what makes "never invent" (refinement #4)
workable rather than just leaving holes.

- **Each gap is a typed record, not an empty cell.** It carries: part number, field,
  reason flagged, the source + page to look at, and any candidate value(s) — enough to
  resolve without a hunt.
- **Three kinds, routed differently:**
  - **Absent** — genuinely not in the catalog (e.g. load rating in the distributor
    tables, price anywhere). Needs *sourcing*: a human (or another document) supplies the
    value.
  - **Low-confidence** — present but extraction failed or was uncertain (a chart cell the
    vision pass couldn't read, an ambiguous row). Needs *verify/correct*; may also be
    fixable by re-extraction.
  - **Conflict** — sources disagree (§4 #8). Needs *adjudication* of which source wins,
    not new data.
- **Auto-flagged by confidence.** Tier-B extraction (geometry/vision) emits a per-field
  confidence; anything below threshold is auto-added to the queue. So the queue catches
  *uncertain* extraction, not only *absent* data.
- **Resolutions flow back as locked, attributed values.** A human-supplied value gets
  `source: human/curator` (+ who/when) and is **non-clobberable** — a later pipeline
  re-run must not overwrite it. (Per-field provenance from refinement #2 plus a
  `locked/curated` marker.)
- **Prioritized by impact.** A gap matters only if it blocks an eval-set query (§8); the
  queue is ranked so the gaps standing between us and a passing §9 walkthrough get fixed
  first.

### Ingestion model

Ingestion is a **per-node, stage-based, idempotent** pipeline — not a blocking job
(a *node* = one product record). Missing data records a gap and keeps going; it does not
halt the pipeline. Three things define the model:

**Node states.**
- **`partial`** — node created but has one or more open gaps. Present and retrievable;
  queries that need a missing field report "unknown" rather than guess, and queries that
  don't, work normally.
- **`complete`** — no open gaps.
- **`quarantined`** — the node could not be formed at all (see blocking gaps).

**Blocking vs. non-blocking gaps.**
- **Attribute gap (non-blocking)** — a spec field is absent or low-confidence. The node
  is created with the field `null` + a gap record, state `partial`, and ingestion
  continues. One missing load rating never blocks the product or the pipeline.
- **Identity gap (blocking)** — no resolvable part number, or a row that can't be tied to
  a product. The node can't be formed, so the record goes to a **quarantine / exceptions**
  store. This is the *only* case where ingestion stops "for that node," and it's an
  identity failure, not an attribute one.

**Resume forward, per node, on resolution.** A human resolution (from the gaps queue) is
an *event*, not a restart:
1. The value is written into the node as a **locked, attributed** field
   (`source: human/curator`, who/when) — protected from future re-extraction.
2. Only that node's **downstream stages** re-run: validate → finalize record → rebuild its
   text chunk/embedding → re-index → re-check the eval queries it was blocking. No PDF
   re-extraction (the human is the source now); no other node is touched.
3. The node flips **`partial → complete`** once its gaps close; any §9 walkthrough it was
   blocking is re-evaluated.

So a human value re-enters at the **record layer** and flows forward — the same entry
point whether the gap was *absent*, *low-confidence*, or *conflict* (only the human action
differs: supply / correct / adjudicate). The corpus stays usable throughout; `partial`
nodes converge to `complete` as the queue drains.

**Curation vs. re-extraction precedence.** If a later re-extraction finds a value a human
had supplied, the `locked` flag means the human value wins by default — but the divergence
is raised as a **new conflict** for review rather than silently kept, so curated data
doesn't drift from the source unnoticed.

### Non-goals (for now)
- Not a pricing or availability system.
- Not a fully-normalized schema covering every family on day one.
- Not inventing specs the catalogs don't state.
- Not the retrieval/LLM application itself — this plan builds the database that app sits on.

---

## 2. Plan

The build breaks into: **(2.1) family schema definitions** → extraction approach per tier
→ join/merge + provenance → validation & gaps → eval harness. We start with the schemas,
because everything downstream (what to extract, how to merge, what "valid" means) is
defined against them.

### 2.1 Family schema definitions

Notation is **serialization-agnostic** (could land as JSON docs, relational tables, or a
graph) and **standalone** — types are generic (`enum`, `number`, `range`, `bool`,
`list<…>`). Value sets shown are **seed values observed in the catalogs**, to be
reconciled during extraction, not a closed list.

#### Entity kinds

Not everything in the corpus is a product. Four entity kinds:

| Entity | What it is | Keyed by | Examples |
|--------|-----------|----------|----------|
| **Product node** | One real, orderable product | part-number core (§3.1) | a hinge, a baseplate, a clip |
| **Reference table** | A spec/lookup table that applies to a *series*, not a SKU | (brand, series) | hinges-per-door load chart, overlay chart |
| **Relationship edge** | A compatibility/companion link | (from, to, type) | hinge → requires → baseplate |
| **Text chunk** | Unstructured prose linked to a node/series | chunk id | install notes, application guidance |

This separation matters: e.g. **load capacity is *not* a hinge field** — the catalogs
publish it as a series-level *hinges-per-door* table (Grass p47/p38), so it's a reference
table, not a column on the product. Putting it on the hinge would be wrong modelling.

#### Field value wrapper (provenance)

Per refinement #2, every stored field is a value object, not a bare scalar:

```
field = {
  value:      <normalized typed value>,
  unit:       <mm | deg | mm² | kg | lb | …, where applicable>,
  raw:        <original extracted token, e.g. "Up to 7/8\" (22mm)">,
  source:     <wurth_b | wurth_c | grass_tiomos | grass_nexis | human>,
  page:       <int>,
  confidence: <0.0–1.0; 1.0 for human/curated>,
  locked:     <bool; true = curated, non-clobberable>
}
```

Field tables below list the **logical field + type**; assume each is wrapped as above.

#### Shared product base (all families)

| Field | Type | Notes |
|-------|------|-------|
| `product_id` | string | canonical id = normalized part-number core (join key) |
| `part_number_core` | string | manufacturer number, distributor prefix stripped (§3.1) |
| `manufacturer_pn` | string | as printed by the manufacturer (e.g. `F028138341228`) |
| `distributor_skus` | list<{sku, source}> | e.g. `GFF028138341228` (wurth_b) |
| `brand` | enum | Blum, Grass, Salice, Pro, SOSS, Peter Meier, Youngdale, … |
| `series` | enum/string | CLIP top BLUMOTION, TIOMOS, NEXIS, COMPACT, Pro, AIR, … |
| `family` | enum | concealed_hinge \| baseplate \| accessory \| (deferred families) |
| `finish` | enum/string | nickel, onyx black, … (optional) |
| `package_qty` | number | PU / box qty (optional) |
| `state` | enum | partial \| complete \| quarantined (ingestion model) |
| `gaps` | list<gap_ref> | open gaps on this node |
| `text_refs` | list<chunk_id> | linked prose |

Identity fields (`part_number_core`, `brand`, `family`) are **required to form a node** —
their absence is the blocking *identity gap* that sends a record to quarantine.

#### Family: `concealed_hinge` *(first iteration)*

| Field | Type | Seed values / notes |
|-------|------|---------------------|
| `opening_angle_deg` | number | 95, 100, 105, 110, 120, 125, 155 (+ diagonal 45 variant) |
| `overlay_class` | enum | full \| half \| inset |
| `overlay_max_mm` | number | e.g. 22, 19 |
| `cranking_code` | string | Grass only: 00 / 03 / 9.5 / 19 (maps to `overlay_class`) |
| `fixing` | enum | screw_on \| dowel \| inserta \| expando \| impresso |
| `closing_type` | enum | soft \| self \| free |
| `soft_close_integrated` | bool | true = damper in arm/cup; false = needs add-on (→ edge) |
| `boring_pattern_mm` | enum | 42 \| 45 \| 42_45 |
| `cup_diameter_mm` | number | typically 35 |
| `cup_depth_mm` | number | e.g. 10.5, 12 |
| `max_door_thickness_mm` | number | 22 / 24 / 26 / 30 / 36 … |
| `min_door_thickness_mm` | number | where stated (Grass: 6, 8) |
| `application` | enum | standard \| blind_corner \| angled_30 \| angled_45 \| zero_protrusion \| narrow_aluminum \| thick_door |
| `adjustment` | object | `{depth: range, height: range, side: range}` mm, where stated |
| `certifications` | list<enum> | ANSI, BIFMA, KCMA, BHMA |
| `requires_baseplate` | bool | true (baseplate sold separately) → edge |

> **No `load_capacity` here** — derived from the `hinges_per_door` reference table
> (below) keyed on this hinge's `(brand, series)` plus door height & weight.

#### Family: `baseplate` *(first iteration)*

| Field | Type | Seed values / notes |
|-------|------|---------------------|
| `height_mm` | number | 0 / 2 / 4 / 6 |
| `plate_style` | enum | wing_one_piece \| cam_adjustable_wing \| face_frame_adapter_steel \| face_frame_adapter_diecast \| thick_inline \| straight |
| `fixing_type` | enum | wood_screw \| premounted_euro_screw \| split_dowel |
| `cam_adjustable` | bool | |
| `compatible_hinge_series` | list<series> | → edge to hinges |

#### Family: `accessory` *(first iteration)*

Restriction clips, soft-close adapters, cover caps, screws/bits/templates.

| Field | Type | Seed values / notes |
|-------|------|---------------------|
| `accessory_type` | enum | restriction_clip \| soft_close_adapter \| cover_cap \| hinge_screw \| drill_bit \| template |
| `for_series` | list<series> | gating condition |
| `for_angle_deg` | list<number> | gating (e.g. adapter "for 170° hinges") |
| `restricts_angle_to_deg` | number | clips only: 75 / 85 / 86 / 92 / 100 / 104 |
| `color` | enum/string | gray, black, white, … |

#### Reference tables (non-product)

| Table | Key | Shape | Source |
|-------|-----|-------|--------|
| `hinges_per_door` | (brand, series) | weight_band `{min_kg,max_kg,min_lb,max_lb}` × door_height_mm → hinge_count | grass_tiomos p47, grass_nexis p38 |
| `overlay_chart` | (brand, series) | (cranking_code, baseplate_height_mm) → overlay_mm (+ reveal for inset) | wurth_b B-4, grass charts |
| `reveal_gap_chart` | (brand, series, angle) | door_thickness_mm → `{reveal, gap, overlay, protrusion, X, Z}` mm | grass model pages |

These are how weight-feasibility and precise-install questions (§5) get answered — they
are looked up at query time using a product's `(brand, series)` and the user's inputs.

#### Relationship edges

| Field | Type | Notes |
|-------|------|-------|
| `from` | product_id \| (brand, series) | series-level rules allowed (e.g. "all TIOMOS need …") |
| `to` | product_id \| family \| series | |
| `type` | enum | requires \| compatible_with \| companion_in_set \| restricts \| adds_soft_close \| replaces |
| `condition` | object | `{text, applies_to_angle?, applies_to_series?, applies_to_overlay?}` |
| `source`, `page` | — | provenance for the link itself |

#### Deferred families (later iterations)

Captured as **text-with-metadata** until the eval set demands structure (refinement #5).
Each has its own force/weight spec model, so each is a *new* schema when promoted:
`lift_system` (AVENTOS / KINVARO / WIND — Power Factor, spring code), `lid_stay` /
`up_stay` (torque), `institutional_hinge`, `piano_hinge`, `invisible_hinge` (SOSS),
`pivot` / `butt` / `glass_door` / `specialty`.

---

*(Remaining §2 phases to iterate: extraction approach per tier · join/merge + conflict
resolution · validation & gap generation · eval harness.)*

---

## 3. Relationship to a constraint engine (integration target)

The database is the **engine-agnostic facts layer**; a constraint engine is one
*consumer* of it. The project already has a reference implementation — `engine_v2`, a
generic multi-family constraint solver — but the DB is deliberately **not coupled** to
it. The same DB could feed engine_v2, an evolved version of it, or a fresh engine.

```
PDFs → [extraction pipeline] → structured product DB → [adapter] → constraint engine → ranked configurations
                                     (this plan)                   (consumer; engine_v2 = reference design)
```

**What the DB supplies an engine** — the four inputs a constraint solver needs:
1. **Typed product attributes** — the operands every rule compares.
2. **Reference tables** — the derivation data rules call (`hinges_per_door`,
   `overlay_chart`, `reveal_gap_chart`).
3. **Relationship edges** — catalog-stated compatibility not derivable from attributes.
4. **Provenance** — so every verdict traces to a catalog page (explainability).

**What stays engine work** (not catalog data → out of scope for the DB): the requirements
model, the rules/compatibility logic, the solver, and ranking. Catalog *conditions*
captured as edges seed some rules, but the logic itself is engineered.

**Design consequences for the DB:**
- **Stay engine-agnostic; integrate via an adapter.** Keep the DB as canonical sourced
  facts; a thin projection maps product nodes → whatever the engine expects
  (`part_number_core → sku`, overlay reference → a plate's achievable overlay range, …).
  Preserves optionality — multiple consumers (engine(s) *and* the RAG chat) off one DB.
- **Build the engine to fit the facts, not the reverse.** The catalogs are ground truth, so
  a DB-backed engine can be *more correct* than a hand-data PoC — e.g. a real weight model
  from the Grass weight×height charts rather than an invented per-hinge kg rating.
- **Multi-family for free.** Per-family schemas + reference tables + edges are exactly what
  a general multi-family engine needs; each promoted catalog family (lift systems, lid
  stays…) becomes a new engine family driven by the same DB shape.
- **Second definition of done.** Beyond answering the RAG eval (§8/§9), the DB succeeds if
  it can *drive a constraint engine* through the adapter.

**Open decisions surfaced by the reference engine:**
- **Weight model. → Deferred — decide at adapter phase.** The reference engine expects a
  per-hinge `max_door_weight_kg` scalar and counts hinges by *height only*; the catalogs
  give no per-hinge kg but a richer weight×height→count chart. Resolve as either (a) source
  the kg as a gap, or (b) have the engine consume our `hinges_per_door` reference table.
  (b) is the lean. Safe to defer because the DB stays neutral: it extracts the weight×height
  chart either way, and models per-hinge weight as a nullable field (→ gap when absent), so
  neither option is foreclosed. Becomes forcing at the adapter phase, or the first eval
  query needing weight feasibility (§9.3).
- **Derived vs. stored compatibility.** The reference engine derives hinge↔plate
  compatibility from attributes via rules (series, mounting, brand). So the DB should
  materialize **only** non-derivable, catalog-stated edges; derivable compatibility stays
  engine logic.
- **Vocabulary target.** Reconcile our seed enums *to* the engine's existing vocabulary
  (mounting methods incl. inserta/expando/impresso already exist there), extending for new
  brands (Salice/Pro) rather than duplicating.
- **Null-tolerance.** `partial` nodes (open gaps) require engine rules to skip gracefully on
  missing fields; most already do, but the weight rule currently assumes the value is
  present.
