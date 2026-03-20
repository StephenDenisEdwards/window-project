# Production Tooling Research — Constraint Engine

Research into tools and databases for moving the constraint engine from in-memory JSON to a production architecture.

---

## Constraint Solvers & Rule Engines

### Do we need a solver?

No — not at current or foreseeable scale. The engine evaluates independent pairwise predicates (hinge × plate), not combinatorial multi-way configurations. Indexed brute force handles this efficiently up to ~10K products per type.

A CSP solver becomes necessary only when configuring across 3+ product families simultaneously (hinge + plate + slide + handle), where the cross-product becomes exponential. Until then, a solver adds overhead without benefit.

### Evaluated Options

| Tool | Type | Verdict |
|------|------|---------|
| **OR-Tools CP-SAT** (Google) | Integer constraint solver | Not needed. Excels at scheduling/routing/bin-packing with complex interdependencies, not filtering pairs through independent predicates. Revisit if multi-family simultaneous configuration is required. |
| **Z3** (Microsoft) | SMT theorem prover | Wrong tool. Designed for "does a solution exist?" over logical formulas, not "enumerate all solutions from a finite catalog." |
| **python-constraint2** | Pure Python CSP | Would be *slower* than current approach. CSP backtracking adds overhead vs. simple indexed iteration. No optimization support. |
| **MiniZinc** | Declarative modeling language | Architecturally interesting for multi-family constraints but subprocess invocation overhead would be 10-100× current solve time. |
| **Drools** (Red Hat) | Production rule system (JVM) | Wrong architecture. Rete-based forward chaining is designed for hundreds of interdependent rules that trigger each other. Our 14 independent predicates don't benefit. JVM dependency. |
| **GoRules Zen Engine** | Rust decision tables with Python bindings | Interesting if non-developers need to edit rules via a visual UI. Decision tables are awkward for range checks and arithmetic though. |
| **business-rules** (Venmo) | Python rules-as-JSON | Largely unmaintained, but the *pattern* (JSON-defined conditions interpreted by a generic evaluator) is worth adopting independently of any library. |

### Rules-as-Data Pattern

The most practical improvement is converting rules from Python code to data definitions — not by adopting a rule engine, but by building a simple hybrid approach:

- **Data-driven** for simple predicates: equality checks, range membership, set membership (covers R001, R002, R003, R006, R009, R013, R015)
- **Python callables** for complex logic: mounting method compatibility matrix (R014), overlay range calculation (R004), weight capacity with hinge count (R007)

This enables non-developer rule editing, rule versioning in the database, and A/B testing different rule sets without a framework dependency.

### Enterprise CPQ Systems (Tacton, SAP VC, Salesforce CPQ)

These are commercial products, not embeddable libraries. The architectural pattern worth borrowing is **progressive domain reduction**: as the user makes each selection, propagate constraints to show only valid remaining options. The engine's `_pre_filter_hinges()` already does this in simple form. A full guided-configuration UX could be built with index lookups — no CSP solver needed.

### Graph Databases (Neo4j, Neptune, ArangoDB)

Not appropriate. The problem is filtering pairs through attribute predicates, not traversing a relationship graph. Neo4j beats SQL for deep traversals (5+ joins), but our problem is a single cross-join with predicate filters — SQL does this faster. A graph DB would add operational complexity without performance benefit.

---

## Databases

### The Core Data Question

Hinge-to-plate compatibility is fundamentally relational: joins on brand, series, cabinet type, mounting method, and overlay ranges. The overlay lookup tables (BPH × drilling distance → overlay) are a textbook relational table. This shapes the database choice.

### Evaluated Options

| Database | Suitability | SOC 2 | Ops Complexity | Cost/mo | Migration Effort |
|----------|------------|-------|----------------|---------|-----------------|
| **PostgreSQL (managed)** | Excellent | Strong | Low | $25–50 | Moderate |
| **SQLite** | Good (stepping stone) | Insufficient alone | Zero | $0 | Trivial |
| **MongoDB** | Moderate | More work | Medium | $60 | Easy initial, harder later |
| **DynamoDB** | Poor | Platform-level only | Low | $5 | Very high |
| **Redis** | Complementary only | N/A as primary | Adds complexity | $15 | N/A |
| **Supabase** | Excellent | Certified | Very low | $0–25 | Moderate |
| **Neon** | Excellent | Certified | Very low | $0–19 | Moderate |
| **PlanetScale** | Not recommended | Certified | Low | $39 | High (MySQL) |
| **CockroachDB** | Overkill | Certified | Medium | $300+ | Moderate |

