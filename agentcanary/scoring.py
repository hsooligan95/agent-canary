"""Diff two version runs and decide PROMOTE / BLOCK against thresholds.

The decision is deliberately boring arithmetic -- no vibes:

* success rate may not drop by more than ``max_success_drop``;
* any forbidden action in the candidate blocks, if ``block_on_forbidden``;
* total cost may not rise by more than ``max_cost_increase_pct``;
* average latency may not rise by more than ``max_latency_increase_pct``.
"""

from __future__ import annotations

from typing import Any


def pct_delta(base: float, candidate: float) -> float:
    """Percentage change from base to candidate (0.0 if base is 0)."""
    if base == 0:
        return 0.0 if candidate == 0 else 100.0
    return round((candidate - base) / base * 100, 2)


def compare_runs(
    base: dict[str, Any], candidate: dict[str, Any], thresholds: dict[str, Any]
) -> dict[str, Any]:
    """Compare two run_version() results. Returns the full diff + verdict."""
    base_tasks = {t["task_id"]: t for t in base["tasks"]}
    cand_tasks = {t["task_id"]: t for t in candidate["tasks"]}

    per_task = []
    for task_id in base_tasks:
        b, c = base_tasks[task_id], cand_tasks[task_id]
        per_task.append(
            {
                "task_id": task_id,
                "base_success": b["success"],
                "cand_success": c["success"],
                "regressed": b["success"] and not c["success"],
                "base_accuracy": b["tool_accuracy"],
                "cand_accuracy": c["tool_accuracy"],
                "base_cost_usd": b["cost_usd"],
                "cand_cost_usd": c["cost_usd"],
                "cost_delta_pct": pct_delta(b["cost_usd"], c["cost_usd"]),
                "base_latency_ms": b["latency_ms"],
                "cand_latency_ms": c["latency_ms"],
                "latency_delta_pct": pct_delta(b["latency_ms"], c["latency_ms"]),
                "cand_failures": c["failures"],
            }
        )

    ba, ca = base["aggregate"], candidate["aggregate"]
    success_drop = round(ba["success_rate"] - ca["success_rate"], 4)
    cost_delta = pct_delta(ba["total_cost_usd"], ca["total_cost_usd"])
    latency_delta = pct_delta(ba["avg_latency_ms"], ca["avg_latency_ms"])

    reasons: list[str] = []
    if success_drop > thresholds["max_success_drop"]:
        reasons.append(
            f"success rate dropped {ba['success_rate']:.0%} -> {ca['success_rate']:.0%} "
            f"(drop {success_drop:.2f} > allowed {thresholds['max_success_drop']})"
        )
    if thresholds.get("block_on_forbidden") and ca["forbidden_hits"] > 0:
        reasons.append(
            f"candidate committed {ca['forbidden_hits']} forbidden action(s)"
        )
    if cost_delta > thresholds["max_cost_increase_pct"]:
        reasons.append(
            f"cost rose {cost_delta:+.1f}% (allowed +{thresholds['max_cost_increase_pct']}%)"
        )
    if latency_delta > thresholds["max_latency_increase_pct"]:
        reasons.append(
            f"avg latency rose {latency_delta:+.1f}% "
            f"(allowed +{thresholds['max_latency_increase_pct']}%)"
        )

    return {
        "base_version": base["version"],
        "candidate_version": candidate["version"],
        "per_task": per_task,
        "base_aggregate": ba,
        "cand_aggregate": ca,
        "success_drop": success_drop,
        "cost_delta_pct": cost_delta,
        "latency_delta_pct": latency_delta,
        "decision": "BLOCK" if reasons else "PROMOTE",
        "reasons": reasons,
    }


def drift_check(
    baseline: dict[str, Any], current: dict[str, Any], thresholds: dict[str, Any]
) -> dict[str, Any]:
    """Compare a fresh run of the pinned version against its stored baseline.

    Drift = the same code + same config behaving differently, i.e. the
    model (or a dependency) moved underneath you. Any success flip is
    drift; metric movement beyond ``drift_max_metric_delta_pct`` is too.
    """
    base_tasks = {t["task_id"]: t for t in baseline["tasks"]}
    findings: list[str] = []
    for task in current["tasks"]:
        b = base_tasks.get(task["task_id"])
        if b is None:
            findings.append(f"{task['task_id']}: not in baseline")
            continue
        if b["success"] != task["success"]:
            findings.append(
                f"{task['task_id']}: success flipped {b['success']} -> {task['success']}"
            )
        for key in ("cost_usd", "latency_ms"):
            delta = pct_delta(b[key], task[key])
            if abs(delta) > thresholds["drift_max_metric_delta_pct"]:
                findings.append(
                    f"{task['task_id']}: {key} moved {delta:+.1f}% vs baseline"
                )
    return {
        "version": current["version"],
        "drift_detected": bool(findings),
        "findings": findings,
    }
