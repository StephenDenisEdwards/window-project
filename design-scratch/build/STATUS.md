# Thin build — status

> **⚠️ RESET (taxonomy-first).** The "913 products" DB was found to be **largely garbage** —
> the hand-rolled positional table parser only works on uniform spec tables and merges prose
> into fields on the many non-uniform pages (e.g. the Onyx list put a marketing blurb into a
> part number). The vanity "eval 11/11" only tested ~11 SKUs on the 3 tuned pages, hiding it.
> **That DB is discarded.** New backbone: a trustworthy **product-type taxonomy** built from
> section banners (reliable), not table cells — [`../taxonomy.md`](../taxonomy.md) /
> `taxonomy.json` (`build/taxonomy.py`). Extraction will be **rebuilt type-by-type with a
> hard validation gate** (only clean SKUs; curate the rest). The analysis + data model +
> provenance/UI/curation machinery are kept; the *extraction* is what's being redone. The
> sections below describe the (now superseded) positional-parser build.


> Where the first end-to-end build ([`thin_pipeline.py`](thin_pipeline.py)) currently
> stands. Companions: [`../plan_build_product_db.md`](../plan_build_product_db.md) (plan),
> [`../gap_analysis.md`](../gap_analysis.md) (gaps), [`../weight_model.md`](../weight_model.md)
> (load), [`../eval_set.md`](../eval_set.md) (eval).

## Scope

Catalogs → records → eval over **all of Würth Section B** (104 pp) + the two Grass load charts.

Output: `product_db.json` (gitignored, reproducible) — **913 products** (527 concealed_hinge /
221 baseplate / 94 accessory / 71 **tool**) + **88 quarantined** (rows with no resolvable
part number) + **2 reference tables**. Eval: **11/11**.

**Quality pass — iteration 1 (family routing) done:** add-on components (TIP-ON, BLUMOTION
soft-close devices, restriction clips, adapters) now route to `accessory`; machines /
assembly aids / overlay-chart / drill-bit pages route to a new `tool` family; the Onyx Black
*hinge* line is corrected to `concealed_hinge`; index-rail/callout rows (`F G H I J`, `1 2 3
4`) no longer mis-detected as banners. `unknown` blocks down to ~4 rows (ECOJIG/PLATEMATE
jigs, a Salice adapter).

