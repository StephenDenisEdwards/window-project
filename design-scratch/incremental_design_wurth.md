# Incremental Design — RAG over the Cabinet-Hardware Catalog Corpus

> Scratch / working notes. The goal of this document is to **analyse the catalogs in
> `catalogs/` and incrementally work out the best way for an LLM to work with this data
> in a RAG setup** — how to extract it, chunk it, retrieve it, and ground answers in it.
>
> Originally scoped to the two Würth Baer catalogs; now widened to the **four-catalog
> corpus**, because the two Grass catalogs turn out to be the manufacturer source for
> brands the Würth catalog only covers shallowly (see §3).
>
> Date: 2026-06-06
> Source files:
> - `catalogs/wurth-baer-section-b-concealed-hinges.pdf` (104 pp) — distributor
> - `catalogs/Wurth_Baer_Section_C.pdf` (56 pp) — distributor
> - `catalogs/grass-tiomos-catalog.pdf` (64 pp) — manufacturer
> - `catalogs/grass-nexis-catalog.pdf` (52 pp) — manufacturer
>
> **Build plan:** the plan to turn these catalogs into the structured product database
> lives in [`plan_build_product_db.md`](plan_build_product_db.md).

---

## 1. What we're trying to figure out

These are dense, tabular product catalogs. A naïve "dump the PDF, embed pages, ask
questions" pipeline will retrieve plausible-looking pages and then hallucinate part
numbers, mismatch specs to the wrong row, or quietly drop options. The aim here is to
understand the *shape* of this data well enough to choose a RAG design that lets an
LLM answer real catalog questions **with correct, traceable part numbers and specs**.

We work up to that design incrementally: start with the simplest thing, name where it
breaks given what's actually in these files, and only add structure where the data
forces us to. A second axis is now in play — the corpus has **two kinds of source**
(distributor vs. manufacturer) that overlap on the same products, so the design also
has to decide how to merge them.

### Target architecture (working answer)

The goal is **not** "RAG over PDFs." It is: **extract a structured product database
from the PDFs, and query that — falling back to retrieval over the leftover prose only
where structure can't hold the content.** Concretely:

