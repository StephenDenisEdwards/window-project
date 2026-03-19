# Catalog Integration — Ingesting Würth's Product Data into the Knowledge Foundation

## Problem Statement

The constraint engine requires a complete, correct, and structured knowledge foundation. Currently, 53 hinges and 55 mounting plates are loaded from hand-curated flat JSON files (`sample-data/hinges.json`, `sample-data/mounting_plates.json`). This data was extracted from four PDF catalogs and supplemented with web-scraped manufacturer specs. It covers approximately 70% of what's needed for the concealed hinge product family alone.

The remaining 30% — authoritative weight capacities, installation-derived constraint rules, distributor pricing, and the other 12 product families in Würth's catalog — requires sources that don't exist in these PDFs. This document defines what needs to be ingested, where it comes from, what's blocking, and how the ingestion pipeline should be built.

## Three Tiers of Knowledge

Product knowledge for the constraint engine breaks into three tiers, each with different extraction difficulty, confidence levels, and data sources.

### Tier 1: Structured Product Attributes

**Confidence:** High — directly extractable from catalogs.

These are the physical facts about each product: dimensions, materials, capacities, and categorizations. They are explicitly stated in manufacturer catalogs and distributor listings.

| Attribute | Current coverage | Source |
|-----------|-----------------|--------|
| SKU / part numbers (manufacturer + distributor) | 92% have `wurth_baer_sku` | Würth Baer Section B & C catalogs |
| Opening angle | 100% | Catalog product listings |
| Application type (full/half/inset/overlay) | 100% | Catalog product listings |
| Boring pattern (42mm, 45mm, 48mm) | 100% | Catalog product listings |
| Mounting method | 100% | Catalog product listings |
| Soft-close vs self-close | 100% | Catalog product listings |
| Cup diameter / cup depth | 100% / 85% (Hafele missing) | Grass catalogs, Blum tech docs |
| Door thickness range | 100% | Catalog product listings |
| Plate height, material, fixing points | 100% / 90% / 85% | Catalog dimension tables |
| Series grouping | 100% | Implicit from catalog structure |

**Status:** Done for the current 108 products. Scaling to the full Würth catalog requires the same extraction process applied to additional catalog sections and manufacturers.

**What carries over to new product families:** The extraction approach (PDF → structured fields → Pydantic models) and the identity architecture (`ManufacturerProduct` → `DistributorSKU`). The specific attributes change per family.

### Tier 2: Compatibility Tables and Technical Specifications

**Confidence:** Medium — requires interpretation or authoritative manufacturer sources.

These are the quantitative relationships between products and parameters that the constraint rules evaluate against. They exist in catalogs but require domain interpretation to extract correctly.

| Data | Current state | Gap | Authoritative source |
|------|---------------|-----|---------------------|
| Overlay lookup tables (BPH × DD → overlay mm) | `OverlayTable` model exists with synthetic min/max entries | Real per-plate BPH × DD entries not yet populated | Catalog dimension tables (per plate page) |
| Per-hinge weight capacity (kg) | Values from retail sites; 34% coverage for pricing | Not stated in distributor catalogs | Manufacturer spec sheets (Blum TechDoc, Grass TechSpec) |
| Hinges-per-door thresholds | Hardcoded `DEFAULT_HEIGHT_THRESHOLDS`; Grass and Blum differ | Brand-specific tables not parameterised | Grass Tiomos catalog p.10; Blum planning guide |
| Mounting method compatibility matrix | `MOUNTING_METHOD_COMPAT` dict in `rules.py` | INSERTA, EXPANDO, Impresso not fully mapped | Manufacturer installation guides |
| Plate ↔ hinge series compatibility | `compatible_hinge_series` on each plate | Derived from catalog grouping — generally accurate | Manufacturer cross-reference charts |

**Key remaining work:**

1. **Overlay tables:** The `OverlayTable` model and `achievable_overlay()` method are production-ready. The data is not. Each plate page in the Grass Tiomos catalog publishes a table of BPH × DD → overlay values. These need to be extracted per plate and stored as `OverlayEntry` lists, replacing the synthetic entries that `_convert_overlay_range()` in `loader.py` currently generates. Once populated, R004 should call `OverlayTable.achievable_overlay()` directly instead of the legacy `overlay_range_mm` shim.

