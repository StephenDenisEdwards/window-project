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

> **No `load_capacity` / per-hinge weight here** — the catalogs don't rate a hinge in kg;
> load is the series-level `hinges-per-door` chart (below), looked up by `(brand, series)` +
> door height & weight. A per-hinge weight field is an *imported assumption*, not a catalog
> concept — see [`weight_model.md`](weight_model.md).

#### Family: `baseplate` *(first iteration)*

| Field | Type | Seed values / notes |
|-------|------|---------------------|
| `height_mm` | number | 0 / 2 / 4 / 6 |
| `plate_style` | enum | wing_one_piece \| cam_adjustable_wing \| face_frame_adapter_steel \| face_frame_adapter_diecast \| thick_inline \| straight |
| `fixing_type` | enum | wood_screw \| premounted_euro_screw \| split_dowel |
| `material` | enum | stamped_steel \| die_cast_steel — *added after the B-100 spike surfaced it in the matrix sub-groups* |
| `cam_adjustment` | enum | none \| single_cam \| two_cam — *discriminator; the thin build (CC2) showed V-series (single-cam) and R-series (two-cam) both have a 0mm stamped plate, so height+material alone conflates them. Lives in the block sub-title.* |
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

### 2.2 Extraction approach (per tier)

Extraction routes each piece of content to one of the four entity kinds (§2.1) and emits
it as **provenance-wrapped, confidence-scored** fields. Absence or low confidence raises a
gap; a missing *identity* field quarantines the record (ingestion model). The method
depends on the content's tier (analysis §4 recap).

**Stages (run per source — each catalog has its own layout profile):**
1. Extract page text **with positional layout** (UTF-8, word bounding boxes retained).
2. Tier-A hygiene over all text.
3. Tier-B layout/vision passes for tables and charts.
4. Tier-C routing/assembly into candidate entities (pre-merge).

Output: per-source candidate entities **plus** a raw, inspectable intermediate (one record
per detected block, with page provenance) for audit — this is the input to the merge phase.

#### Tier A — deterministic text hygiene
Rule-based, cheap, runs on all extracted text:
- **Boilerplate strip** — remove the A–Y index rail, phone/URL/brand headers & footers, and
  page numbers (pattern + position).
- **Unicode + units** — normalize °, ″, •, ↑; parse tokens to typed values while keeping the
  raw (`"Up to 7/8\" (22mm)"` → `{value: 22, unit: mm, raw: …}`); ranges → `{min, max}`.
