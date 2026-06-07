# Gap analysis — what's missing in the product DB, and why

> Worked analysis from the thin build ([`build/thin_pipeline.py`](build/thin_pipeline.py))
> over Würth Section B (B-6 Blum, B-45 Grass TIOMOS, B-100 Salice) + the Grass TIOMOS p47
> load chart. Companion to the plan's §2.4. **The point: a gap *count* is meaningless
> unless every empty field is classified by *why* it's empty.**

## The four reasons a field is empty

| kind | meaning | remediation | example |
|------|---------|-------------|---------|
| **absent_in_catalog** | the source never carries it (on any page) | external sourcing, or a *should-decline* answer | `price` (all products) |
| **not_on_page** | real data, but printed on *other* pages — not this product's | extract from the right page/source later | `certifications` (live on the Pro pages), `cup_depth_mm` |
| **unparsed** | the data **is** on this product's page; we just didn't pull it | more extractor coverage — **the real to-do** | `compatible_hinge_series`, `overlay_max_mm`, TIOMOS `opening_angle_deg` |
| **low_confidence** | extracted but uncertain (vision read) | human verify | `hinges_per_door` chart cells |

Only **unparsed** is a defect in *this* build. `absent_in_catalog` is correct behaviour;
`not_on_page` is out of this slice's scope; `low_confidence` is the ingestion-model
human-verify path.

## How they're told apart (in `generate_gap_report`)

1. **Conditional per-record expectations** — don't demand fields that don't apply
   (drill *bits* have no restriction angle; baseplates have no `series`). This removes
   phantom gaps at the source.
2. **An evidence probe per field** — does the page's text actually contain the field's
   marker (`"cup depth"`, `ANSI`, `"Series F"`, a degree value)? Evidence present + field
   empty → **unparsed**; evidence absent → **not_on_page**.

## Current state (thin build: 68 products, 3 pages)

**212 empty fields**, classified:

| kind | count | detail |
|------|-------|--------|
| absent_in_catalog | **68** | `price` — one per product. Correct empties. (No per-hinge weight: load is a chart, not a field — see [`weight_model.md`](weight_model.md).) |
| not_on_page | **120** | `cup_depth` 30 · `certifications` 30 · `application` 30 · TIOMOS thickness 16 · Blum boring 14 |
| unparsed (real to-do) | **22** | `overlay_max_mm` 22 (`compatible_hinge_series` 35 and TIOMOS `opening_angle_deg` 16 now extracted) |
| low_confidence | **2** | the TIOMOS + NEXIS `hinges_per_door` cell grids |

The actionable backlog is now **1 field → 1 extractor task** (was 3): `overlay_max_mm`.
`compatible_hinge_series` (prose on B-100) and TIOMOS `opening_angle_deg` (page heading)
have been closed.

## Takeaways

- The original "335 gaps" headline was **mostly noise**: a chunk was phantom expectations
  I'd over-declared — including a **per-hinge weight field that the catalogs don't even
  use** (load is the hinges-per-door chart; see [`weight_model.md`](weight_model.md)) —
  plus data the catalog can never have (price) and data simply not on these pages. After
  removing the phantoms the genuine backlog is **~73 across 3 fields**.
- **A gap report is only useful if it classifies by reason.** An undifferentiated count
  reads as chaos and tells you nothing about what to do.
- **Closed so far:** `compatible_hinge_series` (35, prose on B-100) and TIOMOS
  `opening_angle_deg` (16, page heading). **Remaining actionable: `overlay_max_mm` (22)** —
  the Blum "up to 22mm" lives in a block bullet (needs the block-level bullet pass) plus the
  TIOMOS half/inset rows that have no mm.
- **The persistent honest gaps** (per-hinge weight, price) are exactly the two the plan
  already flags for external sourcing / should-decline — nothing new to invent.
