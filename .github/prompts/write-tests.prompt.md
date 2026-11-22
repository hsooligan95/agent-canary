---
mode: agent
description: Write tests for a named module in agent-canary
---

Write tests for the module I name, following this repo's existing test
style, layout, and fixtures. Cover the behavior the module documents,
including these invariants where they apply:

- Scoring is programmatic only — final-state assertions, tool-call sequences, forbidden actions. No LLM judge, ever.
- Exit codes are the contract: 0 = promote / no drift, 2 = block; the CI workflow gates on them.
- The compare verdict JSON shape stays stable — AgentTrace ingests it (run ID resolution and generated_at included).

Then run the test suite:

    pytest
python -m agentcanary compare --base v1 --candidate v2-bad   # expect BLOCK, exit 2

Show the result. Do not claim done unless the suite is green; if a
test cannot pass, say why instead of weakening the assertion.
