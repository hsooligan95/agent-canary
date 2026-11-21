"""Load configs + the golden suite, and run one agent version over it."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent import run_agent
from .checks import evaluate

_PKG = Path(__file__).parent


def load_config(name: str) -> dict[str, Any]:
    path = _PKG / "configs" / f"{name}.json"
    if not path.exists():
        raise SystemExit(f"unknown agent config: {name} (looked for {path})")
    return json.loads(path.read_text(encoding="utf-8"))


def load_thresholds() -> dict[str, Any]:
    return json.loads((_PKG / "configs" / "thresholds.json").read_text(encoding="utf-8"))


def load_suite() -> list[dict[str, Any]]:
    return json.loads((_PKG / "tasks" / "golden_suite.json").read_text(encoding="utf-8"))


def run_version(config_name: str, suite: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Run one config over the whole suite. Deterministic in stub mode."""
    config = load_config(config_name)
    tasks = suite if suite is not None else load_suite()
    results = []
    for task in tasks:
        run = run_agent(config, task["initial_state"], task["goal"])
        results.append(evaluate(task, run))
    total = len(results)
    passed = sum(1 for r in results if r["success"])
    return {
        "version": config_name,
        "tasks": results,
        "aggregate": {
            "tasks_total": total,
            "tasks_passed": passed,
            "success_rate": round(passed / total, 4) if total else 0.0,
            "avg_tool_accuracy": round(
                sum(r["tool_accuracy"] for r in results) / total, 4
            )
            if total
            else 0.0,
            "total_tokens": sum(r["tokens"] for r in results),
            "total_cost_usd": round(sum(r["cost_usd"] for r in results), 6),
            "avg_latency_ms": round(sum(r["latency_ms"] for r in results) / total, 1)
            if total
            else 0.0,
            "forbidden_hits": sum(r["forbidden_hits"] for r in results),
        },
    }
