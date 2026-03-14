# Sample Data — Window Hinge Compatibility

Realistic example data modelling the constraint satisfaction problem for cabinet hinge selection. Based on real product lines from Blum, Grass America, and Häfele.

## Files

| File | Description |
|------|-------------|
| `hinges.json` | 15 concealed European hinge SKUs across 3 manufacturers (Blum, Grass, Häfele), 5 series, covering full/half/inset overlay, 95°–170° opening angles, frameless and face-frame cabinets |
| `mounting_plates.json` | 12 mounting plates — cruciform, wing, and face-frame types with overlay ranges, height adjustments, and series compatibility |
| `compatibility_rules.json` | 14 deterministic constraint rules (hard and soft) that the reasoning engine must enforce |
| `customer_scenarios.json` | 7 end-to-end scenarios including both fast-track and guided-discovery paths, plus a constraint violation case |

## Key Relationships

- Hinges and plates are locked to the same brand and series (rules R001, R002)
- Cabinet type (frameless vs face-frame) must match across hinge and plate (R003)
- Overlay is a function of plate height + hinge crank — the plate defines achievable overlay ranges (R004)
- Door weight capacity is per-hinge, multiplied by hinge count which is derived from door height (R007, R008)
- Wide-angle hinges (>120°) have a 25% weight derating (R010)
- Corner cabinets require minimum 155° opening (R013)
- Adjacent doors sharing a partition have a combined overlay constraint (R012)

## Notes

- SKUs are realistic but not guaranteed to match current Würth catalog numbers exactly
- Prices are approximate 2026 trade pricing
- The constraint rules represent the core logic; a production system would have additional edge cases around special applications (glass doors, pie-cut corners, blind corners, etc.)
