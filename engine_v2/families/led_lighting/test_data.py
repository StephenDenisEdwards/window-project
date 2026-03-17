"""Shared test data for LED lighting tests.

Both the N-candidate and staged pipeline tests use the same products
and scenarios so results can be compared directly.
"""

from engine_v2.families.led_lighting.models import (
    ConnectorType,
    Dimmer,
    DimmingProtocol,
    Driver,
    LightBar,
    Voltage,
)


# ===== Light bars =====

BAR_12V_5W = LightBar(
    sku="LED-BAR-12V-5W",
    brand="Loox",
    price_usd=25.00,
    wattage=5.0,
    voltage=Voltage.DC_12V,
    length_mm=300,
    lumen_output=400,
    dimmable=True,
    connector=ConnectorType.BARREL_JACK,
)

BAR_12V_10W = LightBar(
    sku="LED-BAR-12V-10W",
    brand="Loox",
    price_usd=40.00,
    wattage=10.0,
    voltage=Voltage.DC_12V,
    length_mm=600,
    lumen_output=800,
    dimmable=True,
    connector=ConnectorType.BARREL_JACK,
)

BAR_24V_15W = LightBar(
    sku="LED-BAR-24V-15W",
    brand="Loox",
    price_usd=55.00,
    wattage=15.0,
    voltage=Voltage.DC_24V,
    length_mm=900,
    lumen_output=1200,
    dimmable=True,
    connector=ConnectorType.TERMINAL_BLOCK,
)

BAR_24V_8W_DIM = LightBar(
    sku="LED-BAR-24V-8W",
    brand="Hafele",
    price_usd=35.00,
    wattage=8.0,
    voltage=Voltage.DC_24V,
    length_mm=450,
    lumen_output=600,
    dimmable=True,
    connector=ConnectorType.TERMINAL_BLOCK,
)

BAR_12V_LONG = LightBar(
    sku="LED-BAR-12V-LONG",
    brand="Loox",
    price_usd=65.00,
    wattage=20.0,
    voltage=Voltage.DC_12V,
    length_mm=1200,
    lumen_output=1600,
    dimmable=False,
    connector=ConnectorType.BARREL_JACK,
)


# ===== Drivers =====

DRV_12V_30W = Driver(
    sku="DRV-12V-30W",
    brand="Loox",
    price_usd=30.00,
    output_voltage=Voltage.DC_12V,
    max_wattage=30.0,
    output_channels=4,
    dimmable=True,
    dimming_protocol=DimmingProtocol.TRAILING_EDGE,
    connector=ConnectorType.BARREL_JACK,
)

DRV_12V_15W_NODIM = Driver(
    sku="DRV-12V-15W-ND",
    brand="Loox",
    price_usd=15.00,
    output_voltage=Voltage.DC_12V,
    max_wattage=15.0,
    output_channels=2,
    dimmable=False,
    dimming_protocol=DimmingProtocol.NONE,
    connector=ConnectorType.BARREL_JACK,
)

DRV_24V_60W = Driver(
    sku="DRV-24V-60W",
    brand="Hafele",
    price_usd=50.00,
    output_voltage=Voltage.DC_24V,
    max_wattage=60.0,
    output_channels=6,
    dimmable=True,
    dimming_protocol=DimmingProtocol.ZERO_TO_10V,
    connector=ConnectorType.TERMINAL_BLOCK,
)

DRV_24V_20W = Driver(
    sku="DRV-24V-20W",
    brand="Hafele",
    price_usd=28.00,
    output_voltage=Voltage.DC_24V,
    max_wattage=20.0,
    output_channels=2,
    dimmable=True,
    dimming_protocol=DimmingProtocol.TRAILING_EDGE,
    connector=ConnectorType.TERMINAL_BLOCK,
)


# ===== Dimmers =====

DIM_TRAILING_150W = Dimmer(
    sku="DIM-TE-150W",
    brand="Loox",
    price_usd=45.00,
    dimming_protocol=DimmingProtocol.TRAILING_EDGE,
    max_wattage=150.0,
    voltage_compatible=[Voltage.DC_12V, Voltage.DC_24V],
    min_load_wattage=5.0,
)

DIM_0_10V_200W = Dimmer(
    sku="DIM-010V-200W",
    brand="Hafele",
    price_usd=60.00,
    dimming_protocol=DimmingProtocol.ZERO_TO_10V,
    max_wattage=200.0,
    voltage_compatible=[Voltage.DC_24V],
    min_load_wattage=10.0,
)

DIM_TRAILING_SMALL = Dimmer(
    sku="DIM-TE-25W",
    brand="Loox",
    price_usd=20.00,
    dimming_protocol=DimmingProtocol.TRAILING_EDGE,
    max_wattage=25.0,
    voltage_compatible=[Voltage.DC_12V],
    min_load_wattage=2.0,
)

DIM_LEADING = Dimmer(
    sku="DIM-LE-100W",
    brand="Generic",
    price_usd=15.00,
    dimming_protocol=DimmingProtocol.LEADING_EDGE,
    max_wattage=100.0,
    voltage_compatible=[Voltage.DC_12V, Voltage.DC_24V],
    min_load_wattage=10.0,
)


# ===== Product lists =====

ALL_BARS = [BAR_12V_5W, BAR_12V_10W, BAR_24V_15W, BAR_24V_8W_DIM, BAR_12V_LONG]
ALL_DRIVERS = [DRV_12V_30W, DRV_12V_15W_NODIM, DRV_24V_60W, DRV_24V_20W]
ALL_DIMMERS = [DIM_TRAILING_150W, DIM_0_10V_200W, DIM_TRAILING_SMALL, DIM_LEADING]
