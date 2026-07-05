"""
seed_dashboard.py -- populate the DB with a realistic demo state for the UI.

Deterministic (no LLM): seeds devices, opens a few incidents, and leaves two
investigations in the approval queue (one quarantine, one notify) so the
dashboard's approval panel has something to act on.

Run (venv):  python seed_dashboard.py    (then start: uvicorn main:app)
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import store   # noqa: E402


def main():
    dbfile = os.path.join(HERE, "aegis.db")
    if os.path.exists(dbfile):
        os.remove(dbfile)
    store.setup()

    # incidents from the two sensors
    store.ingest_telemetry("sn1", 11, [1150, 512, 100, 500], 1, 255)   # flood
    store.ingest_telemetry("sn2", 7, [300, 512, 4200, 500], 1, 255)    # replay
    store.ingest_telemetry("sn1", 12, [15000 // 100, 512, 100, 500], 0, 0)  # normal

    # two investigations awaiting a human decision
    store.save_investigation(
        "sn1",
        {"action": "quarantine", "target_device": "sn1",
         "diagnosis": "Sustained packet-rate flood from sensor-node-1.",
         "reasoning": "pkt_rate ~1150 vs ~300 baseline; runbook RB-001 says a "
                      "single flooding node with safe blast radius should be "
                      "quarantined. get_device_impact('sn1') = safe.",
         "runbook": "rb-001-traffic-flood"},
        ["calls get_incident_telemetry(sn1)",
         "calls search_runbooks(high packet rate flood)",
         "calls get_device_impact(sn1) -> safe_to_quarantine=true",
         "proposes: quarantine sn1"])

    store.save_investigation(
        "pi",
        {"action": "notify_operator", "target_device": "pi",
         "diagnosis": "Anomalies across multiple nodes point at the gateway.",
         "reasoning": "Gateway is a single point of failure (breaks fpga, "
                      "control-plane, dashboard). RB-005 forbids auto-quarantine; "
                      "escalate to a human instead.",
         "runbook": "rb-005-gateway-degradation"},
        ["calls get_device_impact(pi) -> safe_to_quarantine=false (SPOF)",
         "proposes: notify_operator pi"])

    print("Seeded:", store.counts())
    print("Approval queue:", len(store.approval_queue()), "items")


if __name__ == "__main__":
    main()
