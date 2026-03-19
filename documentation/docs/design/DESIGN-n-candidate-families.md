# N-Candidate Solver — Family Data and Rules Reference

Comprehensive reference for all product families implemented on the `NCandidateSolver`. Each family defines its own product models, requirements, constraint rules, and data source. The solver treats them uniformly — the only difference is N (the number of product roles).

**Solver implementation:** `engine_v2/core/solver_n.py`

---

## 1. Concealed Hinges (N=2)

A hinge and a mounting plate must be selected together. The contractor specifies their cabinet and door properties; the engine finds all compatible hinge + plate pairs.

**Config:** `engine_v2/families/concealed_hinge/config.py` → `HINGE_N_CONFIG`

### Roles

| Role | Model | Description |
|---|---|---|
| `hinge` | `Hinge` | Concealed European hinge — defines angle, weight rating, boring pattern, series |
| `plate` | `Plate` | Mounting plate — defines overlay range, series compatibility, mounting method |

### Data

**Source:** `sample-data/hinges.json` (53 products), `sample-data/mounting_plates.json` (55 products)
**Loader:** `engine_v2/families/concealed_hinge/loader.py`
**Origin:** Extracted from Würth Baer, Grass Tiomos/Nexis, and Blum PDF catalogs. Real product data.

#### Hinge fields

| Field | Type | Example | Used by rules |
|---|---|---|---|
| `sku` | str | `"BLM-71B3550"` | — |
| `brand` | str | `"Blum"` | R001 |
| `price_usd` | float \| None | `5.50` | Ranking |
| `series` | HingeSeries | `CLIP_TOP_BLUMOTION` | R002 |
| `application` | ApplicationType | `FULL_OVERLAY` | Pre-filter |
| `opening_angle_deg` | int | `110` | R013 |
| `boring_pattern_mm` | int | `45` | R009 |
| `door_thickness_range_mm` | Range (min, max) | `{min: 16, max: 24}` | R006 |
| `max_door_weight_kg` | float | `8.0` | R007 |
| `soft_close` | bool | `true` | PREF |
| `mounting_method` | MountingMethod | `SCREW_ON` | R014 |
| `cabinet_type` | CabinetType | `FRAMELESS` | R003, pre-filter |
| `cup_depth_mm` | float \| None | `11.5` | R015 |

#### Plate fields

| Field | Type | Example | Used by rules |
|---|---|---|---|
| `sku` | str | `"175H7100"` | — |
| `brand` | str | `"Blum"` | R001 |
| `price_usd` | float \| None | `2.00` | Ranking |
| `series` | str | `"CLIP"` | — |
| `compatible_hinge_series` | list[HingeSeries] | `["CLIP top BLUMOTION", "CLIP top"]` | R002 |
| `mounting_method` | MountingMethod | `SCREW_ON` | R014 |
| `cabinet_type` | CabinetType | `FRAMELESS` | R003, R011 |
| `plate_type` | PlateType | `CRUCIFORM` | — |
| `overlay_range_mm` | dict | `{"full": [14, 20], "half": [3, 9], "inset": true}` | R004, R005 |

#### Requirements fields

| Field | Type | Default | Used by rules |
|---|---|---|---|
| `cabinet_type` | CabinetType | (required) | R003 |
| `door_thickness_mm` | float | (required) | R006, R015 |
| `door_height_mm` | float | (required) | Derived: hinges_per_door |
| `door_weight_kg` | float | (required) | R007 |
| `application` | ApplicationType | (required) | R004, R005, pre-filter |
| `desired_overlay_mm` | float | (required) | R004, R011, R012 |
| `boring_pattern_mm` | int | (required) | R009 |
| `soft_close` | bool | (required) | PREF |
| `preferred_brand` | str \| None | `None` | Pre-filter |
| `brand_lock` | bool | `True` | R001 |
| `cabinet_position` | CabinetPosition | `STANDARD` | R013 |
| `has_adjacent_door` | bool | `False` | R012 |
| `adjacent_door_overlay_mm` | float | `0` | R012 |
| `partition_thickness_mm` | float | `19` | R012 |
| `face_frame_width_mm` | float | `0` | R011 |

#### Derived values

| Key | Calculation | Used by |
|---|---|---|
| `hinges_per_door` | Door height → 2 (≤889mm), 3 (≤1400mm), 4 (≤1800mm), 5 (above) | R007 |
| `quantity` | Same as `hinges_per_door` — used for total price calculation | Ranking |

