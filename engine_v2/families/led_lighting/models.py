"""LED cabinet lighting models.

A lighting system has three components:
  1. Light bar — the LED strip/bar (defines voltage, wattage, lumen output)
  2. Driver — transformer that powers the light bar (must match voltage, exceed wattage)
  3. Dimmer — optional switch for brightness control (must match driver's dimming protocol)

These models are shared by both the N-candidate and staged pipeline prototypes.
"""

from enum import Enum
from typing import Optional

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

    cabinet_length_mm: int             # Interior length to illuminate
    num_light_bars: int = 1            # How many bars (e.g., 2 for long cabinets)
    dimming_required: bool = False     # Whether dimming is needed
    min_lumen_output: int = 0          # Minimum brightness per bar
    voltage_preference: Optional[Voltage] = None  # None = no preference
    max_budget_usd: Optional[float] = None         # Total system budget
