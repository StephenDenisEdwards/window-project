# Window Project — Problem Domain Evaluation

## What's Strong

**The constraint problem is real and underserved.** Hinge-to-mounting-plate compatibility is a proper constraint satisfaction problem — not a fuzzy "recommendation" task. Cabinet dimensions, overlay types, weight tolerances, and mounting geometry create a combinatorial space that's too large for filter dropdowns but too precise for an LLM to guess at. This is the sweet spot where deterministic reasoning actually matters.

**The "always correct vs usually correct" framing is exactly right.** In a professional trade context, a contractor who gets the wrong hinge wastes a site visit. They won't come back. This isn't like recommending a slightly wrong shirt size — the cost of error is concrete and measurable. That makes the deterministic engine a genuine moat, not just a technical preference.

**The two-path UX is smart.** A contractor who knows they need a 170° full overlay hinge for a 19mm board with a specific boring pattern has zero patience for a chatbot that asks "what room are you working on?" Separating the pro fast-track from guided discovery is the right call — most AI commerce products get this wrong by forcing everyone through the same funnel.

## Where to Be Cautious

**Knowledge ingestion is the hidden bottleneck.** The brief says Würth has an internal sales process document covering 13 product families. Turning that into clean, structured constraint rules is laborious domain work — not an engineering problem. The timeline (weeks 3–6 for the reasoning engine) is tight if the source data is messy, inconsistent, or has undocumented edge cases that only veteran sales reps know. This is likely where schedule pressure will come from.

**The "platform that compounds" vision needs validation.** Hinge compatibility is deeply mathematical — dimensions, angles, tolerances. Fashion accessories or sporting goods have much fuzzier compatibility (style, body type, use case). The reasoning engine architecture may carry across, but the *type* of constraints changes fundamentally. Deterministic rules work for hinges. They're less obviously right for "does this belt go with these shoes." The platform story is compelling but the jump from trade hardware to fashion is bigger than the brief implies.

**Scaling to 12 brands on the same architecture assumes uniform catalog structure.** If Würth's 12 brands have different catalog schemas, different SKU conventions, or different compatibility logic, each brand deployment could be closer to a fresh build than a configuration change. Worth probing early.

## Bottom Line

The first engagement — hinges for 3 brands — is a well-defined, solvable problem with clear commercial value. It's the kind of thing where you can ship something demonstrably better than what exists today. The broader platform vision is plausible but unproven, and the constraint reasoning approach will need to evolve significantly for less mathematical product domains.

The hardest part won't be the code — it'll be extracting complete, correct constraint rules from Würth's institutional knowledge and making sure nothing falls through the cracks when a contractor is on a job site relying on the output.

## Würth US Subsidiary Landscape

The brief's "twelve-brand operation" maps to **Würth Industry North America (WINA)** — a $1B division of the Würth Group (world's largest fastener distributor), consisting of brands across 110+ North American locations.

For the cabinet hardware / contractor side, the most likely Phase 1 brands are:

- **Würth Louis and Company** (wurthlac.com) — Since 1975, serves cabinetmakers and woodworking professionals. Dedicated Hinges & Lift Systems category.
- **Würth Baer Supply Company** (wurthbaersupply.com) — Serves cabinetmakers, contractors, builders, designers. Dedicated Hinges section.
- **Würth Wood Group** (wurthwoodgroup.com) — Decorative hardware / cabinet shop supplies.

These brands carry hinge lines from manufacturers like **Grass America** (soft-close, European-style concealed hinges) and likely **Blum**, **Häfele**, and others.

### Current State of the Websites

The sites are organized by broad product category with basic filters — exactly the problem the brief describes. A contractor looking for a specific hinge has to manually navigate hundreds of SKUs across multiple filter dimensions. There is no guided selection, no compatibility checking, and no constraint reasoning. This confirms Window's core thesis.

### The Constraint Space

The hinge compatibility problem is defined by at least these parameters:

- **Opening angle** (95°, 110°, 155°, 170°)
- **Overlay type** (full, half, inset)
- **Door thickness / board material**
- **Mounting plate type** (cruciform, linear, face-frame)
- **Cup size / boring pattern** (35mm, 26mm)
- **Weight capacity / door weight**
- **Soft-close vs standard**
- **Cabinet dimensions**

The compatibility between a hinge cup and its mounting plate is mathematically precise — not every combination works, and the valid combinations depend on the cascade of choices above. This is a well-structured CSP where deterministic reasoning is both appropriate and necessary.

## Data Ingestion Risk — The Unknown Variable

