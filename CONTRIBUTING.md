# Contributing to Window

## Prerequisites

- Python 3.13+
- pip

## Setup

```bash
git clone https://github.com/StephenDenisEdwards/window-project.git
cd window-project
pip install -r requirements.txt
```

## Quality Gates

All changes must pass these checks before committing:

```bash
# Tests — V1 engine (70+ tests)
python -m pytest engine_v1/tests/ -v

# Tests — V2 engine (experimental)
python -m pytest engine_v2/tests/ -v
```

## Code Style

- **Type hints:** Required on all public functions
- **Imports:** Use `from __future__ import annotations` in every module
- **Naming:** snake_case for functions/variables, PascalCase for classes
- **Models:** Pydantic v2 for all domain models
- **Enums:** Every constrained string field must be an enum — no raw strings

## Commit Messages

Use conventional prefix style:

| Prefix | Use For |
|--------|---------|
| `feat:` | New features or capabilities |
| `fix:` | Bug fixes |
| `docs:` | Documentation changes only |
| `refactor:` | Code restructuring without behaviour change |
| `chore:` | Build, tooling, dependency updates |
| `test:` | Adding or updating tests |

## Branching

- `master` is the main branch
- Create feature branches for non-trivial changes
- Keep commits focused — one logical change per commit

## Project Structure

```
engine_v1/                         # Production constraint engine
  models.py                     # Domain models (Pydantic v2)
  enums.py                      # Enumeration types
  rules.py                      # Constraint rules (single source of truth)
  solver.py                     # HingeConstraintEngine
  loader.py                     # JSON data adapter
  tests/                        # 70+ tests

engine_v2/                      # Experimental multi-family prototype
  core/                         # Generic solver framework
  families/                     # Product family implementations
  tests/                        # N-candidate + staged solver tests

documentation/docs/             # Full project documentation
demo/                           # Interactive Jupyter notebooks
sample-data/                    # Product catalog JSON
```

## Adding a New Product Family

1. Create `engine_v2/families/<family_name>/` with:
   - `models.py` — product types and requirements (Pydantic v2)
   - `rules.py` — constraint rules as functions
   - `config.py` — `NFamilyConfig` registration
   - `test_data.py` — test fixtures
2. Add tests in `engine_v2/tests/`
3. Add a demo notebook in `demo/`
4. Create a design doc in `documentation/docs/design/`

## Architecture Decisions

Significant design choices are recorded as ADRs in `documentation/docs/architecture/decisions/`. Before proposing a change that affects architecture, check existing ADRs and create a new one if needed.

## Documentation

- Update relevant docs when changing behaviour
- Design docs live in `documentation/docs/design/`
- Planning docs track feature work in `documentation/docs/planning/`
- See [Documentation Guide](documentation/docs/guides/documentation-guide.md) for naming conventions and templates
- Keep `CLAUDE.md` up to date when adding key files or changing conventions
