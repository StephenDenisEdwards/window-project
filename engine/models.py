"""Production domain models using Pydantic v2."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, model_validator

from .enums import (
    ApplicationType,
    CabinetPosition,
    CabinetType,
    DoorMaterial,
    HingeSeries,
    MountingMethod,
    PlateMaterial,
    PlateType,
    ProductFamily,
    RuleCategory,
)


# ---------------------------------------------------------------------------
# Value objects
# ---------------------------------------------------------------------------


class Range(BaseModel):
    min: float
    max: float

    def contains(self, value: float) -> bool:
        return self.min <= value <= self.max


class OverlayEntry(BaseModel):
    base_plate_height_mm: float
    drilling_distance_mm: float
    overlay_mm: float


class OverlayTable(BaseModel):
    entries: dict[ApplicationType, list[OverlayEntry]]

    def supports(self, app: ApplicationType) -> bool:
        app_entries = self.entries.get(app, [])
        return len(app_entries) > 0

    def achievable_overlay(self, app: ApplicationType, drilling_distance: float) -> Optional[float]:
        """Return the exact overlay for the given app and drilling distance, or None."""
        app_entries = self.entries.get(app, [])
        for entry in app_entries:
            if entry.drilling_distance_mm == drilling_distance:
                return entry.overlay_mm
        return None

    def overlay_range(self, app: ApplicationType) -> Optional[Range]:
        """Return the min/max overlay range across all entries for this application type."""
        app_entries = self.entries.get(app, [])
        if not app_entries:
            return None
        overlays = [e.overlay_mm for e in app_entries]
        return Range(min=min(overlays), max=max(overlays))


# ---------------------------------------------------------------------------
# Product identity
# ---------------------------------------------------------------------------


class DistributorSKU(BaseModel):
    sku: str
    brand: str
    price_usd: Optional[float] = None
    in_stock: bool = True
    url: Optional[str] = None


class ManufacturerProduct(BaseModel):
    manufacturer_part: str
    manufacturer: str
    product_family: ProductFamily
    distributor_skus: list[DistributorSKU] = []


# ---------------------------------------------------------------------------
# Concealed hinge
# ---------------------------------------------------------------------------


class ConcealedHinge(ManufacturerProduct):
    series: HingeSeries
    application: ApplicationType
    opening_angle_deg: int
    cup_diameter_mm: float
    cup_depth_mm: Optional[float] = None
    boring_pattern_mm: int
    crank_mm: float
    door_thickness_range_mm: Range
    max_door_weight_kg: float
    soft_close: bool
    mounting_method: MountingMethod
    cabinet_type: CabinetType
    notes: Optional[str] = None

    # Convenience properties that mirror PoC field names for adapter compatibility
    @property
    def sku(self) -> str:
        """Primary distributor SKU for backward compatibility."""
        if self.distributor_skus:
            return self.distributor_skus[0].sku
        return self.manufacturer_part

    @property
    def brand(self) -> str:
        return self.manufacturer

    @property
    def price_usd(self) -> Optional[float]:
        if self.distributor_skus:
            return self.distributor_skus[0].price_usd
        return None

    @property
    def door_thickness_min_mm(self) -> float:
        return self.door_thickness_range_mm.min

    @property
    def door_thickness_max_mm(self) -> float:
        return self.door_thickness_range_mm.max


# ---------------------------------------------------------------------------
# Mounting plate
# ---------------------------------------------------------------------------


class MountingPlate(ManufacturerProduct):
    series: str  # PlateSeries but keep flexible for loading
    plate_type: PlateType
    mounting_method: MountingMethod
    cabinet_type: CabinetType
    plate_height_mm: float
    compatible_hinge_series: list[HingeSeries]
    overlay_table: OverlayTable
    height_adjustment_mm: float = 0
    depth_adjustment_mm: float = 0
    setback_mm: float = 0
    material: Optional[PlateMaterial] = None
    fixing_points: int = 0
    notes: Optional[str] = None

    # Backward-compatible overlay_range_mm property
    @property
    def overlay_range_mm(self) -> dict:
        """Return PoC-compatible overlay range dict."""
        result = {}
        for app_type, entries in self.overlay_table.entries.items():
            if app_type == ApplicationType.INSET:
                result["inset"] = True
            elif app_type == ApplicationType.FULL_OVERLAY:
                overlays = [e.overlay_mm for e in entries]
                result["full"] = [min(overlays), max(overlays)]
            elif app_type == ApplicationType.HALF_OVERLAY:
                overlays = [e.overlay_mm for e in entries]
                result["half"] = [min(overlays), max(overlays)]
        # Add explicit False for unsupported
        if "inset" not in result:
            result["inset"] = False
        return result

    @property
    def sku(self) -> str:
        if self.distributor_skus:
            return self.distributor_skus[0].sku
        return self.manufacturer_part

    @property
    def brand(self) -> str:
        return self.manufacturer

    @property
    def price_usd(self) -> Optional[float]:
        if self.distributor_skus:
            return self.distributor_skus[0].price_usd
        return None


# ---------------------------------------------------------------------------
# Customer requirements
# ---------------------------------------------------------------------------


class CustomerRequirements(BaseModel):
    cabinet_type: CabinetType
    door_thickness_mm: float
    door_height_mm: float
    door_weight_kg: float
    application: ApplicationType
    desired_overlay_mm: float
    boring_pattern_mm: int
    soft_close: bool
    cabinet_position: CabinetPosition = CabinetPosition.STANDARD
    preferred_brand: Optional[str] = None
    brand_lock: bool = True
    preferred_series: Optional[str] = None
    has_adjacent_door: bool = False
    adjacent_door_overlay_mm: float = 0
    partition_thickness_mm: float = 19
    face_frame_width_mm: float = 0
    drilling_distance_mm: float = 5.0
    door_width_mm: Optional[float] = None
    door_material: Optional[DoorMaterial] = None


# ---------------------------------------------------------------------------
# Rule result & configuration
# ---------------------------------------------------------------------------


class RuleResult(BaseModel):
    rule_id: str
    rule_name: str
    passed: bool
    detail: str
    category: RuleCategory = RuleCategory.HARD_CONSTRAINT
    values_compared: Optional[dict] = None
    remediation: Optional[str] = None


class Configuration(BaseModel):
    hinge: ConcealedHinge
    plate: MountingPlate
    hinges_per_door: int
    total_weight_capacity_kg: float
    rule_results: list[RuleResult] = []

    model_config = {"arbitrary_types_allowed": True}

    @property
    def valid(self) -> bool:
        return all(r.passed for r in self.rule_results)

    @property
    def failed_rules(self) -> list[RuleResult]:
        return [r for r in self.rule_results if not r.passed]

    @property
    def total_price_usd(self) -> Optional[float]:
        h_price = self.hinge.price_usd
        p_price = self.plate.price_usd
        if h_price is None or p_price is None:
            return None
        return round((h_price + p_price) * self.hinges_per_door, 2)
