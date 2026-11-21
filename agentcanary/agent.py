"""The bundled sample agent: a LangGraph graph with a scripted planner.

The agent performs multi-step ops tasks ("update these services to
version X") against the sandbox :class:`~agentcanary.world.World`.

There is no real LLM in the loop. The "brain" is a deterministic policy
driven by the agent *config* -- which is the whole point of AgentCanary:
a config change (skip verification, add a post-check, cheaper planning)
is a behavior change, and behavior changes are what we gate on.

Graph shape:

    perceive -> decide -> act -> act -> ... -> finish

* ``perceive``: list inventory, read basic info for goal services.
* ``decide``:   build the work queue from the goal.
* ``act``:      process one service per invocation, following the
                config's policy (verify first? post-verify?), looping
                until the queue is empty.
"""

from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from .world import TOOL_LATENCY_MS, TOOL_TOKENS, World

PRICE_PER_1K_TOKENS = 0.003  # USD, simulated


class AgentState(TypedDict, total=False):
    goal: dict[str, Any]
    queue: list[str]
    observed: dict[str, dict[str, Any]]
    tool_log: list[dict[str, Any]]
    notes: list[str]
    tokens: int
    latency_ms: int
    steps: int


class _Runner:
    """Executes one agent run; owns the world, config and metering."""

    def __init__(self, config: dict[str, Any], world: World):
        self.config = config
        self.world = world

    # -- metering helpers ----------------------------------------------

    def _call(self, state: AgentState, tool: str, **args: Any) -> Any:
        result = getattr(self.world, tool)(**args)
        state["tool_log"].append({"tool": tool, "args": args})
        state["tokens"] += TOOL_TOKENS[tool]
        state["latency_ms"] += TOOL_LATENCY_MS[tool]
        return result

    def _step(self, state: AgentState) -> None:
        state["steps"] += 1
        state["latency_ms"] += self.config["step_latency_ms"]

    # -- graph nodes -----------------------------------------------------

    def perceive(self, state: AgentState) -> AgentState:
        self._step(state)
        state["tokens"] += self.config["planning_tokens"]
        names = self._call(state, "list_inventory")
        observed: dict[str, dict[str, Any]] = {}
        for name in state["goal"]["services"]:
            if name in names:
                info = self._call(state, "get_item", name=name)
                if info is not None:
                    observed[name] = info
            else:
                state["notes"].append(f"{name}: not in inventory, skipped")
        state["observed"] = observed
        return state

    def decide(self, state: AgentState) -> AgentState:
        self._step(state)
        state["queue"] = list(state["goal"]["services"])
        return state

    def act(self, state: AgentState) -> AgentState:
        self._step(state)
        name = state["queue"].pop(0)
        goal = state["goal"]
        info = state["observed"].get(name)
        if info is None:
            return state  # missing service: nothing to do, no calls
        if info["version"] == goal["version"]:
            state["notes"].append(f"{name}: already at {goal['version']}")
            return state
        if self.config["verify_before_apply"]:
            verdict = self._call(state, "verify_item", name=name)
            if verdict is None or not verdict["safe_to_update"]:
                state["notes"].append(f"{name}: verification failed, skipped")
                return state
        self._call(state, "apply_update", name=name, version=goal["version"])
        if self.config["post_verify"]:
            self._call(state, "get_item", name=name)
        return state

    @staticmethod
    def _route(state: AgentState) -> str:
        return "act" if state["queue"] else "finish"

    def finish(self, state: AgentState) -> AgentState:
        self._step(state)
        return state

    # -- entry point -----------------------------------------------------

    def run(self, goal: dict[str, Any]) -> dict[str, Any]:
        graph = StateGraph(AgentState)
        graph.add_node("perceive", self.perceive)
        graph.add_node("decide", self.decide)
        graph.add_node("act", self.act)
        graph.add_node("finish", self.finish)
        graph.set_entry_point("perceive")
        graph.add_edge("perceive", "decide")
        graph.add_edge("decide", "act")
        graph.add_conditional_edges("act", self._route, {"act": "act", "finish": "finish"})
        graph.add_edge("finish", END)
        app = graph.compile()

        initial: AgentState = {
            "goal": goal,
            "queue": [],
            "observed": {},
            "tool_log": [],
            "notes": [],
            "tokens": 0,
            "latency_ms": 0,
            "steps": 0,
        }
        final = app.invoke(initial)
        return {
            "tool_log": final["tool_log"],
            "notes": final["notes"],
            "tokens": final["tokens"],
            "cost_usd": round(final["tokens"] * PRICE_PER_1K_TOKENS / 1000, 6),
            "latency_ms": final["latency_ms"],
            "final_state": self.world.final_state(),
        }


def run_agent(
    config: dict[str, Any], initial_services: dict[str, Any], goal: dict[str, Any]
) -> dict[str, Any]:
    """Run the sample agent once on a fresh world. Fully deterministic."""
    world = World(initial_services)
    return _Runner(config, world).run(goal)