### Rules (14)

Defined in `engine_v2/families/concealed_hinge/rules.py`. Same order as v1.

| Rule | Name | Category | What it checks | Products/fields involved |
|---|---|---|---|---|
| R001 | brand_lock | Hard | Hinge and plate same brand (when `brand_lock=True`) | hinge.brand, plate.brand |
| R002 | series_compatibility | Hard | Plate's `compatible_hinge_series` includes hinge's series | hinge.series, plate.compatible_hinge_series |
| R003 | cabinet_type_match | Hard | Hinge, plate, and requirements all agree on cabinet type | hinge.cabinet_type, plate.cabinet_type, req.cabinet_type |
| R004 | overlay_in_range | Hard | Desired overlay within plate's achievable range for the application | plate.overlay_range_mm, req.desired_overlay_mm, req.application |
| R005 | inset_support | Hard | If application is inset, plate must support it | plate.overlay_range_mm["inset"], req.application |
| R006 | door_thickness_range | Hard | Door thickness within hinge's rated range | hinge.door_thickness_range_mm, req.door_thickness_mm |
| R007 | door_weight_limit | Hard | Door weight ≤ hinge max weight × number of hinges | hinge.max_door_weight_kg, derived.hinges_per_door, req.door_weight_kg |
| R009 | boring_pattern_match | Hard | Hinge boring pattern matches what's pre-drilled in the cabinet | hinge.boring_pattern_mm, req.boring_pattern_mm |
| R013 | corner_cabinet_angle | Hard | Corner cabinets require ≥155° opening angle (skipped if standard position) | hinge.opening_angle_deg, req.cabinet_position |
| R012 | adjacent_door_clearance | Hard | Combined overlay of adjacent doors ≤ partition thickness (skipped if no adjacent door) | req.desired_overlay_mm, req.adjacent_door_overlay_mm, req.partition_thickness_mm |
| R011 | face_frame_overlay | Hard | Overlay ≤ face frame width − 3mm (skipped if not face frame cabinet) | plate.cabinet_type, req.desired_overlay_mm, req.face_frame_width_mm |
| R014 | mounting_method_match | Hard | Hinge and plate mounting methods are compatible (via lookup table) | hinge.mounting_method, plate.mounting_method |
| R015 | cup_depth_door_thickness | Hard | Door thickness ≥ cup depth + 2mm (skipped if cup depth not specified) | hinge.cup_depth_mm, req.door_thickness_mm |
| PREF | soft_close_preference | Preference | Hinge has soft-close if requested (non-blocking) | hinge.soft_close, req.soft_close |

#### Mounting method compatibility table (R014)

Not all methods are directly interchangeable. The lookup table:

| Hinge method | Compatible plate methods |
|---|---|
| SCREW_ON | SCREW_ON, EURO_SCREW, SYSTEM_SCREW |
| DOWEL | DOWEL, SYSTEM_SCREW |
| All others | Must match exactly |

### Pre-filters

Applied before the Cartesian product to reduce the search space. Only hinges are filtered; all plates are evaluated.

| Filter | Effect |
|---|---|
| Application | Only hinges matching `req.application` survive |
| Cabinet type | Only hinges matching `req.cabinet_type` survive |
| Brand | Only hinges matching `req.preferred_brand` survive (if set) |

### Ranking

Sorted by:
1. Priced configs before unpriced (None prices sort last)
2. Total price ascending (price per hinge + plate, multiplied by `hinges_per_door`)
3. Total weight capacity descending (tiebreaker — higher capacity preferred)

### Tests

21 tests in `engine_v2/tests/test_hinge_n_candidate.py`: data loading (4), five customer scenarios (12), cross-solver consistency (5).

---

## 2. LED Lighting (N=3)

A light bar, driver, and dimmer must be selected together. The contractor specifies their cabinet dimensions and whether they want dimming; the engine finds all compatible triples.

**Config:** `engine_v2/families/led_lighting/` (inline in test code, no standalone config file)

### Roles

| Role | Model | Description |
|---|---|---|
| `light_bar` | `LightBar` | LED strip/bar — defines voltage, wattage, length, brightness, connector |
| `driver` | `Driver` | Transformer — converts mains AC to LED DC, must match bar's voltage |
| `dimmer` | `Dimmer` | Brightness control — must match driver's dimming protocol |

