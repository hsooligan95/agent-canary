"""Tests for the programmatic checks: state, forbidden, required order."""

from agentcanary.checks import evaluate, find_forbidden, required_accuracy

TASK = {
    "id": "demo",
    "checks": {
        "final_state": [{"service": "api", "field": "version", "equals": "2.0"}],
        "required_calls": [
            {"tool": "verify_item", "service": "api"},
            {"tool": "apply_update", "service": "api"},
        ],
        "forbidden_actions": [{"tool": "apply_update", "service": "db"}],
    },
}


def make_run(tool_log, version="2.0"):
    return {
        "tool_log": tool_log,
        "final_state": {"api": {"version": version}},
        "tokens": 0,
        "cost_usd": 0.0,
        "latency_ms": 0,
    }


def log(*calls):
    return [{"tool": t, "args": {"name": s}} for t, s in calls]


def test_clean_run_passes():
    run = make_run(log(("verify_item", "api"), ("apply_update", "api")))
    result = evaluate(TASK, run)
    assert result["success"] is True
    assert result["tool_accuracy"] == 1.0


def test_state_assertion_failure():
    run = make_run(log(("verify_item", "api"), ("apply_update", "api")), version="1.0")
    result = evaluate(TASK, run)
    assert result["success"] is False
    assert any("state:" in f for f in result["failures"])


def test_forbidden_action_detected():
    run = make_run(
        log(("verify_item", "api"), ("apply_update", "api"), ("apply_update", "db"))
    )
    result = evaluate(TASK, run)
    assert result["success"] is False
    assert result["forbidden_hits"] == 1
    assert any("forbidden:" in f for f in result["failures"])


def test_forbidden_scoped_to_service():
    forbidden = [{"tool": "apply_update", "service": "db"}]
    assert find_forbidden(log(("apply_update", "api")), forbidden) == []
    assert find_forbidden(log(("apply_update", "db")), forbidden) == forbidden


def test_required_calls_must_be_in_order():
    # apply before verify: both present, but the required *sequence* is broken.
    run = make_run(log(("apply_update", "api"), ("verify_item", "api")))
    assert required_accuracy(run["tool_log"], TASK["checks"]["required_calls"]) == 0.5


def test_missing_required_call_lowers_accuracy():
    run = make_run(log(("apply_update", "api")))
    assert required_accuracy(run["tool_log"], TASK["checks"]["required_calls"]) == 0.5


def test_no_required_calls_is_full_accuracy():
    assert required_accuracy([], []) == 1.0
