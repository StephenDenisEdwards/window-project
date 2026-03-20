# Data Extraction Evaluation — Compatibility Rules from Würth Baer Catalogs

## What We Did

Using three publicly available PDF catalogs — the Würth Baer Supply Company Section B (Concealed Hinges, 104 pages), the official Grass Tiomos catalog (64 pages), and the official Grass Nexis catalog (52 pages) — we attempted to extract structured product data and deterministic compatibility rules suitable for a constraint reasoning engine.

Starting from a hand-crafted sample of 15 hinges / 13 plates / 14 rules, we expanded to **53 hinges / 55 plates / 15 rules** across 3 brands (Blum, Grass, Hafele), 6 series, and 8 opening angles (95°–170°).

## What We Could Extract Accurately

### Product attributes (high confidence)

The catalogs are structured product listing documents. The following fields were extractable with high reliability:

- **SKU / item numbers** — both manufacturer part numbers and Würth Baer distributor SKUs. 92% of products now have a `wurth_baer_sku` mapping.
- **Opening angle** — clearly stated per product line (95°, 100°, 107°, 110°, 120°, 125°, 155°, 170°).
- **Application type** — full overlay, half overlay, inset, and the intermediate "overlay" (cranking 03) type.
- **Boring pattern** — 42mm, 45mm, 48mm clearly documented. The Nexis Impresso's dual 42/45mm pattern is noted.
- **Mounting method** — screw-on, dowel, INSERTA, EXPANDO, Impresso (tool-free) all clearly listed per SKU.
- **Soft-close vs self-close** — explicitly stated per product line.
- **Cup diameter** — universally 35mm for all products in these catalogs.
- **Cup depth** — stated in the Grass catalogs (Tiomos 12.6mm, Tiomos 155° 10mm, Nexis 11mm). Blum states 13.5mm in their technical docs.
- **Door thickness range** — stated per product line ("up to 1 inch / 26mm", "up to 36mm for thick door").
- **Mounting plate heights** — 0mm, 2mm, 3mm, 3.5mm, 6mm, 9.5mm, 12mm, 19mm, 21mm plate heights all clearly listed.
- **Plate fixing type and points** — wood screw vs euro screw vs expanding dowel, 2/3/4-point fixing.
- **Series compatibility** — which plate series work with which hinge series is implicit from the catalog structure (Tiomos plates on Tiomos pages, CLIP plates on CLIP pages).

### Constraint rules (mixed confidence)

| Rule | Confidence | Source | Notes |
|------|-----------|--------|-------|
| R001: Brand lock | **High** | Catalog structure | Hinge and plate are always shown within the same manufacturer section |
| R002: Series compatibility | **High** | Catalog structure | Plates are grouped under their compatible hinge series |
| R003: Cabinet type match | **High** | Explicit | Face frame vs frameless clearly separated in catalog |
| R004: Overlay in range | **Medium** | Derived from tables | Overlay ranges come from dimension tables on each catalog page, but require interpreting base plate height + drilling distance combinations |
| R005: Inset support | **High** | Explicit | Inset hinges and plates clearly labelled |
| R006: Door thickness | **High** | Explicit | "For door thicknesses up to X mm" stated per product line |
| R007: Weight limit | **Medium** | Tiomos catalog page 10 | Weight table exists but references "24-inch standard door width" — unclear how to adjust for non-standard widths |
| R008: Hinges per door | **Medium** | Tiomos catalog page 10 | Table provided but is brand-specific. Grass and Blum may use different thresholds. Tiomos flap hinges (page 54) use a completely different table |
| R009: Boring pattern | **High** | Explicit | Clearly stated per hinge: 42mm, 45mm, 48mm |
| R010: Wide angle derating | **Low** | Not found in catalogs | The 25% derating rule is an engineering approximation. The catalogs don't state this as an explicit rule — they simply publish lower max weights for wide-angle models |
| R011: Face frame overlay | **Low** | Domain knowledge | The "overlay ≤ frame width - 3mm" rule is not stated in these catalogs. It may come from Würth's internal sales process document |
| R012: Adjacent door clearance | **Low** | Domain knowledge | Partition thickness constraint is not in these catalogs. This is installation knowledge |
| R013: Corner cabinet angle | **Medium** | Implied | The catalogs don't say "use ≥155° for corner cabinets" explicitly, but the product descriptions for 155° and 170° hinges reference "corner", "bi-fold", and "zero protrusion" use cases |
| R014: Mounting method match | **High** | Catalog structure | Screw-on hinges shown with screw-on/euro screw/system screw plates; dowel hinges with dowel plates |
| R015: Cup depth vs door thickness | **Medium** | Implied | Cup depths are stated, and minimum door thickness is stated, but the "+2mm" rule is our engineering assumption, not explicitly in the catalogs |

