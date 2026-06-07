# Data model (v2 — taxonomy-driven)

> Reworked from [`taxonomy.md`](taxonomy.md) (the 21 product types), and **supersedes the
> §2.1 schema** in `plan_build_product_db.md` — that one was derived from 3 pages and only
> covered 3 families. This is the spec the rebuilt extraction targets; nothing here is
> implemented yet.

## What changed from v1 (and why)

| v1 problem | v2 fix |
|---|---|
| Only `concealed_hinge`/`baseplate`/`accessory` (3 of 21 types) | Every taxonomy type has a home — **7 families** with type discriminators (below) |
| Documented per-field wrapper, but build used flat records — never reconciled | **One provenance model, implementable**: flat fields + record-level provenance + a sparse `_meta` for the few special fields |
| Identity = digit-run of SKU (`BP71B3580→713550`), collision-prone | **`part_number` as printed is the key**; cross-source linking is an explicit merge → `aliases`, not a fragile derived core |
| Finish / handing / variants / price / distributor-vs-manufacturer unmodeled | First-class **commercial & variant** fields |
| Reference tables & edges named but never specified | Concrete **reference-table** and **edge** shapes |

## 1. Identity & cross-source

- **A *listing* is unique per `(source, part_number)`** — the same product can be listed in
  several catalogs/sections; each listing carries its own provenance.
- **A *product* groups listings of the same real item.** `product_id` = the **manufacturer
  part number** (normalized) when known, else `"{source}:{part_number}"`. Distributor↔
  manufacturer linking (e.g. Würth `GFF028138341228` ↔ Grass `F028138341228`) is done in an
  explicit **merge step** and recorded as `aliases` — never via a lossy derived key.

## 2. Provenance (one model)

Flat, typed fields. Provenance is **record-level by default**, with a **sparse per-field
override** only where needed:

```
product = {
  ...identity + commercial + type-specific fields (flat, typed)...,
  listings: [ {source, page, bbox, sku} ],     # where it appears (>=1); [0] = primary
  aliases:  [ {source, sku} ],                  # same product, other SKUs (merge output)
  _meta:    { <field>: {source?, confidence?, locked?, by?} },  # ONLY for curated / low-conf
                                                #   / cross-source-merged fields
  state: partial | complete | quarantined,
  gaps:  [ ... ],                               # §2.4 typed gaps
}
```

A field's provenance = the **primary listing** unless it has a `_meta` entry. Curated
(human) values, low-confidence (vision-read) values, and values merged from a non-primary
source are the only ones that carry `_meta`. This keeps 95% of fields plain scalars while
still supporting curation, confidence, conflict, and locking.

## 3. Common product base (all types)

| field | type | notes |
|-------|------|-------|
| `product_id` | string | manufacturer PN if known, else `source:part_number` |
| `part_number` | string | as printed (primary listing) |
| `brand` | enum | Blum, Grass, Salice, Pro, SOSS, Youngdale, Peter Meier, … |
| `family` | enum | hinge \| baseplate \| accessory \| tool \| lift_system \| lift_accessory \| lid_stay |
| `product_type` | enum | the taxonomy type (e.g. `piano_hinge`) — discriminator within family |
| `series` | string | CLIP top BLUMOTION, TIOMOS, NEXIS, … (where applicable) |
| `description` | string | the catalog description line (raw) |
| `finish` | enum/str | nickel, onyx_black, dull_chrome, … (nullable) |
| `handing` | enum | none \| left \| right |
| `packaging_qty` | number | box / PU (nullable) |
| `price` | number | nullable — **not in these catalogs** (sourcing gap) |

## 4. Families & type-specific fields

### hinge (family)
A **hinge base** + per-type extensions (the hinge types differ too much for one flat set).

**Base** (euro/concealed, face-frame, angled, blind-corner, zero-protrusion, onyx, flap):
`opening_angle_deg` · `overlay_class {full,half,inset}` · `overlay_max_mm` ·
`door_thickness_min_mm`/`max_mm` · `closing_type {soft,self,free,push}` ·
`soft_close_integrated` · `mounting {screw_on,dowel,inserta,expando,impresso,…}` ·
`boring_pattern_mm` · `cup_depth_mm` · `cabinet_type {frameless,face_frame}` ·
`application {standard,blind_corner,angled_30,angled_45,zero_protrusion,narrow_aluminum,thick_door}` ·
`certifications[]` · `requires_baseplate` · (load via `hinges_per_door` ref).

**Extensions** (these types carry their own key fields instead of/atop the base):
- `piano_hinge` — `length_in`, `open_width_in`, `gauge`, `material`, `screw_size`, `hole_spacing_in`
- `invisible_hinge` (SOSS) — `soss_size`, `dims{A..I}`, `min_door_thickness`, `opening_angle`, `weight_per_n` (capacity per N hinges)
- `institutional_hinge` — `knuckle_count`, `barrel_height`, `material_thickness`, `bhma_grade`, `door_thickness`, `overlay`/`inset`
- `glass_door_hinge` — `glass_thickness_range`, `opening_angle`, `mount {side,top,bottom}`, `max_glass_weight`, `max_glass_size`
- `pivot_hinge` / `butt_hinge` — `door_thickness_range`, `max_door_weight`, `length`, `mount`
- `face_mount_hinge` / `full_inset_hinge` / `wrap_demountable_hinge` — `overlay`/`inset`, `wrap {partial,full}`, `tip_style`, `duty`
- `adjustable_3d_hinge` — `size`, `weight_per_n`, `opening_angle`, `adjustment{x,y,z}`
- `flap_hinge` — `flap_thickness_range`, `opening_angle`, `cup_depth`, `compatible_flap_stay`

