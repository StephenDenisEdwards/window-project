# Competitive Landscape: Cabinet Hardware Selection & Configuration

## Problem Statement

Given a customer's cabinet specifications (construction type, door dimensions, overlay, weight, opening angle), recommend compatible hardware combinations across multiple manufacturers. This is a constraint satisfaction problem involving dozens of interacting rules across thousands of product combinations.

## Existing Solutions

### 1. Manufacturer Tools (Single-Brand)

Each major manufacturer offers selection tools, but all are locked to their own product lines.

#### Blum (Market Leader)

The most sophisticated tooling in the industry:

- **[Product Configurator](https://www.blum.com/us/en/services/e-services/onlineproductconfigurator/)** — browser-based tool for configuring hinge, drawer/runner, lift, pocket, and organization systems. Accepts cabinet dimensions (metric with imperial converter), validates inputs against allowable ranges, and surfaces constraint violations when selections are incompatible. Produces complete parts lists, 2D/3D CAD data, and planning info.
- **[Cabinet Configurator](https://www.blum.com/aa/en/services/planning-construction-product-selection/cabinet-configurator/)** — drag-and-drop hinge placement on line drillings, shelf planning, and central panel layout.
- **[CAD/CAM Interface (BXF)](https://www.blum.com/eu/en/services/industrial-production/cad-cam-interface/)** — Blum Exchange Format, an XML-based interchange containing fittings data, assembly info, drilling patterns, and positions. Primary integration mechanism for third-party CAD software (Pro100, Microvellum, etc.).
- **DYNALOG** — legacy desktop planning software, largely superseded by browser tools.

#### Hettich

- **[Hettich Plan](https://www.hettich.com/en-us/services/hettich-plan)** — browser-based cabinet configurator covering planning, fittings selection, and production output. Automatically updated with latest hardware. Being phased out as of January 1, 2026.

#### Hafele

- **[Design Tools](https://www.hafele.com/us/en/info/services/project-planning-customization/design-tools/143861/)** — CAD database with 40,000+ articles and downloadable 2D/3D models. Includes a panel weight calculator that takes material type and dimensions as input, calculates door weight, and uses that to determine correct hardware — a key constraint for hinge selection. Also offers a custom Loox light bar configurator.

#### Grass

- **[Tiomos Hinge System](https://www.grassusa.com/products/tiomos-hinge-system/)** — well-documented with PDF catalogs and technical supplements, but no public online configurator. Selection is done through distributor channels (Hafele, Richelieu, CabinetParts.com).

#### Wurth Baer

- **[Wurth Baer Supply](https://www.baersupply.com/)** — offers EZ-Build Configurators, ScrewFinder, LaminateFinder, Custom Countertop Configurator, and Custom Drawer Box Quote Form. These are specialized point-solution finders, not a unified constraint engine.

#### Salice

- **[Hinge Selector (via HardwareHut)](https://hardwarehut.com/salice-hinge-help)** — guided selector for European concealed hinges.
- **[Silentia Overlay Hinge Selector (via Craftsman Engineering)](https://shop.craftsmanengineering.com/products/silentia-overlay-hinge-selector)** — Cabinet Vision add-on that auto-assigns the correct Salice Silentia 106-degree hinge based on overlay, face frame stile widths, and mullion widths.

**Key limitation:** Every manufacturer tool only recommends their own products. No cross-brand comparison or recommendation is possible.

---

### 2. Retailer / Distributor Tools (Decision Trees)

Simple guided flows that narrow product selection through 3-5 questions.

- **[CabinetParts.com Hinge Wizard](https://www.cabinetparts.com/wizard/hinge)** — "3 Questions, 100% Confidence." Asks overlay measurement, then narrows by brand and size.
- **[HingeOutlet Hinge Finder](https://www.hingeoutlet.com/pages/hinge-finder)** — similar guided approach.
- **[Rockler Hinge Selection Guide](https://www.rockler.com/learn/choosing-the-right-hinge-for-your-project)** — educational content with selection guidance.
- **[Richelieu Hardware](https://www.richelieu.com/us/en/)** — extensive parametric filtering on their e-commerce site (opening angle, material, slide extension, bearing type, installation type), but no constraint-solving configurator.

**Key limitation:** Shallow decision trees or faceted search. No constraint propagation, no exhaustive evaluation, brittle to extend to new product families.

---

### 3. CPQ Platforms (Configure, Price, Quote)

#### Cabinet/Furniture-Specific CPQ

- **[KitchenDEV](https://www.kitchendev.com/)** — end-to-end cloud CPQ built exclusively for kitchen cabinet manufacturers and retailers. Integrates with Netsuite, Acumatica, QuickBooks, Dynamics 365.
- **[WoodCPQ](https://www.woodcpq.com/)** — SaaS for panel cut-to-size ordering. Parametric cabinet configurator with auto-generated installation instructions, plus AI-based cutting optimization.
- **[Combeenation](https://www.combeenation.com/en/cpq-furniture-configurator/)** — 3D furniture configurator with CPQ. Rules engine enforces sizing, spacing, and placement constraints for doors, handles, and accessories. Blocks invalid/unbuildable combinations.
- **[Ar-range](https://www.ar-range.app/visual-cpq-for-cabinets-wardrobe)** — visual CPQ for cabinets and wardrobes with 2D/3D configurator, constraint-based rules for material/finish/dimension compatibility, instant quoting.
- **[Mercura](https://mercura.io/industries/kitchen-cabinets-and-modular-furniture-manufacturers/)** — CPQ targeting kitchen cabinet and modular furniture manufacturers.
- **[Friedman Frontier](https://friedmancorp.com/blog/cabinet-furniture-manufacturers-need-cpq-software/)** — CPQ for cabinet and furniture manufacturers.
- **[Renaissance Tech](https://renaissancetech.com/industries/furniture-fixtures/)** — furniture manufacturing CPQ with visual configurator.
- **[Microd](https://www.microdinc.com/cpq-software/)** — CPQ for furniture retail.

#### General-Purpose CPQ with Constraint Engines

- **[Tacton](https://www.tacton.com/)** — uses a true Constraint Satisfaction Problem (CSP) solver at its core. Variables represent product attributes/components, domains represent valid values, and constraints define valid combinations. Separates data from logic — new parts can be added without rewriting constraint logic. Constraint models are written in TCstudio (Tacton's modeling language). Case study: Siemens Energy replaced thousands of rules with a few hundred constraints, cutting quoting from 8 weeks to 5 minutes. Most architecturally similar to this project's approach. See also: [Constraint-Based vs Rules-Based Configuration](https://www.tacton.com/cpq-blog/constraint-based-vs-rules-based-configuration-the-advantage-for-complex-manufacturing/).
- **[Logik.io](https://www.logik.io/)** — headless, API-first configuration engine that plugs into Salesforce CPQ and Commerce Cloud. Real-time constraint solving.
- **Epicor CPQ** (formerly KBMax) — visual configurator with 2D, 3D, and AR product displays. Constraint-based rules, auto-generated BOMs and CAD files.
- **[Salesforce Revenue Cloud Product Configurator](https://trailhead.salesforce.com/content/learn/modules/product-configuration-with-revenue-cloud/explore-product-configurator-with-constraint-rules-engine)** — constraint-based engine using Constraint Modeling Language (CML) or a no-code Visual Builder. Defines rules for product/attribute compatibility, auto-adds/removes/suggests products.

**Key limitation:** Enterprise SaaS pricing. Generic platforms — not domain-specific to cabinet hardware. Rules are typically if-then rather than exhaustive constraint evaluation with explainability traces.

---

### 4. Open-Source Constraint Engines

#### Product-Configuration Specific

- **[openCPQ](https://github.com/webXcerpt/openCPQ)** (MIT, JavaScript) — browser-based product configuration library. Product models written in JS using openCPQ functions. Declarative/functional approach: recomputes entire state from accumulated user input. 75 stars, 27 forks. Includes an optical-transport product configurator demo. Also has an Odoo integration.
- **[or-tools-product-configurator](https://github.com/foohardt/or-tools-product-configurator)** — BSc thesis PoC using Google OR-Tools CP-SAT solver. Angular frontend, ASP.NET Core backend, MongoDB. Models product configuration as CSP with decision variables, domains, and constraints. Proves that CP-SAT can power a web configurator.

#### General-Purpose Constraint Solvers (Applicable)

- **[Google OR-Tools CP-SAT](https://developers.google.com/optimization/cp/cp_solver)** — open-source, production-grade. Combines constraint programming with SAT solving. Supports integer variables, AllDifferent constraints, conditional constraints. Python, Java, C#, C++ APIs. Actively maintained.
- **[Choco Solver](https://choco-solver.org/)** ([GitHub](https://github.com/chocoteam/choco-solver)) — open-source Java library for constraint programming (v5.0.0, Feb 2026, BSD 4-Clause). Provides search strategies (first_fail, impact-based, activity-based), explanation-based engine for conflict analysis. Explicitly cited for product configuration use cases.
- **[MiniZinc](https://www.minizinc.org/)** — high-level constraint modeling language that compiles to multiple backend solvers. Good for rapid prototyping of constraint models.

---

### 5. Academic Research

Foundational and directly relevant papers on CSP-based product configuration:

- **"Modelling and solving engineering product configuration problems by constraint satisfaction"** (ResearchGate) — foundational paper on CSP approaches to product configuration.
- **["Applying constraint satisfaction approach to solve product configuration problems with cardinality-based configuration rules"](https://link.springer.com/article/10.1007/s10845-011-0544-2)** (Journal of Intelligent Manufacturing, Springer) — demonstrates encoding configuration graphs as CSPs with cardinality-based rules.
- **["A constraint satisfaction approach to resolving product configuration conflicts"](https://www.sciencedirect.com/science/article/abs/pii/S1474034612000389)** (ScienceDirect) — encodes structural restrictions, configuration rules, and repair rules as CSP constraints.
- **["A constraint-based product configurator for mass customisation"](https://www.researchgate.net/publication/220171257_A_constraint-based_product_configurator_for_mass_customisation)** (ResearchGate) — addresses mass customization through constraint-based configuration.
- **"The Tacton View of Configuration Tasks and Engines"** (ResearchGate) — industry perspective on CSP-based configuration from the Tacton team.

Related domain research:

- **Knowledge graphs for building products** — W3C Linked Building Data ontologies (BOT, PRODUCT, PROPS) for semantic representation of hardware/components in BIM models. Product Manufacturer Data Ontology (BIMMO) integrates manufacturer specs with BIM/IoT data.
- **Multi-criteria material selection** — systematic reviews on MCDM methods for construction material selection, relevant to constraint-based approaches.

---

## Architectural Patterns Summary

| Pattern | Examples | Strengths | Weaknesses |
|---------|----------|-----------|------------|
| **Decision Tree / Wizard** | CabinetParts.com, HingeOutlet, Salice | Simple, fast to build | Brittle, hard to extend, shallow |
| **Parametric Filter** | Richelieu, Hafele CAD | Familiar UX, scales to large catalogs | No constraint propagation |
| **Guided Configurator** | Blum, Hettich Plan | Step-by-step with validation | Constraint logic embedded, not reusable |
| **Full CSP Solver** | Tacton, OR-Tools, Choco | Most scalable and maintainable | Highest implementation complexity |
| **CPQ with Rules Engine** | Combeenation, KitchenDEV | Integrated pricing and quoting | If-then rules, not declarative constraints |

---

## Gap: What Doesn't Exist

No public tool solves **cross-manufacturer cabinet hardware compatibility**. Every manufacturer's configurator only recommends their own products. Retailer tools are shallow decision-tree wizards. CPQ platforms are generic enterprise SaaS without domain-specific hardware knowledge.

Nobody offers: *"Given these cabinet specs, find all valid hinge + plate combinations across Blum, Grass, and Hafele, ranked by price, with full constraint traces explaining every decision."*

This project fills that gap — a distributor-perspective constraint engine that:

1. Treats all brands as equals
2. Derives compatibility from rules rather than hand-maintained matrices
3. Provides full explainability traces for every recommendation and rejection
4. Is designed to back an LLM conversational layer as the safety net ensuring correctness

The closest architectural precedent is Tacton's CSP approach, but Tacton is enterprise SaaS — not a domain-specific open engine with explainability traces designed to back an AI conversational interface.

---

## Appendix A: Deep Dive — Tacton, TCstudio, and the Constraint-Based Approach

### A.1 TCstudio (Tacton's Modeling Tool)

**TCstudio is proprietary and completely locked down.** It is a Windows desktop application bundled with Tacton's CPQ platform, available only to paying customers. There are no public downloads, no free trials, no published syntax or language documentation, and no code examples anywhere online.

#### Access and Training

To learn TCstudio, Tacton requires formal training through their Academy:

- **TCstudio Modeling Basic Training** (ACADEMY-MODELING-101) — prerequisite
- **TCstudio Modeling Methodology Training** (ACADEMY-MODELING-103)
- **TCstudio Modeling Testing** (ACADEMY-MODELING-104)
- **[TCstudio Modeling Certification](https://www.tacton.com/course/tcstudio-modeling-certification/)** — 4 days, **3,150 EUR (~$3,465 USD)** per participant. Includes multiple-choice exam, ~32 hours of modeling assignments, and interview sessions covering part tree structure, BOM, test cases, nomenclature, documentation, and performance optimization. Valid for 2 years; renewal costs 840 EUR.

#### How It Works

Based on all available public sources, TCstudio is a **hybrid visual/declarative tool** — primarily a GUI-based "point and click" environment, not a text-based programming language:

- **Point-and-click constraint definition**: "Engineers and product managers point and click to define constraints without programming."
- **Part tree structure**: Models are organized as hierarchical trees of classes, components, and parts
- **File format**: Models are stored as `.tcx` files (proprietary format)
- **Companion tools**: TCexcel Add-in (managing product data in spreadsheets) and TCstudio Testbench (automated testing of configuration models)

Core modeling concepts:

| Concept | Description |
|---------|-------------|
| **Classes** | Blueprints describing component features (like an OOP class) |
| **Components** | Specific instances of classes in the product tree |
| **Parts** | Physical objects used to build the product |
| **Constraints** | Rules defining valid relationships between components |
| **Named Domains** | Predefined lists of allowable values for attributes |
| **Search Strategies** | Algorithms controlling the order the solver tries combinations |
| **Scenarios** | Conditional rule sets that apply in specific contexts |
| **Questions & Groups** | User-facing input collection during configuration |

#### Underlying Technology

The internal engine is built on **Constraint Satisfaction Problem (CSP)** methodology, powered by **SICStus Prolog** — a Prolog implementation developed at SICS (Swedish Institute for Computer Science). Tacton has used SICStus Prolog for over 25 years.

The solving process works in three phases per user interaction:

1. **State loading** — load the current configuration state
2. **Propagation** — eliminate domain values that would violate constraints (narrows the search space)
3. **Search** — if propagation alone cannot resolve, systematically explore remaining options with backtracking

Attributes become **variables** with defined **domains** (possible values), product rules become **mathematical or logical constraints**, and the solver finds assignments satisfying all constraints simultaneously.

Source: [Unlocking Tacton's Product Configurator](https://www.cpq.se/the-cpq-blog/unlocking-the-power-of-tactons-product-configurator-for-cpq-efficiency)

#### Origins

Tacton was **founded in 1998 as a spinoff from SICS** (Swedish Institute for Computer Science, which merged into RISE in 2017). Headquartered in Stockholm, Sweden. The academic pedigree in constraint logic programming is the core technical differentiator.

Source: [Evolution of Product Configuration: SICS and RISE](https://www.cpq.se/the-cpq-blog/evolution-of-product-configuration-a-journey-through-sics-and-rise)

---

### A.2 Siemens Energy Case Study

**Product:** Gas turbines for power plants. Every turbine is heavily customized to the customer's specific power plant and site conditions. The air intake assembly alone has **120 variants**.

#### The Problem

- Full customer proposals averaged **500 pages**
- Took **8 weeks** to produce
- Nearly every sales case required specialist engineering help
- Endless configuration combinations created complexity and error risk

#### The Solution

Tacton CPQ was deployed to:

- Create **pre-made assemblies** standardizing core turbine components
- Simplify the overall **product architecture**
- Automate conflict detection and error resolution
- Guide sales reps through valid configurations

#### The Result

Sales reps now produce accurate, high-quality quotes with pricing **in minutes** instead of 8 weeks. Thousands of if-then business rules were replaced by **a few hundred declarative constraints**.

> *"The beauty of Tacton's configurator is that it will guide the sales rep through the sale and get the configuration of the product and the quotation correct each time. Where it previously took eight weeks to produce a customer quotation, sales reps can now produce accurate, high-quality quotes, with pricing, in a matter of minutes."*
> — Jan Nilsson, Senior Engineer, CRM Process & IT Development, Siemens Energy

The deployment dates to at least 2012.

Sources:
- [Siemens Energy Success Story](https://www.tacton.com/our-customers/siemensenergy/)
- [Siemens Reduces Quote Time Blog](https://www.tacton.com/cpq-blog/siemens-reduces-quote-time-from-8-weeks-to-minutes-using-cpq/)
- [2012 Press Release](https://www.tacton.com/about/press-releases/2012-01-18-siemens-energy-launches-the-sales-tool-tacton-configurator-world-wide/)

---

### A.3 Other Validated Case Studies

#### Husky Injection Molding Systems (Hot Runner Systems)

- **60-70 variables** per product configuration, thousands of guidelines behind each variable
- Previously used Excel spreadsheets and lookup charts — causing errors and rework
- **75% reduction** in solution time with Tacton
- Achieved **100% error-free quotes**
- Prepares **95%+ of engineering BOM** automatically
- Processes **tens of thousands of quotes per year**

> *"It's key to use 'best of breed solutions' that span across all businesses. Tacton is a key element in Husky's sales process."*
> — Steffen Bonecke, Director, Global Engineering

Source: [Husky Success Story](https://www.tacton.com/success-story/husky-reduces-solution-time-by-75/)

#### FLSmidth (Cement Plant Equipment)

- Documented in *"Knowledge-Based Configuration: From Research to Business Cases"* (2014)
- After a **3-day training**, FLSmidth engineers could model independently
- Integrated with SolidWorks 3D CAD, SmartPlant 3D, Mathcad, and legacy ERP
- Benefits: improved productivity, shorter lead times, standardization, higher quality, increased market share

Sources: [O'Reilly Book Chapter](https://www.oreilly.com/library/view/knowledge-based-configuration/9780124158177/xhtml/CHP017.xhtml) | [ResearchGate](https://www.researchgate.net/publication/292468691_Tacton_Use_of_Tacton_Configurator_at_FLSmidth)

#### Other Notable Tacton Customers

Piab (40K+ self-service configs/month), Xylem (global pump quoting), Atlas Copco (industrial tools eCommerce), Spectrum Industries (50% quote efficiency increase), Metso (20% quotation volume increase), Vantage Elevator Solutions, IMI (90% self-sufficiency).

---

### A.4 Constraint-Based vs Rules-Based Configuration

From Tacton's [August 2025 blog post](https://www.tacton.com/cpq-blog/constraint-based-vs-rules-based-configuration-the-advantage-for-complex-manufacturing/) by Kristina Parren:

**Core argument:** Rule-based systems use rigid "if-then" statements prescribing every allowable combination, while constraint-based systems define conditions that must be true regardless of input order.

**Example:** Instead of writing dozens of individual if-then rules for bolt/washer combinations, a constraint-based system defines one rule: *"The bolt diameter must match the washer diameter, and both must be suitable for corrosive environments if specified."*

| Aspect | Rules-Based | Constraint-Based |
|--------|------------|-----------------|
| Maintenance | High — hard-coded many-to-many relationships | Low — logic reused across SKUs |
| New product onboarding | Slow, error-prone | Fast, scalable |
| User input flexibility | Rigid forced paths | Any input order |
| Multi-market support | Difficult | Built-in with constraint layering |
| Portfolio coverage | Often limited to subsets | Full coverage with fewer constraints |
| AI readiness | Limited | More adaptable to guided selling |

**Diagnostic questions** the blog suggests asking:

- Are hundreds/thousands of rules written per product line?
- Does every product update require developer intervention?
- Do users report configuration rigidity?
- Can the system cover the full portfolio or only subsets?

---

### A.5 Implications for This Project

1. **TCstudio is a black box** — the modeling approach cannot be replicated or learned from directly. The underlying tech (SICStus Prolog / CSP) is well-understood academically, but Tacton's specific modeling UX and language are locked down.

2. **The constraint-based approach is well-validated** — Siemens Energy (thousands of rules → hundreds of constraints), Husky (75% time reduction, 100% accuracy), FLSmidth (3-day training to self-sufficiency) all demonstrate the pattern works at scale.

3. **The closest open equivalent** to build on: **[Google OR-Tools CP-SAT](https://developers.google.com/optimization/cp/cp_solver)** + a custom product modeling layer. There is no off-the-shelf open-source equivalent to TCstudio's modeling environment. See also `documents/cpsat-research.md`.

4. **Data/logic separation is central** to Tacton's architecture — product data is managed separately from constraint logic, so new products can be added without rewriting rules. This maps directly to this project's design principle: "products are facts, compatibility is derived."

5. **Key architectural difference**: Tacton uses constraint propagation (narrowing domains) + backtracking search, while this project uses exhaustive evaluation of all candidates against all rules. Both are valid — exhaustive evaluation is simpler, provides complete explainability traces, and is practical at the current catalog size (~3,000 hinge × plate pairs). CP-SAT would become relevant if the search space grows by orders of magnitude across 13+ product families.
