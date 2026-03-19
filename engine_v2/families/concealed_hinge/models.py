"""Concealed hinge models for the v2 engine.

These extend the core Product/Requirements base classes with hinge-specific
fields. The models mirror engine_v1's domain but use v2's base classes so
they work with NCandidateSolver.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel

from engine_v2.core.models import Product, Requirements


# --- Enums ---

class ApplicationType(str, Enum):
    FULL_OVERLAY = "full_overlay"
    HALF_OVERLAY = "half_overlay"
    INSET = "inset"
    OVERLAY = "overlay"


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


class PlateType(str, Enum):
    CRUCIFORM = "cruciform"
    WING = "wing"
    WING_CAM = "wing_cam"
    THICK_WING = "thick_wing"
    FACE_FRAME = "face_frame"
    FACE_FRAME_ADAPTER = "face_frame_adapter"
    FACE_FRAME_INSET = "face_frame_inset"
    INLINE = "inline"
    CAM_BASEPLATE = "cam_baseplate"
    TWO_PIECE = "two_piece"


# --- Value objects ---

class Range(BaseModel):
    min: float
    max: float

    def contains(self, value: float) -> bool:
        return self.min <= value <= self.max


# --- Products ---

class Hinge(Product):
    """Concealed European hinge."""

    series: HingeSeries
    application: ApplicationType
    opening_angle_deg: int
    boring_pattern_mm: int
    door_thickness_range_mm: Range
    max_door_weight_kg: float
    soft_close: bool
    mounting_method: MountingMethod
    cabinet_type: CabinetType
    cup_depth_mm: Optional[float] = None


class Plate(Product):
    """Mounting plate for concealed hinges."""

    series: str
    compatible_hinge_series: list[HingeSeries]
    mounting_method: MountingMethod
    cabinet_type: CabinetType
    plate_type: PlateType = PlateType.CRUCIFORM
    # Overlay stored as the same dict format as v1 JSON:
    # {"full": [min, max], "half": [min, max], "inset": true/false}
    overlay_range_mm: dict = {}


# --- Requirements ---

class HingeRequirements(Requirements):
    """What the customer needs for their hinge selection."""

    cabinet_type: CabinetType
    door_thickness_mm: float
    door_height_mm: float
    door_weight_kg: float
    application: ApplicationType
    desired_overlay_mm: float
    boring_pattern_mm: int
    soft_close: bool
    cabinet_position: CabinetPosition = CabinetPosition.STANDARD
    has_adjacent_door: bool = False
    adjacent_door_overlay_mm: float = 0
    partition_thickness_mm: float = 19
    face_frame_width_mm: float = 0
