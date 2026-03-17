"""Constraint rules for LED cabinet lighting.

Rules are written for the N-candidate signature:
    (candidates: dict[str, Product], req: Requirements, derived: dict) -> RuleResult

Both the flat N-candidate solver and the staged pipeline solver use
the same rule functions — only the grouping differs. The staged solver
assigns rules to stages; the flat solver runs them all at once.

Constraints by relationship:
    Light bar ↔ Driver:   voltage match (LED001), wattage capacity (LED002), connector (LED003)
    Driver ↔ Dimmer:      dimming protocol (LED004)
    All three:            total wattage under dimmer limit (LED005)
    Light bar only:       length fits cabinet (LED006), minimum brightness (LED007)
    Light bar ↔ Driver:   driver supports dimming if required (LED008)
"""

from engine_v2.core.models import Product, Requirements, RuleCategory, RuleResult
from engine_v2.families.led_lighting.models import (
    Dimmer,
    Driver,
    LightBar,
    LightingRequirements,
)


# --- Stage 1 rules: Light bar ↔ Driver ---

def check_voltage_match(candidates: dict[str, Product], req: Requirements, derived: dict) -> RuleResult:
    """LED001: Light bar voltage must match driver output voltage."""
    bar: LightBar = candidates["light_bar"]  # type: ignore[assignment]
    drv: Driver = candidates["driver"]  # type: ignore[assignment]
    passed = bar.voltage == drv.output_voltage
    return RuleResult(
        rule_id="LED001",
        rule_name="voltage_match",
        passed=passed,
        detail=f"Light bar {bar.voltage.value} {'==' if passed else '!='} driver output {drv.output_voltage.value}",
        category=RuleCategory.HARD_CONSTRAINT,
        values_compared={"bar_voltage": bar.voltage.value, "driver_voltage": drv.output_voltage.value},
        remediation=None if passed else f"Select a {bar.voltage.value} driver or a {drv.output_voltage.value} light bar",
    )


def check_wattage_capacity(candidates: dict[str, Product], req: Requirements, derived: dict) -> RuleResult:
    """LED002: Driver must handle total wattage of all light bars with 20% headroom."""
    bar: LightBar = candidates["light_bar"]  # type: ignore[assignment]
    drv: Driver = candidates["driver"]  # type: ignore[assignment]
    r: LightingRequirements = req  # type: ignore[assignment]
    total_wattage = bar.wattage * r.num_light_bars
    # 80% rule: driver should not be loaded above 80% for longevity
    safe_capacity = drv.max_wattage * 0.8
    passed = total_wattage <= safe_capacity
    return RuleResult(
        rule_id="LED002",
        rule_name="wattage_capacity",
        passed=passed,
        detail=f"Total load {total_wattage}W {'<=' if passed else '>'} safe capacity {safe_capacity}W (80% of {drv.max_wattage}W)",
        category=RuleCategory.HARD_CONSTRAINT,
        values_compared={"total_load": total_wattage, "safe_capacity": safe_capacity, "driver_max": drv.max_wattage},
        remediation=None if passed else f"Need a driver rated for at least {total_wattage / 0.8:.0f}W",
    )


def check_connector_match(candidates: dict[str, Product], req: Requirements, derived: dict) -> RuleResult:
    """LED003: Light bar connector must match driver output connector."""
    bar: LightBar = candidates["light_bar"]  # type: ignore[assignment]
    drv: Driver = candidates["driver"]  # type: ignore[assignment]
    passed = bar.connector == drv.connector
    return RuleResult(
        rule_id="LED003",
        rule_name="connector_match",
        passed=passed,
        detail=f"Bar connector {bar.connector.value} {'==' if passed else '!='} driver connector {drv.connector.value}",
        category=RuleCategory.HARD_CONSTRAINT,
        values_compared={"bar": bar.connector.value, "driver": drv.connector.value},
        remediation=None if passed else "Connectors don't match — use an adapter or select compatible products",
    )


