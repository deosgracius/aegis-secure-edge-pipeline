"""
verify_auth.py -- deterministic test of auth + RBAC + audit logging.

No network, no LLM. Uses FastAPI TestClient.  Run (venv):  python verify_auth.py
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import store   # noqa: E402

VIEWER = {"Authorization": "Bearer viewer-demo-token"}
OPERATOR = {"Authorization": "Bearer operator-demo-token"}
ADMIN = {"Authorization": "Bearer admin-demo-token"}


def prop(action, target):
    return {"action": action, "target_device": target,
            "diagnosis": "d", "reasoning": "r", "runbook": "rb-001-traffic-flood"}


def main():
    dbfile = os.path.join(HERE, "aegis.db")
    if os.path.exists(dbfile):
        os.remove(dbfile)

    from fastapi.testclient import TestClient
    import main
    print("=" * 60)
    print("Auth + RBAC + audit verification")
    print("=" * 60)

    with TestClient(main.app) as c:
        # queue two investigations to act on
        inv_sn1 = store.save_investigation("sn1", prop("quarantine", "sn1"), ["s"])
        inv_pi = store.save_investigation("pi", prop("quarantine", "pi"), ["s"])

        # --- authentication ---
        assert c.get("/health").status_code == 200            # open
        assert c.get("/devices").status_code == 401            # no token
        assert c.get("/devices", headers={"Authorization": "Bearer nope"}).status_code == 401
        print("[ok] no/invalid token -> 401; /health open")

        # --- viewer: read yes, act no ---
        assert c.get("/devices", headers=VIEWER).status_code == 200
        r = c.post("/investigations/%d/decision" % inv_sn1,
                   headers=VIEWER, json={"approved": True, "by": "x"})
        assert r.status_code == 403, r.status_code
        assert c.get("/audit", headers=VIEWER).status_code == 403
        print("[ok] viewer can read; blocked (403) from deciding and from /audit")

        # --- operator: can approve a safe quarantine ---
        r = c.post("/investigations/%d/decision" % inv_sn1,
                   headers=OPERATOR, json={"approved": True, "by": "ignored"})
        assert r.status_code == 200 and r.json()["status"] == "executed", r.text
        # actor is the authenticated user, not the client-supplied "by"
        assert c.get("/audit", headers=OPERATOR).status_code == 403  # operator != admin
        print("[ok] operator approved safe quarantine -> executed; still no /audit")

        # --- guardrail still applies through the API ---
        r = c.post("/investigations/%d/decision" % inv_pi,
                   headers=OPERATOR, json={"approved": True, "by": "x"})
        assert r.json()["status"] == "blocked", r.text
        print("[ok] operator-approved SPOF quarantine -> BLOCKED by guardrail")

        # --- admin: reads the audit trail ---
        audit = c.get("/audit", headers=ADMIN).json()
        actors = {a["actor"] for a in audit}
        actions = [a["action"] for a in audit]
        assert actors == {"operator"}, actors          # decisions logged as operator
        assert "approved" in actions
        print("[ok] admin reads audit log; %d entries, actor=operator, actions=%s"
              % (len(audit), sorted(set(actions))))

    print("-" * 60)
    print(">>> PASS: authentication, RBAC, and audit logging all enforced.")


if __name__ == "__main__":
    main()
