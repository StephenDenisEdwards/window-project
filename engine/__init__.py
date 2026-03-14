"""Production hinge constraint engine package."""

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
from .models import (
    ConcealedHinge,
    Configuration,
    CustomerRequirements,
    DistributorSKU,
    ManufacturerProduct,
    MountingPlate,
    OverlayEntry,
    OverlayTable,
    Range,
    RuleResult,
)
from .loader import load_from_json
from .solver import HingeConstraintEngine

__all__ = [
    # Enums
    "ApplicationType",
    "CabinetPosition",
    "CabinetType",
    "DoorMaterial",
    "HingeSeries",
    "MountingMethod",
    "PlateMaterial",
    "PlateType",
    "ProductFamily",
    "RuleCategory",
    # Models
    "ConcealedHinge",
    "Configuration",
    "CustomerRequirements",
    "DistributorSKU",
    "ManufacturerProduct",
    "MountingPlate",
    "OverlayEntry",
    "OverlayTable",
    "Range",
    "RuleResult",
    # Loader
    "load_from_json",
    # Engine
    "HingeConstraintEngine",
]
