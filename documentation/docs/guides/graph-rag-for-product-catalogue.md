# Guide: Graph RAG for the Product Catalogue

A tutorial introduction to knowledge graphs, Graph RAG (Retrieval-Augmented Generation over a graph), and why they are an interesting fit for this project's multi-brand, multi-family product catalogue. Aimed at engineers who have not worked with graph databases before.

This is **forward-looking material** for the production engine. The deterministic engine (`engine_v1`/`engine_v2`) does not yet use a graph or RAG at runtime — see the [Knowledge Graph Research](../research/knowledge-graph-research.md) note for the recommendation to defer adoption to Phase 4.

> **Working prototype available.** A standalone GraphRAG / vector-RAG prototype over the project's PDF catalogs lives in [`rag/`](../../../rag/README.md) (notebooks, knowledge-graph extraction, community summaries). It is not wired into the engine; it's the experimental ground for the `window.search_documentation` and `window.graph_*` tools in [ADR-003](../architecture/decisions/ADR-003-conversational-via-microx-mcp.md). Read the guide below for vocabulary, then jump to `rag/` to see the same ideas running on the real catalogs.

This guide explains the *why* and *what* so the team has shared vocabulary when that phase arrives.

---

## 1. What RAG Is (and Isn't) Here

**RAG (Retrieval-Augmented Generation)** is the pattern of giving an LLM a fetched chunk of trusted data as context *before* asking it to answer. The LLM doesn't memorise the catalogue; it looks things up at query time and then writes the answer.

- **Vector RAG** — chunks of documents are embedded, stored in a vector DB, retrieved by semantic similarity to the user's question.
- **Graph RAG** — facts are stored as a graph of typed nodes and edges, retrieved by *traversal* from a starting entity.

For a product catalogue, the unit of truth is *"this part fits that part"* — a relationship, not a paragraph. Graph RAG fits that shape directly.

---

## 2. Nodes and Edges: A Working Vocabulary

A knowledge graph has two primitives.

### Nodes — the *things*

A node is an entity with a type and a bag of properties. Properties describe the node but are not queryable as connections.

```
(Hinge {part_number: "71B3550", brand: "Blum", series: "CLIP top",
        opening_angle: 110, capacity_kg: 9})
(Plate {part_number: "175H7100", mount_type: "screw-on", height_mm: 0})
(Brand {name: "Blum"})
(Distributor {name: "Würth Baer"})
(Application {name: "full_overlay"})
(CabinetType {name: "frameless"})
```

The label before `{}` is the node *type*; the dict is its *properties*.

### Edges — the *connections*

An edge is a typed, directed relationship between two nodes. Edges can carry properties of their own — metadata that belongs to the relationship rather than to either endpoint.

```
(71B3550) -[:SERIES_COMPATIBLE_WITH]-> (175H7100)
(71B3550) -[:MANUFACTURED_BY]->         (Blum)
(71B3550) -[:DISTRIBUTED_AS {sku: "BP71B3550"}]-> (Würth Baer)
(175H7100) -[:SUPPORTS_APPLICATION]->   (full_overlay)
(71B3550) -[:REPLACED_BY {date: "2025-03"}]-> (71B3580)
```

The arrow has a *type* (`SERIES_COMPATIBLE_WITH`) and a *direction*. Properties on the edge (`{sku: ...}`, `{date: ...}`) describe the relationship itself.

### The mental model

| Graph element | Linguistic analogue | Catalogue example |
|---|---|---|
| Node | Noun | hinge, plate, brand, distributor |
| Edge | Verb | compatible-with, made-by, sold-as, replaces |
| Property | Adjective | 110°, 9 kg, screw-on |

A knowledge graph is essentially a sentence-shaped database: each edge is one fact of the form *subject — verb — object*, and queries are sentences you ask the graph to complete.

### Why edges matter more than properties

A string property `brand: "Blum"` on a hinge is dead text. A `Brand: Blum` *node* connected by `MANUFACTURED_BY` edges lets you traverse from Blum to every product it makes, every distributor that carries it, every series it owns — in one query. Properties belong to one thing; edges connect two things.

---

## 3. A Worked Example: Three Hinges, Two Plates, Two Distributors

Below is a small slice of catalogue rendered as a graph. It is deliberately tiny so the topology is readable.

