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

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException

import store
from auth import require_role
from schemas import DecisionIn, StatusIn, TelemetryIn


@asynccontextmanager
async def lifespan(app: FastAPI):
    store.setup()          # create tables + seed devices + users on startup
    yield


app = FastAPI(title="AEGIS Control Plane", version="0.2.0", lifespan=lifespan)


# ---- liveness (open) ----
@app.get("/health")
def health():
    return {"status": "ok"}


# ---- reads (viewer+) ----
@app.get("/stats")
def stats(user=Depends(require_role("viewer"))):
    return store.counts()


@app.get("/devices")
def devices(user=Depends(require_role("viewer"))):
    return store.list_devices()


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