def check_bar_length(candidates: dict[str, Product], req: Requirements, derived: dict) -> RuleResult:
    """LED006: Light bar must fit inside the cabinet."""
    bar: LightBar = candidates["light_bar"]  # type: ignore[assignment]
    r: LightingRequirements = req  # type: ignore[assignment]
    passed = bar.length_mm <= r.cabinet_length_mm
    return RuleResult(
        rule_id="LED006",
        rule_name="bar_length",
        passed=passed,
        detail=f"Bar {bar.length_mm}mm {'<=' if passed else '>'} cabinet {r.cabinet_length_mm}mm",
        category=RuleCategory.HARD_CONSTRAINT,
        values_compared={"bar_length": bar.length_mm, "cabinet_length": r.cabinet_length_mm},
        remediation=None if passed else f"Bar is {bar.length_mm - r.cabinet_length_mm}mm too long for this cabinet",
    )


def check_brightness(candidates: dict[str, Product], req: Requirements, derived: dict) -> RuleResult:
    """LED007: Light bar meets minimum lumen output."""
    bar: LightBar = candidates["light_bar"]  # type: ignore[assignment]
    r: LightingRequirements = req  # type: ignore[assignment]
    if r.min_lumen_output == 0:
        return RuleResult(
            rule_id="LED007",
            rule_name="brightness",
            passed=True,
            detail="No minimum brightness requirement",
            category=RuleCategory.PREFERENCE,
        )
    passed = bar.lumen_output >= r.min_lumen_output
    return RuleResult(
        rule_id="LED007",
        rule_name="brightness",
        passed=passed,
        detail=f"Bar output {bar.lumen_output} lm {'>=' if passed else '<'} required {r.min_lumen_output} lm",
        category=RuleCategory.PREFERENCE,
        values_compared={"bar_lumen": bar.lumen_output, "required": r.min_lumen_output},
        remediation=None if passed else f"This bar produces {r.min_lumen_output - bar.lumen_output} lm less than required",
    )


def check_driver_supports_dimming(candidates: dict[str, Product], req: Requirements, derived: dict) -> RuleResult:
    """LED008: If dimming is required, driver must support it."""
    drv: Driver = candidates["driver"]  # type: ignore[assignment]
    r: LightingRequirements = req  # type: ignore[assignment]
    if not r.dimming_required:
        return RuleResult(
            rule_id="LED008",
            rule_name="driver_dimming_support",
            passed=True,
            detail="Dimming not required",
            category=RuleCategory.HARD_CONSTRAINT,
        )
    passed = drv.dimmable
    return RuleResult(
        rule_id="LED008",
        rule_name="driver_dimming_support",
        passed=passed,
        detail=f"Driver dimming {'supported' if passed else 'not supported'}",
        category=RuleCategory.HARD_CONSTRAINT,
        values_compared={"driver_dimmable": drv.dimmable, "required": True},
        remediation=None if passed else "Select a dimmable driver",
    )


# --- Stage 2 rules: Driver ↔ Dimmer (+ light bar for total wattage) ---

def check_dimming_protocol(candidates: dict[str, Product], req: Requirements, derived: dict) -> RuleResult:
    """LED004: Dimmer protocol must match driver protocol."""
    drv: Driver = candidates["driver"]  # type: ignore[assignment]
    dim: Dimmer = candidates["dimmer"]  # type: ignore[assignment]
    passed = drv.dimming_protocol == dim.dimming_protocol
    return RuleResult(
        rule_id="LED004",
        rule_name="dimming_protocol",
        passed=passed,
        detail=f"Driver protocol {drv.dimming_protocol.value} {'==' if passed else '!='} dimmer protocol {dim.dimming_protocol.value}",
        category=RuleCategory.HARD_CONSTRAINT,
        values_compared={"driver": drv.dimming_protocol.value, "dimmer": dim.dimming_protocol.value},
        remediation=None if passed else f"Select a {drv.dimming_protocol.value} dimmer or a {dim.dimming_protocol.value}-compatible driver",
    )


