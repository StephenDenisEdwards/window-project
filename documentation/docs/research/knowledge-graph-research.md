# Knowledge Graph Research — Applicability to Window

Research into whether knowledge graphs are a useful data architecture for the constraint engine, multi-brand product catalog, or conversational AI layer.

---

## What is a Knowledge Graph?

A knowledge graph represents information as a network of **entities** (nodes) and **relationships** (edges), where both carry typed properties. Unlike relational tables (rows/columns) or document stores (JSON blobs), relationships are first-class citizens — queryable, typed, and traversable.

```
[Blum CLIP top 110°] --series_compatible_with--> [CLIP Cruciform Plate]
[CLIP Cruciform Plate] --supports_application-->  [Full Overlay]
[Full Overlay]         --requires_min_overlay-->  14mm
```

Key properties:

- **Schema-flexible** — new entity types and relationship types can be added without migrations
- **Multi-hop reasoning** — "which plates work with hinges that fit 19mm doors on corner cabinets?" is a natural graph traversal rather than a multi-table join
- **Semantic richness** — relationships carry meaning (`compatible_with`, `replaces`, `requires`, `conflicts_with`)

Common implementations: Neo4j (native graph DB), Amazon Neptune, Apache AGE (graph layer on PostgreSQL).

---

## Evaluation Against Current Architecture

### Not warranted for the constraint engine

The engine's existing design is a poor fit for knowledge graphs, and introducing one would work against core design principles.

| Concern | Detail |
|---------|--------|
| **Compatibility is computed, not stored** | Core principle: "products are facts, compatibility is derived." Rules derive compatibility at query time. A knowledge graph would encourage materialising compatibility as stored edges, contradicting this principle and introducing a sync problem. |
| **Flat constraint space** | The engine evaluates hinge × plate pairs against 14 independent predicates. There is no deep graph traversal — it is a two-entity Cartesian product with filters. Brute-force indexed search over 53 × 55 pairs completes in milliseconds. |
| **PostgreSQL is sufficient** | The planned migration to Postgres with indexed queries and JSONB handles structured product data with known schemas. A graph DB adds operational complexity (separate query language, backup tooling, monitoring) without improving correctness or performance at this scale. |

### Potentially valuable at scale (Phase 4+)

As the system scales to 13 product families and 3 brands, relationship complexity grows in ways that are awkward to model relationally.

**1. Cross-family product dependencies**

A drawer slide choice may constrain which hinge works (shared drilling space). AVENTOS lift systems interact with hinge placement. Lighting requires compatible drivers that mount in specific cabinet zones. These are multi-hop relationships across product families that require complex join chains in a relational model but are natural graph traversals.

```
[AVENTOS HK-XS] --requires_clearance_from--> [Hinge Zone]
[Hinge Zone]     --occupied_by-->             [CLIP top 110°]
[CLIP top 110°]  --conflicts_at_angle-->      [AVENTOS HK-XS] (if >120°)
```

**2. Manufacturer-to-distributor identity mapping**

The same Blum 71B3550 appears as `BP71B3550` at Würth Baer and a different SKU at Würth Louis. A graph represents this naturally:

```
[71B3550] --distributed_as--> [BP71B3550] --sold_by--> [Würth Baer]
[71B3550] --distributed_as--> [WL71B3550] --sold_by--> [Würth Louis]
```

Without a graph, this requires a three-table join (manufacturer_products → distributor_skus → brands) that becomes unwieldy as brands and product families multiply.

**3. Conversational AI retrieval (GraphRAG)**

Knowledge graphs are commonly used as retrieval backends for LLM-powered systems. When a contractor asks "what else do I need for this cabinet?", traversing a product knowledge graph is more natural than querying across 13 relational tables. The graph structure maps well to how the conversational layer needs to reason about related products and dependencies.

**4. Product lifecycle relationships**

Discontinued products, replacements, and supersessions are naturally expressed as graph edges:

```
[Old SKU] --replaced_by--> [New SKU]
[New SKU] --backwards_compatible_with--> [Existing Plate]
```

These relationships are difficult to query efficiently in a relational model when they chain (A replaced by B replaced by C).

---

## Implementation Options

If a knowledge graph is adopted in a later phase, two practical approaches:

| Option | Pros | Cons |
|--------|------|------|
| **Apache AGE on PostgreSQL** | Single database, SQL + Cypher in one system, no new infrastructure | Less mature than Neo4j, community-driven |
| **Neo4j alongside PostgreSQL** | Purpose-built graph engine, mature tooling, strong Cypher query language | Two databases to operate, data sync required between transactional store and graph |

Apache AGE is the lower-risk option since the project already plans to use PostgreSQL — it avoids a second database while adding graph query capability.

---

## Recommendation

**Do not introduce a knowledge graph now.** The current architecture is sound for concealed hinges, and the PostgreSQL migration is the correct next step.

**Revisit at Phase 4** (multi-family product expansion) when:

- Cross-family constraints require multi-hop relationship queries
- The conversational AI layer needs to traverse product relationships for retrieval
- Multi-table joins across 13 product families become a maintenance burden

At that point, a hybrid approach — PostgreSQL for transactional product data + a graph layer (Apache AGE or Neo4j) for relationship traversal and LLM-powered discovery — would add genuine value.

---

## Relationship to Other Research

- **Production tooling research** (`production-tooling-research.md`) — concluded CSP solvers are not warranted at current scale; similar conclusion applies here
- **Constraint engine design** (`constraint-engine-design.md`) — "products are facts, compatibility is derived" principle is the main reason a graph is not needed for the core engine
- **Catalog integration** (`catalog-integration.md`) — the manufacturer → distributor SKU mapping is the strongest near-term use case for graph modelling, but can be handled relationally for 3 brands
