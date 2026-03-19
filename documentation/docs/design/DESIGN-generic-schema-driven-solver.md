# Generic Schema-Driven N-Candidate Solver

An architectural exploration: what if product models were JSON Schemas and rules were declarative definitions evaluated against those schemas? No Python classes per family, no Python functions per rule.

**Status:** Idea — not implemented. Captures the design space and trade-offs for future evaluation.

---

## Current State

Each product family requires three Python artifacts:

1. **Models** — Pydantic classes (`Hinge`, `Plate`, `HingeRequirements`)
2. **Rules** — Python functions that cast to typed models and compare fields
3. **Config** — `NFamilyConfig` wiring roles, rules, ranking, pre-filters

Adding a family means writing Python. The 14 hinge rules are ~250 lines. The 8 drawer slide rules are ~200 lines. Most follow the same patterns.

## The Idea

### Products as JSON Schema

Instead of Pydantic classes, product types are defined as JSON Schema:

```json
{
  "hinge": {
    "type": "object",
    "properties": {
      "sku": {"type": "string"},
      "brand": {"type": "string"},
      "series": {"type": "string", "enum": ["CLIP top BLUMOTION", "Tiomos", "Nexis", "Duomatic"]},
      "opening_angle_deg": {"type": "integer"},
      "max_door_weight_kg": {"type": "number"},
      "boring_pattern_mm": {"type": "integer", "enum": [42, 45, 48]},
      "mounting_method": {"type": "string", "enum": ["screw_on", "dowel", "euro_screw"]},
      "cabinet_type": {"type": "string", "enum": ["frameless", "face_frame"]},
      "soft_close": {"type": "boolean"},
      "door_thickness_range_mm": {
        "type": "object",
        "properties": {"min": {"type": "number"}, "max": {"type": "number"}}
      }
    }
  }
}
```

Products are plain dicts validated against the schema. No Pydantic model per product type. The loader reads JSON, validates against the schema, passes dicts to the solver.

### Rules as Declarative Definitions

Rules reference schema paths instead of Python attributes:

```json
{
  "rule_id": "R001",
  "rule_name": "brand_lock",
  "category": "hard_constraint",
  "type": "equality",
  "left": "candidates.hinge.brand",
  "right": "candidates.plate.brand",
  "skip_when": {"field": "requirements.brand_lock", "equals": false},
  "detail_template": "Hinge brand '{left}' {result} plate brand '{right}'",
  "remediation_template": "Select a {left} plate or a {right} hinge"
}
```

A **rule evaluator** interprets these definitions using a small set of rule types.

### Rule Types

| Rule type | What it checks | Declarative form |
|---|---|---|
| `equality` | A == B | `{"left": "path.to.A", "right": "path.to.B"}` |
| `range` | min ≤ value ≤ max | `{"value": "path", "min": "path.min", "max": "path.max"}` |
| `membership` | A in list B | `{"value": "path.to.A", "list": "path.to.B"}` |
| `comparison` | A ≤ B (with optional expression) | `{"left": "path", "operator": "<=", "right": "expression"}` |
| `boolean_preference` | A is true if required | `{"field": "path", "required_when": "path.to.flag"}` |
| `conditional` | Skip if precondition not met | `{"skip_when": {"field": "path", "equals": value}}` |
| `compatible` | A ↔ B via lookup table | `{"left": "path", "right": "path", "table": {...}}` |
| `custom` | Python callable (escape hatch) | `{"handler": "module.function_name"}` |

### Expressions for Computed Values

Simple arithmetic covers most cases:

```json
{
  "type": "comparison",
  "left": "requirements.door_weight_kg",
  "right": {
    "multiply": ["candidates.hinge.max_door_weight_kg", "derived.hinges_per_door"]
  },
  "operator": "<="
}
```

Derived values themselves can be declarative:

```json
{
  "derived_values": {
    "hinges_per_door": {
      "type": "threshold_lookup",
      "input": "requirements.door_height_mm",
      "thresholds": [[889, 2], [1400, 3], [1800, 4]],
      "default": 5
    }
  }
}
```

### Pre-filters and Ranking

Pre-filters: "keep products where field matches requirement."

```json
{
  "pre_filters": [
    {"role": "hinge", "field": "application", "match": "requirements.application"},
    {"role": "hinge", "field": "cabinet_type", "match": "requirements.cabinet_type"},
    {"role": "hinge", "field": "brand", "match": "requirements.preferred_brand", "skip_if_null": true}
  ]
}
```

