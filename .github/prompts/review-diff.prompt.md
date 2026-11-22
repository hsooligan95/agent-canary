---
mode: agent
description: Review the current diff against agent-canary's invariants
---

Review my current diff against this repo's invariants:

- Scoring is programmatic only — final-state assertions, tool-call sequences, forbidden actions. No LLM judge, ever.
- Exit codes are the contract: 0 = promote / no drift, 2 = block; the CI workflow gates on them.
- The compare verdict JSON shape stays stable — AgentTrace ingests it (run ID resolution and generated_at included).
- Golden-suite results must stay byte-reproducible; the bundled configs are the demonstration story.

Flag every violation with file and line. Also flag any change that
alters a documented behavior contract (output shapes, exit codes,
event schemas, recorded artifacts) without updating the docs and
tests that describe it. No style nitpicks — correctness and contract
violations only.
