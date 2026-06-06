# Insight: Understanding RAG and GraphRAG

> **Audience:** someone new to RAG and GraphRAG.
> **Purpose:** this is both a *learning document* (explains the concepts from scratch)
> and a *project document* (explains exactly what we built in `rag/` and why).
>
> Read it top to bottom the first time. Later you can jump straight to the
> [Key files map](#10-key-files-map) or the [Glossary](#11-glossary).

---

## 0. How to read this document

We build up in layers:

1. **The problem** — why RAG exists at all.
2. **RAG fundamentals** — the handful of ideas you need (chunks, embeddings, vector search).
3. **Standard RAG** — the basic pipeline, end to end.
4. **The limits of standard RAG** — what it *can't* do well.
5. **GraphRAG** — what it adds and why.
6. **How we build it here** — the actual three-stage build in this repo.
7. **How we use it at query time** — what happens when you ask a question.
8. **A worked example.**
9. **Critical analysis** — does this design actually make sense? (Spoiler: mostly, with a real caveat.)
10. **Key files map** and **Glossary.**

If a word is unfamiliar, check the [Glossary](#11-glossary) — every bolded term there is defined.

---

## 1. The problem RAG solves

A Large Language Model (an **LLM**, like Claude) is trained on a huge amount of public
text, but it does **not** know about *your* private documents — in our case, a folder of
hardware product catalogs (`catalogs/*.pdf`) describing cabinet hinges, drawer slides,
and lighting.

If you ask the model *"Which Grass hinges support a 110° opening angle?"* it will either:

- guess from general knowledge (often wrong, or **hallucinated**), or
- say it doesn't know.

**The obvious fix:** "just paste all the catalogs into the prompt." This fails for two reasons:

1. **Context limits.** A model can only read so much text at once (its **context window**).
   Hundreds of pages of PDFs won't fit, or are wildly expensive to send every time.
2. **Noise.** Even if it fit, burying the one relevant paragraph in 500 pages makes the
   model's job harder, not easier.

**RAG** — *Retrieval-Augmented Generation* — is the practical answer:

> Don't give the model *everything*. First **retrieve** only the few most relevant
> snippets, then **generate** an answer from those snippets.

It's "open-book exam" for an LLM: instead of memorising the textbook, the model looks up
the relevant pages at question time.

---

## 2. RAG fundamentals (the building blocks)

You only need four ideas.

### 2.1 Chunks

We can't store "a PDF" as a unit — it's too big to retrieve usefully. So we slice each PDF
into small, overlapping pieces of text called **chunks**.

In this project (`rag/pipeline/extract.py`):

- We read each PDF page's text with a library called **PyMuPDF** (imported as `fitz`).
- We cut each page into windows of **800 characters**, with **100 characters of overlap**
  between neighbours.

Why overlap? So a sentence that straddles a boundary isn't cut in half and lost from both
chunks. The overlap is a safety margin.

Each chunk gets a **deterministic ID** like `tiomos_p12_c3` (`{pdf name}_p{page}_c{chunk index}`).
"Deterministic" means: rebuild from the same PDF and you get the *same* IDs. This matters
later — it's the glue that lets the graph and the search database refer to the same chunks.

### 2.2 Embeddings (turning text into numbers)

Computers can't compare meaning directly, but they *can* compare numbers. An **embedding**
is a list of numbers (a **vector**, e.g. 768 numbers long) that represents the *meaning* of
a piece of text.

The magic property: **texts with similar meaning get similar vectors.** So
"soft-close hinge" and "hinge with damped closing" land near each other in this number-space,
even though they share few words.

In this project, embeddings are produced by a local model called **`nomic-embed-text`**,
run via **Ollama** (a tool for running models on your own machine). See the
`OllamaEmbeddingFunction` in `rag/pipeline/store.py`.

> **Mental model:** an embedding is a *coordinate* for a piece of text on a giant
> "map of meaning." Similar meanings = nearby coordinates.

### 2.3 Vector database and similarity search

Once every chunk is an embedding, we store them in a **vector database** — here, **ChromaDB**
(the `chroma_db_graph/` folder). A vector database is built to answer one question very fast:

> "Given this query vector, which stored vectors are *closest* to it?"

"Closest" is measured by **cosine distance** (how similar two vectors' directions are).
This project configures Chroma with `"hnsw:space": "cosine"` (see `store.py`).

So at question time we embed your question into a vector, ask the database for the nearest
chunk vectors, and get back the most *semantically relevant* chunks — not just keyword matches.

### 2.4 The retrieve-then-generate loop

Putting it together, every RAG system is two steps:

1. **Retrieve:** turn the question into a vector → find the nearest chunks.
2. **Generate:** paste those chunks into a prompt → ask the LLM to answer using them.

That's it. Everything else is refinement.

---

## 3. Standard (vector) RAG, end to end

This is the baseline — what most people mean by "RAG." In this repo it's
`standard_rag_answer()` in `rag/pipeline/answer.py`.

```
Your question
   │
   ▼  embed the question
Vector search over chunks  ──►  top 5 most similar chunks
   │
   ▼  paste chunks into a prompt template
LLM (Claude)  ──►  answer (with catalog + page citations)
```

The prompt literally says *"answer based ONLY on the provided catalog context"*
(`STANDARD_RAG_SYSTEM` in `answer.py`), which keeps the model honest and reduces
hallucination. Each chunk carries its `source` PDF and `page`, so the model can cite them.

For many questions, this is genuinely good enough.

---

## 4. Where standard RAG falls short

Standard RAG retrieves chunks that are *individually* similar to your question. It struggles
when the answer requires **connecting facts that live in different chunks**.

Two classic failure shapes:

1. **The "connect the dots" question.**
   *"What mounting plate works with the Tiomos hinge for a thick door?"*
   The hinge is described on page 12, the compatible plate on page 40, the thickness rule on
   page 8. No single chunk contains the whole answer, and the plate's chunk might not even
   look similar to your question (it's about *plates*, you asked about a *hinge*).

2. **The "big picture" question.**
   *"What product families does this catalog cover, and how do they differ?"*
   There's no one paragraph that answers this — the answer is a *summary of the whole
   corpus*. Vector search, which returns a handful of specific snippets, has nothing good
   to grab.

GraphRAG is designed to attack exactly these two weaknesses.

---

## 5. What GraphRAG adds

**GraphRAG** = RAG plus a **knowledge graph** plus **community summaries.** Two new ingredients:

### 5.1 A knowledge graph (for "connect the dots")

A **knowledge graph** is a network of facts:

- **Nodes** (also called *entities*) are the "things": products, manufacturers, features,
  specifications, materials. Example node: `Tiomos` (a product).
- **Edges** (also called *relationships*) connect them: `Tiomos --manufactured_by--> Grass`,
  `Tiomos --compatible_with--> Mounting Plate H`.

Once you have this network, you can **follow the connections**. Start at the hinge the user
asked about, and *hop* one step to find the plate connected to it — even if the plate's text
chunk never showed up in the vector search. That's the dot-connecting standard RAG can't do.

### 5.2 Communities and summaries (for the "big picture")

Within any large graph, some entities cluster tightly together — lots of hinge products,
features, and specs all interlinked. A **community** is one such cluster, found
automatically by an algorithm called **Louvain** (it groups nodes that are densely
connected to each other).

We then ask an LLM to write a short **summary** of each big community
("this cluster is Grass's family of soft-close concealed hinges, characterised by…").
These summaries are the pre-computed "big picture" that standard RAG lacks.

> **One-line difference:**
> Standard RAG finds *similar text*. GraphRAG also follows *relationships between things*
> (the graph) and offers *cluster-level summaries* (communities).

---

## 6. How we build the GraphRAG in this project

The build runs in **three stages**. A guiding principle: **the only expensive, non-repeatable
step is isolated and cached**, so everything downstream can be rebuilt freely.

```
PDF Catalogs (catalogs/*.pdf)
   │
   ▼  STAGE 1 — Extraction (LLM, paid, cached)
Chunk PDFs ──► send each chunk to Claude ──► entities + relationships ──► extractions.json
   │
   ▼  STAGE 2 — Graph (pure compute, no network)
Clean extractions ──► build NetworkX graph ──► detect Louvain communities ──► (+ HTML viz)
   │
   ▼  STAGE 3 — Store (embeddings + summaries)
Summarise top communities (LLM) ──► embed chunks + summaries ──► ChromaDB
```

### Stage 1 — Extraction (`rag/pipeline/entities.py`, run via `scripts/run_extraction.py`)

For every chunk, we send the text to Claude with a strict prompt (`EXTRACTION_PROMPT`) that
forces the output into a fixed vocabulary:

- **7 entity types:** `product, manufacturer, feature, specification, material,
  certification, category`
- **6 relationship types:** `has_feature, manufactured_by, has_specification,
  compatible_with, part_of, variant_of`

Constraining the vocabulary keeps the graph clean — the model can't invent 500 one-off
relationship names.

This is the **only step that costs money and isn't deterministic** (LLMs vary run to run).
So it's **cached** to `extractions.json` and **resumable**: `extract_all()` saves progress
every 50 chunks and can pick up where it left off. Everything after this reads the cache.

### Stage 2 — Build the graph (`scripts/build_graph.py`, pure compute)

1. **Clean** the raw extractions (`rag/pipeline/normalize.py`, the `clean()` function):
   - **Normalise types** — map the LLM's free-form type strings onto the canonical set.
   - **Deduplicate** entity names — merge `Tiomos` / `tiomos` / `TIOMOS` into one node.
     There's an important safety rule here: it **refuses to merge names that differ only in
     numbers** (e.g. `+45° Angle` vs `-45° Angle`, or `105°` vs `120°`). Without this guard,
     fuzzy matching silently collapses distinct specs and corrupts the graph.
   - **Filter noise** — drop stop-words, ultra-short names, and pure numbers.
2. **Build a graph** with **NetworkX** (a Python graph library) in `rag/pipeline/graph.py`.
   Nodes accumulate a `mentions` count, their source PDFs, the chunk IDs they appeared in,
   and a *majority vote* on their type. Edges accumulate a `weight` (how often the two
   things co-occur) and the set of relationships seen.
3. **Detect communities** with **Louvain** (`rag/pipeline/communities.py`), using a fixed
   random `seed=42` so the result is reproducible. Each node is tagged with its community ID.
4. Also writes an interactive **`knowledge_graph.html`** you can open and explore.

Because this stage reads the cache and touches no network, you can re-run it instantly.

### Stage 3 — Build the store (`scripts/build_store.py`)

1. **Summarise** the top-N largest communities by sending each one's entities and
   relationships to an LLM (`summarize_top_communities`).
2. **Embed and persist** into **ChromaDB** (`rag/pipeline/store.py`, `build_store()`),
   creating **two collections**:
   - `graph_rag_chunks` — every text chunk, embedded.
   - `graph_rag_communities` — the community summaries, embedded.

Both use the Ollama `nomic-embed-text` embedder. `build_store` is *destructive* — it wipes
and rebuilds both collections each time.

### Rebuild commands

```bash
python -m rag.scripts.run_extraction    # Stage 1 — Claude API, resumable, cached
python -m rag.scripts.build_graph       # Stage 2 — graph + communities + viz (pure compute)
python -m rag.scripts.build_store       # Stage 3 — summaries + embeddings → ChromaDB (needs Ollama)
```

---

## 7. How we use the GraphRAG at query time

This is the heart of it. Entry point: `graph_rag_answer()` in `rag/pipeline/answer.py`,
which does **retrieve → assemble prompt → call the LLM**.

Two things are loaded and live at query time:

- **`G`** — the knowledge graph, held **in memory** (rebuilt from `extractions.json`).
  *The graph itself is not stored in the database* — only chunks and summaries are.
- **`store`** — the open ChromaDB with its two collections.

The retrieval (`graph_retrieve()` in `rag/pipeline/retrieve.py`) gathers **three channels**
of context and fuses them:

### Channel 1 — Vector search over chunks (the "local evidence")

Embed the question, pull the **top 5 nearest chunks** from `graph_rag_chunks`. Identical to
standard RAG. We also remember which chunk IDs came back.

### Channel 2 — Walk the knowledge graph (the GraphRAG core)

This happens in three sub-steps:

**(a) Seed the graph — from two sources, combined:**

```python
seeds = find_entities_in_chunks(G, chunk_ids) | find_entities_in_query(G, query)
```

- `find_entities_in_chunks` — entities living in the chunks we just retrieved.
- `find_entities_in_query` — entities whose **name appears in your question text** itself.

The `|` is a set union: an entity counts as a seed if *either* source finds it. The second
source is important — it lets the graph start from things you *named*, independent of what
the vector search found.

**(b) Expand by hops** (`expand_via_hops`, default `hop_depth=1`): from each seed, step out
one connection in the graph (a **BFS** — breadth-first search) to pull in directly related
entities. *This is the dot-connecting move:* found the hinge → grab the compatible plate,
even if the plate's chunk never ranked in the top 5.

**(c) Render** the expanded entity set into a readable text block
(`render_graph_context`), like:

```
Tiomos (product, 27 mentions):
  Tiomos --[manufactured_by]--> Grass
  Tiomos --[compatible_with]--> Mounting Plate H
```

Capped at 15 entities × 5 edges to keep the prompt a sensible size.

### Channel 3 — Community summaries (the "big picture")

A *separate* vector search, this time against `graph_rag_communities`, pulling the **top 2**
most relevant cluster summaries. This channel is **independent of the chunk search** — it
gives the model high-level thematic grounding nothing in the chunks contains.

### Assemble the prompt and answer

All three channels are laid into one prompt under labelled headers
(`build_graph_rag_prompt`):

```
=== CATALOG TEXT ===           ← the 5 chunks (with source + page)
=== KNOWLEDGE GRAPH (entity relationships) ===   ← the rendered sub-graph
=== THEMATIC SUMMARIES ===     ← the 2 community summaries

USER QUESTION: ...
ANSWER:
```

The system prompt (`GRAPH_RAG_SYSTEM`) explicitly tells the model it has three sources and
to use all of them, citing catalogs and pages. Then `llm_chat` sends it to the configured
answer model and returns `(answer, retrieval)` — the `retrieval` object lets you inspect
*exactly which sources produced the answer*.

---

## 8. A worked example

**Question:** *"What mounting plate suits the Tiomos hinge on a thick door?"*

- **Standard RAG** retrieves 5 chunks similar to the question. It likely grabs the Tiomos
  hinge description, maybe the thickness rule — but the *plate* chunk is about plates, looks
  dissimilar to a hinge question, and may rank #18. The model never sees it and answers
  incompletely.

- **GraphRAG:**
  - Channel 1 retrieves the **same 5 chunks** as standard RAG — the pages handed to the
    model are *identical to baseline* (this is guaranteed by the code; see §14). The plate's
    detail page is still ranked #18 and still not retrieved.
  - Channel 2 seeds on `Tiomos` (from the chunk **and** from your question naming it), then
    hops to `Mounting Plate H` via the `compatible_with` edge. Crucially, it surfaces this as
    a *fact rendered in text* — `Tiomos --compatible_with--> Mounting Plate H` — **not** by
    fetching Plate H's chunk. So the model can now *name* the right plate, but it still does
    **not** see the plate's specs, part number, or price, because that page was never retrieved.
  - Channel 3 adds the "Grass concealed-hinge family" summary for context.
  - **The honest outcome:** GraphRAG answers the *"which plate?"* part (the connection) that
    standard RAG misses, but cannot give the plate's *details* — both systems lack that page.
    The graph recovered a scattered **fact**, not a scattered **page**. (A graph-driven
    retrieval that used the plate entity's stored `chunk_ids` to *fetch* its page would close
    this gap — see the fix discussion in §13/§14.)

---

## 9. Critical analysis: does this design actually make sense?

A fair challenge: *"We do a vector search first, then add the graph stuff on top. If the
search didn't find the relevant chunks, won't the graph make little difference?"*

This is a **sharp and partly correct** critique. Here's the honest breakdown.

### Where the critique is right

This is a **"vector-first, then expand"** flavour of GraphRAG (sometimes called *local*
GraphRAG). The graph can only walk outward from seeds the early steps found. So:

- If the vector search **completely misses** the topic (zero on-topic chunks) **and** you
  don't name the entity in your question, the graph expands from bad seeds → bad neighbours.
  Garbage in, garbage out. **The graph does not help you *find the topic* in the first place.**

### Where there's important nuance

It is *not* simply "RAG with a sprinkle of graph." There are really **two-and-a-half
independent channels**:

1. **Seeding has a second path that bypasses vector search.** `find_entities_in_query`
   matches entity names against your *question text*, so naming a product seeds the graph
   regardless of what the vector search returned.
2. **The graph's real job is recovering *connected facts*, not pages or the topic.** If the
   search finds even *one* relevant seed, the graph surfaces its neighbours *as rendered text*
   (`A --relation--> B`) — even neighbours the search ranked too low. But note the precise
   limit (see §8 and §14): it recovers the **fact** that B is connected, **not B's source
   page**. Channel 1 — the actual catalog pages — is chosen by plain vector search and is
   *identical to the no-graph baseline*. So the graph helps the *"which thing is related?"*
   case, but cannot supply the related thing's *details* unless that page was independently
   retrieved.
3. **Community summaries are a fully separate search** against a different collection, so the
   "big picture" channel doesn't depend on the chunk search at all.

### The honest verdict

> This design improves **recall of *related/connected* facts**, not **recall of the initial
> topic.** If the search finds a toehold, the graph extends it well. If the search misses the
> subject entirely *and* you didn't name it, GraphRAG quietly degrades to roughly plain RAG —
> which is precisely the weakness the critique identifies.

### What "stronger" would look like (local vs global GraphRAG)

The more advanced design (e.g. Microsoft's GraphRAG "global search") doesn't seed from
vector hits at all for broad questions — it does a *map-reduce over **all** community
summaries*, so it isn't bottlenecked by initial retrieval. Our project only *approximates*
this with a top-2 community lookup. Strengthening that path (use more communities, or
map-reduce over all of them for "big picture" questions) is the natural next improvement.

### A subtle correctness trap worth knowing

GraphRAG here is only as good as the **ID consistency** between the database and the graph.
The chunk-seeding step matches chunk IDs from the vector store against chunk IDs stored on
graph nodes. The original notebook had a bug where these IDs *didn't match*, so the match was
**always empty** ("Graph entities found: 0") and GraphRAG silently collapsed into plain RAG
without anyone noticing. The fix was the **deterministic chunk IDs** (`extract.py`) used
identically in both the store build and the graph build, plus the added query-string seeding
path. The lesson: *a GraphRAG can silently degrade to plain RAG and still "work" — measure it.*

### Measuring it

This is why `rag/eval/` exists — a benchmark harness that runs the **same query set** through
both standard RAG and GraphRAG and compares them. The right way to settle "does the graph
actually help *here*?" is to run it and read the numbers, not to argue from theory.

```bash
python -m rag.eval        # benchmark GraphRAG vs standard vector RAG
```

---

## 10. Key files map

| File | What it does | Stage |
|------|--------------|-------|
| `rag/pipeline/extract.py` | Read PDFs (PyMuPDF), chunk text, deterministic chunk IDs | Build 1 |
| `rag/pipeline/entities.py` | Send chunks to LLM → entities + relationships (cached, resumable) | Build 1 |
| `rag/pipeline/normalize.py` | Clean extractions: normalise types, dedupe, filter noise | Build 2 |
| `rag/pipeline/graph.py` | Build the NetworkX knowledge graph | Build 2 |
| `rag/pipeline/communities.py` | Louvain community detection + LLM summaries | Build 2/3 |
| `rag/pipeline/store.py` | ChromaDB: embed + persist chunks and summaries | Build 3 |
| `rag/pipeline/retrieve.py` | **Query time:** the three retrieval channels + orchestration | Query |
| `rag/pipeline/answer.py` | **Query time:** assemble prompt, call LLM, return answer | Query |
| `rag/scripts/run_extraction.py` | CLI for Stage 1 | Build |
| `rag/scripts/build_graph.py` | CLI for Stage 2 | Build |
| `rag/scripts/build_store.py` | CLI for Stage 3 | Build |
| `rag/eval/` | Benchmark: GraphRAG vs standard RAG | Eval |
| `catalogs/*.pdf` | The source documents (repo root, shared with the engine) | Input |
| `rag/chroma_db_graph/` | The persisted vector database | Artifact |
| `rag/extractions.json` | Cached Stage-1 output (gitignored) | Artifact |
| `rag/knowledge_graph.html` | Interactive graph visualisation (gitignored) | Artifact |

---

## 11. Glossary

- **LLM (Large Language Model)** — a model like Claude that generates text. Knows public
  data it was trained on, not your private documents.
- **Hallucination** — when an LLM confidently states something false. RAG reduces this by
  grounding answers in retrieved source text.
- **Context window** — the maximum amount of text a model can consider at once. The reason
  we can't just paste all the PDFs in.
- **RAG (Retrieval-Augmented Generation)** — retrieve relevant snippets first, then have the
  model generate an answer from them. "Open-book exam" for an LLM.
- **Chunk** — a small slice of a document (here, 800 chars with 100 overlap) — the unit we
  retrieve.
- **Embedding / vector** — a list of numbers representing the *meaning* of text. Similar
  meanings → nearby vectors.
- **Vector database** — a database (here **ChromaDB**) built to find the vectors nearest to a
  query vector, fast.
- **Cosine distance** — the measure of how similar two vectors' directions are; how
  "nearest" is judged.
- **Semantic search** — searching by meaning (via embeddings) rather than exact keywords.
- **Knowledge graph** — a network of **entities** (nodes) connected by **relationships**
  (edges). Lets you follow connections between facts.
- **Entity** — a "thing" in the graph: a product, manufacturer, feature, spec, etc.
- **Relationship / edge** — a typed connection between two entities, e.g. `compatible_with`.
- **NetworkX** — the Python library used to hold and traverse the graph.
- **Community** — a tightly-interconnected cluster of entities within the graph.
- **Louvain** — the algorithm that automatically finds communities.
- **Community summary** — an LLM-written description of one community; the "big picture" layer.
- **Seed (seeding)** — the starting entities from which the graph walk begins.
- **Hop / BFS (breadth-first search)** — stepping outward along edges from the seeds; "1 hop"
  = direct neighbours.
- **PyMuPDF (`fitz`)** — the library used to extract text from PDFs.
- **Ollama** — a tool for running models (here the `nomic-embed-text` embedder) locally.
- **Deterministic** — same input → same output every time. Our chunk IDs are deterministic so
  the graph and the database refer to the same chunks.
- **Local vs global GraphRAG** — *local* starts from a specific query/entity and expands
  (what we do); *global* reasons over all community summaries for broad "big picture"
  questions (the stronger approach we only approximate).

---

## 12. Summary in five sentences

1. **RAG** retrieves a few relevant text chunks and lets the LLM answer from them, instead of
   stuffing whole documents into the prompt.
2. Standard RAG finds *individually similar* text but struggles to **connect facts across
   chunks** or answer **big-picture** questions.
3. **GraphRAG** adds a **knowledge graph** (entities + relationships) so the system can
   *follow connections*, and **community summaries** for the big picture.
4. At query time we fuse **three channels** — vector chunks, a graph walk from seeds, and
   community summaries — into one prompt.
5. The honest caveat: because the graph walk starts from what the search (or your wording)
   found, it boosts recall of *connected* facts but can't rescue a query whose topic the
   search missed entirely — so **measure it with `rag/eval/`** rather than assuming.

---

## 13. Appendix: query-stage weakness analysis (verbatim)

> The following analysis of the query stage is reproduced verbatim.

Here's the tight recap — every weakness lives at query time (the moment someone
asks a question), all in the one graph_retrieve function. Four of them, in plain
terms:

1. The graph doesn't pick the pages. (the big one)
The pages handed to the AI are chosen entirely by plain vector search — same as
the no-graph baseline. The map has zero influence on which pages get found. → This
is why GraphRAG and plain RAG returned identical pages every time, and why
scattered-answer questions ("what plate works with Tiomos") fail on both.

2. The entity grab is wildly over-broad.
It starts from things in your question, then takes one "hop" out to everything
connected. Because the map is dense, one hop balloons to ~500 things — nearly the
whole map. So it's not selecting what's relevant to your question; it's grabbing
almost everything.

3. The bit of map it pastes in is generic, not relevant.
From those ~500, it keeps only the 15 most-mentioned-overall — which means
catalog-wide hubs like "Grass" and "Steel," not the things specific to your
question. So even the decorative use of the map feeds the AI noise rather than
signal.

4. The community summaries are picked the same blind way.
The two "thematic summaries" added to the prompt are also chosen by plain vector
search, with the same blind spot — no use of the map's structure.

---
The through-line: at query time the map is never navigated. Pages, entities, and
summaries are all selected by plain similarity matching; the connections in the
map — the entire reason to build it — are never followed. The map is present but
passive.

Consequence for the numbers we saw:
- Pages identical to baseline → weakness #1.
- The meaningless "100% entity coverage" → weakness #2 (grab nearly everything,
you'll always "cover" the few you wanted).

If we fix #1 — make the query actually follow connections to fetch scattered pages
— #2 and #3 largely fall out as part of the same fix, because you'd be selecting
entities by relevance to the question instead of grabbing a blind 1-hop blob

---

## 14. Verification notes on the query-stage analysis

These notes verify the Section 13 analysis against the actual code in
`rag/pipeline/retrieve.py` and `answer.py`, confirm where it is precisely right, and
refine the few places that need nuance.

### Overall verdict: the core thesis is right

The through-line — *"at query time the map is never navigated; pages, entities, and
summaries are all selected by plain similarity"* — is accurate and is the most important
observation.

### #1 — "The graph doesn't pick the pages." Airtight, and it's the big one

This is provable from the code, not just plausible. Both paths call the *same* function with
the *same* arguments:

- `standard_rag_retrieve` → `vector_retrieve_chunks(store.chunks, query, n=5)`
- `graph_retrieve` → `vector_retrieve_chunks(store.chunks, query, n=5)` (`n_chunks` defaults to 5)

Same collection, same query, same `n`. So the `CATALOG TEXT` section — the only place the AI
gets *detailed source text* — is **byte-identical to baseline by construction.** "Identical
pages every time" isn't a coincidence; it's guaranteed.

The deeper point: when the graph hops to `Mounting Plate H`, it **renders the entity and its
edge as text** (`render_graph_context`) — it does **not** go fetch Plate H's *chunk*. The node
knows which chunks it lives in (the `chunk_ids` attribute), but that's never used to retrieve
them. So the AI learns the *fact* "Tiomos —compatible_with→ Plate H" but never sees Plate H's
actual specs, part number, or price, because that page was never retrieved. (This corrects the
worked example in Section 8, which implied the graph recovers scattered *pages*; it recovers
scattered *facts-as-text* only, and leaves page selection 100% to vector search.)

### #2 — "The entity grab is wildly over-broad." Mechanism correct

`expand_via_hops(G, seeds, hop_depth=1)` takes the union of all neighbours of all seeds, with
no edge-weight, edge-type, or degree filtering. In a dense graph, one hop from any hub floods
most of the map — the ~500 figure is entirely consistent with that. The seeds themselves are
already broad: `find_entities_in_chunks` returns *every* entity in all 5 retrieved chunks.

Refinement on the *harm*: the over-broad set only feeds two things — the rendered context
(capped at 15) and the reported `graph_entities` list. It does **not** touch page selection.
So #2's real damage is exactly the next point — it makes the **"100% entity coverage" metric
meaningless** (grab nearly everything and you trivially "cover" the target). It's a
measurement artifact, not extra noise to the LLM directly.

### #3 — "The pasted map is generic, not relevant." Correct, with one precision

Confirmed: `render_graph_context` does `sorted(entities, key=... mentions ..., reverse=True)[:15]`
— it ranks by **catalog-wide mention count**, so from a ~500 blob you keep the global hubs
(`Grass`, `Steel`), not the query-specific entities.

The one precision: a block is built only for the top-15 entities, but *within* a block, edges
to **any** entity in the full ~500 set are shown. So:

- If your query entity is itself a **hub** (high mentions), it makes the top 15 and its
  specific edges (incl. to Plate H) *do* render — partial signal survives.
- If your query entity is **low-mention** (the common case for a specific product question),
  it never makes the top 15 and gets dropped entirely — then #3 bites fully.

Either way the fix is the same: rank by *relevance to the query* (graph distance from query
seeds), not by global frequency.

### #4 — "Community summaries picked the same blind way." Mechanically true, but the most defensible of the four

Confirmed: `vector_retrieve_communities(store.communities, query, n=2)` is pure vector
similarity. No graph structure at *selection* time.

Nuance worth keeping: the summaries themselves *are* graph-derived (Louvain clusters), so
structure is baked into their *content* — just not into *which two* you pick. And
vector-selecting topically-relevant clusters is a legitimate, common pattern; it's not a bug
the way #1 is. The real upgrade isn't "use the graph to pick communities," it's the *global
search* pattern — map-reduce over **all** community summaries for big-picture questions, so
it isn't gated by a top-2 similarity lookup at all.

### The through-line and the fix — both correct

"The map is present but passive" is the right summary, with one honest tweak: the entities
*are* traversed (one hop), so it's not literally untouched — but the traversal is **blind**
(no weighting, no pathfinding) and, fatally, **never feeds back into page selection.**
Active-but-blind for entities; passive for pages and summaries.

The fix claim is right, and the hook to do it already exists. Every graph node stores
`chunk_ids` (the chunks that entity appears in). So a graph-driven retrieval is wire-up-able
today:

> seed entities from the query → traverse *selectively* (follow `compatible_with`/`part_of`
> edges, weight by edge strength, bound by distance) → collect those entities' `chunk_ids` →
> **fetch those chunks** and merge them with the vector hits.

Do that and you're (a) using connections to pull *scattered pages* (#1), (b) selecting a
*tight, relevant* entity set instead of a 1-hop blob (#2), and (c) rendering context from
query-relevant entities rather than global hubs (#3). One fix, three weaknesses gone.

### Two calibration caveats

- It's worth confirming the ~500 figure and the "identical pages" claim came from the eval
  run rather than inspection — the *page* identity is guaranteed by code, but the
  entity-explosion magnitude is graph-dependent. If those came from `rag/eval/`, the numbers
  are solid.
- For a question that *names* the product, the graph edge `Tiomos —compatible_with→ Plate H`
  can still answer the *"which plate"* part by name even today — so GraphRAG isn't strictly
  zero-value, it just can't deliver the plate's *details*. The eval scoring determines whether
  that partial value shows up.
