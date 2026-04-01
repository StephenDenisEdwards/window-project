"""Concealed hinge models for the v2 engine.

These extend the core Product/Requirements base classes with hinge-specific
fields. The models mirror engine_v1's domain but use v2's base classes so
they work with NCandidateSolver.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

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

    cabinet_type: CabinetType = Field(
        description="Construction style: frameless (European, door mounts to side panel) or face_frame (American, wooden frame around opening).",
    )
    door_thickness_mm: float = Field(
        description="Thickness of the door panel in mm (typically 16-22mm). Must be thick enough for the hinge cup bore.",
    )
    door_height_mm: float = Field(
        description="Door height in mm. Determines how many hinges are needed: 2 for standard, 3 for ~900mm+, 4 for ~1600mm+.",
    )
    door_weight_kg: float = Field(
        description="Total door weight in kg. Each hinge has a max weight rating; combined capacity must exceed this.",
    )
    application: ApplicationType = Field(
        description="How the door sits: full_overlay (covers cabinet edge), half_overlay (shares partition with adjacent door), or inset (flush inside opening).",
    )
    desired_overlay_mm: float = Field(
        description="How far the door overlaps the cabinet edge in mm. Full overlay is typically 14-20mm, half overlay 3-9mm.",
    )
    boring_pattern_mm: int = Field(
        description="Distance from door edge to hinge cup centre in mm. Industry standard is 45mm; some hinges use 52mm.",
    )
    soft_close: bool = Field(
        description="Whether damped closing is required (door decelerates and pulls itself shut quietly).",
    )
    cabinet_position: CabinetPosition = Field(
        default=CabinetPosition.STANDARD,
        description="Cabinet location: standard or corner. Corner cabinets need wide-angle hinges (>=155 deg) so the door clears the adjacent cabinet.",
    )
    has_adjacent_door: bool = Field(
        default=False,
        description="Whether another door shares the same partition (e.g. two doors meeting in the middle). Triggers clearance check.",
    )
    adjacent_door_overlay_mm: float = Field(
        default=0,
        description="How far the neighbouring door overlaps the shared partition in mm. Combined overlay of both doors cannot exceed partition thickness.",
    )
    partition_thickness_mm: float = Field(
        default=19,
        description="Thickness of the panel between two adjacent doors in mm (default 19mm). Used with adjacent door overlay for clearance check.",
    )
    face_frame_width_mm: float = Field(
        default=0,
        description="Width of the face frame rail in mm (face-frame cabinets only). Overlay cannot exceed frame width minus 3mm.",
    )