Ranking: ordered list of sort keys with direction.

```json
{
  "ranking": [
    {"field": "total_price_usd", "direction": "asc", "nulls": "last"},
    {"field": "candidates.hinge.max_door_weight_kg", "direction": "desc", "multiplier": "derived.hinges_per_door"}
  ]
}
```

### Complete Family Definition

A single JSON file per family replaces models.py + rules.py + config.py + loader.py:

```json
{
  "name": "concealed_hinge",
  "title": "Concealed Hinges",
  "roles": {
    "hinge": {"schema": "...", "data_file": "hinges.json"},
    "plate": {"schema": "...", "data_file": "mounting_plates.json"}
  },
  "requirements_schema": {"...JSON Schema for HingeRequirements..."},
  "derived_values": {"..."},
  "pre_filters": ["..."],
  "rules": ["...14 rule definitions..."],
  "ranking": ["..."]
}
```

---

## What This Buys

1. **No Python needed to add a family.** A domain expert defines the product schema and rules in JSON. The engine evaluates them generically.

2. **The web demo becomes a rule editor.** Build and modify families in the browser — add fields, create rules by picking fields and operators, test against sample data. No deployment.

3. **Catalog ingestion simplifies.** Products are dicts validated against a JSON Schema. No Pydantic class per product type.

4. **Rules become inspectable data.** The web UI already shows rule source — with declarative rules, it could show the rule definition in a human-readable format and let users modify it.

5. **The conversational layer can reason about rules.** An LLM can read JSON rule definitions and explain them to a contractor, or suggest which rules are blocking a configuration. Harder to do with Python source.

6. **Version control and audit.** Rule definitions are JSON — diffs are clean, changes are auditable, rollback is trivial.

---

## Where It Gets Hard

### Complex Business Logic

**Overlay check (R004)** — looks up a key in a dict, checks if the value is `true`, `false`, `null`, or a `[min, max]` list, and behaves differently for each. This is multi-branch business logic that resists declarative expression.

**Mounting method compatibility (R014)** — needs a lookup table where `SCREW_ON` is compatible with `{SCREW_ON, EURO_SCREW, SYSTEM_SCREW}`. Expressible as a `compatible` rule type with an explicit table, but adds complexity to the evaluator.

**Wattage with headroom (LED002)** — "total wattage ≤ 80% of driver max wattage." The 0.8 multiplier is domain knowledge baked into the rule. Declarative form: `{"right": {"multiply": ["candidates.driver.max_wattage", 0.8]}}`. Works, but where do you stop?

### Expression Language Creep

Each new pattern requires either a new rule type or a more expressive expression language. Risk: you end up building a programming language in JSON — worse than Python because it's less readable, less debuggable, and less testable.

The question is whether the set of rule types stabilises after a few families. If the 13 Würth families all use the same 6-8 patterns, declarative wins. If each family introduces a new pattern, you're fighting the abstraction.

### Type Safety

With Pydantic models, referencing a non-existent field fails at import time. With JSON Schema paths like `"candidates.hinge.opening_angle_deg"`, typos become runtime errors. Mitigation: a validation step at family load time that checks all rule references resolve against the schemas.

### Testing

Python rules are tested with pytest — straightforward. Declarative rules need a test framework that loads a family definition, runs scenarios, and asserts results. The test data is the same, but the test harness changes.

### Debugging

When a rule fails unexpectedly, a developer currently reads the Python function to understand the logic. With declarative rules, they read JSON — potentially less clear for complex rules. The `custom` escape hatch (Python callables for complex rules) helps, but creates two systems to understand.

---

## How Current Rules Break Down

Analysis of all 31 rules across the three implemented families:

| Rule type | Count | Rules |
|---|---|---|
| Equality | 8 | R001, R003, R009, R014, LED001, LED003, LED004, DS004 |
| Comparison (≤ / ≥) | 6 | R007, LED002, LED005, LED006, DS001, DS002 |
| Range (min ≤ val ≤ max) | 2 | R006, R004 (simple case) |
| Membership (A in list B) | 2 | R002, LED009 |
| Boolean preference | 5 | PREF, DS006, DS007, DS008, LED008 |
| Conditional skip | 5 | R005, R011, R012, R013, DS005 |
| Complex / custom | 3 | R004 (full logic), R014 (compat table), R015 (cup depth formula) |