### Data

**Source:** `engine_v2/families/led_lighting/test_data.py`
**Loader:** None — hardcoded fixtures
**Origin:** Synthetic test data. Not from any real catalog.

#### Light bar fields

| Field | Type | Example | Used by rules |
|---|---|---|---|
| `sku` | str | `"LED-BAR-12V-5W"` | — |
| `brand` | str | `"Loox"` | — |
| `price_usd` | float | `25.00` | Ranking |
| `wattage` | float | `5.0` | LED002, LED005 |
| `voltage` | Voltage | `DC_12V` | LED001 |
| `length_mm` | int | `300` | LED006 |
| `lumen_output` | int | `400` | LED007 |
| `dimmable` | bool | `true` | — |
| `connector` | ConnectorType | `BARREL_JACK` | LED003 |
| `color_temp_k` | int | `4000` | — (not constrained) |
| `ip_rating` | str | `"IP20"` | — (not constrained) |

#### Driver fields

| Field | Type | Example | Used by rules |
|---|---|---|---|
| `sku` | str | `"DRV-12V-30W"` | — |
| `brand` | str | `"Loox"` | — |
| `price_usd` | float | `30.00` | Ranking |
| `output_voltage` | Voltage | `DC_12V` | LED001, LED009 |
| `max_wattage` | float | `30.0` | LED002 |
| `output_channels` | int | `4` | — (not constrained) |
| `dimmable` | bool | `true` | LED008 |
| `dimming_protocol` | DimmingProtocol | `TRAILING_EDGE` | LED004 |
| `connector` | ConnectorType | `BARREL_JACK` | LED003 |
| `efficiency` | float | `0.90` | — (not constrained) |

#### Dimmer fields

| Field | Type | Example | Used by rules |
|---|---|---|---|
| `sku` | str | `"DIM-TE-150W"` | — |
| `brand` | str | `"Loox"` | — |
| `price_usd` | float | `45.00` | Ranking |
| `dimming_protocol` | DimmingProtocol | `TRAILING_EDGE` | LED004 |
| `max_wattage` | float | `150.0` | LED005 |
| `voltage_compatible` | list[Voltage] | `[DC_12V, DC_24V]` | LED009 |
| `min_load_wattage` | float | `5.0` | LED005 |

#### Requirements fields

| Field | Type | Default | Used by rules |
|---|---|---|---|
| `cabinet_length_mm` | int | (required) | LED006 |
| `num_light_bars` | int | `1` | LED002, LED005 |
| `dimming_required` | bool | `False` | LED008 |
| `min_lumen_output` | int | `0` | LED007 |
| `voltage_preference` | Voltage \| None | `None` | — (not constrained) |
| `max_budget_usd` | float \| None | `None` | — (not constrained) |
| `preferred_brand` | str \| None | `None` | — |
| `brand_lock` | bool | `True` | — (no brand lock rule for LED) |

### Rules (9)

Defined in `engine_v2/families/led_lighting/rules.py`.

| Rule | Name | Category | What it checks | Products/fields involved |
|---|---|---|---|---|
| LED001 | voltage_match | Hard | Light bar voltage matches driver output voltage | bar.voltage, driver.output_voltage |
| LED002 | wattage_capacity | Hard | Total wattage (bar × num_bars) ≤ 80% of driver max wattage | bar.wattage, driver.max_wattage, req.num_light_bars |
| LED003 | connector_match | Hard | Light bar connector matches driver connector | bar.connector, driver.connector |
| LED006 | bar_length | Hard | Light bar fits inside cabinet | bar.length_mm, req.cabinet_length_mm |
| LED007 | brightness | Preference | Light bar meets minimum lumen output (skipped if no minimum set) | bar.lumen_output, req.min_lumen_output |
| LED008 | driver_dimming_support | Hard | Driver supports dimming if required (skipped if not required) | driver.dimmable, req.dimming_required |
| LED004 | dimming_protocol | Hard | Driver and dimmer use same dimming protocol | driver.dimming_protocol, dimmer.dimming_protocol |
| LED005 | dimmer_wattage | Hard | Total wattage within dimmer's min/max range | bar.wattage, dimmer.min_load_wattage, dimmer.max_wattage, req.num_light_bars |
| LED009 | dimmer_voltage | Hard | Dimmer is compatible with driver's output voltage | driver.output_voltage, dimmer.voltage_compatible |

