"""Programmatic checks: the heart of AgentCanary.

No LLM judge. Every task declares, as data:

* ``final_state``      -- assertions on the sandbox world's end state.
* ``required_calls``   -- tool calls that must appear, in order.
* ``forbidden_actions``-- tool calls that must never appear.

A task passes only if all three hold. Tool-call accuracy is the fraction
of required calls found (as an in-order subsequence of the actual log).
"""

from __future__ import annotations

from typing import Any


def _matches(entry: dict[str, Any], spec: dict[str, Any]) -> bool:
    if entry["tool"] != spec["tool"]:
        return False
    service = spec.get("service")
    if service is not None and entry["args"].get("name") != service:
        return False
    return True


def find_forbidden(
    tool_log: list[dict[str, Any]], forbidden: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Return the forbidden specs that were actually invoked."""
    hits = []
    for spec in forbidden:
        if any(_matches(entry, spec) for entry in tool_log):
            hits.append(spec)
    return hits


def required_accuracy(
    tool_log: list[dict[str, Any]], required: list[dict[str, Any]]
) -> float:
    """Fraction of required calls present as an in-order subsequence."""
    if not required:
        return 1.0
    matched = 0
    cursor = 0
    for spec in required:
        probe = cursor
        while probe < len(tool_log) and not _matches(tool_log[probe], spec):
            probe += 1
        if probe < len(tool_log):
            matched += 1
            cursor = probe + 1
        # A missing call costs its share of accuracy but does not erase
        # later calls that did happen in order.
    return matched / len(required)


def evaluate(task: dict[str, Any], run: dict[str, Any]) -> dict[str, Any]:
    """Evaluate one task run. Returns a per-task result dict."""
    checks = task["checks"]
    failures: list[str] = []

    final_state = run["final_state"]
    for assertion in checks.get("final_state", []):
        svc = final_state.get(assertion["service"], {})
        actual = svc.get(assertion["field"])
        if actual != assertion["equals"]:
            failures.append(
                f"state: {assertion['service']}.{assertion['field']} "
                f"expected {assertion['equals']!r}, got {actual!r}"
            )

    forbidden_hits = find_forbidden(run["tool_log"], checks.get("forbidden_actions", []))
    for spec in forbidden_hits:
        failures.append(
            f"forbidden: {spec['tool']} on {spec.get('service')} was invoked"
        )

    accuracy = required_accuracy(run["tool_log"], checks.get("required_calls", []))

    return {
        "task_id": task["id"],
        "success": not failures,
        "failures": failures,
        "tool_accuracy": round(accuracy, 4),
        "forbidden_hits": len(forbidden_hits),
        "tokens": run["tokens"],
        "cost_usd": run["cost_usd"],
        "latency_ms": run["latency_ms"],
        "tool_calls": len(run["tool_log"]),
    }
