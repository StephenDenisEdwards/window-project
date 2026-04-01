"""LED cabinet lighting models.

A lighting system has three components:
  1. Light bar — the LED strip/bar (defines voltage, wattage, lumen output)
  2. Driver — transformer that powers the light bar (must match voltage, exceed wattage)
  3. Dimmer — optional switch for brightness control (must match driver's dimming protocol)

These models are shared by both the N-candidate and staged pipeline prototypes.
"""

from enum import Enum
from typing import Optional

from pydantic import Field

from engine_v2.core.models import Product, Requirements


class Voltage(str, Enum):
    DC_12V = "12V"
    DC_24V = "24V"


class DimmingProtocol(str, Enum):
    TRAILING_EDGE = "trailing_edge"
    LEADING_EDGE = "leading_edge"
    ZERO_TO_10V = "0-10V"
    DALI = "DALI"
    NONE = "none"


class ConnectorType(str, Enum):
    BARREL_JACK = "barrel_jack"
    TERMINAL_BLOCK = "terminal_block"
    PROPRIETARY = "proprietary"


# --- Products ---

class LightBar(Product):
    """LED light bar or strip for cabinet interior."""

    wattage: float                    # Power consumption in watts
    voltage: Voltage                  # Required input voltage
    length_mm: int                    # Physical length
    lumen_output: int                 # Brightness
    dimmable: bool                    # Whether the LEDs support dimming
    connector: ConnectorType          # How it connects to the driver
    color_temp_k: int = 4000          # Color temperature (warm=2700, cool=6500)
    ip_rating: str = "IP20"           # Ingress protection


class Driver(Product):
    """LED driver / transformer — converts mains AC to LED DC voltage."""

    output_voltage: Voltage           # Must match light bar voltage
    max_wattage: float                # Maximum load in watts
    output_channels: int              # How many light bars it can power
    dimmable: bool                    # Whether it supports dimming
    dimming_protocol: DimmingProtocol # Which dimming standard it uses
    connector: ConnectorType          # Output connector type
    efficiency: float = 0.90          # Power efficiency (0-1)


class Dimmer(Product):
    """Dimmer switch for brightness control."""

    dimming_protocol: DimmingProtocol  # Must match driver protocol
    max_wattage: float                 # Maximum load
    voltage_compatible: list[Voltage]  # Which voltages it works with
    min_load_wattage: float = 0        # Minimum load (some dimmers flicker below this)


# --- Requirements ---

class LightingRequirements(Requirements):
    """What the customer needs for their cabinet lighting."""

    cabinet_length_mm: int = Field(
        description="Interior length of the cabinet to illuminate in mm. The light bar must be shorter than this to fit.",
    )
    num_light_bars: int = Field(
        default=1,
        description="Number of light bars to install. Long cabinets or those needing even coverage may use 2+. Affects driver/dimmer sizing.",
    )
    dimming_required: bool = Field(
        default=False,
        description="Whether brightness control is needed. Requires a dimmable driver and compatible dimmer.",
    )
    min_lumen_output: int = Field(
        default=0,
        description="Minimum brightness per bar in lumens. Task lighting (cooking) needs more than accent lighting. 0 means no minimum.",
    )
    voltage_preference: Optional[Voltage] = Field(
        default=None,
        description="Preferred system voltage: 12V (common for short runs) or 24V (better for long runs, less voltage drop).",
    )
    max_budget_usd: Optional[float] = Field(
        default=None,
        description="Maximum total budget in USD for the complete system (bar + driver + dimmer).",
    )