#### Constraint topology

This is why LED lighting needs N=3 — three cross-product axes between catalog products:

```
Light bar ↔ Driver:    LED001 (voltage), LED002 (wattage), LED003 (connector)
Driver ↔ Dimmer:       LED004 (protocol), LED009 (voltage)
Light bar ↔ Dimmer:    LED005 (wattage range)
Light bar ↔ Cabinet:   LED006 (length), LED007 (brightness)
Driver ↔ Cabinet:      LED008 (dimming support)
```

Note: bar ↔ dimmer has only one rule (LED005). This is why the staged pipeline works well for LED lighting — Stage 1 (bar × driver) prunes heavily on voltage/connector, and Stage 2 (valid pairs × dimmer) only needs to check 3 rules.

#### Staged pipeline grouping

The same rules are also used by the `StagedPipelineSolver` with this decomposition:

| Stage | New roles | Rules |
|---|---|---|
| Stage 1: Electrical | light_bar, driver | LED001, LED002, LED003, LED006, LED007, LED008 |
| Stage 2: Dimming | dimmer | LED004, LED005, LED009 |

### Ranking

Sorted by total price ascending (bar + driver + dimmer). Unpriced configs sort last.

### Tests

26 tests in `engine_v2/tests/test_n_candidate.py`, 25 + 5 cross-solver in `engine_v2/tests/test_staged.py`.

### Test catalog

| Role | Count | Products |
|---|---|---|
| Light bars | 5 | BAR-12V-5W, BAR-12V-10W, BAR-24V-15W, BAR-24V-8W, BAR-12V-LONG |
| Drivers | 4 | DRV-12V-30W, DRV-12V-15W-ND, DRV-24V-60W, DRV-24V-20W |
| Dimmers | 4 | DIM-TE-150W, DIM-010V-200W, DIM-TE-25W, DIM-LE-100W |

Total Cartesian product: 5 × 4 × 4 = 80 triples.

---

## 3. Drawer Slides (N=1)

A single slide is selected — no pairing with other products. The contractor specifies cabinet depth, drawer weight, and preferences; the engine filters to matching slides.

**Config:** `engine_v2/families/drawer_slide/config.py` → `SLIDE_N_CONFIG`

### Roles

| Role | Model | Description |
|---|---|---|
| `slide` | `DrawerSlide` | Drawer slide (sold in pairs) — defines length, load rating, extension, mount type |

### Data

**Source:** `engine_v2/families/drawer_slide/test_data.py`
**Loader:** None — hardcoded fixtures
**Origin:** Synthetic test data. Not from any real catalog.

#### Slide fields

| Field | Type | Example | Used by rules |
|---|---|---|---|
| `sku` | str | `"563H5330B"` | — |
| `brand` | str | `"Blum"` | Pre-filter |
| `price_usd` | float | `45.00` | Ranking |
| `series` | str | `"TANDEM plus BLUMOTION"` | — |
| `slide_length_mm` | int | `533` | DS002 |
| `max_load_kg` | float | `30.0` | DS001 |
| `extension_type` | ExtensionType | `FULL` | DS003 |
| `mount_type` | SlideMountType | `UNDERMOUNT` | DS004, DS005, pre-filter |
| `close_type` | SlideCloseType | `SOFT_CLOSE` | DS007, DS008 |
| `requires_rear_bracket` | bool | `true` | — |
| `min_cabinet_depth_mm` | int | `10` | DS002 |
| `disconnect_feature` | bool | `true` | DS006 |

#### Requirements fields

| Field | Type | Default | Used by rules |
|---|---|---|---|
| `cabinet_depth_mm` | int | (required) | DS002 |
| `drawer_weight_kg` | float | (required) | DS001 |
| `drawer_width_mm` | int \| None | `None` | DS005 |
| `extension_type` | ExtensionType \| None | `None` | DS003 |
| `mount_type` | SlideMountType \| None | `None` | DS004, pre-filter |
| `soft_close` | bool | `False` | DS007 |
| `push_open` | bool | `False` | DS008 |
| `disconnect_required` | bool | `False` | DS006 |
| `preferred_brand` | str \| None | `None` | Pre-filter |
| `brand_lock` | bool | `True` | — (no brand lock rule for slides) |

### Rules (8)

Defined in `engine_v2/families/drawer_slide/rules.py`.

