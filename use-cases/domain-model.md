# Canonical Domain Model

## Problem Statement

The PoC domain model grew organically — fields were added as the data expanded, business logic leaked into data classes, and there's no clear boundary between product data, compatibility relationships, pricing, and presentation. The JSON schema has 20+ fields per product that the engine dataclass only partially loads.

This document defines the canonical domain model for the production constraint engine.

## Design Principles

1. **Products are facts. Compatibility is derived.** A hinge has physical dimensions. Whether it works with a given plate is computed by the rules engine, not stored on the product.
2. **Separate identity from presentation.** A product has a canonical manufacturer identity. SKUs, prices, and images are brand-specific overlays.
3. **Enumerate the enums.** Every constrained string field gets a defined set of valid values. No silent failures from typos.
4. **The engine only sees what it needs.** Product data, pricing data, image data, and catalog metadata are separate concerns. The engine operates on a minimal projection.

## Entity Model

### Product Identity

```
ManufacturerProduct
├── manufacturer_part: str          # "71B3550" — canonical identity
├── manufacturer: str               # "Blum" — who makes it
├── product_family: ProductFamily    # CONCEALED_HINGE, MOUNTING_PLATE, DRAWER_SLIDE, ...
└── distributor_skus: list[DistributorSKU]

DistributorSKU
├── sku: str                        # "BP71B3550"
├── brand: str                      # "Würth Baer Supply"
├── price_usd: float | None
├── in_stock: bool
└── url: str | None
```

This separates the canonical product (Blum part 71B3550) from how it appears at each Würth brand. The constraint engine operates on `ManufacturerProduct`. Pricing, stock, and URLs live on `DistributorSKU`.

### Concealed Hinge

```
ConcealedHinge (extends ManufacturerProduct)
├── series: HingeSeries             # CLIP_TOP_BLUMOTION, TIOMOS, NEXIS, DUOMATIC
├── application: ApplicationType    # FULL_OVERLAY, HALF_OVERLAY, INSET, OVERLAY
├── opening_angle_deg: int          # 95, 100, 107, 110, 120, 125, 155, 170
├── cup_diameter_mm: float          # 35.0 (universally)
├── cup_depth_mm: float             # 13.5, 12.6, 11.0, 10.0
├── boring_pattern_mm: int          # 42, 45, 48
├── crank_mm: float                 # 0, 4.5, 6.5, 9.5, 12.7, 19
├── door_thickness_range_mm: Range  # {min: 16, max: 26}
├── max_door_weight_kg: float       # manufacturer's published rating (no derating)
├── soft_close: bool
├── mounting_method: MountingMethod # SCREW_ON, DOWEL, INSERTA, EXPANDO, IMPRESSO
├── cabinet_type: CabinetType       # FRAMELESS, FACE_FRAME
└── notes: str | None
```

**Key changes from PoC:**
- `door_thickness_min_mm` / `door_thickness_max_mm` → `door_thickness_range_mm: Range` (typed value object)
- `mounting` → `mounting_method: MountingMethod` (enum, matching the plate field name)
- `compatible_mounting_plate_skus` removed — derived by rules
- `price_usd`, `image` removed — live on `DistributorSKU` and `ProductMedia`
- `effective_max_weight_kg` property removed — R010 derating eliminated, use `max_door_weight_kg` directly
- `application` uses enum including `OVERLAY` (Tiomos cranking 03)

### Mounting Plate

```
MountingPlate (extends ManufacturerProduct)
├── series: PlateSeries             # CLIP, TIOMOS, NEXIS, DUOMATIC
├── plate_type: PlateType           # CRUCIFORM, WING, WING_CAM, INLINE, FACE_FRAME,
│                                   # FACE_FRAME_ADAPTER, THICK_WING, TWO_PIECE, ...
├── mounting_method: MountingMethod # SCREW_ON, EURO_SCREW, SYSTEM_SCREW, DOWEL
├── cabinet_type: CabinetType       # FRAMELESS, FACE_FRAME
├── plate_height_mm: float          # 0, 2, 3, 3.5, 6, 9.5, 12, 19, 21
├── compatible_hinge_series: list[HingeSeries]
├── overlay_table: OverlayTable     # full BPH × DD lookup, not simplified [min, max]
├── height_adjustment_mm: float     # typically 2
├── depth_adjustment_mm: float      # 0, 2, 2.5
├── setback_mm: float               # 37 (frameless), 9.5 (face frame)
├── material: PlateMaterial         # STAMPED_STEEL, ZINC_DIECAST, STEEL_NICKEL_PLATED
├── fixing_points: int              # 2, 3, 4
└── notes: str | None
```

