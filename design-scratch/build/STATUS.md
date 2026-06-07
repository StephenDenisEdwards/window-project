# Thin build — status

> Where the first end-to-end build ([`thin_pipeline.py`](thin_pipeline.py)) currently
> stands. Companions: [`../plan_build_product_db.md`](../plan_build_product_db.md) (plan),
> [`../gap_analysis.md`](../gap_analysis.md) (gaps), [`../weight_model.md`](../weight_model.md)
> (load), [`../eval_set.md`](../eval_set.md) (eval).

## Scope

Catalogs → records → eval, over a deliberately thin slice:

- **Würth Section B** pages **B-6** (Blum), **B-45** (Grass TIOMOS), **B-100** (Salice baseplates)
- **Grass TIOMOS p47** + **Grass NEXIS p8** load charts

Output: `product_db.json` (gitignored, reproducible) — **68 products** + **2 reference tables**.
`gap_report.json` — the typed gap queue. Eval: **11/11**.

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