| Rule | Name | Category | What it checks | Products/fields involved |
|---|---|---|---|---|
| DS001 | load_capacity | Hard | Drawer weight ≤ slide's max load rating | slide.max_load_kg, req.drawer_weight_kg |
| DS002 | cabinet_depth | Hard | Cabinet deep enough for slide length + rear clearance | slide.slide_length_mm, slide.min_cabinet_depth_mm, req.cabinet_depth_mm |
| DS003 | extension_type | Hard | Slide extension matches requirement (skipped if no preference) | slide.extension_type, req.extension_type |
| DS004 | mount_type | Hard | Slide mount type matches requirement (skipped if no preference) | slide.mount_type, req.mount_type |
| DS005 | undermount_width_limit | Hard | Drawer width ≤ 900mm for undermount slides (skipped if not undermount or width not specified) | slide.mount_type, req.drawer_width_mm |
| DS006 | disconnect_feature | Preference | Slide has tool-free disconnect if required (skipped if not required) | slide.disconnect_feature, req.disconnect_required |
| DS007 | soft_close | Preference | Slide has soft-close damping if requested (skipped if not requested) | slide.close_type, req.soft_close |
| DS008 | push_open | Preference | Slide has push-open/touch-latch if requested (skipped if not requested) | slide.close_type, req.push_open |

#### Constraint topology

All constraints are slide ↔ requirements. There are no cross-product constraints because there's only one product role:

```
Slide ↔ Cabinet:      DS001 (weight), DS002 (depth), DS005 (width)
Slide ↔ Preferences:  DS003 (extension), DS004 (mount), DS006 (disconnect),
                      DS007 (soft close), DS008 (push open)
```

### Pre-filters

| Filter | Effect |
|---|---|
| Brand | Only slides matching `req.preferred_brand` survive (if set) |
| Mount type | Only slides matching `req.mount_type` survive (if set) |

### Ranking

Sorted by:
1. Priced configs before unpriced
2. Total price ascending
3. Load capacity descending (tiebreaker)

### Tests

16 tests in `engine_v2/tests/test_slide_n_candidate.py`: basic solve (5), constraints (7), explanation format (4).

### Test catalog

| Role | Count | Products |
|---|---|---|
| Slides | 4 | Blum TANDEM (full/undermount/30kg), Grass Dynapro (full/undermount/40kg), KV 8400 (¾/side/45kg), KV Center Mount (¾/center/15kg) |

Total: 4 products evaluated individually (no Cartesian product for N=1).

---

## Cross-Family Summary

| | Concealed Hinges | LED Lighting | Drawer Slides |
|---|---|---|---|
| **N (roles)** | 2 | 3 | 1 |
| **Roles** | hinge, plate | light_bar, driver, dimmer | slide |
| **Rules** | 14 | 9 | 8 |
| **Hard constraints** | 13 | 8 | 5 |
| **Preferences** | 1 | 1 | 3 |
| **Data source** | Real catalog (JSON) | Synthetic fixtures | Synthetic fixtures |
| **Catalog size** | 53 × 55 = 2,915 pairs | 5 × 4 × 4 = 80 triples | 4 products |
| **Cross-product rules** | 3 (R001, R002, R014) | 5 (LED001-004, LED009) | 0 |
| **Product ↔ req rules** | 9 | 4 | 8 |
| **Requirements-only rules** | 1 (R012) | 0 | 0 |
| **Derived values** | hinges_per_door | — | — |
| **Pre-filters** | 3 (app, cabinet, brand) | 0 | 2 (brand, mount) |
| **Tests** | 21 | 26 + 30 staged | 16 |

### What the solver does for each N

| N | Cartesian product | Evaluation count (worst case) |
|---|---|---|
| 1 | None — iterate products | products × rules |
| 2 | A × B | (products_A × products_B) × rules |
| 3 | A × B × C | (products_A × products_B × products_C) × rules |

The algorithm is identical — only the number of roles in the Cartesian product changes.

## Related

- [ADR-001: Flat N-Candidate Solver](../architecture/decisions/ADR-001-flat-n-candidate-solver.md) — Why this is the default
- [Solver Architecture Diagrams](../architecture/solver-architecture-diagrams.md) — Visual flowcharts
- [Multi-Family Architecture](../architecture/multi-family-architecture.md) — Generic vs independent engines
- [Constraint Engine Design](DESIGN-constraint-engine.md) — V1 rule reference
