"""
engine_v2 — Multi-family constraint engine prototype (Option A).

Generic solver with pluggable rule sets. Each product family registers
its models, rules, pre-filters, and ranking criteria. The solver
evaluates candidates without knowing what products it's working with.

This is a prototype that coexists with the production engine in engine/.
"""
