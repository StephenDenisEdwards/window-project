# Product Extraction — Status & Handoff

_Last updated: 2026-06-10. Snapshot of the catalog→product-database work in `design-scratch/`._

## Goal

Turn the cabinet-hardware catalog PDFs in `catalogs/` into a single, **trustworthy** structured
product database, with a UI to verify every record against its source page. The spine is the
**hinge ↔ baseplate** relationship (every hinge mounts on a plate), which is what makes the data
queryable for compatibility.

## Where we are

**888 products** extracted and verified across **38 / 84** taxonomy sections, all from the
**Würth Baer Section B** catalog (`catalogs/wurth-baer-section-b-concealed-hinges.pdf`).

| product_type | count | | brand | hinge | ff_hinge | baseplate |
|---|--:|---|---|--:|--:|--:|
| concealed_hinge | 588 | | Blum | 175 | 56 | 49 |
| face_frame_hinge | 140 | | Grass | 280 | 0 | 50 |
| baseplate | 160 | | Salice | 120 | 76 | 43 |
| | | | Pro | 13 | 8 | 18 |

**Done:** every euro / specialty / angled / Onyx / face-frame **hinge** line and every
**baseplate** line across all 5 brands in Section B. This is the full hinge↔plate core.

## Key files (all under `design-scratch/`)

| File | What it is |
|---|---|
| `build/extract.py` | All 18 extractors + the `EXTRACTORS` list. Run it to (re)generate `products.json`. |
| `build/products.json` | The product database (gitignored — regenerable). One flat list, each record tagged `product_type` + `section` + provenance (`_source/_page/_bbox`). |
| `build/coverage.py` | Stock-take: taxonomy vs extracted. Run anytime to see done/remaining. |
| `build/extraction_issues.json` | Durable registry of problematic pages (committed). Surfaces in the UI under *Other › Needs Review*. |
| `build/taxonomy_review.json` | Human curation overlay (committed). Currently: B-4 overlay charts → *Other › Charts*. |
| `taxonomy.json` / `taxonomy.md` | The product-type taxonomy (84 sections). Built by `build/taxonomy.py`. |
| `ui/taxonomy_app.py` + `ui/static/taxonomy.html` | The verifier UI (port 8001). Tree: Sections › product_type › section › products; click any node → its JSON + the source page with the bbox highlighted. |
| `spikes/table_extract_spike.py` | `tx` — the shared parse layer (`parse_page`, `emit_hinge`, `strip_callout`, `PDF` path, etc.). |

## How to run

```bash
python design-scratch/build/extract.py        # regenerate products.json (888 products)
python design-scratch/build/coverage.py        # see what's done vs remaining
python design-scratch/ui/taxonomy_app.py       # verifier UI -> http://localhost:8001
```

## Methodology (the rules that keep it trustworthy)

These are the hard-won principles — follow them for every new extractor:

1. **Look before writing.** Inspect each page's `parse_page` structure first; catalogs vary wildly.
2. **Validation gate.** Only emit a record if its SKU is clean (brand-specific regex, uppercase,
   no prose). Quarantine the rest — never emit garbage.
3. **Independent cross-check.** Compare extracted SKUs against the raw page **text layer**
   (`get_text`): **phantom must be 0** (every SKU appears verbatim on its page); **investigate
   every "missed" SKU** — don't assume. This is what catches silent data loss (it caught the TEC
   side-by-side collision, the NEXIS dotted-SKU blindness, the B-15/30/33 dropped rows).
4. **Render-verify.** Draw each record's bbox on the page and look — boxes must sit on real rows,
   accessory tables must NOT be boxed.
5. **Preserve, don't coerce.** Real values that don't fit an enum are kept raw (`overlay_raw`,
   `fixing_raw`) — never silently dropped or forced.
6. **Flag problem pages.** Anything that can't be extracted cleanly → `extraction_issues.json`
   (status open) so the user can review. Don't bury limitations in clean-looking output.
7. **Section comes from the taxonomy** (`_section_for(page)`), not `parse_page`'s per-block banner
   (which can diverge), so every product links to a taxonomy node.

