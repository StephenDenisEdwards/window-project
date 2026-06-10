# Engine v2 ↔ extracted data — fit, rules & gaps

_Report (no code). How the `engine_v2` concealed-hinge constraint engine could consume the 888
extracted products, what new rules/data are needed, and an analysis of the existing rules and
their overlap. Companion to [EXTRACTION_STATUS.md](EXTRACTION_STATUS.md)._

## 1. Bottom line

The engine and the data are **structurally compatible but at different altitudes.** The engine is
a clean N-candidate solver that pairs a `hinge` with a `plate` and runs 14 hard rules + 1
preference (`engine_v2/families/concealed_hinge/`). Our 888 products give it a real, broad catalog
(5 brands vs the 53 hand-curated hinges in `sample-data/`). But the rules assume **engineering
spec fields a distributor catalog doesn't print** — door-thickness range, hinge load, cup depth,
and a plate "overlay range" dict. We extracted the **catalog surface** (SKU, series, overlay class,
opening angle, fixing, boring, plate height), not those derived specs.

Realistic path: **an adapter loader + make the spec-dependent rules degrade gracefully** (skip and
flag when data is absent — which the engine already does for `cup_depth` and `inset`), plus
**derive** the two things the catalog encodes implicitly (plate↔hinge series compatibility, and
eventually overlay range from the overlay charts). This fits the project's "missing data is marked,
not invented" philosophy.

## 2. What the engine needs vs what we have

Engine `Hinge`/`Plate` models require these fields; mapping to our records:

**Hinge**

| Engine field (required) | Our data | Status |
|---|---|---|
| `series` | `series` (CLIP top BLUMOTION, TIOMOS, TEC, NEXIS, Air…) | ✅ direct (TEC/Air not yet in the `HingeSeries` enum) |
| `application` | `overlay_class` (full/half/inset) | ✅ maps; ~80% (1/2″, diagonal, bi-fold kept as `overlay_raw`) |
| `opening_angle_deg` | `opening_angle_deg` | ✅ 532/588 |
| `boring_pattern_mm` | `boring_pattern` ("42/45mm") / `boring_pattern_mm` | ⚠️ partial — Grass has it; Blum euro tables print Opening instead |
| `mounting_method` | `fixing` | ✅ 583/588 (new values rapido/logica/impresso) |
| `soft_close` | `closing_type == "soft"` | ✅ derivable |
| `cabinet_type` | — | ✅ **derivable** from `product_type` (concealed→frameless, face_frame_hinge→face_frame) |
| `door_thickness_range_mm` | — | ❌ not in catalog (manufacturer spec) |
| `max_door_weight_kg` | — | ❌ not in catalog (see §5 — wrong abstraction) |
| `cup_depth_mm` (optional) | — | ❌ not extracted (manufacturer spec) |

**Plate**

| Engine field (required) | Our data | Status |
|---|---|---|
| `series` | `series` | ✅ |
| `mounting_method` | `fixing_type` | ✅ |
| `cabinet_type` | — | ✅ derivable |
| `compatible_hinge_series` (list) | — | ⚠️ **derivable** from brand+system (§6 — the linchpin) |
| `plate_type` (enum) | `plate_style` (freeform) | ⚠️ needs mapping to `PlateType` |
| `overlay_range_mm` (`{full:[lo,hi], half:[…], inset:bool}`) | `height_mm` only | ❌ the big gap (§6) |

**Also:** the engine ranks by `price_usd` then capacity. We **didn't extract price**, and we don't
have capacity — ranking needs rework or price extraction.

## 3. Existing rules — status against our data

| Rule | Needs | With our data |
|---|---|---|
| **R001** brand_lock | brand | ✅ works now |
| **R002** series_compatibility | plate `compatible_hinge_series` | ⚠️ works once derived (§6) |
| **R003** cabinet_type_match | cabinet_type ×3 | ✅ with derivation |
| **R004** overlay_in_range | plate `overlay_range_mm` | ❌ needs overlay-chart data |
| **R005** inset_support | plate `overlay_range_mm["inset"]` | ❌ same gap (partial: `inset_recess_in` on B-21) |
| **R006** door_thickness_range | hinge `door_thickness_range_mm` | ❌ manufacturer spec |
| **R007** door_weight_limit | hinge `max_door_weight_kg` | ❌ **wrong model — see §5** |
| **R009** boring_pattern_match | hinge `boring_pattern_mm` == req | ⚠️ partial; needs multi-value ("42/45mm") |
| **R011** face_frame_overlay | requirement-side only | ✅ works (no product data) |
| **R012** adjacent_clearance | requirement-side only | ✅ works |
| **R013** corner_angle | `opening_angle_deg` | ✅ works |
| **R014** mounting_method_match | hinge/plate fixing | ✅ works (extend compat for rapido/logica) |
| **R015** cup_depth | hinge `cup_depth_mm` | ❌ manufacturer spec (already skips when absent) |
| **PREF** soft_close | `closing_type` | ✅ works |