**~90% of rules (28 of 31) fit 6 declarative types.** Three rules would need the `custom` escape hatch or a more expressive rule type.

---

## Pragmatic Layered Approach

Don't try to make everything declarative at once. Three layers:

**Layer 1 — Schema-defined products.** Products are dicts validated against JSON Schema. No Pydantic classes per family. This is the easiest win and independent of declarative rules.

**Layer 2 — Declarative rules for the common 80%.** A rule evaluator handles equality, range, membership, comparison, boolean preference, and conditional skip. Most rules across all families fit these patterns.

**Layer 3 — Python callables for the complex 20%.** Registered by name, called when the evaluator hits a `"type": "custom"` rule. This is the escape hatch that prevents the expression language from growing unbounded.

---

## Validation Strategy

Before building this, validate with:

1. **Drawer slides first** — simplest family (8 rules, no complex logic). Write the complete family definition as JSON. If it works cleanly, the approach is viable for the common case.

2. **LED lighting second** — tests cross-product rules (bar ↔ driver, driver ↔ dimmer) and the expression language (wattage × 0.8).

3. **Concealed hinges last** — the hardest family. Tests the overlay lookup, mounting compatibility table, and derived value (hinges_per_door). If this works without too many `custom` escape hatches, the approach scales.

4. **Count the rule types after 3 families.** If the evaluator has 6-8 rule types and the set feels stable, proceed. If each family added 2-3 new types, the abstraction isn't earning its keep.

---

## Alternative: LLM-Generated Code Instead of Declarative Rules

The schema-driven approach solves for a world where adding a product family means filing a ticket and waiting for a developer to write Python. But LLM code generation changes the equation fundamentally: a domain expert describes the family in plain English and gets working, testable Python in minutes.

### Why this may eliminate the need for declarative rules

The entire premise of moving rules out of code is "non-developers can't write Python." With an LLM agent, they don't need to. The process:

1. **Domain expert describes the products** — "A drawer slide has a length, load rating, extension type, mount type, close type"
2. **Domain expert describes the rules** — "Load must not exceed rating. Slide must fit cabinet depth. Extension type must match if specified"
3. **Domain expert provides sample data** — a few example products
4. **LLM agent generates** `models.py`, `rules.py`, `config.py`, `loader.py`, and test data

This was proven in this project. The drawer slide and LED lighting families were generated in a single conversation — models, rules, config, loader, tests, all working on the first pass. The concealed hinge rules were ported from v1 to v2 (14 rules, different signature) in one step with no manual coding.

### Advantages of generated code over declarative rules

| Concern | Declarative (JSON) | Generated code (Python) |
|---|---|---|
| **Expression language** | Must build and maintain a mini-language in JSON | Python *is* the expression language — already better than anything custom |
| **Debugging** | Can't set breakpoints in JSON rule definitions | Standard Python debugging, breakpoints, stack traces |
| **Type safety** | JSON Schema paths fail at runtime on typos | Pydantic catches field errors at import time |
| **Testing** | Needs custom test harness for declarative rules | Standard pytest — same framework as everything else |
| **Complex rules** | Need an escape hatch to Python for ~10% of rules | No escape hatch needed — you never left code |
| **Readability** | JSON rule definitions can be harder to follow than Python | Rule functions are self-documenting with docstrings |
| **Tooling** | Need a custom editor, validator, test runner | VS Code, pytest, git — standard developer tools |

### The key insight

The schema-driven approach optimises for **runtime flexibility** — changing rules without redeploying code. But for a constraint engine where correctness is the core promise ("no recommendation reaches the user without passing all constraint validation"), you probably *want* a deploy gate with tests before rule changes go live. Generated code with a CI pipeline gives you that safety net. Declarative rules that can be changed at runtime bypass it.

### A specialised agent for robust family generation

The LLM generation process can be made highly robust with a **specialised family-builder agent** that includes built-in validation steps:

**Step 1 — Requirements gathering.** The agent interviews the domain expert: "What products are in this family? What fields does each product have? What constraints must be satisfied? What does the customer specify?" Structured questions, not freeform.

**Step 2 — Model generation.** The agent generates Pydantic models from the gathered requirements. Validates that:
- All fields have types and constraints
- Enums are defined for constrained string fields
- Requirements model captures all customer inputs
- Models follow the existing patterns (extend `Product`/`Requirements` base classes)