**Key changes from PoC:**
- `overlay_range_mm: dict` → `overlay_table: OverlayTable` (typed, structured)
- `plate_type` uses enum with all 10 types discovered in the catalog
- `compatible_hinge_series` stays — this is a product attribute (which hinge arm clips into this plate), not a derived relationship

### Customer Requirements

```
CustomerRequirements
├── cabinet_type: CabinetType           # FRAMELESS, FACE_FRAME
├── door_thickness_mm: float
├── door_height_mm: float
├── door_width_mm: float | None         # NEW — affects weight check for non-standard widths
├── door_weight_kg: float
├── application: ApplicationType        # FULL_OVERLAY, HALF_OVERLAY, INSET, OVERLAY
├── desired_overlay_mm: float
├── drilling_distance_mm: float = 5.0   # NEW — needed for exact overlay calculation
├── boring_pattern_mm: int
├── soft_close: bool
├── cabinet_position: CabinetPosition   # STANDARD, CORNER, BLIND_CORNER
├── preferred_brand: str | None
├── preferred_series: str | None        # NEW — some contractors are series-specific
├── has_adjacent_door: bool = False
├── adjacent_door_overlay_mm: float = 0
├── partition_thickness_mm: float = 19
├── face_frame_width_mm: float = 0
└── door_material: DoorMaterial | None  # NEW — affects weight derating for particleboard
```

**Key additions:**
- `drilling_distance_mm` — enables exact overlay calculation instead of simplified ranges
- `door_width_mm` — weight tables reference "24-inch standard width", non-standard widths may need adjustment
- `cabinet_position` adds `BLIND_CORNER` (different from regular corner — needs specific hinges like the Tiomos 110/90A)
- `door_material` — particleboard vs MDF vs solid wood affects pull-out resistance and weight ratings
- `preferred_series` — a pro who uses Blum CLIP top BLUMOTION exclusively

## Value Objects

### Range

```
Range
├── min: float
├── max: float
└── contains(value: float) -> bool
```

### OverlayTable

Replaces the simplified `{"full": [14, 20], "half": [3, 9], "inset": true}` with a proper lookup:

```
OverlayTable
├── entries: dict[ApplicationType, list[OverlayEntry]]
│
│   OverlayEntry
│   ├── base_plate_height_mm: float     # 0, 2, 3, 3.5
│   ├── drilling_distance_mm: float     # 3, 4, 5, 6, 7
│   └── overlay_mm: float               # exact achievable overlay
│
├── supports(app: ApplicationType) -> bool
├── achievable_overlay(app, drilling_distance) -> float
└── overlay_range(app) -> Range          # simplified fallback
```

The `overlay_range()` method provides backward compatibility with the PoC's `[min, max]` approach. But `achievable_overlay()` gives the exact answer when drilling distance is known.

**Data source:** These tables are published on each catalog page. Example from Grass Tiomos 110° (catalog page 21):

```
Drilling Distance (DD):  3     4     5     6     7
Base Plate Height 0:     22.0  —     —     —     —
Base Plate Height 2:     —     —     20.0  —     —
Base Plate Height 3:     —     —     19.0  18.5  —
Base Plate Height 3.5:   —     —     —     —     17.0
```

### RuleResult

```
RuleResult
├── rule_id: str                    # "R006"
├── rule_name: str                  # "door_thickness_range"
├── category: RuleCategory          # HARD_CONSTRAINT, SOFT_CONSTRAINT, PREFERENCE, DERIVED
├── passed: bool
├── detail: str                     # human-readable explanation
├── values_compared: dict | None    # {"actual": 19, "min": 16, "max": 26}
└── remediation: str | None         # "Consider a thick-door hinge (95°) for doors over 24mm"
```

**Additions over PoC:**
- `category` — distinguishes hard failures from preferences (soft-close is a preference, not a hard constraint)
- `values_compared` — structured data for the conversational layer to format
- `remediation` — actionable suggestion when a rule fails

