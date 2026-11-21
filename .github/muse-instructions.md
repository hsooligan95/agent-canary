# Copilot instructions — agent-canary

You are working in **AgentCanary**, CI for agent behavior: it shadow-runs a
candidate agent version against the current one over a golden suite of
multi-step tasks, scores behavior programmatically, and blocks promotion
when the candidate regresses.

## Stack

- Python 3; package `agentcanary/` with CLI entry `agentcanary.cli:main`.
- The bundled sample agent is a small LangGraph agent
  (perceive -> decide -> act* -> finish) running against a deterministic
  stub — no API keys, no network, every number reproducible.

## Tests

```bash
pytest            # scoring/checks unit tests
python -m agentcanary compare --base v1 --candidate v2-bad    # -> BLOCK, exit 2
python -m agentcanary compare --base v1 --candidate v2-good   # -> PROMOTE, exit 0
```

## Architecture notes

- Scoring is programmatic only — final-state assertions, expected
  tool-call sequences, forbidden actions. No LLM judge, ever.
- Exit codes are the contract: 0 = promote / no drift, 2 = block. The CI
  workflow (`.github/workflows/agent-canary.yml`) gates on them; never
  change exit-code semantics without updating the workflow and README.
- `compare` resolves a run ID (`--run-id` > `AGENTCANARY_RUN_ID` env >
  freshly minted), stamps `generated_at`, and writes a JSON verdict.
  AgentTrace ingests that verdict — keep its shape stable.
- Configs under `agentcanary/configs/` (v1, v2-good, v2-bad) are the
  demonstration story; golden-suite results must stay byte-reproducible.

## Shared rules

- Use Unix LF line endings in every file; never CRLF.
- Never commit secrets, tokens, or credentials — real or synthetic-looking.
- Tests must pass before you describe a change as complete; run the test
  command above and report honestly if you cannot.
- Prefer the smallest complete implementation: reuse what already exists in
  this repo before adding new code, files, or dependencies.