2. **Weight capacities:** The per-hinge `max_door_weight_kg` values in the current data come from a mix of retail product listings and manufacturer web pages. For production, these should be sourced from authoritative manufacturer specification sheets with clear provenance.

3. **Brand-specific rule parameters:** The `hinges_per_door()` function in `rules.py` accepts optional thresholds but they're never passed — `DEFAULT_HEIGHT_THRESHOLDS` is always used. Grass Tiomos uses ≤889mm→2, ≤1422mm→3. Blum uses ≤900mm→2, ≤1400mm→3. A brand-parameter registry keyed by manufacturer/series should feed the correct thresholds at evaluation time.

### Tier 3: Institutional and SME Knowledge

**Confidence:** Low — not documented in any catalog. Lives in veteran sales reps' heads.

These are the installation-derived rules, edge cases, and practical constraints that professional users rely on but that no product catalog publishes.

| Knowledge | Current state | Why it matters |
|-----------|---------------|----------------|
| Face frame overlay ≤ frame_width − 3mm (R011) | Hardcoded approximation | Incorrect overlay on face-frame cabinets causes binding |
| Adjacent door clearance / partition thickness (R012) | Hardcoded approximation | Adjacent doors that overlap a partition don't open |
| Corner cabinet → ≥155° angle (R013) | Coded from implied catalog language | Explicit SME confirmation needed |
| Material-specific pull-out resistance | Not modelled | Particleboard screws vs solid wood have different hold |
| Non-standard cabinet geometries | Not modelled | Angled cabinets, curved doors, glass doors |
| Mixed-brand installation viability | Excluded by R001 brand lock | Some cross-brand combinations work in practice |
| The "13 product families" sales process | Not available | Covers drawer slides, lift systems, handles, locks, lighting, etc. |

**The internal sales process document is the single highest-value missing asset.** It is referenced in the project brief as covering hinge selection across 13 product families. It likely contains the installation rules, weight guidelines, edge cases, and product family constraint logic that catalogs don't publish. Access to this document is a prerequisite for extending beyond concealed hinges.

**Structured SME capture:** For institutional knowledge that isn't documented anywhere, a structured interview process is needed:

- "Given [scenario], what would you recommend and why?"
- "What configurations have you seen fail in the field?"
- "What rules do you apply that aren't in any catalog?"
- "Where do the catalogs mislead or omit important information?"

Output: rule candidates with confidence levels, source attribution, and test scenarios for validation.

## Current Data Flow

```
sample-data/hinges.json          sample-data/mounting_plates.json
         │                                    │
         └────────────┬───────────────────────┘
                      │
              engine_v1/loader.py
              load_from_json()
                      │
          ┌───────────┼───────────┐
          │           │           │
    Enum validation   │    _convert_overlay_range()
    (HingeSeries,     │    (simplified [min,max] →
     ApplicationType, │     synthetic OverlayTable)
     MountingMethod,  │
     etc.)            │
          └───────────┼───────────┘
                      │
                      ▼
        list[ConcealedHinge], list[MountingPlate]
                      │
                      ▼
            HingeConstraintEngine(hinges, plates)
```

**Limitations of this flow:**
- No validation beyond Pydantic type checking — missing fields, out-of-range values, and orphaned products are not flagged
- No diff reporting — when data changes, there's no visibility into what changed
- No staging — raw extracted data goes directly into the engine
- No provenance — no record of which catalog page or spec sheet a value came from
- Single format — only reads the PoC JSON schema; no support for CSV, API feeds, or alternative extraction output

## Target Ingestion Architecture

