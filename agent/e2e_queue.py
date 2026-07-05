"""
e2e_queue.py -- prove the dashboard flow end to end:
agent investigates -> proposes -> lands in the approval queue -> a human
approves via the control-plane API -> it executes.

Run (venv, network on):  python e2e_queue.py
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "control-plane"))
sys.path.insert(0, HERE)

import store   # noqa: E402
import agent   # noqa: E402


def main():
    dbfile = os.path.join(HERE, "..", "control-plane", "aegis.db")
    if os.path.exists(dbfile):
        os.remove(dbfile)
    store.setup()

    # a flood on sn1 arrives and opens an incident
    for i in range(3):
        store.ingest_telemetry("sn1", i, [1150, 512, 100, 500], 1, 255)
    incident_id = store.list_incidents()[0]["id"]
    print("incident #%d opened on sn1" % incident_id)

    # agent investigates in QUEUE mode: proposes, does NOT decide
    final = agent.investigate("sn1", "FPGA flagged suspicious telemetry (score 255)",
                              approver=agent.QUEUE, incident_id=incident_id)
    print("agent proposed:", final["proposal"]["action"], "->",
          final["proposal"]["target_device"])

    queue = store.approval_queue()
    print("approval queue now has %d item(s), status=%s"
          % (len(queue), queue[0]["status"]))
    inv_id = queue[0]["id"]

    # a human approves via the API path
    result = store.decide_investigation(inv_id, approved=True, by="operator-deo")
    print("after human approval -> status=%s, result=%s"
          % (result["status"], result["result"]))

    dev = next(d for d in store.list_devices() if d["id"] == "sn1")
    print("sn1 device status:", dev["status"])
    assert result["status"] == "executed" and dev["status"] == "quarantined"
    print("\n>>> PASS: agent -> queue -> human approval -> execution works end to end.")


if __name__ == "__main__":
    main()
