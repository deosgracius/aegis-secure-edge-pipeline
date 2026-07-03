"""
tools.py -- the tools the AI agent can call while investigating an incident.

Each tool wraps the control plane's service layer (store.py) or the knowledge
graph. The definitions follow the Anthropic tool-use schema; execute_tool()
dispatches a tool_use request from the model to the matching Python function.

Safety rule: there is NO tool that quarantines a device directly. The agent can
only PROPOSE a remediation; execution happens after the human approval gate in
agent.py. That guarantee lives in the tool surface itself, not in prompt text.
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "control-plane"))
sys.path.insert(0, os.path.join(HERE, "..", "knowledge-graph"))

import store          # noqa: E402  (control plane service layer)
import rag            # noqa: E402  (runbook retrieval)

TOOL_DEFINITIONS = [
    {
        "name": "get_incident_telemetry",
        "description": (
            "Get the recent telemetry readings for a device, newest first. "
            "Call this first when investigating an incident, to see the raw "
            "features (pkt_rate, pkt_size, seq_gap x100, iat_var x100) and "
            "which readings the FPGA flagged as suspicious."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "device_id": {"type": "string", "description": "e.g. 'sn1'"},
                "limit": {"type": "integer", "description": "max readings, default 10"},
            },
            "required": ["device_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "get_device_impact",
        "description": (
            "Ask the topology knowledge graph what breaks if a device is "
            "quarantined. Call this BEFORE proposing any quarantine — if "
            "safe_to_quarantine is false, you must not propose quarantine."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "device_id": {"type": "string"},
            },
            "required": ["device_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "search_runbooks",
        "description": (
            "Search the operations runbooks for guidance matching the symptoms "
            "you observe (e.g. 'high packet rate flood', 'sequence gap replay'). "
            "Ground your diagnosis and remediation in what the runbook says."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "symptom keywords"},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    },
    {
        "name": "list_devices",
        "description": "List all devices with their type, criticality, and current status.",
        "input_schema": {"type": "object", "properties": {},
                         "additionalProperties": False},
    },
]


def _get_incident_telemetry(device_id, limit=10):
    from db import SessionLocal, Telemetry
    with SessionLocal() as s:
        rows = (s.query(Telemetry)
                 .filter(Telemetry.device_id == device_id)
                 .order_by(Telemetry.id.desc())
                 .limit(limit))
        return [{"seq": t.seq,
                 "pkt_rate": t.f0, "pkt_size": t.f1,
                 "seq_gap_x100": t.f2, "iat_var_x100": t.f3,
                 "verdict": "suspicious" if t.verdict else "normal",
                 "score": t.score}
                for t in rows]


def execute_tool(name, tool_input):
    """Run one tool call from the model. Returns a JSON string result."""
    try:
        if name == "get_incident_telemetry":
            result = _get_incident_telemetry(
                tool_input["device_id"], tool_input.get("limit", 10))
        elif name == "get_device_impact":
            result = store.device_impact(tool_input["device_id"])
        elif name == "search_runbooks":
            hits = rag.retrieve(tool_input["query"], k=2)
            result = [{"id": h["id"], "title": h["title"], "text": h["text"]}
                      for h in hits]
        elif name == "list_devices":
            result = store.list_devices()
        else:
            return json.dumps({"error": "unknown tool: %s" % name}), True
        return json.dumps(result), False
    except Exception as exc:                       # tool errors go back to the model
        return json.dumps({"error": str(exc)}), True
