"""LED lighting family — N-candidate solver configuration (N=3)."""

from __future__ import annotations

from engine_v2.core.solver_n import NFamilyConfig
from engine_v2.families.led_lighting.models import (
    Dimmer,
    Driver,
    LightBar,
    LightingRequirements,
)
from engine_v2.families.led_lighting.rules import ALL_RULES


LED_N_CONFIG = NFamilyConfig(
    name="led_lighting",
    roles=[
        ("light_bar", LightBar),
        ("driver", Driver),
        ("dimmer", Dimmer),
    ],
    requirements_type=LightingRequirements,
    rules=ALL_RULES,
    rank_key=lambda c: (
        0 if c.total_price_usd is not None else 1,
        c.total_price_usd or 0,
    ),
    early_termination=True,
)
