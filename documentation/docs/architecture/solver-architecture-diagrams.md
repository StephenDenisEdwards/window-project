# Solver Architecture Diagrams

Visual comparison of the three constraint solver approaches used in this project.

---

## 1. V1 Paired Solver (`engine_v1/solver.py`)

The original hinge constraint engine. Handles two-product families (hinge + mounting plate) with indexed pre-filtering on hinges before brute-force plate evaluation.

```mermaid
flowchart TD
    subgraph Input
        REQ[CustomerRequirements<br/><i>cabinet type, door dims,<br/>application, brand</i>]
        H[(53 Hinges)]
        P[(55 Plates)]
    end

    REQ --> PF

    subgraph Pre-filter["Pre-filter Hinges (indexed)"]
        PF[Application index] --> CT[Cabinet type index]
        CT --> BL{Brand<br/>preferred?}
        BL -->|Yes| BI[Brand index<br/><i>intersection</i>]
        BL -->|No| SK[Skip brand filter]
        BI --> FH
        SK --> FH
    end

    H --> PF
    FH[Filtered hinges<br/><i>~5-15 from 53</i>]

    subgraph Evaluate["Pairwise Evaluation"]
        FH --> LOOP["For each hinge × plate pair"]
        P --> LOOP
        LOOP --> R008[R008: hinges_per_door<br/><i>from door height</i>]
        R008 --> RULES["14 constraint rules<br/><i>R001 brand lock<br/>R002 series compat<br/>R003 cabinet type<br/>R004-R015 ...</i>"]
        RULES --> RES[RuleResults + Configuration]
    end

    subgraph Output
        RES --> VALID{All rules<br/>passed?}
        VALID -->|Yes| RANK["Rank valid configs<br/><i>price ASC, capacity DESC</i>"]
        VALID -->|No| DISCARD[Discard]

        RANK --> BEST["Recommended + alternatives"]

        DISCARD -.-> BF["_best_failing()<br/><i>closest match for<br/>failure explanation</i>"]
    end

    style Pre-filter fill:#e8f4e8,stroke:#4a9
    style Evaluate fill:#e8e8f4,stroke:#66a
    style Output fill:#f4f0e8,stroke:#a96
```

**Key characteristics:**
- Pre-filter indexes narrow hinges before evaluation (53 → ~5-15)
- All plates evaluated against every filtered hinge
- Fixed two-product structure (hinge + plate)
- 14 rules, all evaluated per pair (no early termination)

---

## 2. V2 Flat N-Candidate Solver (`engine_v2/core/solver_n.py`)

Generalised solver for families with any number of product roles. Computes the full Cartesian product and evaluates every combination against every rule.

```mermaid
flowchart TD
    subgraph Input
        REQ[Requirements<br/><i>family-specific</i>]
        R1[(Role A products<br/><i>e.g. light bars</i>)]
        R2[(Role B products<br/><i>e.g. drivers</i>)]
        R3[(Role C products<br/><i>e.g. dimmers</i>)]
    end

    subgraph PreFilter["Pre-filters (optional)"]
        R1 --> F1[Filter A]
        R2 --> F2[Filter B]
        R3 --> F3[Filter C]
    end

    subgraph Cartesian["Full Cartesian Product"]
        F1 --> CP["A × B × C<br/><i>all combinations</i>"]
        F2 --> CP
        F3 --> CP
        CP --> COUNT["e.g. 5 × 4 × 4 = 80<br/>or 100 × 40 × 50 = 200,000"]
    end

    subgraph Evaluate["Evaluate Every Combination"]
        COUNT --> DERIVE["Compute derived values<br/><i>from requirements</i>"]
        REQ --> DERIVE
        DERIVE --> EACH["For each (A, B, C) triple"]
        EACH --> RULE1["Rule 1"]
        RULE1 --> ET1{Early<br/>termination?}
        ET1 -->|"FAIL + enabled"| SKIP[Skip remaining rules]
        ET1 -->|"PASS or disabled"| RULE2["Rule 2"]
        RULE2 --> DOTS["..."]
        DOTS --> RULEN["Rule N"]
        RULEN --> CONF[NConfiguration<br/><i>candidates dict + rule results</i>]
        SKIP --> CONF
    end

    subgraph Output
        CONF --> VALID{All hard<br/>constraints<br/>passed?}
        VALID -->|Yes| RANK["Rank by rank_key<br/><i>price, capacity, etc.</i>"]
        VALID -->|No| DISC[Discard]

        RANK --> REC["Recommended + alternatives"]
        DISC -.-> BF["_best_failing()<br/><i>full Cartesian re-eval<br/>no early termination</i>"]
    end

    style PreFilter fill:#e8f4e8,stroke:#4a9
    style Cartesian fill:#fde8e8,stroke:#c66
    style Evaluate fill:#e8e8f4,stroke:#66a
    style Output fill:#f4f0e8,stroke:#a96
```

**Key characteristics:**
- Supports arbitrary number of product roles
- No pruning between roles — every combination visited
- Early termination skips remaining rules on first hard failure (per combination)
- Redundant work: a bad A-B pair is re-tested with every C
- Simple to configure: one flat rule list

---

## 3. V2 Staged Pipeline Solver (`engine_v2/core/solver_staged.py`)