## Enumerations

```python
class ProductFamily(Enum):
    CONCEALED_HINGE = "concealed_hinge"
    MOUNTING_PLATE = "mounting_plate"
    DRAWER_SLIDE = "drawer_slide"
    LIFT_SYSTEM = "lift_system"
    # ... 13 families total

class ApplicationType(Enum):
    FULL_OVERLAY = "full_overlay"
    HALF_OVERLAY = "half_overlay"
    INSET = "inset"
    OVERLAY = "overlay"          # Tiomos cranking 03

class CabinetType(Enum):
    FRAMELESS = "frameless"
    FACE_FRAME = "face_frame"

class CabinetPosition(Enum):
    STANDARD = "standard"
    CORNER = "corner"
    BLIND_CORNER = "blind_corner"

class MountingMethod(Enum):
    SCREW_ON = "screw_on"
    DOWEL = "dowel"
    EURO_SCREW = "euro_screw"
    SYSTEM_SCREW = "system_screw"
    INSERTA = "inserta"
    EXPANDO = "expando"
    IMPRESSO = "impresso"

class HingeSeries(Enum):
    CLIP_TOP_BLUMOTION = "CLIP top BLUMOTION"
    CLIP_TOP = "CLIP top"
    CLIP = "CLIP"
    TIOMOS = "Tiomos"
    NEXIS = "Nexis"
    DUOMATIC = "Duomatic"

class PlateType(Enum):
    CRUCIFORM = "cruciform"
    WING = "wing"
    WING_CAM = "wing_cam"
    INLINE = "inline"
    FACE_FRAME = "face_frame"
    FACE_FRAME_ADAPTER = "face_frame_adapter"
    FACE_FRAME_INSET = "face_frame_inset"
    THICK_WING = "thick_wing"
    TWO_PIECE = "two_piece"
    CAM_BASEPLATE = "cam_baseplate"

class PlateMaterial(Enum):
    STAMPED_STEEL = "stamped_steel"
    ZINC_DIECAST = "zinc_diecast"
    STEEL_NICKEL_PLATED = "steel_nickel_plated"

class RuleCategory(Enum):
    HARD_CONSTRAINT = "hard_constraint"     # must pass or config is invalid
    SOFT_CONSTRAINT = "soft_constraint"     # should pass but can be overridden
    PREFERENCE = "preference"               # customer preference, not a physical constraint
    DERIVED = "derived"                     # computed value (hinges per door)

class DoorMaterial(Enum):
    PARTICLEBOARD = "particleboard"
    MDF = "mdf"
    SOLID_WOOD = "solid_wood"
    PLYWOOD = "plywood"
    ALUMINUM = "aluminum"
    GLASS = "glass"
```

## What This Replaces

| PoC | Production |
|-----|-----------|
| `Hinge.sku` (mixed format, distributor-specific) | `ManufacturerProduct.manufacturer_part` (canonical) + `DistributorSKU.sku` (per-brand) |
| `Hinge.price_usd` (embedded, mostly null) | `DistributorSKU.price_usd` (separate feed) |
| `Hinge.image` (embedded path) | `ProductMedia` (separate concern) |
| `Hinge.compatible_mounting_plate_skus` (hand-maintained list) | Derived at query time by rules R001–R003, R014 |
| `Hinge.effective_max_weight_kg` (applies derating) | Removed — use `max_door_weight_kg` directly |
| `MountingPlate.overlay_range_mm: dict` (untyped, simplified) | `OverlayTable` with full BPH × DD lookup |
| `CustomerRequirements` (no drilling distance) | Adds `drilling_distance_mm`, `door_width_mm`, `door_material`, `preferred_series` |
| `RuleResult` (flat pass/fail + string) | Adds `category`, `values_compared`, `remediation` |
| String fields like `"frameless"` | `CabinetType.FRAMELESS` enum |

## Migration Path

The PoC dataclasses and JSON files remain as-is for the demo. The production model is implemented alongside them:

1. Define enums and value objects (zero risk — additive)
2. Define production entity classes using Pydantic (validation built-in)
3. Write adapters: `PoC JSON → production model` and `production model → engine input`
4. Run both engines in parallel against the golden test scenarios
5. Once parity is confirmed, retire the PoC loader

This avoids a risky big-bang rewrite while building toward the correct architecture.
