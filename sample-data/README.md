# Sample Data — Window Hinge Compatibility

Realistic example data modelling the constraint satisfaction problem for cabinet hinge selection. Based on real product lines from Blum, Grass America, and Hafele.

## Files

| File | Description |
|------|-------------|
| `hinges.json` | 53 concealed European hinge SKUs across 3 manufacturers (Blum, Grass, Hafele), covering full/half/inset overlay, 95-170 opening angles, frameless and face-frame cabinets |
| `mounting_plates.json` | 55 mounting plates — cruciform, wing, and face-frame types with overlay ranges, height adjustments, and series compatibility |

## Key Relationships

- Hinges and plates are locked to the same brand and series (rules R001, R002)
- Cabinet type (frameless vs face-frame) must match across hinge and plate (R003)
- Overlay is a function of plate height + hinge crank — the plate defines achievable overlay ranges (R004)
- Door weight capacity is per-hinge (manufacturer's published rating), multiplied by hinge count derived from door height (R007, R008)
- Corner cabinets require minimum 155 opening (R013)
- Adjacent doors sharing a partition have a combined overlay constraint (R012)

Constraint rules are defined in `engine/rules.py` — the single source of truth.

## Notes

- SKUs are realistic but not guaranteed to match current Wurth catalog numbers exactly
- Prices are approximate 2026 trade pricing
- The constraint rules represent the core logic; a production system would have additional edge cases around special applications (glass doors, pie-cut corners, blind corners, etc.)