- **Vocabulary + join key** — canonicalize strings to enum values (reconciled to the
  engine's vocabulary, §3), and strip the distributor prefix to compute `part_number_core`.

#### Tier B — layout & vision extraction
The two content types that don't survive plain text:
- **B1 · Distributor tables → rows.** Reconstruct rows from the PDF's **positional layout**
  (word boxes clustered by *y* into rows, by *x* into columns), or via a table extractor,
  then apply a **per-layout column map** to bind columns to schema fields. One product row →
  one product node. Brand layouts differ — Blum specialty / Salice baseplate matrices need
  their own maps; spike the messiest first.

  **✓ Method validated by spike** — proves the extraction *mechanism*, **not
  field-completeness** (`row_reconstruct_spike.py` → `row_bind_spike.py` →
  `table_extract_spike.py`). Source: *Würth Baer Section B —
  Concealed Hinges* (`catalogs/wurth-baer-section-b-concealed-hinges.pdf`; PDF page N ==
  printed "B-N"), pages **B-6** Blum Soft-Close Euro Hinges, **B-45** Grass TIOMOS
  Soft-Close Euro Hinges, **B-100** Salice Wing Baseplates. The full path works: row
  reconstruction → **block segmentation on header rows** → **x-position column binding** →
  schema records. Key results and the refinements they surfaced:
  - **x-binding detects blank cells** instead of collapsing them — essential for the dense
    Salice matrices (a missing SKU stays an explicit empty in the right column).
  - **A field can be a *column* on one brand and a *sub-group heading* on another.** Overlay
    is a column on Blum p6 but lives in the divider row on Grass p45
    (`"Full Overlay Hinges (Cranking 00) …"`). So extraction must capture **both** column
    cells *and* the mixed-case sub-group divider above a run of rows, and attach the divider
    context to each record.
  - **Refinements — now also validated by the stage-3 spike** (`table_extract_spike.py`;
    30 hinge / 3 accessory / 35 baseplate records, 0 unnamed columns, 0 callout leaks):
    1. **✓ Multi-row headers** — when the binding row has duplicate labels, compose real
       column meaning from the stacked label rows above it (Salice: Wood Screw / Euro
       Screw / Dowel) → each matrix cell emits a baseplate with the right `fixing_type`.
    2. **✓ Per-block family routing** — classify each block (`concealed_hinge` /
       `baseplate` / `accessory`) from its columns + banner/divider context; the
       "Accessory Items" sub-table now routes to `accessory`, not hinge.
    3. **✓ Callout-letter filtering** — stray single-letter diagram keys (`A`, `B`) are
       dropped so they don't prepend to part numbers.
  - **Parser rule the spike established:** assign a header's column-label rows by looking
    **backward** from the header (contiguous label rows immediately above), *not* by
    forward-accumulation — otherwise one block's data loop swallows the next block's
    label rows.
  - **Still open (minor):** column *display* names are slightly garbled because naming bins
    label words on the narrow binding-row column centres (the `fixing_type` keyword still
    resolves correctly) — set column x-ranges from the union of binding + label + data
    positions. And a matrix row carries **material** (Stamped vs Die-Cast Steel) with no
    home in the §2.1 `baseplate` schema (see schema note).
- **B2 · Manufacturer charts → reference tables.** Render the chart page to an image and use
  a **vision model** to extract it into structured reference records (`hinges_per_door`:
  weight-band × height → count; `reveal_gap_chart`: DT → R/G/OL/DP).

  **✓ Method validated by spike** — proves the chart-extraction *method*, **not
  field-completeness** (`chart_extract_spike.py` + `grass_tiomos_p47_hinges_chart.png`)
  on *Grass TIOMOS* p47 "Number of Hinges Per Door":
  - Vision recovered the chart **structure** that plain text scrambles — hinge-count axis
    [2,3,4,5], door-height steps [500/900/1600/2200/2450 mm], weight bands
    [4-6 / 7-12 / 13-17 / 18-22 kg].
  - **Refinement — hybrid, not vision-alone:** render the chart for *structure*, but take
    *values* from the text layer and **cross-check**. All 9 scaffold tokens (4 bands +
    5 height thresholds) matched the text layer exactly → high-confidence scaffold without
    trusting vision OCR for digits.
  - **The dense 2-D cell grid is the genuine low-confidence part.** Axes/bands read cleanly;
    the icon→cell staircase (which height×weight → how many hinges) is best-effort and is
    flagged for human verify — i.e. even a well-read chart legitimately yields a
    **low-confidence gap** for its cell grid (exactly the ingestion-model path).
- Both passes attach a **confidence** to each field; below threshold → auto-gap.

#### Tier C — routing & assembly (extraction side)
Prepares the cross-cutting work the merge/query phases finish:
- **Family routing** — assign each record a `family` from its section banner, selecting the
  right schema (§2.1).
- **Candidate edges** — pull catalog-stated conditions from prose/captions ("for 170°
  hinges", "*requires 85° clip", set-member lists) as *candidate* relationship edges, to be
  confirmed at merge.
- **Dup/conflict flags** — mark records that look like the same product (for the merge join)
  or that carry out-of-range values, without resolving them yet.

**Mapping to analysis §6:** Tier A = Step 0 · B1 = Step 2 · B2 = Step 5 · Tier C feeds
Steps 4 & 6 (merge, links).

#### Spike evidence (`design-scratch/spikes/`)

Runnable scripts behind the ✓ notes above (all read the catalogs directly). **They prove
the hard extraction *mechanisms* and emit table/chart fields only** — breadth fields
(brand/series from the banner, prose-bullet specs) were out of scope for the spikes and are
closed in the build below.

| File | Validates | Pages |
|------|-----------|-------|
| [`row_reconstruct_spike.py`](spikes/row_reconstruct_spike.py) | B1 — rows from positional layout; boilerplate strip | B-6, B-100 |
| [`row_bind_spike.py`](spikes/row_bind_spike.py) | B1 — segmentation + x-binding (blank cells) + schema records | B-6, B-45, B-100 |
| [`table_extract_spike.py`](spikes/table_extract_spike.py) | B1 — multi-row header naming + per-block family routing | B-6, B-45, B-100 |
| [`chart_extract_spike.py`](spikes/chart_extract_spike.py) | B2 — chart via vision + text-layer cross-check | Grass TIOMOS p47 |
| [`grass_tiomos_p47_hinges_chart.png`](spikes/grass_tiomos_p47_hinges_chart.png) | B2 — rendered chart crop (evidence) | Grass TIOMOS p47 |

#### First thin end-to-end build

[`build/thin_pipeline.py`](build/thin_pipeline.py) composes the spikes into a minimal DB
(B-6/B-45/B-100 + the p47 chart): **68 products** (30 hinge / 3 accessory / 35 baseplate)
+ the `hinges_per_door` reference, a GF→F join, provenance, a small query layer, and JSON
persistence (`product_db.json`, build-once/query-many). It runs 8 eval-set items.

**Cheap (bucket-B) gaps now closed in the build** — fields that were on the page but the
spikes didn't emit: `brand` 68/68 (from the banner), baseplate `plate_style` 35/35 (wing),
B-6 `max_door_thickness_mm` 14/14 (prose-bullet pass), restriction-clip
`restricts_angle_to_deg` (parsed from the description), TIOMOS `series` 16/16.

Now also closed (via the block **title**, now returned by `parse_page`):
- **`overlay_max_mm`** parsed from the TIOMOS sub-group ("…(22mm) Overlay") → **SF3 now
  unambiguous** (cranking 00 = 22mm vs 03 = 19mm).
- **`cam_adjustment`** (single/two cam) from the block title → **CC2 now genuinely passes**
  (was only passing by key-sort order); plus Blum `series` ("CLIP top BLUMOTION") from its
  title.
- **Gap report** (`gap_report.json`, gitignored) — the §2.4 queue, with **conditional
  per-record expectations** (no demanding fields that don't apply) and each empty field
  classified by *why*: **absent_in_catalog** (source never has it — price) ·
  **not_on_page** (printed elsewhere, not on this product's page) · **unparsed** (data *is*
  on the page, we missed it = the real to-do) · **low_confidence**. Current run: 292 empty
  fields → 98 absent · 120 not-on-page · **73 actionable (unparsed)** · 1 low-confidence.
  The 73 actionable collapse to **3 fields**: `compatible_hinge_series` (35),
  `overlay_max_mm` (22), TIOMOS `opening_angle_deg` (16) — i.e. ~3 small extractor tasks,
  not 300-odd problems.

Findings still open:
- **SF1 stays ambiguous** — Blum "110 vs 110+" overlay-mm is in a *block bullet* (not the
  title/sub-group), so it needs the block-level prose association below.
- **Block-level prose association** — Blum overlay-mm, certifications, `cup_depth_mm`,
  `application`, and baseplate `compatible_hinge_series` live in block bullets/notes; the
  current page-level prose pass doesn't bind them to the right block (top extraction gaps in
  the report).
- **Tier-A unicode finding:** the catalogs write degrees as **º (U+00BA, ordinal
  indicator)**, *not* **° (U+00B0, degree sign)** — normalization must canonicalize both, or
  degree-keyed parses silently miss (this bit the restriction-clip angle parse first).

### 2.3 Join / merge + conflict resolution

Extraction (§2.2) produces **per-source candidate entities**; this phase merges them into
the **canonical** DB — one node per real product, reference tables, and confirmed edges —
carrying per-field provenance. (Analysis §6 Steps 4a/4b/4c, plus edge confirmation from
Step 6.)

#### Join — which candidates are the same product
- **Key = `part_number_core`** (manufacturer number with the distributor prefix stripped,
  §3.1). Candidates grouped by key form one logical product.
- **Within-source dedup** — the same SKU printed across several spec rows (§4 #8) collapses
  to one candidate before grouping.
- **Cross-source twin resolution** — a distributor candidate and its manufacturer twin join
  on the shared key; the node records both the `manufacturer_pn` and the `distributor_skus`.
- **Unjoinable / ambiguous** — a record with no resolvable part number, or one whose key
  collides with a *different* product, is an **identity gap → quarantine** (not silently
  merged). A product that legitimately appears in only one source is a valid single-source
  node, not a gap.

#### Merge — combine fields, keep provenance
Per logical product, merge field by field. Each field keeps its full provenance set
(`{value, source, page, confidence}` per contributing source):
- **Single source** → take it.
- **Multiple sources agree** (after Tier-A normalization) → take it, recording the
  corroborating sources. *Normalize before comparing* so unit/rounding artifacts
  (`7/8″` vs `22mm`) are **not** treated as conflicts — this keeps the queue clean.
- **Sources disagree materially** → apply precedence (below), keep **both** values in
  provenance, and raise a **conflict gap** for human adjudication.
- Node `state` = `complete` if no open gaps, else `partial` (ingestion model).

#### Source precedence (conflict policy)
| Field class | Authority | Rationale |
|-------------|-----------|-----------|
| Specs (angle, overlay, thickness, boring, cup, load charts) | **manufacturer** | deepest, most authoritative |
| Catalog coverage / distributor SKU / packaging | **distributor** | distributor owns availability |
| Any **locked/curated** field | **human** | always wins; non-clobberable |

A human-resolved value is never overridden by extraction; but a later re-extraction that
*disagrees* with a locked value raises a **new** conflict for review rather than being
dropped (ingestion model).

#### Edges — candidate → confirmed
Candidate edges from Tier C are resolved against the now-merged nodes: "for 170° hinges" →
the matching `series`/`product_id`s; set-member lists → `companion_in_set` edges. **Only
non-derivable, catalog-stated edges are materialized** — compatibility the engine can derive
from attributes (series, mounting, brand) is left to engine rules (§3). Each kept edge keeps
its own `source`/`page`.

#### Reference tables
Merged on their key `(brand, series[, angle])`, deduped across sources, with provenance per
table. These are not products and are not part-number-joined.

**Output of this phase:** canonical product nodes (`partial`/`complete`/`quarantined`),
reference tables, confirmed edges, linked text chunks — and the populated gaps/conflicts
queue.

### 2.4 Validation & gap generation

Merge (§2.3) yields canonical entities; this phase **checks** them and consolidates every
gap — from extraction, merge, *and* these checks — into the single prioritized
gaps/exceptions queue (§1). Gaps are **generated** here, not just collected: absent expected
fields are detected by comparing each node to its family schema. Runs per node and is
idempotent (re-runs forward when a gap is resolved — ingestion model).

#### Validation checks
- **Schema** — identity fields present (else quarantine); types correct; enum values in the
  canonical vocabulary; units present where required.
- **Range / sanity** — values within a plausible domain (angle in the known set, positive
  thickness, boring ∈ {42, 45}, …). Out-of-range → flagged as a likely extraction error vs a
  genuine outlier (this catches the OCR/typo noise, §4 #8).
- **Intra-product consistency** — the product's *own* fields cohere: `cranking_code` ↔
  `overlay_class`; `closing_type = soft` ⇒ integrated damper **or** an `adds_soft_close`
  edge; `cup_depth` sensible vs `max_door_thickness`. (Internal coherence only — *cross*-
  product compatibility is the engine's job at query time, §3.)
- **Referential integrity** — edges resolve to existing nodes/series; a `requires_baseplate`
  hinge has ≥1 compatible plate (else flag); a series needing feasibility lookups has its
  reference table.
- **Vocabulary reconciliation** — enum strings that don't map to the canonical vocabulary →
  a *reconciliation* gap (extend the vocabulary, or it's an extraction error).

#### Severity → outcome
| Severity | Meaning | Outcome |
|----------|---------|---------|
| Blocking | can't form identity | quarantine |
| Error | field untrusted or absent | gap; node `partial` |
| Warning | suspicious but usable | flag for review; node stays usable |

#### Gap generation (the queue)
Consolidate gaps from all phases into one typed queue. Each gap carries part number, field,
reason, source + page, and any candidate value(s). **An empty field must be classified by
*why* it's empty** — an undifferentiated count is meaningless (the thin build's "335 gaps"
was ~30% data the catalog can't have, ~40% not-on-this-page, ~15% phantom). The
build-validated taxonomy ([`gap_analysis.md`](gap_analysis.md)):
- **absent_in_catalog** — source never carries it (price) → sourcing / should-decline.
  (Per-hinge weight is *not* here: it's not a catalog concept — load is the
  hinges-per-door chart, see [`weight_model.md`](weight_model.md).)
- **not_on_page** — real data, but on another page/source, not this product's → defer.
- **unparsed** — data *is* on this page, not pulled yet → **the real to-do**.
- **low_confidence** — extracted but uncertain (vision) → human verify. (Plus
  **conflict** / **reconciliation** from the merge phase; quarantine tracked separately.)

Mechanics:
- **Conditional per-record expectations** — don't demand fields that don't apply (drill
  bits have no restriction angle; baseplates no `series`), so no phantom gaps.
- **Evidence probe** distinguishes `not_on_page` from `unparsed`: does the page text contain
  the field's marker? present + empty → unparsed; absent → not_on_page.
- **Absent gaps generated here** by diffing each node's populated fields against its family
  schema's (conditional) expected fields.
- **Criticality is set by the consumer** — a field needed by an eval query (§8/§9) or an
  engine rule (§3) is *critical*; cosmetic fields are not.
- **Prioritized by impact** (refinement #6) — gaps blocking an eval-set query rank first;
  cosmetic absences sit at the bottom.

**Output:** the validated DB + the finalized, typed, prioritized **gaps/exceptions queue** —
the deliverable that drives human resolution and gates "done".

### 2.5 Eval harness

"Done" is eval-driven (refinement #6). The harness measures whether the DB answers the §5
query patterns / §9 walkthroughs correctly, and — when it doesn't — says **why** (data gap
vs pipeline bug). It is both the **per-iteration gate** and the **regression net** as the DB
evolves.

#### Eval set
> Concrete draft: [`eval_set.md`](eval_set.md) — 15 grounded items (answers taken from the
> spike-extracted data), covering all capabilities below.

- **Golden questions with known answers** — expected part number(s) + page citation(s).
  Seeded from the §9 walkthroughs and §5 query patterns.
- **Covers each capability** — exact SKU lookup (incl. cross-source `GF→F` resolution),
  spec-filtered search, weight feasibility, compatibility/completeness, comparison, lift
  sizing.
- **Includes "should-decline" cases** — questions whose answer depends on an open gap; the
  correct behaviour is "unknown / insufficient data" + cite the gap, **not** a fabricated
  value.

#### What's measured
| Dimension | Question it answers |
|-----------|---------------------|
| Correctness | the right part number(s)? |
| Completeness | all required companions returned (baseplate, clips, set members)? |
| Grounding | does each citation point to a source + page that actually contains the value? |
| Honesty | does it decline when the fact is a gap, instead of hallucinating? |

#### Run against the DB first
Exact lookups / filters / joins / feasibility are scored as **direct queries against the
DB** (target architecture) — that is what the harness measures. The LLM/RAG layer (phrasing,
comparison, prose) is evaluated separately on top, so a wording failure isn't confused with
a data failure.

#### Failure attribution — gap vs. bug
Each miss is classified:
- **Data gap** — the DB doesn't contain the fact (absent / low-confidence / conflict) →
  routes to the gaps queue; resolution unblocks the question.
- **Pipeline / query bug** — the DB *does* hold the right fact but the answer is wrong →
  defect in extraction / merge / validation / query.

Per-field provenance is what makes this distinction possible: the harness can check whether
the value is in the DB and from where.

#### Gate + regression
- **Per-iteration gate** — an iteration is done when its targeted questions pass; a failing
  question names the blocking gap(s), feeding prioritization (§2.4).
- **Regression net** — re-run as the DB evolves (new extraction passes, resolved gaps,
  schema changes); idempotent per-node rebuild keeps re-checks cheap and targeted.

#### Metrics
Per-query-type pass rate · coverage (share of eval questions answerable) · grounding
accuracy · gap-vs-bug attribution — tracked across iterations to show the DB converging.

**Output:** a repeatable eval report — pass/fail per question with citations, failure
attribution, and the ranked gaps blocking the misses.

---

*§2 outline complete. Phases read top-to-bottom but the pipeline is re-runnable per node:
resolving a gap re-enters at the record layer and flows forward through merge → validation →
eval (ingestion model).*

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
- **Weight model. → Deferred — decide at adapter phase.** ([`weight_model.md`](weight_model.md))
  The reference engine expects a per-hinge `max_door_weight_kg` scalar and counts hinges by
  *height only*; the catalogs give **no per-hinge kg** at all — load is the series-level
  weight×height→count chart. Resolve as either (a) source a per-hinge kg externally, or
  (b) have the engine consume our `hinges_per_door` reference table. (b) is the lean and the
  faithful one. Safe to defer because the DB stays neutral: it carries the chart and does
  **not** model a per-hinge weight field at all (so it's not even a gap), leaving either
  choice open. Becomes forcing at the adapter phase, or the first eval query needing weight
  feasibility (§9.3).
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
