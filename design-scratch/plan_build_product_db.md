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

### Non-goals (for now)
- Not a pricing or availability system.
- Not a fully-normalized schema covering every family on day one.
- Not inventing specs the catalogs don't state.
- Not the retrieval/LLM application itself — this plan builds the database that app sits on.

---

## 2. Plan

*(to be iterated — next we'll work through extraction approach per tier, the family
schema definitions, the join/merge + provenance model, validation, and the eval
harness.)*
