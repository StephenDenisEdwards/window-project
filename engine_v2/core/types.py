"""Type aliases for the multi-family constraint engine."""

from typing import Any, Callable

from engine_v2.core.models import Configuration, Product, Requirements, RuleResult

# A rule function takes (primary, secondary_or_None, requirements, derived_values)
# and returns a RuleResult.
RuleFn = Callable[[Product, Product | None, Requirements, dict], RuleResult]

# A pre-filter function takes (list of products, requirements) and returns
# a filtered list. Applied to primary products before the evaluation loop.
PreFilterFn = Callable[[list[Product], Requirements], list[Product]]

# A rank key function takes a Configuration and returns a sort key.
# Lower sort key = better configuration.
RankKeyFn = Callable[[Configuration], Any]

# A derived values function takes requirements and returns a dict of
# values computed from requirements (e.g., hinge count from door height).
DerivedValuesFn = Callable[[Requirements], dict]