The sample data in `sample-data/` (53 hinges, 55 mounting plates across Blum, Grass, and Hafele) was built from web research against publicly available manufacturer specs. It demonstrates the *shape* of the problem but tells us nothing about what Würth's actual catalog data looks like or how hard ingestion will be. The real difficulty hinges on questions that can only be answered during discovery:

**Format uncertainty.** The catalog data could be anything from a well-structured database export (easy) to scanned PDF lookup tables that a sales rep printed out years ago (hard). The brief mentions an internal sales process document covering 13 product families — that could be a goldmine or a 4-page flowchart with gaps.

**Explicit vs implicit compatibility.** Does Würth maintain a table that says "hinge X works with plate Y", or does a veteran sales rep just *know* that from experience with the Blum/Grass spec sheets? If compatibility lives in people's heads rather than structured data, extraction becomes an interview-driven process, not an engineering one.

**Consistency across product families.** Hinges from Blum are well-documented with exact specs and published compatibility matrices. Another product family in the catalog might have rules that only exist as institutional knowledge. The 13 product families will not all be equally clean.

**Imperial/metric inconsistency.** US contractors think in inches. Manufacturers spec in millimetres. The catalog, sales documents, and customer-facing content may mix both inconsistently. The reasoning engine needs canonical units, which means a normalisation layer during ingestion.

**Completeness.** The constraint solver is only as good as the rules it encodes. Missing a single edge case — a hinge that technically fits but fails under load in a specific mounting configuration — is the kind of gap that erodes trust with professional users. Validating completeness requires domain expertise, not just engineering rigour.

**Bottom line on ingestion:** The engineering work (building a constraint solver, standing up a knowledge base) is well-understood and estimable. Extracting complete, correct rules from messy institutional knowledge is not. This is the part of the timeline most likely to slip, and it's the part least visible in the brief's week-by-week milestones.

## Open Areas Beyond Ingestion and the AI Layer

### Constraint Engine Design Decisions

- The engine uses indexed pre-filtering on hinges (by brand, cabinet type, application) followed by brute-force evaluation against all plates. This handles the current catalog (53 hinges, 55 plates) easily. Tooling research (`production-tooling-research.md`) concluded that CSP solvers (OR-Tools, Z3) are not warranted at foreseeable scale — indexed brute force works up to ~10K products per type. Solvers only become necessary for simultaneous multi-family configuration (3+ product types at once).
- Rules are Python functions in `engine_v1/rules.py` — the single source of truth. Adding or modifying a rule currently requires a code change and deploy. Moving simple predicate rules to a data-driven format (JSON definitions interpreted by a generic evaluator, with Python callables for complex logic) is the next step for maintainability. See `../design/DESIGN-constraint-engine.md` for rule maintenance risks.

### Multi-Brand Catalog Architecture

- Are the 3 Phase 1 brands on separate e-commerce platforms or one shared backend? This determines whether Window integrates via API, database, or scraping.
- SKU identity across brands — the same Blum hinge has different distributor SKUs at different Würth brands (e.g. `BP71B3550` at Würth Baer). The domain model now handles this via `ManufacturerProduct` (canonical manufacturer part number) with per-brand `DistributorSKU` mappings. Pricing lives on the SKU, not the product.

### Session and State Management

- The two-path conversational flow is multi-turn and stateful. Where does session state live? How long do sessions persist? Can a contractor start on mobile, leave for a job site, and resume?
- Cart/checkout integration — Window recommends products, but how does that connect to the brand's actual ordering system?

### Infrastructure and Compliance

- SOC 2 from day one is a real constraint on architectural choices. Audit logging, encryption at rest/in transit, RBAC, and data deletion on contract termination all need to be designed in from the start, not bolted on.
- Client-isolated environment — does each brand get its own tenant, or is it one environment with logical isolation? This affects cost and complexity significantly.

### Testing and Domain Validation

- How do you verify the constraint engine is correct against real-world installations? The test suite (70+ tests, 7 customer scenarios) proves internal consistency but not domain correctness. You need a domain expert validating outputs against known-good configurations.
- Regression testing when catalog data changes — new products, discontinued SKUs, updated compatibility rules.

### The Dashboard

- The brief mentions a "brand intelligence dashboard" with anonymised session data, behavioural insights, and operator controls. This is a separate frontend build that could easily eat weeks if scope isn't locked down early.

### Deployment Across Brands

- The timeline assumes Brand 2 and 3 are fast follows on the same architecture. But "same architecture, different catalog" still requires per-brand configuration, testing, and UAT with each brand's team. That's not zero effort.
