"""Enumerations for the hinge constraint engine domain model."""

from enum import Enum


class ProductFamily(str, Enum):
    CONCEALED_HINGE = "concealed_hinge"
    MOUNTING_PLATE = "mounting_plate"
    DRAWER_SLIDE = "drawer_slide"
    LIFT_SYSTEM = "lift_system"


class ApplicationType(str, Enum):
    FULL_OVERLAY = "full_overlay"
    HALF_OVERLAY = "half_overlay"
    INSET = "inset"
    OVERLAY = "overlay"  # Tiomos cranking 03


class CabinetType(str, Enum):
    FRAMELESS = "frameless"
    FACE_FRAME = "face_frame"


class CabinetPosition(str, Enum):
    STANDARD = "standard"
    CORNER = "corner"
    BLIND_CORNER = "blind_corner"


class MountingMethod(str, Enum):
    SCREW_ON = "screw_on"
    DOWEL = "dowel"
    EURO_SCREW = "euro_screw"
    SYSTEM_SCREW = "system_screw"
    INSERTA = "inserta"
    EXPANDO = "expando"
    IMPRESSO = "impresso"


class HingeSeries(str, Enum):
    CLIP_TOP_BLUMOTION = "CLIP top BLUMOTION"
    CLIP_TOP = "CLIP top"
    CLIP = "CLIP"
    TIOMOS = "Tiomos"
    NEXIS = "Nexis"
    DUOMATIC = "Duomatic"


class PlateSeries(str, Enum):
    CLIP = "CLIP"
    TIOMOS = "Tiomos"
    NEXIS = "Nexis"
    DUOMATIC = "Duomatic"


class PlateType(str, Enum):
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


class PlateMaterial(str, Enum):
    STAMPED_STEEL = "stamped_steel"
    ZINC_DIECAST = "zinc_diecast"
    STEEL_NICKEL_PLATED = "steel_nickel_plated"
    ZINC_DIECAST_STEEL = "zinc_diecast_steel"
    STEEL_DIECAST_NICKEL_PLATED = "steel_diecast_nickel_plated"


class RuleCategory(str, Enum):
    HARD_CONSTRAINT = "hard_constraint"
    SOFT_CONSTRAINT = "soft_constraint"
    PREFERENCE = "preference"
    DERIVED = "derived"


class DoorMaterial(str, Enum):
    PARTICLEBOARD = "particleboard"
    MDF = "mdf"
    SOLID_WOOD = "solid_wood"
    PLYWOOD = "plywood"
    ALUMINUM = "aluminum"
    GLASS = "glass"