**Quality pass — iteration 2 (quarantine triage) — diagnosed, not yet fixed:** the 88
quarantined rows cluster on ~6 pages — **Grass TEC (p82–87)** and **Salice face-frame
(p103–104)** — which use a **two-tables-side-by-side** layout. The single-table row binder
conflates the left/right tables (columns double up; the SKU column, here named e.g.
"Side-Mount", only fills where the two sides' rows align), so most rows lose their part
number. They're **recoverable parser misses, not non-products** — recovering them needs
side-by-side table splitting (detect the horizontal gap, parse each half). Next iteration.

> **Attempt + revert (honest):** a gutter-detection splitter (find a vertical empty band,
> parse each side) was tried and **backed out** — it false-positived on the multi-column
> **baseplate matrix** (many SKU columns look like a "gutter" → broke it, eval 8/11) while
> **missing** the actual TEC/Salice pages (their gutter isn't a clean central empty band).
> A simple x-gap heuristic can't distinguish *one multi-column table* from *two side-by-side
> tables*. A better approach: detect a **repeated header-group structure** (e.g. the column
> sequence Item/Boring/Fixing appearing twice) or handle these specific layouts explicitly.
> The 88 remain quarantined for now (no regression shipped).

> **⚠️ Coverage-first, quality pass owed.** The pipeline + heuristics were validated on only
> **3 pages** (B-6/B-45/B-100); they now run over all 104 with no crashes, but the other ~84
> pages are **unvalidated**. So 884 is honest *coverage*, not 884 *verified* records. Known
> follow-ups: (a) **family routing** only knows hinge/baseplate/accessory — pages for hinge
> machines, screws, drivers, TIP-ON devices, assembly aids mis-bin or quarantine; (b) field
> heuristics (brand/series/overlay/cam) tuned on 3 layouts may misfire elsewhere; (c) the
> gap report is now catalog-wide and dominated by unvalidated pages. **Next work is the
> quality pass, not more coverage.** (Section C + the Grass product pages are still out.)

The detailed per-field coverage below was measured on the **3-page pilot** and is kept as an
illustration of *what good looks like* — it needs re-measuring after the quality pass.

## What's in the DB now

**Provenance:** every product carries `_source` + `_page` + **`_bbox`** (the source row's
box, normalized 0..1 fractions of the page). The DB also carries a top-level **`sources`
registry** mapping each `_source` code → its catalog PDF, label, and page-label format — so
`record._source → sources[code].pdf` + `_page` + `_bbox` is a fully resolvable
`(catalog, page, region)` from the JSON alone (e.g. `BP71B3580 → …section-b….pdf, B-6, [bbox]`).
Region-level today; cell-level (per-field) bbox is a later refinement.

**Product photos:** 66/68 products carry a block-level **`_image`** (`{path, source, page,
bbox, scope:"block"}`) — the representative photo extracted from the page's embedded rasters
(logo/icons filtered). Saved to `build/images/` (gitignored, reproducible). Per-block, not
per-SKU; the 2 without are the boring-bit accessories whose block has no photo.

**Reference tables:** `hinges_per_door` for `Grass/TIOMOS` (mm/kg) and `Grass/NEXIS`
(inches/pounds) — both low-confidence vision reads.

**concealed_hinge (30)** — `part_number`, `brand`, `series`, `opening_angle_deg`,
`overlay_class`, `closing_type`, `fixing` all 30/30; `boring_pattern_mm` 16/30,
`max_door_thickness_mm` 14/30, `overlay_max_mm` 12/30 (partials are correct — see below).

**baseplate (35)** — fully populated 35/35: `part_number`, `brand`, `height_mm`,
`plate_style`, `fixing_type`, `material`, `cam_adjustment`, `compatible_hinge_series`.

**accessory (3)** — `part_number`, `brand`, `accessory_type`, `description` 3/3;
`restricts_angle_to_deg` 1/3 (only the restriction clip; correct — bits have no angle).

## Gaps: 194 empty fields, all correctly categorized

```
absent_in_catalog  68   price (1/product) — never in the catalog
not_on_page       124   on other pages (cup_depth, certifications, application,
                        TIOMOS thickness, Blum boring, Blum-110 overlay-mm)
unparsed            0   ← nothing left that's on the page and unextracted
low_confidence      2   the TIOMOS + NEXIS chart cell grids
```

**The actionable (unparsed) backlog is empty.** The partial coverage above is *expected*,
not a defect:
- `opening_angle_deg` 30/30 but `boring_pattern_mm` 16/30 — the two brands put different
  attributes in columns vs. headings (Blum has an Opening column, TIOMOS has a Boring column).
- `overlay_max_mm` 12/30 — only full-overlay hinges have a max overlay; half/inset don't, and
  the Blum-110 block simply doesn't state one (→ `not_on_page`). The Blum 110+ block does
  (→ extracted, 22mm).

## How the gap headline went from "335" to a real picture

| | gaps | note |
|---|---|---|
| initial | "335" | undifferentiated count — looked like chaos |
| removed phantoms | −43 | fields that don't apply (`baseplate.series`, drill-bit restriction angle) |
| dropped per-hinge weight | −30 | not a catalog concept — load is the chart ([`weight_model.md`](../weight_model.md)) |
| classified by reason | — | absent / not-on-page / unparsed / low-confidence |
| closed the 3 unparsed fields | −73 | `compatible_hinge_series`, TIOMOS `opening_angle_deg`, `overlay_max_mm` |
| **now** | **0 unparsed** | every on-page field extracted |

## UI (option C — FastAPI explorer)

[`../ui/app.py`](../ui/app.py) + [`../ui/static/index.html`](../ui/static/index.html): a
split-pane **record ↔ catalog** viewer. Run from the repo root:
`python design-scratch/ui/app.py` → http://localhost:8000. It builds the DB at startup and
serves: `/api/db`, `/api/gaps/{pn}`, `/page/{source}/{n}.png` (rendered catalog page),
`/img/{name}` (product photo). The frontend lets you filter/search products, shows each
one's fields + photo + typed gap badges, and **highlights the exact source row on the
rendered catalog page** via `_source`/`_page`/`_bbox`.

**Human curation (manual gap-filling):** each gap is an editable field — read the value off
the page (shown on the right) and type it in. `POST /api/curate` persists it to a durable,
**committed** `curations.json` overlay (keyed by part-number + field). `build_db` applies
curations on top of extraction as **locked, `source: human`** values (never clobbered by a
re-extraction; shown with a "human" badge), and the gap closes. Survives rebuilds. For
existing products only; quarantined rows (no part number yet) are a later case.

## Reproducibility

`python design-scratch/build/thin_pipeline.py` rebuilds `product_db.json` + `gap_report.json`
from the catalogs. **Tables** are re-extracted from the PDFs each run; the **chart** data is a
stored vision read (re-rendered crop, not re-OCR'd). Both generated JSONs are gitignored.

## Remaining work (sourcing & scale, not extraction bugs)

- **Sourcing gaps** (need documents/decisions, can't be extracted):
  - `price` — not in these catalogs.
  - **Blum & Salice** hinges-per-door charts — no Blum/Salice manufacturer catalog in
    `catalogs/`; the DB correctly *declines* weight-feasibility for them (eval SD3).
- **Low-confidence** — the two chart cell-grids are best-effort vision reads; need human
  verification (or fuller digitization).
- **Scale** — this is 3 pages of ~160; widening to the rest of Section B (and Section C
  families) is volume, not new mechanism.
- **Engine integration** — the deferred weight-model decision (§3 / `weight_model.md`):
  have a constraint engine consume the `hinges_per_door` chart.