## What We Could NOT Extract

### Missing from these catalogs entirely

1. **Prices.** The Würth Baer catalog does not list prices — it's a product reference, not a price list. Only 34% of hinges and 22% of plates have prices (from earlier web scraping of retail sites). The actual Würth Baer pricing would come from their ordering system, not these PDFs.

2. **Explicit compatibility matrices.** No catalog says "hinge X works with plates Y and Z." Compatibility is implicit — you have to infer it from series grouping, cabinet type, and mounting method. We rebuilt `compatible_mounting_plate_skus` programmatically using brand + series + cabinet type + mounting method rules, but this is reconstructed logic, not published data.

3. **Weight capacity per hinge.** The Grass Tiomos catalog (page 10) provides a hinges-per-door table based on door height and weight, but the actual per-hinge weight rating (kg) that we use in R007 is not clearly stated in these catalog PDFs. The values in our data (7.5kg for Blum 110°, 9.0kg for Tiomos 110°, etc.) come from manufacturer spec sheets and retail product listings, not from these catalogs.

4. **The "13 product families" sales process document.** The brief mentions Würth has an internal document covering hinge selection across 13 product families. This is the most critical missing piece. Our catalogs cover concealed European hinges only — one product family. The remaining 12 families (drawer slides, lift systems, locks, handles, etc.) have their own constraint spaces that these catalogs don't touch.

5. **Installation-derived rules (R011, R012).** The face frame overlay constraint and adjacent door clearance rule are practical installation knowledge — the kind of thing a veteran sales rep or installer knows. These are not documented in product catalogs. They'd come from the internal sales process document or SME interviews.

6. **Edge cases and exceptions.** The catalogs describe standard applications. They don't cover: mixed-brand installations (using a Blum hinge with a third-party plate that happens to fit), custom boring distances, non-standard cabinet geometries, or weight derating for specific mounting conditions (e.g., particleboard vs solid wood pull-out resistance).

### Data quality issues discovered during extraction

1. **Overlay ranges required interpretation.** The catalogs present overlay as a function of base plate height (BPH) and drilling distance (DD), published as lookup tables. Converting these into [min, max] ranges per plate required choosing standard drilling distances. Different drilling distances give different overlay ranges — our data uses a single range, which is a simplification.

2. **The "overlay" application type (cranking 03) is ambiguous.** Grass Tiomos has four cranking values (00, 03, 9.5, 19) mapping to full overlay, overlay, half overlay, and inset. "Overlay" (cranking 03) achieves overlays between full and half — roughly 10–19mm depending on plate height. We map this to the plate's "full" overlay range, which is a reasonable approximation but not exact.

3. **Hinge-per-door tables vary by brand.** Grass Tiomos: ≤889mm=2, ≤1422mm=3. Blum: ≤900mm=2, ≤1400mm=3. We use the more conservative Grass thresholds, but a production system might need brand-specific tables, especially for non-standard door materials or widths.

4. **R010 weight derating was an approximation — now removed.** The PoC applied a blanket 25% derating for hinges >120°. In reality, the manufacturer simply publishes a lower max weight for wide-angle models. The derating was already baked into `max_door_weight_kg`, making R010 a double penalty. R010 has been removed; the engine uses `max_door_weight_kg` directly.

5. **Hafele Duomatic data is thin.** We have 2 Hafele hinges and 2 plates with no Würth Baer SKUs, no cup depth, no material data, and no images. Hafele data came from web scraping, not catalog extraction. The Würth Baer Section B catalog covers Blum, Grass, Salice, and Titus — but not Hafele Duomatic. Either Würth Baer doesn't carry Duomatic, or it's in a different catalog section.

6. **41 mounting plates were orphaned after expansion.** We added plates from the catalog (thick plates, inline plates, face frame adapters) but didn't always have matching hinges. After rebuilding compatibility mappings, 10 plates remain orphaned — mostly Grass face frame plates and dowel wing plates without corresponding hinge entries.