```
                          ┌──────────────┐
                          │   Brand      │
                          │  name: Blum  │
                          └──────┬───────┘
                                 │ MANUFACTURED_BY
              ┌──────────────────┼──────────────────┐
              │                  │                  │
              ▼                  ▼                  ▼
      ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
      │   Hinge      │   │   Hinge      │   │   Hinge      │
      │ pn: 71B3550  │   │ pn: 71B3580  │   │ pn: 71T550   │
      │ series: CLIP │   │ series: CLIP │   │ series: CLIP │
      │ angle: 110°  │   │ angle: 120°  │   │ angle: 110°  │
      │ cap: 9 kg    │   │ cap: 11 kg   │   │ cap: 9 kg    │
      └──┬────────┬──┘   └──────┬───────┘   └──────┬───────┘
         │        │             │                  │
         │        │ REPLACED_BY │                  │
         │        └────────────►│                  │
         │     {date: 2025-03}  │                  │
         │                      │                  │
         │ SERIES_COMPATIBLE_WITH                  │
         │                      │                  │ FITS_FRAME_TYPE
         ▼                      ▼                  ▼
    ┌──────────────┐      ┌──────────────┐   ┌──────────────┐
    │   Plate      │      │   Plate      │   │ CabinetType  │
    │ pn: 175H7100 │      │ pn: 177H7100 │   │ name:        │
    │ mount: screw │      │ mount: clip  │   │ face_frame   │
    │ height: 0mm  │      │ height: 3mm  │   └──────────────┘
    └──────┬───────┘      └──────────────┘
           │
           │ SUPPORTS_APPLICATION
           ▼
    ┌──────────────┐
    │ Application  │
    │ name:        │
    │ full_overlay │
    └──────────────┘

  Distributor edges (shown separately for clarity):

  (71B3550) ─[:DISTRIBUTED_AS {sku: BP71B3550, price: $4.20}]─► (Würth Baer)
  (71B3550) ─[:DISTRIBUTED_AS {sku: WL71B3550, price: $4.05}]─► (Würth Louis)
  (71B3580) ─[:DISTRIBUTED_AS {sku: BP71B3580, price: $5.10}]─► (Würth Baer)
  (175H7100)─[:DISTRIBUTED_AS {sku: BP175H,    price: $1.80}]─► (Würth Baer)
```

### What each piece is doing

**Nodes:**

- `Brand: Blum` — one node; every Blum product points at it.
- `Hinge: 71B3550 / 71B3580 / 71T550` — three product nodes with physical properties as attributes.
- `Plate: 175H7100 / 177H7100` — two mounting plates.
- `Application: full_overlay`, `CabinetType: face_frame` — taxonomy nodes that products attach to.
- `Distributor: Würth Baer / Würth Louis` — two retailers.

**Edges:**

- `MANUFACTURED_BY` — three hinges all point to the single Blum node. Adding a new Blum product = one new edge.
- `SERIES_COMPATIBLE_WITH` — `71B3550 → 175H7100` says this hinge fits this plate. A hard compatibility fact, encoded once.
- `REPLACED_BY {date: 2025-03}` — supersession. The edge carries the date as a property — useful metadata that isn't a node in its own right.
- `DISTRIBUTED_AS {sku, price}` — same hinge, multiple distributors, each edge carrying the distributor-specific SKU and price. This is the catalogue-overlay pattern from `engine_v1/models.py` (`DistributorSKU`) expressed as edges instead of an embedded list.
- `SUPPORTS_APPLICATION`, `FITS_FRAME_TYPE` — link products to taxonomy.

### What a traversal looks like

Question: *"What is the cheapest hinge + plate combo for a full-overlay face-frame cabinet, and where do I buy it?"*

The walk:

1. Start at `Application: full_overlay` → follow `SUPPORTS_APPLICATION` *backwards* → land on `Plate: 175H7100`.
2. From that plate, follow `SERIES_COMPATIBLE_WITH` backwards → land on `Hinge: 71B3550`.
3. Check the hinge has `FITS_FRAME_TYPE → face_frame`.
4. From both the hinge and the plate, follow `DISTRIBUTED_AS` → collect `(sku, price, distributor)` tuples.
5. Return the cheapest pair: `WL71B3550 @ $4.05` + `BP175H @ $1.80`.

Five hops, ~8 nodes touched. The LLM gets a tiny, fully-connected subgraph as context — not a dump of every Blum product.

### The same query in Cypher

