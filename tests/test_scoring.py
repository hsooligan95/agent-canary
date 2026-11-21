"""Tests for the diff + threshold decision logic."""

from agentcanary.runner import load_thresholds
from agentcanary.scoring import compare_runs, drift_check, pct_delta

THRESHOLDS = load_thresholds()


def make_run(version, per_task):
    """per_task: list of (task_id, success, accuracy, cost, latency, forbidden)."""
    tasks = [
        {
            "task_id": tid,
            "success": ok,
            "failures": [] if ok else ["boom"],
            "tool_accuracy": acc,
            "forbidden_hits": forb,
            "tokens": 0,
            "cost_usd": cost,
            "latency_ms": lat,
            "tool_calls": 0,
        }
        for tid, ok, acc, cost, lat, forb in per_task
    ]
    total = len(tasks)
    passed = sum(1 for t in tasks if t["success"])
    return {
        "version": version,
        "tasks": tasks,
        "aggregate": {
            "tasks_total": total,
            "tasks_passed": passed,
            "success_rate": passed / total,
            "avg_tool_accuracy": sum(t["tool_accuracy"] for t in tasks) / total,
            "total_tokens": 0,
            "total_cost_usd": round(sum(t["cost_usd"] for t in tasks), 6),
            "avg_latency_ms": sum(t["latency_ms"] for t in tasks) / total,
            "forbidden_hits": sum(t["forbidden_hits"] for t in tasks),
        },
    }


BASE = make_run("v1", [("t1", True, 1.0, 0.01, 500, 0), ("t2", True, 1.0, 0.01, 500, 0)])


def test_pct_delta():
    assert pct_delta(100, 110) == 10.0
    assert pct_delta(100, 90) == -10.0
    assert pct_delta(0, 0) == 0.0
    assert pct_delta(0, 5) == 100.0


def test_promote_when_better_and_cheap():
    cand = make_run("v2", [("t1", True, 1.0, 0.011, 520, 0), ("t2", True, 1.0, 0.011, 520, 0)])
    diff = compare_runs(BASE, cand, THRESHOLDS)
    assert diff["decision"] == "PROMOTE"
    assert diff["reasons"] == []


def test_block_on_success_drop():
    cand = make_run("v2", [("t1", True, 1.0, 0.01, 500, 0), ("t2", False, 0.5, 0.01, 500, 0)])
    diff = compare_runs(BASE, cand, THRESHOLDS)
    assert diff["decision"] == "BLOCK"
    assert any("success rate dropped" in r for r in diff["reasons"])
    assert diff["per_task"][1]["regressed"] is True


def test_block_on_forbidden_even_without_success_drop():
    # Candidate "passes" both tasks but committed a forbidden action.
    cand = make_run("v2", [("t1", True, 1.0, 0.01, 500, 1), ("t2", True, 1.0, 0.01, 500, 0)])
    diff = compare_runs(BASE, cand, THRESHOLDS)
    assert diff["decision"] == "BLOCK"
    assert any("forbidden" in r for r in diff["reasons"])


def test_block_on_cost_explosion():
    cand = make_run("v2", [("t1", True, 1.0, 0.02, 500, 0), ("t2", True, 1.0, 0.02, 500, 0)])
    diff = compare_runs(BASE, cand, THRESHOLDS)
    assert diff["decision"] == "BLOCK"
    assert any("cost rose" in r for r in diff["reasons"])


def test_block_on_latency_explosion():
    cand = make_run("v2", [("t1", True, 1.0, 0.01, 900, 0), ("t2", True, 1.0, 0.01, 900, 0)])
    diff = compare_runs(BASE, cand, THRESHOLDS)
    assert diff["decision"] == "BLOCK"
    assert any("latency rose" in r for r in diff["reasons"])


def test_small_success_drop_within_tolerance_promotes():
    tasks = [(f"t{i}", True, 1.0, 0.01, 500, 0) for i in range(20)]
    base = make_run("v1", tasks)
    cand_tasks = list(tasks)
    cand_tasks[0] = ("t0", False, 0.5, 0.01, 500, 0)  # 1/20 = 0.05 drop, at tolerance
    cand = make_run("v2", cand_tasks)
    diff = compare_runs(base, cand, THRESHOLDS)
    assert diff["decision"] == "PROMOTE"


def test_drift_detects_success_flip():
    current = make_run("v1", [("t1", True, 1.0, 0.01, 500, 0), ("t2", False, 0.5, 0.01, 500, 0)])
    drift = drift_check(BASE, current, THRESHOLDS)
    assert drift["drift_detected"] is True
    assert any("flipped" in f for f in drift["findings"])


def test_drift_clean_when_identical():
    drift = drift_check(BASE, BASE, THRESHOLDS)
    assert drift["drift_detected"] is False
    assert drift["findings"] == []
