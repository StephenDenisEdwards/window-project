"""Base models for the multi-family constraint engine."""

from enum import Enum
from typing import Optional

from pydantic import BaseModel


class RuleCategory(str, Enum):
    HARD_CONSTRAINT = "hard_constraint"
    SOFT_CONSTRAINT = "soft_constraint"
    PREFERENCE = "preference"
    DERIVED = "derived"


class Product(BaseModel):
    """Base class for all products across all families."""

    sku: str
    brand: str
    price_usd: Optional[float] = None


class Requirements(BaseModel):
    """Base class for customer requirements across all families.

    Each family subclasses this with its specific fields.
    """

    preferred_brand: Optional[str] = None
    brand_lock: bool = True


class RuleResult(BaseModel):
    """Result of evaluating a single constraint rule.

    Identical structure to engine.models.RuleResult — the tracing format
    is shared across all families so the API and conversational layers
    don't need family-specific formatting.
    """

    rule_id: str
    rule_name: str
    passed: bool
    detail: str
    category: RuleCategory = RuleCategory.HARD_CONSTRAINT
    values_compared: Optional[dict] = None
    remediation: Optional[str] = None


class Configuration(BaseModel):
    """A candidate configuration: one or two products evaluated against requirements.

    For paired families (hinges + plates): primary and secondary are both set.
    For single-product families (drawer slides): only primary is set.
    """

    primary: Product
    secondary: Optional[Product] = None
    rule_results: list[RuleResult] = []
    derived: dict = {}  # Family-specific derived values (e.g., hinges_per_door)

    @property
    def valid(self) -> bool:
        return all(r.passed for r in self.rule_results)

    @property
    def failed_rules(self) -> list[RuleResult]:
        return [r for r in self.rule_results if not r.passed]

    @property
    def passed_count(self) -> int:
        return sum(1 for r in self.rule_results if r.passed)

    @property
    def total_price_usd(self) -> Optional[float]:
        qty = self.derived.get("quantity", 1)
        p_price = self.primary.price_usd
        s_price = self.secondary.price_usd if self.secondary else 0
        if p_price is None:
            return None
        s = s_price if s_price is not None else 0
        return (p_price + s) * qty