### PostgreSQL — Recommended Primary Choice

**Why it fits:**

- **Overlay tables map to relational tables naturally.** `overlay_entries(plate_id, application_type, bph_mm, drilling_distance_mm, overlay_mm)` with composite indexes gives microsecond lookups and cross-plate queries ("which plates achieve 16mm overlay at DD=5?") that JSON cannot do without full scans.
- **JSONB for brand-specific flex attributes.** Core fields as typed columns with CHECK constraints. Brand-specific oddities (Grass "cranking 03", Blum INSERTA fields) in a `brand_attributes JSONB` column with GIN indexes.
- **Row-Level Security for brand isolation.** RLS policies enforce `WHERE brand = current_setting('app.current_brand')` at the database level — not application-enforced. Satisfies SOC 2 access control natively.
- **Audit trails via pgaudit + triggers.** `pgaudit` provides statement-level audit logging. Trigger-populated `audit_log` table for business-level change tracking.
- **Materialized views for pre-computed compatibility.** A `compatible_hinge_plate_pairs` view pre-joining on R001, R002, R003, R014. Refresh on catalog update. Engine queries become a filtered SELECT instead of a cartesian evaluation.
- **Pricing as a separate table.** `distributor_pricing(product_id, distributor_brand, customer_tier, price_usd, effective_date)` — clean separation, easy to update from external feeds.
- **Versioning via temporal tables.** `valid_from/valid_to` pattern or `catalog_version_id` FK. The `temporal_tables` extension automates it.

**Python ecosystem:** `psycopg` v3 (async-native), `SQLAlchemy 2.0` (with Pydantic integration via `SQLModel`), `Alembic` for migrations. The most mature Python database ecosystem.

### SQLite — Best Stepping Stone

**Why it fits as an interim step:**

- Zero operational overhead — database is a single file
- Full SQL support including JOINs, triggers, JSON1 extension
- Migration from JSON is trivial (afternoon of work)
- The engine's "load filtered subset into memory" pattern maps perfectly
- Using SQLAlchemy makes the later Postgres migration a connection-string change

**Why it can't be the final answer:** No RLS, no user management, single-writer limitation, no pgaudit equivalent. Insufficient for SOC 2 on its own.

### MongoDB — Viable but Fights the Relational Aspects

Initial migration is easy (insert JSON as-is), but the core query pattern "find all plates compatible with this hinge" requires joins on brand, series, cabinet type, and mounting method. MongoDB's `$lookup` is significantly slower and more awkward than SQL JOINs. You'd end up denormalizing compatibility into documents — reintroducing the `compatible_mounting_plate_skus` anti-pattern the domain model explicitly eliminated.

### DynamoDB — Wrong Tool

Your problem is complex relational queries on a small dataset. DynamoDB excels at high-throughput known-access-pattern workloads. Every new query pattern requires a new GSI. The overlay lookup tables are extremely awkward in key-value. Developer time fighting the data model would dwarf the $45/month saved over Postgres.

### Redis — Cache Layer Only

Not a primary store. Valuable later as a cache for pre-computed compatibility sets if latency becomes a measured problem. At current scale, the engine evaluates all constraints in <100ms from a SQL database — caching is premature.

### Managed Postgres: Supabase vs Neon

Both are real Postgres (not just compatible) with SOC 2 Type II certification and free tiers sufficient for this scale.

- **Supabase** adds built-in REST API (PostgREST), auth with RLS integration, and real-time subscriptions. Best if the engine will have a web frontend.
- **Neon** adds serverless scale-to-zero and database branching for safe migrations. Best for cost optimization and development workflow.

Either is a better starting point than self-hosted Postgres or RDS.

---

## Recommended Path

**Phase 1 (now):** Migrate from JSON to **SQLite** via SQLAlchemy. Trivial effort, gives SQL queries and schema validation immediately. The engine continues to load filtered subsets into memory — SQLite replaces the JSON reader.

**Phase 2 (when multi-user access, auth, or SOC 2 needed):** Move to **Supabase or Neon** (managed Postgres). SQLAlchemy makes this a connection-string change plus Alembic migrations. Add RLS for brand isolation, pgaudit for compliance, normalized overlay tables.

**Phase 3 (if measured latency problem):** Add **Redis** as a caching layer. Pre-compute and cache compatibility sets on catalog update.

**Constraint solving:** Stay with indexed brute force. Adopt the **rules-as-data pattern** (JSON definitions for simple predicates, Python callables for complex logic) for maintainability. Only revisit CSP solvers if multi-family simultaneous configuration becomes a requirement.