## Gap Analysis Against the Work Brief

The brief requires: *"Encode mathematical hinge-to-mounting-plate compatibility logic as deterministic rules... cabinet dimensions, door overlay types, installation constraints, and weight tolerances all have precise relationships that must be represented as structured constraints."*

### What our extraction proves is feasible

- **Product data ingestion from PDF catalogs works.** We extracted 108 products with 15+ structured fields each from 220 pages of PDFs. The data is structured enough to parse programmatically (PyMuPDF text extraction), though it required page-level targeting — not every page is a clean table.

- **Core constraint rules (R001–R006, R009, R014) are derivable from public catalogs.** Brand lock, series compatibility, cabinet type, boring pattern, door thickness, and mounting method are all explicitly or structurally present in the data.

- **The constraint engine architecture works at scale.** With 53 hinges × 55 plates = 2,915 combinations, brute-force evaluation takes <0.3 seconds and produces correct results. At the brief's target of "thousands of SKUs across 13 product families," indexed lookups or pre-computed matrices would be sufficient — a full CSP solver (OR-Tools, Z3) is not needed for this problem size.

### What cannot be extracted from catalogs alone

| Gap | Impact | Likely source |
|-----|--------|---------------|
| Per-hinge weight capacity (kg) | R007 cannot be evaluated | Manufacturer spec sheets, not distributor catalogs |
| Installation rules (R011, R012) | Face frame and partition constraints missing | Würth's internal sales process document, SME interviews |
| ~~Wide-angle derating specifics (R010)~~ | ~~Risk of double-penalising~~ | **RESOLVED** — R010 removed |
| Pricing | Cannot sort by price or calculate per-door cost | Würth's ordering system / ERP, not catalogs |
| The remaining 12 product families | Only concealed European hinges are covered | Additional catalog sections + the internal sales document |
| Overlay as a function of drilling distance | R004 still uses simplified [min, max] ranges | `OverlayTable` model exists with full BPH × DD lookup but R004 uses the legacy `overlay_range_mm` shim. `CustomerRequirements` now accepts `drilling_distance_mm` |

### Recommendations for the engagement

1. **The internal sales process document is the highest-value asset.** It likely contains the installation rules (R011, R012), weight guidelines, and edge cases that catalogs don't publish. Getting access to this document early in Week 1–2 discovery is critical.

2. ~~**Don't build R010 (derating) into the engine.**~~ **DONE** — R010 removed. The engine uses `max_door_weight_kg` directly.

3. **Overlay ranges need drilling distance.** `CustomerRequirements` now accepts `drilling_distance_mm` and the `OverlayTable` model stores full BPH × DD lookup data. However, R004 still evaluates against the simplified `overlay_range_mm` shim rather than the structured table. Wiring R004 to use `OverlayTable.achievable_overlay()` is remaining work.

4. **Plan for brand-specific rule parameters.** The hinge-per-door table, reveal calculations, and overlay formulas differ between Blum and Grass. The engine should support per-brand rule configuration rather than a single set of universal thresholds.

5. **Hafele (or whichever third brand Würth selects) will require separate data sourcing.** The Würth Baer catalog didn't cover Hafele Duomatic. The third Phase 1 brand may have its data in a completely different format.

6. **Budget 40% of Weeks 3–6 for data cleaning, not engine building.** The engine is the easy part — it's ~800 lines of Python across 6 modules. The hard part is validating every overlay range, every weight capacity, every compatible plate SKU against source data. This is the conclusion the original evaluation predicted, and the extraction exercise confirms it.

## Summary

From three publicly available PDF catalogs, we were able to extract **~70% of the data needed** for a production constraint reasoning engine. The core product attributes and structural compatibility rules are well-documented. The remaining 30% — weight capacities, installation-derived rules, pricing, and edge cases — requires access to manufacturer spec sheets, Würth's internal sales documentation, and SME knowledge.

The extraction exercise validates the brief's core thesis: hinge-to-mounting-plate compatibility is a genuine, well-structured constraint satisfaction problem with enough published data to build a deterministic engine. But it also confirms the original evaluation's warning: the hardest part is not the code — it's extracting complete, correct rules from institutional knowledge that lives partly in catalogs, partly in spec sheets, and partly in people's heads.