### baseplate
`height_mm` · `plate_style {wing,cam_adjustable_wing,straight,thick,inline,face_frame_adapter_steel,face_frame_adapter_diecast,cruciform}` · `fixing_type {wood_screw,premounted_euro_screw,split_dowel,expando}` · `material {stamped_steel,die_cast_steel}` · `cam_adjustment {none,single,two}` · `compatible_hinge_series[]` · `adjustment{height,depth,side}`

### accessory  (discriminator `accessory_type`)
`restriction_clip` → `restricts_angle_to_deg`, `for_series[]` · `soft_close_device`/`soft_close_adapter` → `for_series[]`, `for_angle_deg[]` · `cover_cap` → `color`, `for_series[]` · `push_mechanism` (TIP-ON/TIPMATIC) → `mechanism`, `door_size_range`, `finish` · `hinge_screw` → `length`, `gauge`, `drive`, `finish` · plus `for_product[]` edges.

### tool  (discriminator `tool_type`)
`boring_machine` / `machine_accessory` / `assembly_aid` / `drill_bit` / `template` / `vix_bit` — `tool_type`, `description`, `fits[]`. (Overlay-chart pages are **reference data, not products** — see §5.)

### lift_system  (AVENTOS / KINVARO / WIND / PACTA)
`system {aventos_hf,aventos_hs,aventos_hl,aventos_hk,aventos_hks,aventos_hkxs,kinvaro_*,wind,pacta}` · `component_role {lift_mechanism,cover_set,arm_set,mounting_plate,hardware_set,full_set}` · `power_factor_min`/`max` · `door_weight_min`/`max` · `cabinet_height_min`/`max` · `opening_angle` · `spring_code` · `servo_drive_compatible`. (Selection via a `lift_selection` ref table.)

### lift_accessory
`type {servo_drive,power_supply,restriction_clip,stabilizer_rod,face_frame_bracket,template}` · `for_system[]`.

### lid_stay  (lid supports / up- & down-stays / counterbalance)
`stay_type {up_stay,down_stay,lid_support,counterbalance}` · `duty {light,medium,heavy}` · `torque_rating` · `handing` · `opening_angle` · `soft_close` · `cycles` · `door_height_range` · `door_weight_range`. (Selection via a `lid_torque` ref table.)

## 5. Reference tables (series/family-level lookups — NOT products)

Keyed, looked up at query time; never a per-product field.

| table | key | shape |
|-------|-----|-------|
| `hinges_per_door` | (brand, series) | weight-band × door-height → hinge count |
| `overlay_chart` | (brand, series) | (cranking, baseplate_height) → overlay mm |
| `reveal_gap_chart` | (brand, series, model) | door_thickness → reveal/gap/overlay/protrusion |
| `lid_torque` | — | (lid height × weight) → duty / stay count |
| `lift_selection` | (system) | power-factor or (weight × cabinet height) → mechanism + qty |

## 6. Relationship edges (only catalog-stated, non-derivable links)

`requires` (hinge→baseplate) · `compatible_with` (by series) · `companion_in_set` (lift-kit
members) · `restricts` (clip→hinge, with angle) · `adds_soft_close` (device→hinge) ·
`available_in_finish` (e.g. → Onyx SKU) · `fits` (tool→hinge/series) · `replaces`.
Each edge: `{from, to, type, condition{text, applies_to_*}, source, page}`. Compatibility
that an engine can *derive* from attributes (series/mounting/brand match) is **not** stored.

## 7. Taxonomy → schema mapping (every type has a home)

| taxonomy product_type | family | discriminator |
|-----------------------|--------|---------------|
| concealed_hinge, face_frame_hinge, specialty_hinge | hinge | application / cabinet_type |
| flap_hinge | hinge | type=flap |
| institutional_hinge, piano_hinge, invisible_hinge, face_mount_hinge, full_inset_hinge, pin_knife_hinge, pivot_hinge, glass_door_hinge, adjustable_3d_hinge, wrap_demountable_hinge | hinge | the matching extension |
| baseplate | baseplate | plate_style |
| hinge_accessory, push_mechanism | accessory | accessory_type |
| hinge_tool | tool | tool_type |
| lift_system, counterbalance_lift | lift_system / lid_stay | system / stay_type |
| lift_accessory | lift_accessory | type |
| lid_stay | lid_stay | stay_type |

## 8. Open decisions

- **Identity normalization** — exact rule for the manufacturer-PN key per brand (the `GF→F`
  prefix is Grass-only; Blum/Salice need their own, or fall back to `source:part_number`).
- **How many hinge extensions are worth modelling now** vs deferring the long-tail (piano,
  glass, pivot…) to a generic `{description + raw fields}` until the eval demands them.
- **Variant explosion** — finish/handing as fields on one product vs separate SKUS/listings
  (the catalogs list, e.g., each finish as its own part number → likely separate products
  linked by `available_in_finish`).