Optimised solver that decomposes evaluation into sequential stages. Each stage introduces new product roles and prunes invalid partial configurations before the next stage.

```mermaid
flowchart TD
    subgraph Input
        REQ[Requirements]
        R1[(Role A products<br/><i>e.g. light bars</i>)]
        R2[(Role B products<br/><i>e.g. drivers</i>)]
        R3[(Role C products<br/><i>e.g. dimmers</i>)]
    end

    REQ --> DV["Compute derived values"]

    subgraph Stage1["Stage 1: Electrical Compatibility"]
        R1 --> S1CP["A × B<br/><i>bars × drivers</i>"]
        R2 --> S1CP
        S1CP --> S1EVAL["Stage 1 rules only<br/><i>LED001 voltage match<br/>LED002 wattage capacity<br/>LED003 connector type<br/>LED006-008</i>"]
        DV --> S1EVAL
        S1EVAL --> S1CHECK{All stage 1<br/>rules passed?}
        S1CHECK -->|Yes| S1KEEP["Keep partial config<br/><i>(bar, driver)</i>"]
        S1CHECK -->|No| S1PRUNE["PRUNE<br/><i>never reaches Stage 2</i>"]
    end

    subgraph Pruning["Pruning Gate"]
        S1KEEP --> SURV["Surviving pairs<br/><i>e.g. 4 of 20 pairs</i>"]
        S1PRUNE --> WASTE["Eliminated<br/><i>e.g. 16 of 20 pairs<br/>= 80% pruned</i>"]
    end

    subgraph Stage2["Stage 2: Dimming Compatibility"]
        SURV --> S2CP["valid pairs × C<br/><i>4 pairs × 4 dimmers = 16<br/>vs 80 without pruning</i>"]
        R3 --> S2CP
        S2CP --> S2EVAL["Stage 2 rules only<br/><i>LED004 protocol match<br/>LED005 dimmer wattage<br/>LED009 voltage compat</i>"]
        DV --> S2EVAL
        S2EVAL --> S2CHECK{All stage 2<br/>rules passed?}
        S2CHECK -->|Yes| S2KEEP["Complete config<br/><i>(bar, driver, dimmer)<br/>with traces from both stages</i>"]
        S2CHECK -->|No| S2DISC[Discard]
    end

    subgraph Output
        S2KEEP --> RANK["Rank by rank_key"]
        RANK --> REC["Recommended + alternatives"]
        S2DISC -.-> BF["_best_failing()<br/><i>disables pruning,<br/>full Cartesian eval</i>"]
    end

    style Stage1 fill:#e8f4e8,stroke:#4a9
    style Pruning fill:#fde8e8,stroke:#c66
    style Stage2 fill:#e8e8f4,stroke:#66a
    style Output fill:#f4f0e8,stroke:#a96
```

**Key characteristics:**
- Stages introduce roles incrementally — not all products evaluated at once
- Invalid partial configs pruned between stages (the key optimisation)
- Constraint traces accumulate across stages — final output identical to flat solver
- Failure analysis disables pruning (must search full space for closest match)
- More complex config: rules must be assigned to stages

---

## Comparison at a Glance

```mermaid
flowchart LR
    subgraph V1["V1: Paired"]
        direction TB
        A1["Pre-filter<br/>hinges"] --> B1["H × P<br/>evaluate all"] --> C1["Rank"]
    end

    subgraph V2F["V2: Flat N-Candidate"]
        direction TB
        A2["Pre-filter<br/>per role"] --> B2["A × B × C<br/>evaluate all"] --> C2["Rank"]
    end

    subgraph V2S["V2: Staged Pipeline"]
        direction TB
        A3["Pre-filter<br/>per role"] --> B3["A × B<br/>stage 1 rules"]
        B3 --> P3["Prune"]
        P3 --> D3["valid × C<br/>stage 2 rules"]
        D3 --> C3["Rank"]
    end

    style V1 fill:#f0f8f0,stroke:#4a9
    style V2F fill:#f0f0f8,stroke:#66a
    style V2S fill:#f8f0f0,stroke:#a96
```

| | V1 Paired | V2 Flat N-Candidate | V2 Staged Pipeline |
|---|---|---|---|
| **Product roles** | 2 (fixed) | N (generic) | N (generic) |
| **Pre-filtering** | Indexed (brand/type/app) | Optional hooks | Optional hooks |
| **Search strategy** | Filtered × all | Full Cartesian | Staged Cartesian with pruning |
| **Complexity** | O(F × P × R) | O(∏Roles × R) | O(A×B×R₁) + O(valid×C×R₂) |
| **Inter-role pruning** | N/A (only 2 roles) | None | Between stages |
| **Early termination** | No | Per-combination | Per-combination per-stage |
| **Failure analysis** | Brand fallback + closest | Full Cartesian (no ET) | Full Cartesian (no pruning) |
| **Config complexity** | Low | Low | Medium (stage decomposition) |
| **Best for** | Hinge+plate pairs | Small catalogs, analytics | Large catalogs, APIs |
| **Demo notebook** | `v1_hinge_constraint_demo` | `v2_n_candidate_demo` | `v2_staged_pipeline_demo` |