```
┌──────────────────────────────────────────────────────────┐
│                      SOURCE LAYER                         │
├────────────────┬────────────────┬─────────────────────────┤
│  PDF Catalogs  │  Spec Sheets   │  SME Documentation      │
│  (Würth Baer   │  (Blum TechDoc,│  (internal sales doc,   │
│   B & C, Grass │   Grass Tech,  │   interview transcripts,│
│   Tiomos/Nexis)│   Hafele specs)│   field validation)     │
├────────────────┼────────────────┼─────────────────────────┤
│  Price Feeds   │  Inventory API │  Catalog Updates        │
│  (Würth ERP)   │  (stock status)│  (new/discontinued SKUs)│
└────────┬───────┴────────┬───────┴──────────┬──────────────┘
         │                │                  │
         ▼                ▼                  ▼
┌──────────────────────────────────────────────────────────┐
│              PARSER LAYER (per-brand, per-format)         │
│                                                           │
│  BlumParser    GrassParser    HafeleParser    SMEParser   │
│  (PDF/CSV)     (PDF/CSV)      (PDF/CSV)       (JSON)     │
│                                                           │
│  Each parser outputs a common intermediate format:        │
│  list[dict] with canonical field names                    │
└──────────────────────────┬───────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────┐
│                    NORMALIZATION                           │
│                                                           │
│  • Imperial → metric (inches → mm, lbs → kg)             │
│  • Field mapping to canonical names                       │
│  • Enum validation against engine_v1/enums.py               │
│  • manufacturer_part as canonical identity                │
│  • DistributorSKU per brand (Würth Baer, Louis, Wood)    │
│  • OverlayTable population from full BPH × DD tables     │
└──────────────────────────┬───────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────┐
│                     VALIDATION                            │
│                                                           │
│  Required fields:                                         │
│    manufacturer_part, manufacturer, series, application,  │
│    opening_angle_deg, boring_pattern_mm, mounting_method, │
│    door_thickness_range, max_door_weight_kg, cabinet_type │
│                                                           │
│  Range checks:                                            │
│    opening_angle_deg ∈ [0, 360]                          │
│    max_door_weight_kg > 0                                │
│    cup_diameter_mm ∈ {26, 35, 40}                        │
│    boring_pattern_mm ∈ {42, 45, 48}                      │
│    door_thickness_min < door_thickness_max                │
│                                                           │
│  Referential integrity:                                   │
│    Every plate.compatible_hinge_series has ≥1 hinge match │
│    Every hinge series has ≥1 compatible plate             │
│                                                           │
│  Orphan detection:                                        │
│    Flag plates with no compatible hinges                  │
│    Flag hinges with no compatible plates                  │
│                                                           │
│  Diff report:                                             │
│    New products, changed fields, removed products         │
│    vs current production data                             │
└──────────────────────────┬───────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────┐
│              STAGING → REVIEW → PRODUCTION                │
│                                                           │
│  Staging: validated data written to staging store         │
│  Review: human inspection of diff report + quality flags  │
│  SME sign-off: domain expert validates new/changed rules  │
│  Production: versioned deployment with audit trail        │
│                                                           │
│  Each production version is immutable and timestamped.    │
│  Rolling back = pointing to a previous version.           │
└──────────────────────────────────────────────────────────┘
```

## Parser Design — Per-Brand Strategy

The three manufacturers in scope have fundamentally different catalog structures. A single generic parser will break. Each brand needs its own extraction logic that outputs a common intermediate format.

### Grass (reference implementation)

**Source:** Tiomos catalog (64pp), Nexis catalog (52pp). Best-structured of the three — clean product tables, explicit overlay dimension tables, weight tables on p.10.

**Extraction approach:**
- Page-level targeting with PyMuPDF text extraction
- Product listing pages: SKU, application, angle, mounting method
- Dimension table pages: BPH × DD → overlay entries per plate
- Weight table (Tiomos p.10): door height × weight → hinges per door

**Why start here:** Cleanest data, most complete overlay tables, two distinct series (Tiomos and Nexis) that exercise series-level separation.

### Blum

**Source:** Würth Baer Section B (104pp covering all brands, Blum section ~30pp). Blum's own TechDoc PDF available from blum.com.

**Extraction approach:**
- Würth Baer Section B: SKU mappings (`BP71B3550` → `71B3550`), product listings, image references
- Blum TechDoc: precise weight capacities, hinge-per-door thresholds, cup depth, boring distances
- Two sources must be cross-referenced: Würth catalog for SKU identity, Blum TechDoc for engineering specs

