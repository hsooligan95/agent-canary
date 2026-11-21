"""Render comparison and drift results as Markdown reports."""

from __future__ import annotations

from typing import Any


def _mark(ok: bool) -> str:
    return "PASS" if ok else "FAIL"


def render_compare(diff: dict[str, Any], thresholds: dict[str, Any]) -> str:
    ba, ca = diff["base_aggregate"], diff["cand_aggregate"]
    lines = [
        f"# AgentCanary comparison: {diff['base_version']} (base) vs "
        f"{diff['candidate_version']} (candidate)",
        "",
        f"## Verdict: {diff['decision']}",
        "",
    ]
    if diff["reasons"]:
        lines += ["Blocking reasons:"] + [f"- {r}" for r in diff["reasons"]] + [""]
    else:
        lines += ["All thresholds satisfied.", ""]

    lines += [
        "## Aggregate",
        "",
        "| Metric | Base | Candidate | Delta |",
        "|---|---|---|---|",
        f"| Success rate | {ba['success_rate']:.0%} ({ba['tasks_passed']}/{ba['tasks_total']}) "
        f"| {ca['success_rate']:.0%} ({ca['tasks_passed']}/{ca['tasks_total']}) "
        f"| {-diff['success_drop']:+.0%} |",
        f"| Avg tool-call accuracy | {ba['avg_tool_accuracy']:.2f} "
        f"| {ca['avg_tool_accuracy']:.2f} | {ca['avg_tool_accuracy'] - ba['avg_tool_accuracy']:+.2f} |",
        f"| Total cost | ${ba['total_cost_usd']:.4f} | ${ca['total_cost_usd']:.4f} "
        f"| {diff['cost_delta_pct']:+.1f}% |",
        f"| Avg latency / task | {ba['avg_latency_ms']:.0f} ms | {ca['avg_latency_ms']:.0f} ms "
        f"| {diff['latency_delta_pct']:+.1f}% |",
        f"| Forbidden actions | {ba['forbidden_hits']} | {ca['forbidden_hits']} | "
        f"{ca['forbidden_hits'] - ba['forbidden_hits']:+d} |",
        "",
        "Thresholds: "
        f"success drop <= {thresholds['max_success_drop']}, "
        f"cost <= +{thresholds['max_cost_increase_pct']}%, "
        f"latency <= +{thresholds['max_latency_increase_pct']}%, "
        f"block on forbidden = {thresholds['block_on_forbidden']}.",
        "",
        "## Per task",
        "",
        "| Task | Base | Cand | Accuracy (base -> cand) | Cost (base -> cand) | Latency (base -> cand) |",
        "|---|---|---|---|---|---|",
    ]
    for t in diff["per_task"]:
        lines.append(
            f"| {t['task_id']} | {_mark(t['base_success'])} | {_mark(t['cand_success'])} "
            f"| {t['base_accuracy']:.2f} -> {t['cand_accuracy']:.2f} "
            f"| ${t['base_cost_usd']:.4f} -> ${t['cand_cost_usd']:.4f} ({t['cost_delta_pct']:+.0f}%) "
            f"| {t['base_latency_ms']} ms -> {t['cand_latency_ms']} ms ({t['latency_delta_pct']:+.0f}%) |"
        )

    failed = [t for t in diff["per_task"] if t["cand_failures"]]
    if failed:
        lines += ["", "## Candidate failures", ""]
        for t in failed:
            lines.append(f"### {t['task_id']}")
            lines += [f"- {f}" for f in t["cand_failures"]]
            lines.append("")
    return "\n".join(lines) + "\n"


def render_drift(drift: dict[str, Any]) -> str:
    lines = [
        f"# AgentCanary drift check: {drift['version']} vs stored baseline",
        "",
        f"## Verdict: {'DRIFT DETECTED' if drift['drift_detected'] else 'NO DRIFT'}",
        "",
    ]
    if drift["findings"]:
        lines += [f"- {f}" for f in drift["findings"]]
    else:
        lines.append(
            "The pinned version behaves identically to its baseline: same "
            "per-task success, and cost/latency within tolerance on every task."
        )
    return "\n".join(lines) + "\n"
