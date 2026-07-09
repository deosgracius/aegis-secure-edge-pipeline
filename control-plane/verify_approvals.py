"""
verify_approvals.py -- deterministic test of the investigation/approval backend.

Exercises save_investigation -> approval_queue -> decide_investigation (approve,
reject, and the SPOF guardrail) plus the REST endpoints, WITHOUT calling the LLM.

Run (venv):  python verify_approvals.py
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import store   # noqa: E402


def fake_proposal(action, target):
    return {"action": action, "target_device": target,
            "diagnosis": "test diagnosis", "reasoning": "test reasoning",
            "runbook": "rb-001-traffic-flood"}


def main():
    dbfile = os.path.join(HERE, "aegis.db")
    if os.path.exists(dbfile):
        os.remove(dbfile)
    store.setup()
    print("=" * 60)
    print("Investigation / approval-queue backend verification")
    print("=" * 60)

    # agent proposes two remediations (queue mode: no decision yet)
    inv_sn1 = store.save_investigation("sn1", fake_proposal("quarantine", "sn1"), ["step"])
    inv_pi = store.save_investigation("pi", fake_proposal("quarantine", "pi"), ["step"])
    inv_rej = store.save_investigation("sn2", fake_proposal("quarantine", "sn2"), ["step"])

    q = store.approval_queue()
    assert len(q) == 3, q
    print("[ok] 3 investigations queued for approval")

    # 1) approve a SAFE quarantine -> executes
    r = store.decide_investigation(inv_sn1, approved=True, by="alice")
    assert r["status"] == "executed", r
    assert store.list_devices()  # sanity
    dev = next(d for d in store.list_devices() if d["id"] == "sn1")
    assert dev["status"] == "quarantined", dev
    print("[ok] approve safe quarantine -> executed, sn1 quarantined")

    # 2) approve a SPOF quarantine -> guardrail BLOCKS it
    r = store.decide_investigation(inv_pi, approved=True, by="alice")
    assert r["status"] == "blocked", r
    dev = next(d for d in store.list_devices() if d["id"] == "pi")
    assert dev["status"] == "active", dev
    print("[ok] approve SPOF quarantine -> BLOCKED by guardrail, pi stays active")

    # 3) reject
    r = store.decide_investigation(inv_rej, approved=False, by="bob", note="false alarm")
    assert r["status"] == "rejected", r
    print("[ok] reject -> rejected, no action taken")

    # 4) deciding again on a settled one is refused
    try:
        store.decide_investigation(inv_sn1, approved=True, by="alice")
        print("[FAIL] double-decision allowed"); sys.exit(1)
    except ValueError:
        print("[ok] double-decision refused")

    # 5) queue is now empty; history has all three
    assert store.approval_queue() == []
    assert len(store.list_investigations()) == 3
    print("[ok] queue empty; 3 records in history")

    # --- REST layer (endpoints now require an operator bearer token) ---
    from fastapi.testclient import TestClient
    import main
    op = {"Authorization": "Bearer operator-demo-token"}
    with TestClient(main.app) as c:
        iid = store.save_investigation("sn1", fake_proposal("notify_operator", "sn1"), ["s"])
        assert len(c.get("/approvals", headers=op).json()) == 1
        resp = c.post("/investigations/%d/decision" % iid, headers=op,
                      json={"approved": True, "by": "carol", "note": "ok"})
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "approved", resp.json()
        assert len(c.get("/approvals", headers=op).json()) == 0
        print("[ok] REST: /approvals + POST decision working (authenticated)")

    print("-" * 60)
    print(">>> PASS: investigation audit trail + approval queue + guardrail all work.")


if __name__ == "__main__":
    main()
