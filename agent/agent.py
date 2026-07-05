"""
agent.py -- the AEGIS incident-investigation agent (LangGraph + Anthropic SDK).

Flow (a LangGraph state machine):

    call_model  --tool_use-->  run_tools  --> call_model   (the ReAct loop)
        |
        | (model calls propose_remediation)
        v
    approval  --approved+actionable-->  execute  --> END
        |
        +--rejected/no-op--> END

Design choices worth explaining in an interview:
- The model reaches the world only through tools (tools.py). There is NO tool
  that quarantines a device, so the model *cannot* act on its own — it can only
  emit a `propose_remediation` "tool call" that the harness intercepts.
- The human approval gate is a real graph node, not a prompt instruction.
- A hard guardrail in `execute` re-checks the knowledge graph and refuses to
  quarantine a single-point-of-failure even if a human approved it by mistake.

Model: defaults to claude-opus-4-8 (override with AEGIS_AGENT_MODEL). Uses the
Anthropic Messages API tool-use loop directly.
"""

import json
import os
import sys
from typing import Optional, TypedDict

import anthropic
from langgraph.graph import END, START, StateGraph

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import tools as agent_tools   # noqa: E402

MODEL = os.environ.get("AEGIS_AGENT_MODEL", "claude-opus-4-8")
MAX_STEPS = 8


# ---------------------------------------------------------------------------
# Load ANTHROPIC_API_KEY from the project's .env.txt if not already set.
# ---------------------------------------------------------------------------
def _load_api_key():
    if os.environ.get("ANTHROPIC_API_KEY"):
        return
    env_path = os.path.join(HERE, "..", "..", ".env.txt")
    if os.path.exists(env_path):
        with open(env_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line.startswith("ANTHROPIC_API_KEY="):
                    val = line.split("=", 1)[1].strip().strip('"').strip("'")
                    os.environ["ANTHROPIC_API_KEY"] = val
                    return


# The proposal is emitted as a special "tool call" the harness intercepts
# (never executed like the investigative tools) — this is how the model hands a
# structured recommendation to the approval gate.
PROPOSE_TOOL = {
    "name": "propose_remediation",
    "description": (
        "Call this exactly once, at the end, to submit your recommendation to "
        "the human approval gate. You may only propose 'quarantine' if you "
        "have called get_device_impact for that device AND safe_to_quarantine "
        "was true."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "action": {"type": "string",
                       "enum": ["quarantine", "notify_operator", "no_action"]},
            "target_device": {"type": "string"},
            "diagnosis": {"type": "string",
                          "description": "one-line root-cause conclusion"},
            "reasoning": {"type": "string",
                          "description": "why, citing telemetry + runbook"},
            "runbook": {"type": "string", "description": "runbook id used, e.g. rb-001-traffic-flood"},
        },
        "required": ["action", "target_device", "diagnosis", "reasoning"],
        "additionalProperties": False,
    },
}

ALL_TOOLS = agent_tools.TOOL_DEFINITIONS + [PROPOSE_TOOL]

SYSTEM_PROMPT = """You are the AEGIS security agent. An anomaly was flagged on a device by the FPGA scorer, and you must investigate and recommend a response.

Your investigation loop:
1. get_incident_telemetry for the affected device to see the raw features and which readings were flagged. Feature units: pkt_rate (packets/sec, baseline ~300), pkt_size (bytes, baseline ~512), seq_gap_x100 (sequence jump x100, baseline ~100), iat_var_x100 (timing variance x100, baseline ~500).
2. search_runbooks with the symptoms you see, and follow the matching runbook.
3. get_device_impact for any device you might quarantine, BEFORE proposing it.
4. Finish by calling propose_remediation exactly once.

Hard rules:
- You can only PROPOSE. You cannot quarantine anything yourself.
- Never propose 'quarantine' unless get_device_impact returned safe_to_quarantine=true for that device. If it is not safe, propose 'notify_operator' instead.
- If many devices are affected at once, suspect infrastructure (see the gateway runbook) and propose 'notify_operator', not quarantining sensors.
Be concise and evidence-based."""


# ---------------------------------------------------------------------------
# Graph state
# ---------------------------------------------------------------------------
class AgentState(TypedDict, total=False):
    device_id: str
    incident_summary: str
    messages: list
    proposal: Optional[dict]
    decision: Optional[dict]
    result: Optional[dict]
    steps: list          # human-readable transcript of the investigation
    n_calls: int


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------
def _client():
    _load_api_key()
    return anthropic.Anthropic()


def call_model(state: AgentState) -> AgentState:
    client = _client()
    if not state.get("messages"):
        state["messages"] = [{
            "role": "user",
            "content": ("Investigate this incident and recommend a response.\n"
                        "Device: %s\nAlert: %s"
                        % (state["device_id"], state["incident_summary"])),
        }]
        state["steps"] = []
        state["n_calls"] = 0

    resp = client.messages.create(
        model=MODEL, max_tokens=1500,
        system=SYSTEM_PROMPT, tools=ALL_TOOLS,
        messages=state["messages"],
    )
    state["n_calls"] = state.get("n_calls", 0) + 1
    state["messages"].append({"role": "assistant", "content":
                              [b.model_dump() for b in resp.content]})

    for block in resp.content:
        if block.type == "text" and block.text.strip():
            state["steps"].append("think: " + block.text.strip())
        elif block.type == "tool_use" and block.name == "propose_remediation":
            state["proposal"] = block.input
            state["steps"].append("proposes: %s %s" %
                                  (block.input["action"], block.input["target_device"]))
    return state