(No R008/R010 check — R008 is the derived `hinges_per_door`; R010 doesn't exist.)

**Net: ~8 of 15 run today** on catalog-surface data (R001, R003, R009*, R011, R012, R013, R014,
PREF); ~1 needs a cheap **derivation** (R002); ~5 need **manufacturer data** (R004, R005, R006,
R007, R015).

## 4. Rule overlap / redundancy

- **R005 ⊂ R004** — `inset_support` is a special case of `overlay_in_range` (R004 already fails when
  the application key, including `inset`, isn't in the plate dict). Keep R005 only for messaging.
- **R001 ↔ R002** — series compatibility is brand-scoped in reality (CLIP is Blum-only), so passing
  R002 usually implies R001. With `brand_lock=False`, R002 is the real gate and R001 is moot.
- **R006 ↔ R015** — both constrain door thickness; R015 (`thickness ≥ cup_depth+2`) is a finer
  lower-bound a correct `door_thickness_range_mm.min` should already encode. Redundant if both set.
- **R004 / R011 / R012 — the "overlay feasibility" trio** — three overlay limits from different
  sources (plate capability / face-frame width / adjacent-door partition). Not redundant, but they
  interact; the trace must show *which* limit bound.
- **R007 ↔ derived `hinges_per_door`** — entangled (capacity = per-hinge × count, count derived
  from height). See §5/§7.

## 5. The weight rule (R007) is the key finding

R007 multiplies a **per-hinge `max_door_weight_kg`** by the hinge count. **The catalogs told us
this model is wrong** — load is published as a **series-level hinges-per-door chart** (door height
× door weight → number of hinges), not a per-hinge kilogram rating. (This matches the extraction
learning that "per-hinge weight was a wrong assumption; load is a series-level chart.") So R007
shouldn't just be fed data — it should be **redesigned**, and the framing matters (§7).

## 6. Two derivations that unlock the most rules

1. **`compatible_hinge_series` (unlocks R002).** The catalog encodes hinge↔plate compatibility by
   **brand + system**, not an explicit list (a TIOMOS plate fits TIOMOS hinges; Blum CLIP plates
   fit CLIP / CLIP top / CLIP top BLUMOTION). A small derivable lookup, and the catalog even states
   it in places ("Compatible with Tiomos base plates"). Our records carry brand + series + section,
   so it's buildable from what we have. **Highest-leverage addition.**
2. **`overlay_range_mm` (unlocks R004/R005).** Achievable overlay is a function of **plate height +
   hinge crank** — exactly what the **manufacturer overlay charts** tabulate. Note: **B-4 `PRO VALUE
   OVERLAY CHARTS`** — which we moved to *Other › Charts* as "reference, not a product" — **is this
   data.** Those charts are the future source for R004's overlay ranges. Until then, R004/R005
   skip-and-flag.

## 7. Hinge count: a derived output, not a weight pass/fail

**Reframe the question.** Not *"will these hinges hold this door?"* (boolean, given a fixed count)
but *"how many hinges does this door need?"* (solve for the count). This matters and is the correct
framing, because **it matches the data**: the catalogs publish a hinges-per-door chart (height ×
weight → count); they never publish a per-hinge kg rating. The "will it hold" framing is what led to
the wrong per-hinge-weight field in the first place.

Consequences:
- Hinge count is a **derived value**, not a hard-constraint rule. It belongs in the derivation step,
  **not** in the `RULES` list.
- The standalone weight check (R007) shrinks to a **boundary check**: if `(height, weight)` is off
  the chart entirely (beyond what the series supports at any count), no config of that series works.
- The count **ripples outward** — it drives quantity → price → bill of materials (the engine already
  multiplies price by `hinges_per_door`). Making it weight-aware improves the whole costed config.
- It **flips the UX**: the engine should *tell* the user "this door needs 3 hinges," not ask how many
  they're using. The requirements model already takes door height + weight (not a count), so no model
  change is needed there.

### Implementation: derivation vs. iterate-until-pass

Two ways to solve for the count — **same result, same data need**, different mechanics:

- **Iterate:** start at the height-based minimum, increment N, re-check the load rule until it passes,
  cap at the max supported count. Reuses the rule as a pass/fail oracle. *This is still computing the
  derivation — by search instead of lookup.* Caveat: iterate on weight **alone** can under-count
  (a tall but light door needs a 3rd hinge for rigidity/anti-sag, not load) — so seed from the
  height floor, not from 2.
- **Derivation (recommended):** read the count directly from the chart in the derivation step.

**Decision: derivation is the better approach**, for two concrete reasons:
1. **It matches the data shape** — the catalog publishes a count chart, so derivation *reads* the
   answer the chart already gives; iterating re-discovers a number that's already stated.
2. **It fits the engine's existing structure** — `compute_derived()` already returns
   `hinges_per_door` (height-only today). Making it weight/chart-aware is an upgrade to a slot that
   already exists. Iterate, by contrast, needs **new solver control flow** (a retry-with-N+1 loop
   the engine doesn't currently have). So derivation is the *smaller, more natural* change.

Iterate would only win if the data turned out to be a **per-hinge load curve** (capacity = f(height)
per hinge) rather than a count chart — there, searching for the minimum N is natural. Evidence says
it's a count chart, so derivation is the call — **but confirm the chart is count-keyed when the
manufacturer catalogs are extracted.** Either way, keep the one boundary check ("off the chart → no
config of this series works").

## 8. New rules our data enables

Fields we captured that the engine doesn't yet use → candidate new rules:
- **Multi-value boring (improve R009):** "42/45mm" means either — change exact `==` to "required ∈
  supported set."
- **Specialty/position match (new):** `variant` (blind-corner, pie-cut, +45° angle-corner, bi-fold)
  and `degree` (angled) match `cabinet_position` to the right specialty hinge — R013 only checks the
  angle.
- **Mount-type rule (new):** TEC `mount_type` (side-mount / wrap-around / face-mount).
- **Finish preference (new, soft):** `finish` (Onyx, Titanium, Nickel) → a preference like soft-close.
- **Cranking-based overlay (derivation):** Grass `cranking` + `max_overlay_mm` → overlay capability
  without a full chart.
- **Mounting enum/compat extension:** add rapido / logica / impresso to `MountingMethod` + R014 table.

## 9. Recommended sequencing

1. **Adapter loader** `products.json → Hinge/Plate`, synthesizing derivable fields (cabinet_type,
   application, soft_close, mounting) + the series-compat map.
2. **Make spec fields Optional** (`door_thickness_range_mm`, `max_door_weight_kg`, `overlay_range_mm`)
   and have their rules return **"data-insufficient — skipped"** when absent (the R015/R005 pattern).
   Engine validates everything it *can*, reports what it couldn't — instead of failing to load.
3. **Build `compatible_hinge_series`** (brand+system) — cheapest big win, turns on R002.
4. **Redesign the count as a weight-aware derivation** in `compute_derived` (§7); demote R007 to the
   boundary check. Defer until the load charts are extracted.
5. **Extract the manufacturer load + overlay charts** — the single source that unlocks R004/R005/R007
   (and R006/R015 via thickness/cup specs). This is the same "manufacturer-catalog gap" the stock-take
   flagged; almost everything still missing points back to it. **First "map" those catalogs** (a
   reconnaissance/taxonomy pass — what's there, where, vision vs table, and the manufacturer-part ↔
   Würth-SKU join); see _Next step in detail: mapping the manufacturer catalogs_ in
   [EXTRACTION_STATUS.md](EXTRACTION_STATUS.md).
6. **Add the new rules** (§8) incrementally.

**Headline:** with just the adapter + the series-compat derivation, the engine would run ~8 rules
against all 888 real products today and return ranked, fully-traced hinge+plate configurations —
with weight/thickness/overlay rules cleanly marked "needs manufacturer data" rather than guessed.
That's a useful engine on real data, and it sharpens exactly which catalog to extract next and why.