def check_dimmer_wattage(candidates: dict[str, Product], req: Requirements, derived: dict) -> RuleResult:
    """LED005: Total system wattage must be within dimmer's rated range."""
    bar: LightBar = candidates["light_bar"]  # type: ignore[assignment]
    dim: Dimmer = candidates["dimmer"]  # type: ignore[assignment]
    r: LightingRequirements = req  # type: ignore[assignment]
    total_wattage = bar.wattage * r.num_light_bars

    under_max = total_wattage <= dim.max_wattage
    over_min = total_wattage >= dim.min_load_wattage
    passed = under_max and over_min

    if not under_max:
        detail = f"Total load {total_wattage}W > dimmer max {dim.max_wattage}W"
        remediation = f"Need a dimmer rated for at least {total_wattage}W"
    elif not over_min:
        detail = f"Total load {total_wattage}W < dimmer minimum {dim.min_load_wattage}W (may cause flickering)"
        remediation = "Add more light bars or use a dimmer with a lower minimum load"
    else:
        detail = f"Total load {total_wattage}W within dimmer range [{dim.min_load_wattage}-{dim.max_wattage}W]"
        remediation = None

    return RuleResult(
        rule_id="LED005",
        rule_name="dimmer_wattage",
        passed=passed,
        detail=detail,
        category=RuleCategory.HARD_CONSTRAINT,
        values_compared={"total_wattage": total_wattage, "dimmer_min": dim.min_load_wattage, "dimmer_max": dim.max_wattage},
        remediation=remediation,
    )


def check_dimmer_voltage(candidates: dict[str, Product], req: Requirements, derived: dict) -> RuleResult:
    """LED009: Dimmer must be compatible with the system voltage."""
    drv: Driver = candidates["driver"]  # type: ignore[assignment]
    dim: Dimmer = candidates["dimmer"]  # type: ignore[assignment]
    passed = drv.output_voltage in dim.voltage_compatible
    return RuleResult(
        rule_id="LED009",
        rule_name="dimmer_voltage",
        passed=passed,
        detail=f"Driver voltage {drv.output_voltage.value} {'in' if passed else 'not in'} dimmer compatible voltages {[v.value for v in dim.voltage_compatible]}",
        category=RuleCategory.HARD_CONSTRAINT,
        values_compared={"driver_voltage": drv.output_voltage.value, "dimmer_voltages": [v.value for v in dim.voltage_compatible]},
        remediation=None if passed else f"Select a dimmer that supports {drv.output_voltage.value}",
    )


# === Rule groupings ===

# All rules in flat order (for N-candidate solver)
ALL_RULES = [
    check_voltage_match,      # LED001 — bar ↔ driver
    check_wattage_capacity,   # LED002 — bar ↔ driver
    check_connector_match,    # LED003 — bar ↔ driver
    check_bar_length,         # LED006 — bar ↔ cabinet
    check_brightness,         # LED007 — bar ↔ requirements
    check_driver_supports_dimming,  # LED008 — driver ↔ requirements
    check_dimming_protocol,   # LED004 — driver ↔ dimmer
    check_dimmer_wattage,     # LED005 — bar + dimmer
    check_dimmer_voltage,     # LED009 — driver ↔ dimmer
]

# Rules split by stage (for staged pipeline solver)
STAGE_1_RULES = [
    check_voltage_match,      # LED001
    check_wattage_capacity,   # LED002
    check_connector_match,    # LED003
    check_bar_length,         # LED006
    check_brightness,         # LED007
    check_driver_supports_dimming,  # LED008
]

STAGE_2_RULES = [
    check_dimming_protocol,   # LED004
    check_dimmer_wattage,     # LED005
    check_dimmer_voltage,     # LED009
]
