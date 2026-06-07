# How weight is handled in the catalogs

> Captures a correction: there is **no "per-hinge weight" rating** in these catalogs. Load
> is expressed completely differently — and differently again per product family. Companion
> to [`plan_build_product_db.md`](plan_build_product_db.md) (§2.1 schema, §3 engine
> decision) and [`gap_analysis.md`](gap_analysis.md).

## Concealed hinges — load is a *chart*, not a hinge field

The catalogs do **not** give each hinge a "max door weight (kg)". Instead, the manufacturer
catalogs (Grass TIOMOS p47, Grass NEXIS p38) carry a **hinges-per-door chart**:

```
door weight band  ×  door height   →   number of hinges
  (e.g. 7–12 kg)      (≤ 1600 mm)         3
```

- It answers **"how many hinges does my door need?"** — *not* "what does this one hinge
  hold?"
- It is **series-level reference data** (keyed on brand + series), looked up at query time
  with the customer's door height and weight. It is **not** an attribute of an individual
  part number.
- The **distributor** catalog (Würth Section B) carries **no weight information at all** —
  not per-hinge, not the chart. The chart only exists in the manufacturer catalogs.

So in the DB, load lives in the `hinges_per_door` **reference table**, exactly as §2.1
already specifies — never as a field on the hinge record.

## Why "per-hinge weight" was a wrong assumption

`max_door_weight_kg` was **imported from the existing engine** (engine_v2), whose rule
simplifies capacity to `kg-per-hinge × number-of-hinges`, with the PoC `sample-data`
supplying invented kg values. That model:
- is **not how the catalogs express load** (they use the chart), and
- is a physical **over-simplification** — real capacity depends on hinge count, door
  height/leverage, mounting method, and material, which is exactly why the catalog uses a
  2-D chart, not a single number.

Consequence for the gap report: counting "missing per-hinge weight" as 30 gaps was a
**phantom** (same class of error as expecting `baseplate.series`). It's been removed from
the hinge's expected fields, so `absent_in_catalog` is now just **price (68)**, not 98.

## The chart itself is a low-confidence read

The chart is a diagram, recovered via the B2 vision pass (`chart_extract_spike.py`). The
axes/bands/thresholds cross-check against the text layer (high confidence), but the
**cell grid** (which weight×height → which count) is best-effort and flagged for human
verification — a `low_confidence` gap, not a clean fact.

## Section C — weight/force is handled *differently again* per family

"Weight" isn't one concept across the corpus. Each lift/stay family has its own load model:

| Family (Section C) | Load model |
|--------------------|-----------|
| **Blum AVENTOS** lifts (HF/HK) | **Power Factor = cabinet height × door weight** → selects the lift mechanism *and* how many mechanisms |
| AVENTOS HS/HL, **Grass KINVARO**, **Salice WIND** | door-weight range + cabinet-height range + **spring colour code** |
| **Lid stays / up-stays** | **torque = lid height × lid weight × ½** |
| Traditional (SOSS, institutional) | **weight capacity per N units** (e.g. "one closer per 75 lb") |

So every Section C family promoted to the DB needs **its own load model** — there is no
shared per-product weight field to inherit.

## The open engine decision (deferred)

This is the **weight-model decision tagged "deferred to adapter phase"** in §3: a constraint
engine that wants a per-hinge `max_door_weight_kg` (option a) is asking for something the
catalog doesn't have; the faithful path (option b) is to have the engine **consume the
`hinges_per_door` chart** (height + weight → count). The DB stays neutral — it carries the
chart and no per-hinge kg — so either choice remains open.