**Complication:** Blum has the most complex series hierarchy (CLIP top BLUMOTION, CLIP top, CLIP — same physical hinge, different dampening). The parser needs to handle series variants that share dimensions but differ on soft-close capability.

### Hafele

**Source:** No Hafele-specific catalog in the repo. Current data (2 hinges, 2 plates) came from web scraping with no Würth Baer SKUs, no cup depth, and no material data.

**Status:** Data is thin and unverified. Either Würth Baer doesn't carry Hafele Duomatic, or it's in a catalog section we don't have. The third Phase 1 brand may require completely separate data sourcing.

**Action:** Confirm whether Hafele is actually in Würth's catalog. If not, identify the actual third brand (Salice and Titus appear in Section B).

## Data Quality — Known Issues

Issues discovered during the initial extraction that the ingestion pipeline must handle:

| Issue | Impact | Resolution |
|-------|--------|------------|
| Overlay ranges are simplified to [min, max] | R004 evaluates against a range instead of exact BPH × DD lookup | Populate real `OverlayEntry` lists from catalog dimension tables |
| "Overlay" application type (Tiomos cranking 03) is ambiguous | Maps to full overlay range — not exact | Need Grass-specific overlay formula or explicit table |
| Weight capacities from retail sites, not manufacturer specs | May be incorrect or inconsistent | Source from authoritative manufacturer spec sheets |
| Hinges-per-door thresholds hardcoded as single default | Grass and Blum thresholds differ by 11mm (889 vs 900) | Parameterise per brand/series |
| Hafele data has no Würth Baer SKUs or cup depth | Cannot be recommended or fully evaluated | Requires separate data sourcing or exclusion |
| 10 mounting plates orphaned (no matching hinges) | Wasted evaluation cycles; confusing when inspected | Referential integrity check in validation layer |
| 34% hinge / 22% plate price coverage | Cannot sort by price for most configurations | Separate price feed from Würth ERP |
| Imperial/metric inconsistency in source documents | Potential unit errors | Normalisation layer with explicit unit conversion |

## Price Integration

Pricing is architecturally separated from product data — already implemented via `DistributorSKU`. The constraint engine evaluates compatibility without prices. Pricing is applied as a post-sort layer.

**Current state:** Only 34% of hinges and 22% of plates have `price_usd` values, scraped from retail sites. These are not Würth's actual distributor prices.

**Target:**
- Price feed from Würth's ERP/ordering system, updated independently of product catalog changes
- Per-brand pricing (same Blum hinge may have different prices at Würth Baer vs Würth Louis)
- Customer-tier pricing if applicable (contractor vs retail)
- The engine remains correct regardless of pricing data availability — missing prices sort to the end, not excluded

**Integration point:** `DistributorSKU.price_usd` is already nullable. The solver's sort in `solve()` handles `None` prices gracefully (they sort after priced items). No engine changes needed for price feed integration — only a data loading path.

## Overlay Table — Closing the Gap

The overlay simplification is the largest known data quality issue affecting recommendation correctness.

**Current state (simplified):**
```python
# In sample-data/mounting_plates.json:
"overlay_range_mm": {"full": [14, 20], "half": [3, 9], "inset": true}

# loader.py converts to synthetic OverlayTable entries:
OverlayEntry(bph=0, dd=3.0, overlay=14.0)  # min
OverlayEntry(bph=0, dd=7.0, overlay=20.0)  # max
```

**Target state (full lookup):**
```python
# Real data from Grass Tiomos catalog dimension table:
OverlayTable(entries={
    ApplicationType.FULL_OVERLAY: [
        OverlayEntry(bph=0, dd=3.0, overlay=20.5),
        OverlayEntry(bph=0, dd=5.0, overlay=18.5),
        OverlayEntry(bph=0, dd=7.0, overlay=16.5),
        OverlayEntry(bph=3, dd=3.0, overlay=17.5),
        OverlayEntry(bph=3, dd=5.0, overlay=15.5),
        OverlayEntry(bph=3, dd=7.0, overlay=13.5),
        # ... full table
    ],
    ApplicationType.HALF_OVERLAY: [ ... ],
})
```

