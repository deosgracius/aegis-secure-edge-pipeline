"""
verify_mfa.py -- deterministic end-to-end test of TOTP MFA login.

Uses pyotp to generate valid codes (as an authenticator app would), so the whole
flow is verified with no external service.  Run (venv):  python verify_mfa.py
"""

import os
import sys
from datetime import datetime, timedelta

import pyotp

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import store   # noqa: E402

OPERATOR_SECRET = "JBSWY3DPEHPK3PXB"   # operator's seeded TOTP secret
ADMIN = {"Authorization": "Bearer admin-demo-token"}
VIEWER = {"Authorization": "Bearer viewer-demo-token"}


def bearer(tok):
    return {"Authorization": "Bearer " + tok}


def prop():
    return {"action": "quarantine", "target_device": "sn1",
            "diagnosis": "d", "reasoning": "r", "runbook": "rb-001-traffic-flood"}


def main():
    dbfile = os.path.join(HERE, "aegis.db")
    if os.path.exists(dbfile):
        os.remove(dbfile)

    from fastapi.testclient import TestClient
    import main
    print("=" * 60)
    print("MFA (TOTP) login verification")
    print("=" * 60)

    with TestClient(main.app) as c:
        # --- login with a valid TOTP code -> session token ---
        code = pyotp.TOTP(OPERATOR_SECRET).now()
        r = c.post("/auth/login", json={"username": "operator", "totp": code})
        assert r.status_code == 200, r.text
        sess = r.json()["token"]
        assert sess.startswith("sess-") and r.json()["role"] == "operator"
        print("[ok] valid TOTP -> session token issued (role operator)")

        # --- the session token authenticates protected calls, with the role ---
        assert c.get("/devices", headers=bearer(sess)).status_code == 200
        inv = store.save_investigation("sn1", prop(), ["s"])
        r = c.post("/investigations/%d/decision" % inv, headers=bearer(sess),
                   json={"approved": True, "by": "x"})
        assert r.status_code == 200 and r.json()["status"] == "executed", r.text
        print("[ok] session token works on reads + operator-gated actions")

        # --- bad code / unknown user rejected ---
        assert c.post("/auth/login", json={"username": "operator", "totp": "000000"}).status_code == 401
        assert c.post("/auth/login", json={"username": "nobody", "totp": code}).status_code == 401
        print("[ok] wrong TOTP code and unknown user -> 401")

        # --- logout revokes the session ---
        c.post("/auth/logout", headers=bearer(sess))
        assert c.get("/devices", headers=bearer(sess)).status_code == 401
        print("[ok] logout revokes the session (subsequent calls 401)")

        # --- expired session is rejected ---
        from db import Session as Sess, SessionLocal
        with SessionLocal() as s:
            s.add(Sess(token="sess-expired", user_name="operator",
                       expires_at=datetime.utcnow() - timedelta(seconds=1)))
            s.commit()
        assert store.resolve_token("sess-expired") is None
        print("[ok] expired session token is rejected")

        # --- enrollment URI (admin only) ---
        r = c.get("/auth/provisioning-uri", params={"username": "operator"}, headers=ADMIN)
        assert r.status_code == 200 and r.json()["otpauth_uri"].startswith("otpauth://totp/")
        assert c.get("/auth/provisioning-uri", params={"username": "operator"},
                     headers=VIEWER).status_code == 403
        print("[ok] admin gets otpauth enrollment URI; viewer blocked (403)")

        # --- audit captured logins ---
        actions = [a["action"] for a in c.get("/audit", headers=ADMIN).json()]
        assert "login" in actions and "login_failed" in actions
        print("[ok] audit log recorded login and login_failed")

    print("-" * 60)
    print(">>> PASS: TOTP MFA login, session lifecycle, and enrollment all work.")


if __name__ == "__main__":
    main()