**Two parse modes:** most tables go through `tx.parse_page` (cell parser). Pages it can't read —
side-by-side dual tables (TEC), dot-separated SKUs (NEXIS), multi-SKU-per-cell (Salice FF),
truncated multi-line headers (TIOMOS specialty) — are read **positionally** from the word layer
(`get_text("words")`) using each block's column x-bands. Reach for positional when the cross-check
shows the cell parser losing rows.

## The 18 extractors

| extractor | pages | n | notes |
|---|---|--:|---|
| blum_euro | B-6-15 | 117 | standard Item#/Opening/Overlay/Fixing/Close |
| blum_angled | B-16-17 | 30 | Degree column; series in Close-Type col |
| blum_onyx | B-18 | 30 | prose-embedded -ONYX SKUs; finish=onyx; +5 cover caps deferred |
| blum_baseplate | B-19-21 | 47 | |
| blum_compact_ff | B-30-35 | 56 | face-frame; fractional overlay |
| grass_tiomos | B-45-52 | 116 | overlay in sub-group; cranking |
| grass_tiomos_specialty | B-53-58 | 33 | blind-corner/pie-cut; **positional** title recovery |
| grass_tiomos_baseplate | B-60-62 | 50 | |
| grass_nexis | B-67-70 | 42 | **positional** (dot-separated SKUs); overlay bands + inset angle override |
| grass_tec | B-82-88 | 84 | **positional** (side-by-side dual tables) |
| grass_misc_specialty | B-59/71/73 | 5 | TIOMOS H hidden + NEXIS pie-cut |
| pro_hinge | B-2 | 13 | |
| pro_ff | B-5 | 8 | face-frame |
| pro_baseplate | B-3 | 18 | |
| salice_hinge | B-92-97 | 97 | TIOMOS-style; **positional** overlay bands (1/2" preserved) |
| salice_specialty | B-98-99 | 23 | 4-fixing-column matrix + Salice Air |
| salice_ff | B-103-104 | 76 | **positional**: multi-SKU/cell; fixing decoded from SKU char 4 |
| salice_baseplate | B-100-101 | 43 | SKU matrix |

Adding a type = write one function (verify it), then add it to `EXTRACTORS`.

## Open issues

`build/extraction_issues.json` — 4 total, **1 open**:
- **`parse-page-dropped-rows`** (open): `parse_page` dropped 5 trailing rows — B-15 `BP75T4300`;
  B-30 `BP39C355B25`, `BP39C358B25`; B-33 `BP39C358C24`, `BP39C358C25`. Fix = positional row
  recovery. (3 resolved issues document the TIOMOS header-variant, TEC side-by-side, and TIOMOS
  specialty-title problems and their fixes.)

## What's left (buckets, prioritised)

- **Bucket C — accessories & tools** (~18 sections): restriction clips, BLUMOTION/soft-close
  devices, TIP-ON/Tipmatic, hinge machines, assembly aids. **Needs a modeling decision first**:
  new `accessory`/`tool` product types, or compatibility edges off the hinges? (5 Onyx cover caps
  are already waiting here.)
- **Bucket D — Section C** (26 sections, `catalogs/Wurth_Baer_Section_C.pdf`): lift systems
  (AVENTOS/KINVARO/wind-lift), lid stays, flap/institutional/piano/SOSS/pivot/glass hinges.
  Structurally diverse — biggest lift.
- **Manufacturer-catalog gap**: the standalone Grass TIOMOS (64pp) and NEXIS (52pp) catalogs are
  almost unmapped in the taxonomy (0 and 1 sections) — everything so far is from the Würth
  *distributor* catalog. Mapping them would unlock the manufacturer **load/weight key charts**
  (hinges-per-door). Needs taxonomy work first.
- **Loose ends**: recover the 5 dropped rows (closes the open issue); decide whether finish
  variants (Onyx, Air) should be separate SKUs or a finish overlay on a base part.

## Conventions

- Trunk-based: commit straight to `master`, push, no PRs. Commit prefixes `feat:`/`fix:`/`chore:`.
- `products.json`, `gap_report.json`, `_verify_*.png` are gitignored (regenerable).
  `extraction_issues.json` and `taxonomy_review.json` are committed (durable curation).
