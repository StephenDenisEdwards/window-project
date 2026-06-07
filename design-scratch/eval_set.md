# Eval set — product-DB / RAG golden questions

> Concrete eval set for [`plan_build_product_db.md`](plan_build_product_db.md) §2.5.
> Each item has a question, an expected answer, and a **citation** so the harness can
> score correctness *and* grounding. Seeded from the §9 walkthroughs and §5 query
> patterns of [`incremental_design_wurth.md`](incremental_design_wurth.md).
>
> **Grounding:** every expected answer below is taken from data the committed spikes
> actually extracted (Würth B-6 / B-45 / B-100, Grass TIOMOS p47) or from those pages'
> text. Citations use `source:page` — `wurth_b` = Würth Baer Section B (PDF page N ==
> printed "B-N"); `grass_tiomos` = Grass TIOMOS manufacturer catalog.
>
> **Capabilities** (from §2.5): `exact_lookup`, `spec_filter`, `compatibility`,
> `weight_feasibility`, `comparison`, `should_decline`, `deferred_family`.
> `should_decline` items have **no answer in the corpus** — the correct behaviour is to
> say so and surface the gap, never to fabricate.

```yaml
# --- A. Exact lookup (incl. cross-source resolution) ---
- id: EX1
  capability: exact_lookup
  q: "What is BP71B3580?"
  expect:
    brand: Blum
    family: concealed_hinge
    series: CLIP top BLUMOTION
    opening_angle_deg: 110
    overlay_class: full
    fixing: dowel
    closing_type: soft
    max_door_thickness_mm: 26
  cite: [wurth_b:B-6]
  ref: §9.1

- id: EX2
  capability: exact_lookup        # cross-source GF->F resolution
  q: "Show the full specs for GFF028138341228."
  expect:
    part_number_core: "028138341228"
    distributor_sku: GFF028138341228      # wurth_b
    manufacturer_pn: F028138341228        # grass_tiomos (drop the GF prefix)
    brand: Grass
    series: TIOMOS
    family: concealed_hinge
    overlay_class: full           # "Cranking 00" sub-group
    boring_pattern_mm: "42mm"
    fixing: dowelled
    closing_type: soft
  cite: [wurth_b:B-45, grass_tiomos:p16]
  ref: §9.3

- id: EX3
  capability: exact_lookup
  q: "What is UBBAV4L09F16?"
  expect:
    brand: Salice
    family: baseplate
    plate_style: wing
    height_mm: 0
    fixing_type: split_dowel
    material: stamped_steel
  cite: [wurth_b:B-100]
  ref: §9.2

# --- B. Spec-filtered search ---
- id: SF1
  capability: spec_filter
  q: "Soft-close Blum hinge, 110 degrees, full overlay, dowel fixing."
  expect: { part_number: BP71B3580 }
  cite: [wurth_b:B-6]
  ref: §9.1
  note: "still ambiguous with BP73B3580 (110+); Blum overlay-mm is in a block bullet, not yet extracted"

- id: SF2
  capability: spec_filter
  q: "Blum 110-degree soft-close INSET hinge with INSERTA fixing."
  expect: { part_number: BP71B3790 }
  cite: [wurth_b:B-6]

- id: SF3
  capability: spec_filter
  q: "Grass TIOMOS soft-close, full overlay (22mm), screw-on, 45mm boring."
  expect: { part_number: GFF028138519228 }   # unambiguous once overlay_max_mm is extracted
  cite: [wurth_b:B-45]

- id: SF4
  capability: spec_filter
  q: "Grass TIOMOS soft-close INSET hinge, dowelled, 42mm boring."
  expect: { part_number: GFF028138344228, overlay_class: inset }   # "Cranking 19"
  cite: [wurth_b:B-45]

# --- C. Compatibility / completeness ---
- id: CC1
  capability: compatibility
  q: "0mm Salice stamped-steel wing baseplate with pre-mounted euro-screw fixing for a Series F hinge."
  expect: { part_number: UBBAVGL09F16 }
  cite: [wurth_b:B-100]
  note: "page states wing plates fit all Salice Series F and Series B hinges"
  ref: §9.2

- id: CC2
  capability: compatibility       # exploded matrix completeness
  q: "List the 0mm Salice single-cam stamped-steel wing baseplates by fixing type."
  expect:
    wood_screw: UBBAV3L09F
    premounted_euro_screw: UBBAVGL09F16
    split_dowel: UBBAV4L09F16
  cite: [wurth_b:B-100]
  note: "single-cam (V-series) needed to disambiguate from two-cam (R-series); both have a 0mm stamped plate"

- id: CC3
  capability: compatibility
  q: "How do I limit a Grass TIOMOS hinge to an 85-degree opening angle?"
  expect:
    part_number: GFF072135751517
    accessory_type: restriction_clip
  cite: [wurth_b:B-45]
  ref: §9.4

# --- D. Weight feasibility (needs the manufacturer load chart) ---
- id: WF1
  capability: weight_feasibility
  q: "How many TIOMOS hinges for a 1500mm-tall, 11 kg door?"
  expect: { hinges: 3 }           # 7-12 kg band, up to 1600mm
  cite: [grass_tiomos:p47]
  note: "cell mapping is the B2 low-confidence read -> confirm at human-verify"
  ref: §9.3

- id: WF2
  capability: weight_feasibility
  q: "How many TIOMOS hinges for a 2300mm-tall, 20 kg door?"
  expect: { hinges: 5 }           # 18-22 kg band, up to 2450mm
  cite: [grass_tiomos:p47]
  note: "same B2 low-confidence caveat as WF1"

- id: WF3
  capability: weight_feasibility
  q: "How many NEXIS hinges for a 56in-tall, 19 lb door?"
  expect: { hinges: 2 }           # NEXIS chart is in inches/pounds; matches the page example
  cite: [grass_nexis:p8]
  note: "different series -> different chart (inches/pounds); low-confidence cell read"

# --- E. Comparison ---
- id: CM1
  capability: comparison
  q: "Which fixings are offered for Blum vs Grass TIOMOS 110-deg full-overlay soft-close hinges?"
  expect:
    blum: [screw_on, dowel, inserta, expando]      # BP71B3550/3580/3590/358E
    grass_tiomos: [dowelled, screw_on, impresso]   # GFF...341/519/523/414 (42 & 45mm)
  cite: [wurth_b:B-6, wurth_b:B-45]
  ref: §9 (comparison)

# --- F. Should-decline (answer is a gap, not in the corpus) ---
- id: SD1
  capability: should_decline
  q: "What is the maximum door-weight rating of hinge BP71B3580?"
  expect:
    answer: decline
    reason: "no per-hinge kg rating is published in the distributor catalog (absent gap)"
  cite: [wurth_b:B-6]
  note: "correct = 'not published' + surface the gap; load is a series-level chart, not a per-hinge field"

- id: SD2
  capability: should_decline
  q: "What is the price of BP71B3550?"
  expect:
    answer: decline
    reason: "catalogs carry no pricing (absent gap)"
  cite: [wurth_b:B-6]

# --- G. Deferred family (Section C not yet structured) ---
- id: DF1
  capability: deferred_family
  q: "Which AVENTOS HF lift mechanism for a 30in cabinet with an 18 lb door?"
  expect:
    answer: text_or_decline
    reason: "lift_system is a deferred family (refinement #5) — answer from retained text or decline a structured answer; do not invent a SKU"
  cite: [wurth_c:C-2]
  note: "selection is Power-Factor (cabinet height x door weight) based; promote to structured only if eval demands"
```

## Coverage

| Capability | Items |
|------------|-------|
| exact_lookup (incl. cross-source) | EX1, EX2, EX3 |
| spec_filter | SF1–SF4 |
| compatibility / completeness | CC1, CC2, CC3 |
| weight_feasibility | WF1, WF2 |
| comparison | CM1 |
| should_decline (gap) | SD1, SD2 |
| deferred_family | DF1 |

**Notes for the harness (§2.5):** score `expect` for correctness, `cite` for grounding
(does the page actually contain the value), and the `should_decline` items for **honesty**
(a fabricated answer is a failure). `WF1/WF2` depend on the B2 chart's low-confidence cell
read, so a miss there should be attributed to that gap, not a pipeline bug.
