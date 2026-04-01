"""Drawer slide models.

Drawer slides are a single-product family — no secondary product to pair with.
The customer specifies cabinet depth, drawer weight, extension type, and mounting
preference. The engine finds all slides that satisfy these constraints.
"""

from enum import Enum
from typing import Optional

from pydantic import Field

from engine_v2.core.models import Product, Requirements


class ExtensionType(str, Enum):
    THREE_QUARTER = "three_quarter"  # Slide extends 75% of its length
    FULL = "full"                     # Slide extends 100% of its length
    OVER_TRAVEL = "over_travel"       # Slide extends beyond cabinet face


class SlideMountType(str, Enum):
    SIDE_MOUNT = "side_mount"
    UNDERMOUNT = "undermount"
    CENTER_MOUNT = "center_mount"


class SlideCloseType(str, Enum):
    SELF_CLOSE = "self_close"       # Spring-assisted return
    SOFT_CLOSE = "soft_close"       # Damped closing
    PUSH_OPEN = "push_open"         # Touch-latch, no handle needed
    STANDARD = "standard"           # Manual, no assist


class DrawerSlide(Product):
    """A single drawer slide (sold in pairs — pricing is per pair)."""

    series: str
    slide_length_mm: int             # Nominal length (matches cabinet depth)
    max_load_kg: float               # Per-pair load rating
    extension_type: ExtensionType
    mount_type: SlideMountType
    close_type: SlideCloseType
    requires_rear_bracket: bool = False
    min_cabinet_depth_mm: int = 0    # Some slides need extra depth behind the drawer
    disconnect_feature: bool = False  # Can drawer be removed without tools?


class SlideRequirements(Requirements):
    """What the customer needs for their drawer slide selection."""

    cabinet_depth_mm: int = Field(
        description="Internal depth of the cabinet box in mm. The slide must fit inside this depth.",
    )
    drawer_weight_kg: float = Field(
        description="Total loaded weight of the drawer (contents + drawer box) in kg. Slides are rated for a maximum load.",
    )
    drawer_width_mm: Optional[int] = Field(
        default=None,
        description="Drawer opening width in mm. Only relevant for undermount slides, which have maximum width limits.",
    )
    extension_type: Optional[ExtensionType] = Field(
        default=None,
        description="How far the drawer pulls out: three_quarter (75%), full (100%, clears cabinet face), or over_travel (extends past face).",
    )
    mount_type: Optional[SlideMountType] = Field(
        default=None,
        description="How the slide attaches: side_mount (screws to wall), undermount (hidden beneath drawer), or center_mount (single slide underneath).",
    )
    soft_close: bool = Field(
        default=False,
        description="Whether the drawer should decelerate and self-close with a damped mechanism.",
    )
    push_open: bool = Field(
        default=False,
        description="Whether the drawer opens with a push (no handle needed). Uses a spring-loaded touch latch.",
    )
    disconnect_required: bool = Field(
        default=False,
        description="Whether the drawer must be removable without tools (e.g. for cleaning). Requires a quick-release lever.",
    )
