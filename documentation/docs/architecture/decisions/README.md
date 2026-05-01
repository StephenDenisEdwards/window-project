# Architecture Decision Records

We record significant architectural decisions using the [Nygard ADR format](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions).

## Template

```markdown
# ADR-XXX: Title

## Status
Proposed | Accepted | Deprecated | Superseded by ADR-YYY

## Context
What is the issue that we're seeing that is motivating this decision or change?

## Decision
What is the change that we're proposing and/or doing?

## Consequences
What becomes easier or more difficult to do because of this change?
```

## Index

| ADR | Title | Status |
|-----|-------|--------|
| [ADR-001](ADR-001-flat-n-candidate-solver.md) | Flat N-candidate solver as default production solver | Accepted |
| [ADR-002](ADR-002-llm-agent-family-generation.md) | LLM agent code generation for product family onboarding | Accepted |
| [ADR-003](ADR-003-conversational-via-microx-mcp.md) | Conversational layer via Micro-X MCP server with deterministic-first guardrail | Proposed |
