"""
main.py -- AEGIS control-plane REST API (FastAPI).

Thin web layer over store.py, with bearer-token auth + RBAC + audit logging.
Run it with:
    uvicorn main:app --reload        (from the control-plane folder)
then open http://127.0.0.1:8000/docs for interactive API docs.

Every endpoint except /health requires `Authorization: Bearer <token>`. Roles:
  viewer   -> read-only
  operator -> + ingest / quarantine / approve-reject
  admin    -> + read the audit log
Demo tokens are seeded by store.setup(): viewer-demo-token / operator-demo-token
/ admin-demo-token. Mutating actions are recorded in the audit log.
"""

import logging
import time
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

import store
from auth import require_role
from schemas import DecisionIn, LoginIn, StatusIn, TelemetryIn
from settings import settings

logging.basicConfig(level=settings.log_level,
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("aegis")


@asynccontextmanager
async def lifespan(app: FastAPI):
    store.setup()          # create tables + seed devices + users on startup
    log.info("%s v%s started", settings.app_name, settings.version)
    yield


app = FastAPI(title=settings.app_name, version=settings.version, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    t0 = time.perf_counter()
    response = await call_next(request)
    dt_ms = (time.perf_counter() - t0) * 1000
    log.info("%s %s -> %d (%.1f ms)",
             request.method, request.url.path, response.status_code, dt_ms)
    return response


# ---- liveness (open) ----
@app.get("/health")
def health():
    return {"status": "ok"}


# ---- MFA login (open) ----
@app.post("/auth/login")
def login(body: LoginIn):
    """Exchange username + a valid TOTP code for a short-lived session token."""
    user = store.verify_totp(body.username, body.totp)
    if user is None:
        store.write_audit(body.username, "login_failed", "bad username or TOTP code")
        raise HTTPException(status_code=401, detail="invalid credentials")
    sess = store.create_session(user["name"])
    store.write_audit(user["name"], "login", "MFA session issued")
    return {"token": sess["token"], "role": user["role"],
            "expires_at": sess["expires_at"]}


@app.post("/auth/logout")
def logout(authorization: str = Header(default="")):
    token = authorization.split(" ", 1)[1].strip() if " " in authorization else ""
    store.revoke_session(token)
    return {"status": "logged out"}


@app.get("/auth/provisioning-uri")
def provisioning_uri(username: str, user=Depends(require_role("admin"))):
    """otpauth:// URI to enroll a user's authenticator (admin only)."""
    uri = store.provisioning_uri(username)
    if uri is None:
        raise HTTPException(status_code=404, detail="no such user / no TOTP secret")
    return {"username": username, "otpauth_uri": uri}


# ---- OAuth / OIDC (Google SSO) ----
@app.get("/auth/oauth/login")
def oauth_login_start():
    """Return the Google authorization URL for the browser to redirect to."""
    import secrets as _secrets
    import config
    import oauth
    if not config.oauth_configured():
        raise HTTPException(status_code=503, detail="Google OAuth not configured")
    state = _secrets.token_urlsafe(12)
    return {"authorization_url": oauth.build_authorization_url(state), "state": state}


@app.get("/auth/oauth/callback")
def oauth_callback(code: str, state: str = ""):
    """Google redirects here; exchange the code and issue a session."""
    import oauth
    email = oauth.exchange_code(code)
    if email is None:
        raise HTTPException(status_code=401, detail="OAuth exchange failed")
    result = store.oauth_login(email)
    if result is None:
        store.write_audit(email, "oauth_denied", "email not allow-listed")
        raise HTTPException(status_code=403, detail="email not authorized")
    store.write_audit(email, "oauth_login", "SSO session issued")
    return result


# ---- reads (viewer+) ----
@app.get("/stats")
def stats(user=Depends(require_role("viewer"))):
    return store.counts()


@app.get("/devices")
def devices(user=Depends(require_role("viewer"))):
    return store.list_devices()


@app.get("/topology")
def topology(user=Depends(require_role("viewer"))):
    """Nodes + edges for the dashboard topology graph."""
    return store.topology_graph()


@app.get("/incidents")
def incidents(status: str | None = None, user=Depends(require_role("viewer"))):
    return store.list_incidents(status)


@app.get("/devices/{device_id}/impact")
def impact(device_id: str, user=Depends(require_role("viewer"))):
    try:
        return store.device_impact(device_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/investigations")
def investigations(status: str | None = None, user=Depends(require_role("viewer"))):
    return store.list_investigations(status)


@app.get("/approvals")
def approvals(user=Depends(require_role("viewer"))):
    """The approval queue: investigations awaiting a human decision."""
    return store.approval_queue()


# ---- mutations (operator+) ----
@app.post("/telemetry")
def post_telemetry(t: TelemetryIn, user=Depends(require_role("operator"))):
    try:
        res = store.ingest_telemetry(t.device_id, t.seq, t.features, t.verdict, t.score)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    if res.get("incident_id"):
        store.write_audit(user["name"], "incident_opened",
                          "device %s, incident %s" % (t.device_id, res["incident_id"]))
    return res


@app.post("/devices/{device_id}/status")
def set_status(device_id: str, body: StatusIn, user=Depends(require_role("operator"))):
    try:
        dev = store.set_device_status(device_id, body.status)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    store.write_audit(user["name"], "device_status",
                      "%s -> %s" % (device_id, body.status))
    return dev


@app.post("/investigations/{inv_id}/decision")
def decide(inv_id: int, body: DecisionIn, user=Depends(require_role("operator"))):
    # the actor is the authenticated user, never client-supplied
    try:
        result = store.decide_investigation(inv_id, body.approved, user["name"], body.note)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    store.write_audit(user["name"],
                      "approved" if body.approved else "rejected",
                      "investigation %d -> %s" % (inv_id, result["status"]))
    return result


# ---- audit (admin only) ----
@app.get("/audit")
def audit(user=Depends(require_role("admin"))):
    return store.list_audit()
