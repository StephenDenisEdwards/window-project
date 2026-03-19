"""Load sample-data/ JSON into v2 LED lighting models."""

from __future__ import annotations

import json
from pathlib import Path

from .models import (
    ConnectorType,
    Dimmer,
    DimmingProtocol,
    Driver,
    LightBar,
    Voltage,
)


def load_from_json(data_dir: Path) -> tuple[list[LightBar], list[Driver], list[Dimmer]]:
    """Load light bars, drivers, and dimmers from JSON files."""
    with open(data_dir / "light_bars.json") as f:
        raw_bars = json.load(f)
    with open(data_dir / "drivers.json") as f:
        raw_drivers = json.load(f)
    with open(data_dir / "dimmers.json") as f:
        raw_dimmers = json.load(f)

    bars = [
        LightBar(
            sku=b["sku"],
            brand=b["brand"],
            price_usd=b.get("price_usd"),
            wattage=b["wattage"],
            voltage=Voltage(b["voltage"]),
            length_mm=b["length_mm"],
            lumen_output=b["lumen_output"],
            dimmable=b["dimmable"],
            connector=ConnectorType(b["connector"]),
        )
        for b in raw_bars
    ]

    drivers = [
        Driver(
            sku=d["sku"],
            brand=d["brand"],
            price_usd=d.get("price_usd"),
            output_voltage=Voltage(d["output_voltage"]),
            max_wattage=d["max_wattage"],
            output_channels=d["output_channels"],
            dimmable=d["dimmable"],
            dimming_protocol=DimmingProtocol(d["dimming_protocol"]),
            connector=ConnectorType(d["connector"]),
        )
        for d in raw_drivers
    ]

    dimmers = [
        Dimmer(
            sku=d["sku"],
            brand=d["brand"],
            price_usd=d.get("price_usd"),
            dimming_protocol=DimmingProtocol(d["dimming_protocol"]),
            max_wattage=d["max_wattage"],
            voltage_compatible=[Voltage(v) for v in d["voltage_compatible"]],
            min_load_wattage=d.get("min_load_wattage", 0),
        )
        for d in raw_dimmers
    ]

    return bars, drivers, dimmers