**Step 3 — Rule generation.** The agent generates rule functions from the constraint descriptions. For each rule, validates that:
- All referenced fields exist on the models (cross-referencing models.py)
- The rule function signature matches the N-candidate interface
- The rule returns a `RuleResult` with rule_id, rule_name, category, detail, and remediation
- The rule handles skip conditions (conditional rules return early with `passed=True`)

**Step 4 — Sample data and golden tests.** The agent generates:
- JSON data files with realistic sample products
- A loader that reads the JSON and produces typed model instances
- Golden scenario tests — known inputs with expected outcomes (solved/no_solution, expected SKUs)
- Edge case tests — boundary values, impossible scenarios, empty catalogs

**Step 5 — Cross-validation.** The agent runs the full test suite and verifies:
- All tests pass
- Every rule is exercised by at least one test scenario
- The solver produces results for the golden scenarios
- No rule is unreachable (every rule can both pass and fail across the test data)
- The family integrates with the web demo (solver loads, examples work, API returns valid JSON)

**Step 6 — Human review.** The agent presents a summary: models, rules, test coverage, sample results. The domain expert reviews the constraint traces for the golden scenarios and confirms the rules match their domain knowledge. Only then is the code committed.

This pipeline is more robust than hand-coding because:
- The validation steps are **automated and consistent** — a developer might forget to test edge cases, the agent always checks
- The cross-referencing between models and rules is **exhaustive** — every field reference is verified
- The test generation is **systematic** — the agent generates scenarios specifically to exercise each rule in both pass and fail states
- The review step is **structured** — the domain expert sees constraint traces, not code

### When declarative rules still win

There are scenarios where the schema-driven approach is still preferable:

1. **Runtime rule tuning by non-technical users.** If a sales manager needs to adjust a weight threshold or add a brand to a compatibility list without any deployment, declarative rules in a database are the right answer. But this is a narrow use case and could be addressed with parameterised rules (rules as code, parameters as data) rather than full declarative rules.

2. **Hundreds of families with identical patterns.** If 50+ families all use the exact same 6 rule types with different field names, the declarative approach avoids code duplication. But the LLM approach handles this too — generating 50 families from templates is trivial for an LLM.

3. **The conversational layer needs to modify rules.** If the LLM-powered conversational interface needs to dynamically add or adjust constraints based on user conversation, declarative rules are easier to manipulate programmatically. But this blurs the line between recommendation and constraint enforcement in ways that may undermine the "provably correct" guarantee.

### Recommendation

**Keep rules as Python code. Use LLM agents to generate families.** The schema-driven approach is an interesting architectural idea, but LLM code generation solves the same problem (non-developers adding families) without the costs (expression language, custom tooling, debugging complexity, two-system maintenance). The validation pipeline described above makes the generated code as robust as — or more robust than — hand-written code.

Reserve the declarative approach for a specific future need: runtime rule parameterisation where thresholds and lookup tables are data, but the rule logic stays as code. This is a smaller, more focused version of "rules as data" that avoids the expression language problem.

---

## Open Questions

1. **Who is the user?** If only developers add families, Python is simpler and more debuggable. If domain experts or the conversational layer need to define families, declarative is essential. The answer depends on the internal sales process document and who will encode the remaining 10 families.

2. **JSON or YAML?** YAML is more readable for humans writing rules. JSON is more parseable and matches the existing data format. Could support both with a thin loading layer.

3. **Where do family definitions live?** In `sample-data/` alongside product data? In a separate `families/` directory? In a database (for the production system)?

4. **How does this interact with the API?** The current `/api/solve/{family}` endpoint already receives JSON and validates against a schema. A schema-driven solver would make the entire pipeline JSON-in, JSON-out — no Python types in the request path.

5. **Can the web demo become a family editor?** If families are JSON, the web UI could let users create product schemas, define rules by picking fields and operators, and test against sample data — a low-code configuration tool for the constraint engine.

---

## Related

- [ADR-001: Flat N-Candidate Solver](../architecture/decisions/ADR-001-flat-n-candidate-solver.md) — Current solver architecture
- [N-Candidate Families Reference](DESIGN-n-candidate-families.md) — Current data and rules for all three families
- [Production Roadmap](../planning/PLAN-production-roadmap.md) — "Rules as data" identified as Phase 1 work
- [Constraint Engine Design](DESIGN-constraint-engine.md) — Current rule reference