def route_after_model(state: AgentState) -> str:
    if state.get("proposal"):
        return "approval"
    last = state["messages"][-1]["content"]
    has_tool = any(b.get("type") == "tool_use" for b in last)
    if has_tool and state.get("n_calls", 0) < MAX_STEPS:
        return "run_tools"
    return END


def run_tools(state: AgentState) -> AgentState:
    last = state["messages"][-1]["content"]
    results = []
    for block in last:
        if block.get("type") != "tool_use" or block["name"] == "propose_remediation":
            continue
        out, is_err = agent_tools.execute_tool(block["name"], block["input"])
        state["steps"].append("calls %s(%s)" %
                              (block["name"], json.dumps(block["input"])))
        results.append({"type": "tool_result", "tool_use_id": block["id"],
                        "content": out, "is_error": is_err})
    state["messages"].append({"role": "user", "content": results})
    return state


QUEUE = "__queue__"   # sentinel: propose and stop, leaving it for a human
_APPROVER = None      # set by investigate(); the approval node reads it


def approval(state: AgentState) -> AgentState:
    if _APPROVER == QUEUE:
        # dashboard flow: don't decide here — leave it in the approval queue
        state["decision"] = None
        state["steps"].append("queued for human approval")
        return state
    approver = _APPROVER or auto_approver
    decision = approver(state["proposal"])
    state["decision"] = decision
    state["steps"].append("human %s: %s" %
                          ("APPROVED" if decision["approved"] else "REJECTED",
                           decision.get("note", "")))
    return state


def route_after_approval(state: AgentState) -> str:
    decision = state.get("decision")
    if decision and decision["approved"] and state["proposal"]["action"] == "quarantine":
        return "execute"
    return END


def execute(state: AgentState) -> AgentState:
    prop = state["proposal"]
    target = prop["target_device"]
    # Hard guardrail: re-verify the blast radius even after human approval.
    impact = agent_tools.store.device_impact(target)
    if not impact["safe_to_quarantine"]:
        state["result"] = {"action": "blocked",
                           "reason": "guardrail: %s is a single point of failure "
                                     "(%s)" % (target, impact["breaks_if_quarantined"])}
        state["steps"].append("GUARDRAIL BLOCKED quarantine of " + target)
        return state
    dev = agent_tools.store.set_device_status(target, "quarantined")
    state["result"] = {"action": "quarantined", "device": dev["name"],
                       "status": dev["status"]}
    state["steps"].append("EXECUTED: quarantined " + dev["name"])
    return state


# ---------------------------------------------------------------------------
# Approvers
# ---------------------------------------------------------------------------
def auto_approver(proposal):
    """Non-interactive policy for evals/CI: approve safe actions automatically."""
    if proposal["action"] in ("notify_operator", "no_action"):
        return {"approved": True, "by": "auto-policy", "note": "non-destructive"}
    impact = agent_tools.store.device_impact(proposal["target_device"])
    ok = impact["safe_to_quarantine"]
    return {"approved": ok, "by": "auto-policy",
            "note": "safe to quarantine" if ok else "SPOF — denied"}


def cli_approver(proposal):
    """Interactive gate: prints the proposal and asks a human y/n."""
    print("\n--- APPROVAL REQUIRED ---")
    print("  action:    ", proposal["action"], "->", proposal["target_device"])
    print("  diagnosis: ", proposal["diagnosis"])
    print("  reasoning: ", proposal["reasoning"])
    ans = input("  approve? [y/N] ").strip().lower()
    return {"approved": ans == "y", "by": "cli-human",
            "note": "operator decision"}


# ---------------------------------------------------------------------------
# Build + run
# ---------------------------------------------------------------------------
def build_graph():
    g = StateGraph(AgentState)
    g.add_node("call_model", call_model)
    g.add_node("run_tools", run_tools)
    g.add_node("approval", approval)
    g.add_node("execute", execute)
    g.add_edge(START, "call_model")
    g.add_conditional_edges("call_model", route_after_model,
                            {"run_tools": "run_tools", "approval": "approval", END: END})
    g.add_edge("run_tools", "call_model")
    g.add_conditional_edges("approval", route_after_approval,
                            {"execute": "execute", END: END})
    g.add_edge("execute", END)
    return g.compile()


def investigate(device_id, incident_summary, approver=None,
                incident_id=None, persist=True):
    """Run the full investigation for one incident. Returns the final state.

    If persist=True, writes an audit Investigation record to the control plane
    (proposal + decision + result + transcript). Pass approver=agent.QUEUE to
    propose and leave the decision to a human via the dashboard/API.
    """
    global _APPROVER
    _APPROVER = approver
    graph = build_graph()
    state: AgentState = {"device_id": device_id,
                         "incident_summary": incident_summary}
    final = graph.invoke(state, {"recursion_limit": 50})

    if persist and final.get("proposal"):
        final["investigation_id"] = agent_tools.store.save_investigation(
            device_id=device_id,
            proposal=final["proposal"],
            transcript=final.get("steps", []),
            incident_id=incident_id,
            decision=final.get("decision"),
            result=final.get("result"),
        )
    return final


if __name__ == "__main__":
    # Ensure the DB has data to investigate, then run one incident interactively.
    sys.path.insert(0, os.path.join(HERE, "..", "control-plane"))
    import demo as cp_demo   # noqa: E402
    cp_demo.main()

    final = investigate("sn1", "FPGA flagged suspicious telemetry (score 255)",
                        approver=cli_approver)
    print("\n=== investigation transcript ===")
    for i, step in enumerate(final["steps"], 1):
        print("%2d. %s" % (i, step))
    print("\nproposal:", json.dumps(final.get("proposal"), indent=2))
    print("decision:", final.get("decision"))
    print("result:  ", final.get("result"))