- **Backbone: a structured product database.** One record per part number, with typed
  spec fields (angle, overlay, fixing, boring, thickness, load, …). Not one schema but
  **several linked tables** (concealed hinges, baseplates, lift systems, lid stays, …),
  because the corpus is heterogeneous (§4 #7). Distributor and manufacturer records for
  the same product are **joined on the shared part-number core** (§3.1).
- **Plus retained text.** The genuinely unstructured content — marketing/application
  notes, installation guidance, and the qualitative compatibility conditions
  ("for use with Blum Euro free-swing hinges", "*only achievable with 85° angle
  reduction clip") — is kept as text chunks **linked to the relevant records by part
  number**, not discarded into a column.
- **Query directly where possible.** Exact SKU lookups, spec filters, joins and
  range/feasibility checks are **direct queries against the records** — exact and
  verifiable, not routed through vector similarity. The LLM + retrieval layer is
  reserved for natural-language phrasing, comparison, the qualitative/prose content, and
  open browsing.

Why this shape: the real questions here are **relational and numeric** (filter, join,
table lookup), which structured data answers exactly and traceably, whereas embeddings
only approximate — and approximation is precisely how you return the wrong part number.
The whole incremental plan (§6) is, in effect, the pipeline that **builds this database
out of the PDFs**.

---

## 2. Corpus inventory

### Source map

| Source | Role | Brands | Depth |
|--------|------|--------|-------|
| Würth Baer Section B | Distributor | Pro, Blum, Grass TIOMOS, Grass NEXIS, Grass TEC, Salice | Broad, shallow |
| Würth Baer Section C | Distributor | Blum, Grass, Salice, SOSS, Peter Meier, Youngdale, others | Broad, shallow |
| Grass Tiomos | Manufacturer | Grass TIOMOS only | Narrow, deep |
| Grass Nexis | Manufacturer | Grass NEXIS only | Narrow, deep |

The distributor catalogs give **breadth** (many brands, availability, the cross-brand
view). The manufacturer catalogs give **depth** (load tables, full installation
geometry) for two of those brands. They are complementary, not redundant — the
reasoning for that is §3.

### Würth Baer Section B — Concealed Hinges (104 pp)

Euro/concealed-hinge catalog, organised by **brand → closing type → geometry**:

| Brand | Pages | Contents |
|-------|-------|----------|
| **Pro** (Würth house brand) | B-2…B-5 | Self/Soft-close Euro + Face Frame hinges, baseplates, overlay charts. `DSPRO…` |
| **Blum** | B-6…B-44 | The bulk. CLIP top BLUMOTION (soft), CLIP top (self), zero-protrusion, specialty/blind-corner, angled, Onyx black, COMPACT face frame, mounting plates, restriction clips, BLUMOTION devices, TIP-ON, hinge machines, assembly aids. `BP…` |
| **Grass TIOMOS** | B-45…B-66 | Soft/self-close Euro + specialty, wing/thick/inline/face-frame baseplates, TIPMATIC. `GFF…` / `MEM…` |
| **Grass NEXIS** | B-67…B-80 | Self-close & free-swing Euro + specialty, baseplates, face-frame plates, soft-close adapters. `GFNX…` |
| **Grass TIPMATIC / TEC** | B-81…B-91 | Handle-free push systems; TEC 861/872 self-close; hinge machines. |
| **Salice** | B-92…B-104 | Soft/self-close Euro, specialty, AIR hinge system, wing baseplates, face-frame adapters, soft-close adapters, face-frame hinges. `UBC…` |

**Repeating spec fields in the hinge tables** (consistent brand-to-brand):
Item # · opening angle (95/100/105/110/110+/120/125/155°, plus diagonal 45°) ·
overlay class (Full/Half/Inset, with an mm cap) · fixing (Screw-on / Dowel / INSERTA /
EXPANDO / Impresso) · closing type (Soft / Self / Free-swing) · boring pattern
(42 / 45 / 42-45mm) · max door thickness (e.g. up to 26 / 30 / 24 / 22mm) ·
cup depth (e.g. 10.5 / 12mm) · Grass "cranking" code (00/03/9.5/19 ↔ overlay class) ·
certifications (ANSI/BIFMA/KCMA/BHMA) · baseplate height (0/2/4/6mm) + plate fixing.
**No per-hinge load/weight rating, no price.**

### Würth Baer Section C — Lift Systems & Semi-Concealed Hinges (56 pp)

A grab-bag of *other* cabinet hardware, with a **different spec model** (sized by
force/weight, not geometry):

- **Blum AVENTOS** lifts: HF / HS / HL / HK / HK-S / HK-XS, TIP-ON & SERVO-DRIVE,
  accessories, electrical, assembly aids (C-2…C-21)
- **Grass KINVARO** lifters: F-20, L-80, T-65/71/76/57, T-105, D-M, D-S (C-22…C-29)
- **Grass TIOMOS flap hinges** (C-30); **Salice WIND** lift (C-31); **Salice PACTA**
  drop-down hinges (C-32)
- **Lid supports & up/down stays**, chest hinges (C-33…C-37)
- **Counterbalance lifts** — Lift-A-SYST II, Counter-A-SYST (C-38)
- **Institutional hinges** — 5-knuckle, Grass MB barrel, Salice Grade-1 (C-39…C-42)
- **Continuous piano** (C-43) · **SOSS invisible** (C-44…C-45) · **Peter Meier 3-D**
  `CMC…` (C-46) · **demountable/wrap** `AMBPR/AMCM…` (C-47)
- **Face-mount, full-inset, pin/knife (Youngdale), pivot, butt, glass-door, specialty**
  hinges (C-48…C-56)

Spec vocabulary: Power Factor (cabinet height × door weight), door-weight & cabinet-
height ranges, spring color codes, torque rating (lid height × lid weight × ½),
restriction clips, plus per-hinge inch dims / knuckle counts / material gauge /
weight-capacity-per-N-hinges for the traditional styles.

### Grass Tiomos (64 pp) and Grass Nexis (52 pp) — manufacturer catalogs

Single-line, brochure-style: marketing/overview pages, then a model-by-model technical
section. Each model (Tiomos 110/120/155/95/blind-corner/angled…; Nexis equivalents)
gets door-thickness reveal/gap charts, base-plate options, and drilling/installation
diagrams. Critically, both carry a **hinges-per-door load chart** (see §3).

---

## 3. Why the Grass catalogs belong in the corpus (reasoning)

This is the reasoning that widened the scope from two catalogs to four.

**3.1 They cover the same products — verified by part number.** The Grass catalogs are
the manufacturer source for the Tiomos and Nexis lines that Würth Section B also lists.
The part numbers join cleanly: Würth prepends a `GF` distributor prefix to the Grass
number.

| Grass (manufacturer) | Würth Baer (distributor) |
|----------------------|--------------------------|
| `F028138341228`      | `GFF028138341228`        |
| `F017139414228`      | `GFF017139414228`        |

The shared core number (`028138341228`, …) is a clean **join key** across sources.

**3.2 They fill the single biggest gap in the distributor data — load capacity.** The
Würth hinge tables give geometry but no weight rating. Both Grass catalogs publish a
**hinges-per-door chart keyed on door weight × door height**, e.g. Tiomos p47:
`4–6 kg (9–13 lb)` → `7–12 kg (14–26 lb)` → `13–17 kg (27–37 lb)` → `18–22 kg
(38–48 lb)`, with hinge counts of 2/3/4/5 across door heights 500–2450 mm. Nexis p38
carries the equivalent chart. This makes weight-driven questions ("how many hinges for
a 35″, 20 kg door?") answerable — impossible from the Würth corpus alone.

**3.3 They add full installation geometry.** Door thickness (DT), reveal/gap (R/G),
door overlay (OL), door protrusion (DP), hinge setback (X/Z), base-plate height (BPH),
and drilling/screw specs — the engineering detail a distributor roll-up omits.

**3.4 But they overlap, so merging them is a new design problem.** Because the same
SKU now appears in two sources with different wording (and occasionally different
values), the corpus is no longer "a pile of pages" — it's **multi-source**. That forces
three decisions the two-catalog version didn't need: how to **join/dedup** on part
number, how to set **source precedence** when sources disagree, and how to keep
**provenance** so an answer can say *where* a fact came from. These are folded into the
incremental plan (§6, Steps 4a–4c).

**3.5 They extract differently.** The distributor catalog is table-dense; the
manufacturer catalogs are brochure prose **plus** technical pages where the key charts
(including the p47 load chart) are rendered as **diagrams/drawings**. Those pages do
*not* come out as clean text — the load chart extracts as scrambled fragments. So the
manufacturer pages likely need image/layout-aware handling, not just text chunking
(§6, Step 5).

**Conclusion:** include all four. Treat the **distributor catalogs as the breadth/
availability layer** and the **manufacturer catalogs as the deep-spec authority** for
their two brands, joined on part number.

---

## 4. What the raw data actually looks like (and why it matters for RAG)

Observations taken directly from the extracted text layers — these drive every design
choice below.

**Two terms used throughout this section:**

- **Distributor tables** — the product-listing tables in the **Würth Baer** catalogs
  (Sections B and C). Würth Baer is a *distributor* reselling many manufacturers in one
  book, so its pages are dense grids: a caption, column headers (`Item #`, `Opening`,
  `Overlay`, `Fixing`, `Close Type`…), then row after row of part numbers + attributes.
  Broad but shallow (many SKUs, geometry only — **no load rating, no price**). Example
  (Section B, p6):

  ```
  Item #        Opening  Overlay  Fixing    Close Type
  BP71B3550     110°     Full     Screw-On  Soft-Close
  BP71B3580     110°     Full     Dowel     Soft-Close
  BP71B3590     110°     Full     INSERTA   Soft-Close
  ```

- **Manufacturer key charts** — the decisive reference charts in the **Grass**
  (manufacturer) catalogs, which go deep on one product line. The two that matter most —
  and that the distributor catalog does *not* carry — are (1) the **hinges-per-door load
  chart** (door weight band × door height → number of hinges; Tiomos p47 / Nexis p38)
  and (2) the **reveal/gap geometry chart** (door thickness → reveal, gap, overlay,
  protrusion, setback, base-plate height). "Charts," not "tables," because on the page
  they are rendered as **engineering diagrams** — numbers positioned around a drawing of
  the hinge — not as a clean grid.

1. **Distributor tables come out as flat column streams, not rows.** A hinge table
   emits the caption, then `Item #`, then *every* opening angle stacked, then *every*
   overlay stacked, etc. The row binding (which part number has which overlay/fixing)
   is **positional and implicit**. Embedding a page as free text scrambles this — the
   model can no longer tell which spec belongs to which SKU. *This is the central RAG
   problem for the distributor catalogs.*

2. **Manufacturer key charts are embedded as diagrams.** The Grass load/geometry
   charts extract as disordered tokens (numbers and labels detached from their column).
   Text-only chunking will misrepresent them; these pages need layout- or image-aware
   parsing (§3.5).

3. **Per-page boilerplate is heavy.** Würth pages carry an A–Y index rail and a
   `800-289-2237 • WWW.WURTHBAERSUPPLY.COM • WÜRTH BAER SUPPLY` header/footer; Grass
   pages carry `www.grassusa.com` and "Subject to technical modifications" footers.
   All must be stripped pre-chunk or they dilute embeddings and waste budget.

4. **One "product" spans multiple fragments — and now multiple sources.** A hinge
   needs a separate baseplate and optional accessories (restriction clip, soft-close
   adapter, cover cap), listed in adjacent tables; and its deep specs live in a
   *different catalog*. Answering "what do I need to hang this door" requires stitching
   fragments *within* and *across* sources.

5. **Strong, regular key vocabulary + a clean cross-source join key.** Brands, series,
   angles, overlay classes, fixings and boring patterns recur consistently — good for
   metadata filtering and hybrid retrieval — and the shared part-number core (§3.1)
   ties distributor and manufacturer records together.

6. **Numbers carry units in mixed form** — °, ″, mm and inch-fractions together
   ("Up to 7/8″ (22mm)"), ranges ("231 - 470", "13–17 kg (27–37 lb)"), and Unicode
   (°, ″, ↑, •). Extraction must be UTF-8 and unit-aware.

7. **Section C is genuinely heterogeneous.** Lift systems, flap stays, invisible
   hinges and piano hinges share almost no schema; a single rigid record shape won't
   fit.

8. **Source noise / conflict risk.** Carried-through typos, SKUs duplicated across
   spec rows, and — now — the possibility that distributor and manufacturer disagree on
   a value. Answers should cite source + page so a human can verify.

### Recap — the issues at a glance

| # | Issue | Why it breaks naïve RAG | Tier | Addressed by |
|---|-------|-------------------------|:----:|--------------|
| 1 | Distributor tables extract as **flat column streams**, not rows | Spec↔SKU binding is lost → blended/wrong specs | B | Step 2 (row chunking) |
| 2 | Manufacturer **key charts are diagrams** | Load/geometry data extracts as scrambled tokens | B | Step 5 (layout/image extraction) |
| 3 | Heavy **per-page boilerplate** (index rail, phone/URL footers) | Dilutes embeddings, wastes chunk budget | A | Step 0 (clean extraction) |
| 4 | A product **spans many fragments and two sources** | Single-chunk retrieval can't answer "what do I need" | C | Steps 4 + 6 (merge, links) |
| 5 | Regular vocabulary **+ clean part-number join key** | (Asset, not a bug) under-used by pure vector search | A | Steps 3 + 4a (metadata/hybrid, join) |
| 6 | **Mixed units & Unicode** (°, ″, mm/inch, ranges) | Numeric filters/compares unreliable if parsed naïvely | A | Step 0 (UTF-8, unit-aware) |
| 7 | **Section C is heterogeneous** (no shared schema) | One rigid record shape won't fit | C | Step 7 (family-aware shapes) |
| 8 | **Source noise / cross-source conflict** | Typos, dup rows, distributor vs. manufacturer disagreement | C | Steps 4b + 8 (precedence, citation) |

**Bottom line:** the two issues that sink a naïve pipeline are **#1 (rows → columns)** and
**#2 (charts as images)** — they corrupt the data *before retrieval ever runs*. **#4**
and **#8** are the new costs of the four-catalog corpus (stitching + merging across
sources). **#5** is the lever that makes precise retrieval possible.

### Preprocessing vs. query-time

Almost every issue above is an **ingestion-time** problem, not a query-time one. The
right architecture is a **one-time preprocessing pipeline** that turns the four PDFs
into clean, structured, per-product records; once that exists, retrieval is the easy
part. The `Tier` column above sorts the issues by *how cleanly preprocessing solves
them*:

- **Tier A — clean, deterministic preprocessing** (#3, #5, #6). Rule-based ingestion
  hygiene: strip boilerplate, normalise units/Unicode, canonicalise vocabulary, compute
  the part-number join key. Fully reliable, no judgement required.
- **Tier B — preprocessing, but geometry/vision** (#1, #2). Fixed before retrieval, but
  not with text wrangling: reconstruct rows from the PDF's **positional layout**
  (bounding boxes / a table extractor) for the distributor tables; **render + vision-
  model** the handful of manufacturer charts. One-time, but may need per-layout tuning
  (Blum specialty / Salice matrices are messier than Pro).
- **Tier C — preprocessing prepares it; query-time finishes it** (#4, #7, #8).
  Preprocessing builds the records, the join, the relationship links, the family
  schemas, the dedupe and the source-precedence rule — but **stitching companions,
  cross-source comparison, and applying the conflict policy happen per query**.
  Preprocessing makes these tractable; it doesn't complete them. And it cannot invent a
  correct value for a genuine typo — that's a data/policy limit, not a pipeline one.

**Mapping to §6.** The *preprocessing stage* is Steps **0, 2, 4a–b, 5, 7**, plus the
field-extraction in Step 3 and the link-building in Step 6. The *query stage* is the
retrieval/ranking in Step 3, dedup in Step **4c**, link expansion in Step 6, citation
in Step **8**, and the comparison/feasibility behaviours in §5.

**Net:** do Tiers A+B well and you have effectively built a **structured product
database** out of the PDFs — at which point the system shifts from "vector RAG over
scrambled text" toward **structured extraction + hybrid retrieval over clean records**,
which is far more reliable for catalog data. Only the genuinely per-query behaviours
live outside preprocessing.

---

## 5. Query patterns to design for

Retrieval design should be driven by what people will actually ask:

- **Lookup by part number** — "what is `BP71B3580`?" / "`GFF028138341228`?" → exact-match
  retrieval + the full spec row; should resolve a distributor SKU to its manufacturer
  twin.
- **Spec-filtered search** — "soft-close Blum hinge, 110°, full overlay, dowel, 26mm
  door" → metadata/attribute filter, then rank.
- **Weight/capacity feasibility** — "how many hinges for a 35″, 20 kg Tiomos door?" →
  needs the manufacturer load chart (only in the Grass catalogs).
- **Compatibility / completeness** — "which baseplate and clips go with this hinge?" →
  multi-fragment stitching, possibly cross-source.
- **Comparison** — "TIOMOS vs NEXIS soft-close for inset doors" → retrieve across two
  brand sections / sources, align on shared attributes.
- **Lift-system sizing** — "lift mechanism for a 30″ cabinet, 18 lb door?" → Section C,
  range-match against Power Factor / weight tables.
- **Open browse** — "what corner-cabinet options are there?" → broad, recall-oriented.

The first four are where naïve, single-source RAG fails hardest on this data.

---

## 6. Incremental RAG design

Each step is something we can build and test; we only adopt the next step because the
previous one demonstrably breaks on the data above.

### Step 0 — Clean extraction (prerequisite)
UTF-8 extraction; strip the per-source boilerplate (§4.3); keep
`{source, page, section, brand-banner}` provenance on every fragment. Emit a raw,
inspectable intermediate (JSONL per detected block). Nothing downstream beats this layer.

### Step 1 — Naïve baseline: page-as-chunk vector RAG
Embed cleaned page text, top-k retrieve, stuff context. **Expected failures (§4):**
scrambled row↔spec binding → wrong/blended specs; opaque SKUs embed poorly so lookups
miss; multi-fragment questions return one fragment; manufacturer diagram-charts are
noise. Build once as a measured baseline, not the answer.

### Step 2 — Structure-aware chunking: one chunk per product row
Reconstruct table rows during extraction (positional parse re-pairs the stacked
columns). Emit **one chunk per part number**, each a self-contained mini-record
(`part_number, brand, series, opening_angle, overlay, fixing, closing, boring,
max_door_thickness, cup_depth, source, page`) rendered as a compact blurb *and* kept as
structured fields. Fixes the row-binding problem and makes each SKU individually
retrievable. Highest-leverage step.

### Step 3 — Metadata + hybrid retrieval
Attach structured fields as chunk metadata; add a keyword/BM25 channel beside the
vector channel. Spec-filtered queries become *filter-then-rank*; part-number lookups
hit exactly. Folds the regular vocabulary and opaque SKUs into retrieval.

### Step 4 — Multi-source merge (the new work from going to four catalogs)
- **4a — Join on the part-number core.** Normalise the `GF` distributor prefix (§3.1)
  so a distributor record and its manufacturer twin resolve to one logical product.
- **4b — Source precedence + provenance.** Tag every fact with its source; when
  distributor and manufacturer disagree, prefer **manufacturer for specs/load**,
  **distributor for catalog coverage/availability**. Keep both so an answer can cite
  which it used.
- **4c — Dedup at retrieval.** Collapse twin chunks so the LLM doesn't see the same
  hinge twice with conflicting wording; surface the union of attributes with sources.

### Step 5 — Layout/image-aware handling for manufacturer charts
The Grass load and reveal/gap charts (§3.2–3.5) don't survive text extraction. Parse
these pages with layout/table or vision extraction into structured records
(weight-band → hinge-count → door-height; DT → R/G/OL/DP). This is what unlocks the
weight/capacity query pattern.

### Step 6 — Relationship links for stitching
Capture "needs-a-baseplate / compatible-clip / soft-close-adapter / cover-cap"
relationships as explicit links between records (brand+series+geometry are the catalog's
own join keys). Lets retrieval expand from a hinge to its required companions — within
and across sources — instead of returning a lone row. (A light graph layer earns its
keep here; evaluate GraphRAG-style retrieval only if flat metadata expansion is
insufficient.)

### Step 7 — Family-aware handling for Section C
Don't force Section C into the hinge schema. Per-family record shapes (lifts keep Power
Factor / weight-range / spring-code; lid stays keep torque; traditional hinges keep
inch dims / knuckles / capacity). Same chunk-per-product principle, fields differ by
family; metadata carries `family` so retrieval can scope.

### Step 8 — Grounding, citation & evaluation
- Answers **cite source + page + part number** so facts are verifiable against the noisy,
  multi-source corpus (§4.8).
- Build a small **eval set** from §5 (exact-SKU lookup incl. cross-source resolution,
  spec-filter recall, weight feasibility, compatibility completeness, comparison).
  Measure each step against it; that's how we know a step was worth it.

---

## 7. Working hypothesis

- The make-or-break move is **Step 2: chunk per product row with reconstructed fields.**
  The flat-column layout (§4.1) means page-level chunking will always mis-bind specs.
- **Step 3 (metadata + hybrid)** turns the regular vocabulary and opaque part numbers
  from a liability into precise retrieval.
- **Step 4 (multi-source merge)** is the price of the four-catalog corpus, and the
  payoff is breadth (distributor) + depth (manufacturer) under one logical product.
- **Step 5 (chart extraction)** is what makes weight/capacity answerable at all.
- **Step 6 (relationship links)** is what lets the LLM answer *"what's the complete set
  of parts I need?"* rather than describing a single SKU.
- Section C is best treated as **several sub-catalogs**, not one schema.

---

## 8. Open questions

1. **Row reconstruction robustness** — how reliably can the stacked-column distributor
   tables be re-paired into rows across all brand layouts? Spike the messiest pages
   (Blum specialty, Salice baseplate matrices) before committing to Step 2.
2. **Part-number normalisation** — is the `GF`-prefix rule the only distributor→
   manufacturer transform, or do other brands (Blum, Salice) have their own? Confirm
   before relying on the join.
3. **Conflict policy** — when distributor and manufacturer specs disagree, is
   "manufacturer wins for specs" always right, or are there fields (availability,
   packaging) where the distributor is authoritative?
4. **Chart extraction approach** — layout/table parser vs. vision model for the Grass
   diagram pages? Which is reliable enough to trust the load numbers?
5. **Part-number retrieval** — exact index, fuzzy match (typo'd queries), or both?
   Opaque SKUs don't embed well; likely a dedicated lookup path.
6. **How much relationship structure is worth it** — does flat metadata expansion
   (Step 3/4) cover most compatibility questions, or is the explicit link/graph layer
   (Step 6) needed from the start?
7. **Section C granularity** — how many distinct family record shapes before it's
   over-engineered? Group where schemas genuinely overlap.
8. **Eval coverage** — minimum question set that proves the pipeline answers correctly
   (incl. cross-source resolution) without hand-checking every response?

---

## 9. Worked compatibility walkthroughs

Representative journeys a catalog user takes to find **what product works with what** —
written as the manual steps a person would follow, with the pages/data they'd touch.
These are the real shape of the "compatibility / completeness" query pattern (§5), and
each has a checkable answer (final SKU(s) + source pages), so they double as **seeds
for the §8 eval set**.

The common shape: a **funnel of attribute filters** (section → construction → closing →
overlay → thickness → angle → fixing) lands on a part number, then **hops to companion
products** (baseplate, add-on, clip, arm/cover sets), and sometimes **hops to another
catalog** for data the first one doesn't carry (load, drilling).

### 9.1 "Given this cabinet door, what hinges can I use?"

*Door: frameless base cabinet, 18 mm thick, 716 mm tall, ~3.5 kg, full-overlay,
soft-close, ~110° swing.*

1. **Pick the section** — concealed/euro hinge → Würth Baer **Section B** (not C).
2. **Filter by construction** — frameless → "Euro Hinges" tables, *not* Face Frame / COMPACT.
3. **Filter by closing type** — soft-close → Blum **CLIP top BLUMOTION** (B-6) or Grass **TIOMOS Soft-close** (B-45).
4. **Filter by overlay class** — full → "Full" rows (Blum) / "Cranking 00" rows (Tiomos, B-45).
5. **Check door-thickness limit** — 110° CLIP top BLUMOTION = "up to 26 mm" (B-6) → 18 mm passes. (30 mm door → 95° thick-door hinge, B-7.)
6. **Pick opening angle** — standard clearance → 110°. (Roll-out behind door → 155° zero-protrusion, B-8; blind corner → 95° blind-corner, B-9.)
7. **Pick fixing method** — Screw-on / Dowel / INSERTA / EXPANDO.
8. **Land on a part number** — e.g. `BP71B3580` (110°, full, dowel, soft-close).
9. **→ continues into 9.2** (needs a baseplate) **and 9.3** (how many, weight OK?).

*Data touched:* B-6 (or B-45) hinge table + the door-thickness bullet.

### 9.2 "I picked a hinge — which baseplate, and what overlay will I actually get?"

The key two-product pairing: **hinge + baseplate together produce the overlay**, so
neither can be chosen in isolation.

1. From the hinge family go to its **baseplate** pages ("Pro Euro Hinge Baseplates" B-3; "Blum CLIP Mounting Plates" B-19/20; "TIOMOS Wing Base Plates" B-60).
2. **Choose plate height** (0 / 2 / 4 / 6 mm) and **plate fixing** (wood screw / pre-mounted euro screw / split dowel / face-frame adapter — steel or diecast).
3. **Read the overlay chart** to combine them — "Pro Value European Hinge Overlay Charts" (B-4) and the Tiomos charts use `D = overlay (mm)`, `H = baseplate height`, `K = boring distance`: hinge cranking + plate height → resulting overlay/reveal.
4. **Confirm it hits the target overlay**; if not, step plate height up/down and re-read.
5. **Land on the plate part number** — e.g. `DSPRO-2C` (2 mm, cam-adjustable, wood screw).

*Data touched:* baseplate table (height + fixing) **and** the overlay chart on the same spread. Pairing = hinge-cranking × plate-height → overlay.

### 9.3 "How many hinges does this door need, and will they hold the weight?"

The question the **distributor catalog can't answer** (no load rating) — cross to the
**manufacturer** catalog.

1. Note the Würth part number — say Tiomos `GFF028138341228`.
2. **Resolve to the manufacturer number** — drop the `GF` prefix → `F028138341228`.
3. Open **grass-tiomos-catalog.pdf** → **hinges-per-door chart** (p47).
4. **Enter by door height and weight** — 716 mm / ~3.5 kg falls in `4–6 kg (9–13 lb)` → chart gives the **hinge count** (2/3/4/5, scaling with height up to 2450 mm).
5. **(Optional) reveal/gap chart** on the model page (DT → R/G/OL/DP) to confirm gap/reveal for an 18 mm door.

*Data touched:* Tiomos p47 weight-band × door-height → hinge-count chart (Nexis equivalent p38). Cross-source join on the shared part-number core.

### 9.4 "This hinge is self-close only — how do I make it soft-close?"

A pairing where the second product is an **add-on device**, not a baseplate.

1. Confirm the hinge is self-close / free-swing (Blum **CLIP** self-close, B-10; Nexis free-swing, B-67).
2. Go to the matching **add-on**:
   - Blum → "BLUMOTION Soft-Close Devices for Blum Euro Hinges" (B-25–27), incl. EXPANDO variants.
   - Nexis → "Soft-Close Adapters for Nexis Hinges" (B-78/79); the Nexis catalog lists `F069073729225` for 170° wide-angle hinges (p38) — adapter must match the hinge's angle.
3. **Check the match condition** — the adapter/device is specified *for a given hinge angle/series*; verify compatibility.
4. (Related pairing) to **limit** opening angle instead, pick a **restriction clip** — Tiomos 85° `GFF072135751517`; Blum 86° `BP70T3553` — listed against the specific hinge.

*Data touched:* the hinge's own page (which names the compatible clip/adapter) + the accessory table. Compatibility stated as a condition ("for X° / X series hinges").

### 9.5 "Large lift-up wall-cabinet door — what's the full AVENTOS kit?"

A **Section C** journey: selection driven by **force (Power Factor)**, and the answer is
a *bundle of SKUs*, not one product.

1. **Choose the lift type** by application — wall cabinet, lift-up → AVENTOS HF / HL / HK; here HF bi-fold (C-2).
2. **Compute Power Factor = cabinet height × door weight** (formula on the page).
3. **Select the lift-mechanism set** from the PF range — `BP20F2200N5` (85–230), `…2500N5` (471–880), … — which *also tells you how many mechanisms* (1/2/3) the door needs.
4. **Add the mandatory companions** on the same page — **cover set** (`BP20F8000NA`), **telescopic arm set** by cabinet height (`BP20F32000…39000`), **door hardware set** (`BP78Z5530TA8`).
5. **If face-frame**, add the **face-frame mounting bracket set** (`BP20F6001`, C-13).
6. **If powered**, add **SERVO-DRIVE set + power supply** (C-15/C-19) and any **angle-restriction clip** (C-12).

*Data touched:* C-2 (PF → mechanism + qty; cover/arm/hardware sets) + C-12/13/15/19. "Compatibility" here is a checklist of required + optional companions gated on cabinet height, weight, and frame type.