**What this enables:**
- R004 calls `plate.overlay_table.achievable_overlay(app, drilling_distance)` for exact match
- Professional users who specify drilling distance get precise overlay confirmation
- Guided discovery users get range-based evaluation (existing behaviour preserved via `overlay_range()`)

**Remaining code change:** Wire R004 in `rules.py` to call `achievable_overlay()` when `requirements.drilling_distance_mm` is provided, falling back to `overlay_range()` when it's not.

## Extension to Additional Product Families

The constraint engine architecture — data-driven product models, rule evaluation, indexed search, configuration output with full trace — is designed to extend beyond concealed hinges.

### What carries across all families

- `ManufacturerProduct` → `DistributorSKU` identity model
- `RuleResult` with category, values_compared, remediation
- `HingeConstraintEngine` evaluation loop (generalised to `ConstraintEngine`)
- Ingestion pipeline: parser → normalise → validate → stage → production
- Testing framework: unit + golden scenarios + SME validation

### What changes per family

| Product family | New models needed | Constraint type | Estimated complexity |
|---------------|-------------------|-----------------|---------------------|
| Drawer slides | `DrawerSlide`, `DrawerSlideRequirements` | Length × cabinet depth × weight × extension type | Similar to hinges |
| Lift systems (AVENTOS) | `LiftSystem`, `LiftRequirements` | Door height × weight × power factor calculation | More complex — power factor is a non-trivial formula |
| Handles / knobs | `Handle`, `HandleRequirements` | Bore spacing × door thickness × aesthetic | Simpler — fewer hard constraints |
| Locks | `Lock`, `LockRequirements` | Backset × door thickness × function | Simpler |
| Lighting | `CabinetLight`, `LightingRequirements` | Voltage × length × driver compatibility | Different constraint domain |

**The internal sales process document is the gate.** Without it, each new product family requires a from-scratch discovery process with SME interviews to identify the constraint rules. With it, the constraint space for each family is pre-mapped and the engineering work becomes structured extraction rather than domain exploration.

## Implementation Sequence

### Phase 1: Validation layer (immediate)

Build a validation module between raw data and the engine. Even before replacing JSON or building parsers, this catches data quality issues in the current dataset.

- Validate all fields against Pydantic model constraints and enum values
- Check referential integrity (plates ↔ hinges)
- Flag orphaned products, missing fields, out-of-range values
- Generate a data quality report

### Phase 2: Real overlay table population

Extract full BPH × DD → overlay tables from catalog dimension pages. Start with Grass Tiomos (cleanest source). Wire R004 to use `achievable_overlay()` when drilling distance is provided.

### Phase 3: Per-brand parsers

Build structured extraction for Grass (reference), then Blum (cross-referencing Würth catalog + TechDoc), then the confirmed third brand. Each parser outputs the common intermediate format consumed by the normalisation layer.

### Phase 4: Price feed integration

Connect to Würth's pricing source (format TBD — likely ERP export or API). Map prices to `DistributorSKU` entries per brand. No engine changes needed.

### Phase 5: Database migration

Move from flat JSON to PostgreSQL with versioned product data, audit trail, and diff reporting. This enables the staging → review → production workflow.

### Phase 6: Additional product families

Contingent on access to the internal sales process document. Each family follows the same pipeline: define models → extract data → encode rules → validate with SME → deploy.

## Dependencies and Blockers

| Blocker | Impact | Owner |
|---------|--------|-------|
| Internal sales process document not available | Cannot extend beyond concealed hinges; installation rules (R011, R012) unvalidated | Würth stakeholder |
| Hafele data sourcing unclear | Third brand may need complete re-sourcing | Confirm with Würth which brands are in scope |
| Würth ERP pricing format unknown | Cannot integrate real pricing | Würth technical contact |
| SME availability for validation | Cannot confirm installation-derived rules or edge cases | Würth sales team |
| Würth Louis / Würth Wood catalog access | Cannot map distributor SKUs for brands 2 and 3 | Würth stakeholder |
