"""Product family registry — each family registers its components here."""

from dataclasses import dataclass, field
from typing import Optional

from engine_v2.core.models import Product, Requirements
from engine_v2.core.types import DerivedValuesFn, PreFilterFn, RankKeyFn, RuleFn


def _default_derived(req: Requirements) -> dict:
    return {}


def _default_rank(config) -> tuple:
    price = config.total_price_usd
    return (0 if price is not None else 1, price or 0)


@dataclass
class FamilyConfig:
    """Everything the generic solver needs to handle a product family."""

    name: str
    primary_type: type[Product]
    secondary_type: Optional[type[Product]]  # None for single-product families
    requirements_type: type[Requirements]
    rules: list[RuleFn]
    pre_filters: list[PreFilterFn] = field(default_factory=list)
    rank_key: RankKeyFn = _default_rank
    derived_values: DerivedValuesFn = _default_derived
    early_termination: bool = True  # Stop evaluating rules after first hard constraint failure


class FamilyRegistry:
    """Central registry of product families."""

    def __init__(self):
        self._families: dict[str, FamilyConfig] = {}

    def register(self, config: FamilyConfig) -> None:
        self._families[config.name] = config

    def get(self, name: str) -> FamilyConfig:
        if name not in self._families:
            raise KeyError(f"Unknown product family: {name!r}. Registered: {list(self._families.keys())}")
        return self._families[name]

    def list_families(self) -> list[str]:
        return list(self._families.keys())


# Global registry instance
registry = FamilyRegistry()