[Cypher](https://neo4j.com/docs/cypher-manual/current/) is Neo4j's query language. Apache AGE uses it on top of PostgreSQL.

```cypher
MATCH (h:Hinge)-[:SERIES_COMPATIBLE_WITH]->(p:Plate)
      -[:SUPPORTS_APPLICATION]->(:Application {name: 'full_overlay'}),
      (h)-[:FITS_FRAME_TYPE]->(:CabinetType {name: 'face_frame'}),
      (h)-[dh:DISTRIBUTED_AS]->(d1:Distributor),
      (p)-[dp:DISTRIBUTED_AS]->(d2:Distributor)
RETURN h.part_number, p.part_number,
       dh.price + dp.price AS total_price
ORDER BY total_price ASC
LIMIT 1;
```

One `MATCH` describes the *shape* of the answer; the engine finds it. Compare to the equivalent SQL across `hinges`, `plates`, `compatibility`, `applications`, `cabinet_types`, `distributor_skus` — six tables, multiple joins, harder to extend when the next product family arrives.

---

## 4. Why Graph RAG Suits This Catalogue

The catalogue has structural properties that play to a graph's strengths.

### 4.1 Manufacturer ↔ distributor SKU identity is a graph natively

The same Blum 71B3550 surfaces as `BP71B3550` at Würth Baer and `WL71B3550` at Würth Louis. As edges (`distributed_as`, `sold_by`), retrieval can pivot from any SKU back to the canonical part and out to every other distributor in one hop — instead of a 3-table join that grows with each new brand.

### 4.2 Cross-family "what else do I need?" queries

A contractor asking *"I picked this hinge, what slides and lighting fit this cabinet?"* maps directly to graph traversal across `requires_clearance_from`, `occupied_by`, `conflicts_at_angle` edges. Retrieval pulls a connected subgraph as context, so the LLM gets *only* the products that actually relate.

### 4.3 Lifecycle and supersession chains

`Old SKU → REPLACED_BY → New SKU → BACKWARDS_COMPATIBLE_WITH → Existing Plate` is awkward in SQL when chains extend (A→B→C). Traversing the chain at query time means the model sees the live replacement and its compatibility footprint, not stale catalogue text.

### 4.4 Relationship-typed retrieval beats vector similarity for compatibility

Vector RAG retrieves by *semantic closeness* of text — useful for descriptions, useless for "these two parts physically fit." Graph edges encode the actual compatibility predicates (`series_compatible_with`, `supports_application`, `requires_min_overlay`), so retrieval returns parts that genuinely interoperate rather than parts that merely read similarly.

### 4.5 Explainable citations for free

Each retrieved edge carries a typed relationship the model can cite back ("CLIP top 110° → series_compatible_with → CLIP Cruciform Plate"). That dovetails with the engine's existing rule-trace explainability — the conversational layer can quote graph edges the same way the solver quotes `RuleResult`s.

### 4.6 Schema-flexible as families grow

Adding AVENTOS lifts or LED drivers means new node/edge types, not migrations. For a catalogue projected to span 13 product families × 3 brands, the graph absorbs new relationship kinds (`requires_driver`, `mounts_in_zone`) without reshaping the retrieval layer.

### 4.7 Subgraph context is token-efficient

A Cypher traversal returns ~10–50 connected facts; a vector store would return whole product datasheets to cover the same ground. Lower token cost per LLM call, and the context window stays focused on relationships that matter to the question.

---

## 5. When *Not* to Reach for Graph RAG

The advantages above compound at multi-family scale. Today they don't.

| Situation | Why a graph doesn't help |
|---|---|
| Single family, two entity types (hinge, plate) | Brute-force indexed search over 53 × 55 pairs completes in milliseconds. No traversal needed. |
| Compatibility derived from rules | Storing edges for derived facts contradicts "products are facts, compatibility is derived" and creates a sync problem. |
| One brand, one distributor | The SKU-overlay benefit is a join saved, not a query class enabled. |
| LLM is not in scope | If there is no conversational/RAG layer to feed, the graph carries operational cost (separate query language, backups, monitoring) for no retrieval payoff. |

The current architecture sits firmly in this column. Postgres + JSONB is the right next step.

---

## 6. Implementation Options When the Time Comes

If a graph layer is adopted later, two practical paths:

| Option | Pros | Cons |
|---|---|---|
| **Apache AGE on PostgreSQL** | Single database, SQL + Cypher in one system, no new infrastructure | Less mature than Neo4j, community-driven |
| **Neo4j alongside PostgreSQL** | Purpose-built graph engine, mature tooling, strong Cypher support | Two databases to operate, sync required between transactional store and graph |

Apache AGE is the lower-risk option since the project already plans to use PostgreSQL — it avoids a second database while adding graph query capability.

The retrieval layer itself would typically be:

1. **Entity linker** — map the user's free-text question to one or more starting nodes (`"BP71B3550"` → `Hinge: 71B3550`).
2. **Traversal** — Cypher query templates parameterised by intent ("compatible plates", "alternative distributors", "what fits with this").
3. **Subgraph serialiser** — render retrieved nodes/edges as structured text or JSON for the prompt.
4. **LLM** — answers the question, citing the edges as sources.

---

## 7. Glossary

- **Node** — a typed entity with properties; a noun in the catalogue (hinge, plate, brand).
- **Edge / relationship** — a typed, directed connection between two nodes; a verb (`SERIES_COMPATIBLE_WITH`).
- **Property** — a key/value attribute attached to a node *or* an edge.
- **Traversal** — walking the graph from a starting node along edges of specified types.
- **Cypher** — Neo4j's declarative query language; also supported by Apache AGE.
- **Subgraph** — the connected slice of nodes and edges returned by a traversal; the unit of context for Graph RAG.
- **GraphRAG** — RAG where the retrieval step is a graph traversal rather than vector similarity search.
- **Vector RAG** — RAG where retrieval uses embedding similarity over text chunks.
- **Entity linking** — mapping free-text mentions in a user's question to specific nodes in the graph.

---

## Related

- [Knowledge Graph Research](../research/knowledge-graph-research.md) — the formal evaluation and Phase 4 recommendation
- [Window Tech Brief](../research/window-tech-brief-research-report.md) — broader LLM integration patterns including RAG
- [Catalog Integration Plan](../planning/PLAN-catalog-integration.md) — manufacturer/distributor data model that the SKU-edge example draws on
- [Constraint Engine Design](../design/DESIGN-constraint-engine.md) — the "products are facts, compatibility is derived" principle
