"""
verify_oauth.py -- test the OAuth email->role->session mapping (the part that
matters for security), without the live Google round-trip.

The HTTP exchange with Google needs a real consent screen and can't run
headlessly; here we feed a "verified email" straight into store.oauth_login,
exactly as the callback does after Google returns one.

Run (venv):  python verify_oauth.py
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
# deterministic allow-list for the test
os.environ["AEGIS_OAUTH_ALLOWLIST"] = "admin@example.com:admin,operator@example.com:operator"
import store   # noqa: E402


def bearer(tok):
    return {"Authorization": "Bearer " + tok}


def main():
    dbfile = os.path.join(HERE, "aegis.db")
    if os.path.exists(dbfile):
        os.remove(dbfile)

    from fastapi.testclient import TestClient
    import main
    print("=" * 60)
    print("OAuth / OIDC (email -> role -> session) verification")
    print("=" * 60)

    with TestClient(main.app) as c:
        # allow-listed email -> session with the right role
        r = store.oauth_login("Operator@Example.com")   # case-insensitive
        assert r and r["role"] == "operator", r
        tok = r["token"]
        print("[ok] allow-listed email -> operator session issued")

        # that session authenticates protected calls with its role
        assert c.get("/devices", headers=bearer(tok)).status_code == 200
        inv = store.save_investigation("sn1", {"action": "quarantine",
            "target_device": "sn1", "diagnosis": "d", "reasoning": "r",
            "runbook": "rb-001-traffic-flood"}, ["s"])
        assert c.post("/investigations/%d/decision" % inv, headers=bearer(tok),
                      json={"approved": True, "by": "x"}).status_code == 200
        print("[ok] SSO session works on reads + operator-gated actions")

        # non-allow-listed email is rejected
        assert store.oauth_login("stranger@evil.com") is None
        print("[ok] non-allow-listed email -> denied")

        # login endpoint: 200 (configured) or 503 (no Google creds in this env)
        code = c.get("/auth/oauth/login").status_code
        assert code in (200, 503), code
        print("[ok] /auth/oauth/login -> %d (%s)"
              % (code, "URL returned" if code == 200 else "not configured here"))

        # audit captured the SSO login
        audit = c.get("/audit", headers={"Authorization": "Bearer admin-demo-token"}).json()
        # oauth_login writes audit only via the callback; store.oauth_login here
        # doesn't, so just assert the log endpoint works
        assert isinstance(audit, list)
        print("[ok] audit log reachable (%d entries)" % len(audit))

    print("-" * 60)
    print(">>> PASS: OAuth email->role->session mapping works and is guarded.")


if __name__ == "__main__":
    main()
