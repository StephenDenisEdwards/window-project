# Guide: Documentation

Where each type of document goes, naming conventions, templates, and how to keep the docs consistent.

## Directory Structure

```
/
├── CLAUDE.md                    AI assistant context (update when adding key files/conventions)
├── CONTRIBUTING.md              Contributor guide
├── CHANGELOG.md                 Curated feature history
├── README.md                    Project overview
│
├── documentation/docs/
│   ├── index.md                 Central navigation hub — UPDATE when adding new docs
│   │
│   ├── architecture/
│   │   ├── multi-family-architecture.md    Multi-family solver evaluation
│   │   ├── solver-architecture-diagrams.md Mermaid flowcharts
│   │   └── decisions/
│   │       ├── README.md        ADR index table — UPDATE when adding new ADRs
│   │       └── ADR-NNN-*.md     Architecture Decision Records
│   │
│   ├── design/
│   │   └── DESIGN-*.md          Core system design documents
│   │
│   ├── planning/
│   │   ├── INDEX.md             Priority queue and status — UPDATE when plans change
│   │   └── PLAN-*.md            Feature/phase plans
│   │
│   ├── research/
│   │   ├── README.md            Research index
│   │   └── *.md                 Studies, evaluations, analysis
│   │
│   ├── operations/              User-facing: how to run, configure, troubleshoot
│   └── guides/                  Developer-facing: how to extend, contribute
```

## Document Types and Templates

### Architecture Decision Records (ADRs)

**Location:** `architecture/decisions/ADR-NNN-<slug>.md`
**Naming:** Sequential number, kebab-case slug: `ADR-001-flat-n-candidate-solver.md`
**When:** Any significant architectural choice — technology selection, pattern adoption, structural change.

```markdown
# ADR-NNN: Title

## Status
Proposed | Accepted | Deprecated | Superseded by ADR-YYY

## Context
What is the issue that we're seeing that is motivating this decision or change?

## Decision
What is the change that we're proposing and/or doing?

## Consequences
What becomes easier or more difficult to do because of this change?
```

**After creating:** Add a row to the index table in `architecture/decisions/README.md`.

### Design Documents

**Location:** `design/DESIGN-<name>.md`
**Naming:** `DESIGN-` prefix, kebab-case: `DESIGN-constraint-engine.md`
**When:** Documenting how a major system component works — its structure, rules, data model, and design rationale.

### Planning Documents

**Location:** `planning/PLAN-<name>.md`
**Naming:** `PLAN-` prefix, kebab-case: `PLAN-production-roadmap.md`
**When:** Phased work plans with scope, deliverables, and status tracking.

**After creating:** Add a row to `planning/INDEX.md`.

### Research Documents

**Location:** `research/<name>.md`
**When:** Studying external technologies, approaches, or market context to inform project decisions.

### Operations Documents

**Location:** `operations/<name>.md`
**When:** User-facing how-to content — setup, configuration, running the engine.

### Developer Guides

**Location:** `guides/<name>.md`
**When:** Developer-facing how-to content — extending the engine, adding families, writing rules.

## Naming Conventions

| Type | Pattern | Example |
|------|---------|---------|
| ADR | `ADR-NNN-kebab-slug.md` | `ADR-001-flat-n-candidate-solver.md` |
| Design | `DESIGN-kebab-name.md` | `DESIGN-constraint-engine.md` |
| Plan | `PLAN-kebab-name.md` | `PLAN-production-roadmap.md` |
| Research | `kebab-name.md` | `cpsat-research.md` |
| Operations | `kebab-name.md` | `getting-started.md` |
| Guides | `kebab-name.md` | `adding-a-product-family.md` |

## Cross-Referencing

Use relative markdown links between documents:

```markdown
- From design to ADR: [ADR-001](../architecture/decisions/ADR-001-flat-n-candidate-solver.md)
- From plan to design: [Constraint Engine Design](../design/DESIGN-constraint-engine.md)
```

Include a "Related" section at the bottom of documents linking to relevant ADRs, design docs, and plans.

## Updating Indexes

When you add a new document, update these files:

| New Doc Type | Update These |
|-------------|-------------|
| ADR | `architecture/decisions/README.md` (index table) |
| Plan | `planning/INDEX.md` (priority queue) |
| Any | `index.md` (if it belongs in the navigation hub) |
| Key file/convention | `CLAUDE.md` (if it changes how AI assistants should work with the project) |

## Formatting Standards

- **Headings:** Use `##` for main sections, `###` for subsections. Only one `#` per file (the title).
- **Tables:** Use for structured data (parameters, comparisons, indexes).
- **Code blocks:** Use fenced blocks with language tags (```python, ```bash).
- **Links:** Relative paths to other docs. Full URLs for external references.
- **Mermaid diagrams:** Use where they add clarity (architecture, flows, relationships).

## Checklist for New Documents

- [ ] File is in the correct directory
- [ ] Filename follows the naming convention
- [ ] Title matches the filename intent
- [ ] "Related" section links to relevant ADRs, design docs, plans
- [ ] Relevant indexes are updated (ADR README, planning INDEX, index.md)
- [ ] CLAUDE.md updated if the doc introduces new key files or conventions
