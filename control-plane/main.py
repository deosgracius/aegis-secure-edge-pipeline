"""
main.py -- AEGIS control-plane REST API (FastAPI).

Thin web layer over store.py. Run it with:
    uvicorn main:app --reload        (from the control-plane folder)
then open http://127.0.0.1:8000/docs for interactive API docs.

Endpoints:
    GET  /health                       liveness
    GET  /devices                      list devices + status
    POST /telemetry                    gateway ingests a scored reading
    GET  /incidents?status=open        list incidents (what the agent reads)
    GET  /devices/{id}/impact          blast radius via the knowledge graph
    POST /devices/{id}/status          quarantine / reactivate a device
    GET  /stats                        row counts
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

import store
from schemas import StatusIn, TelemetryIn


@asynccontextmanager
async def lifespan(app: FastAPI):
    store.setup()          # create tables + seed devices on startup
    yield


app = FastAPI(title="AEGIS Control Plane", version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/stats")
def stats():
    return store.counts()


@app.get("/devices")
def devices():
    return store.list_devices()


@app.post("/telemetry")
def post_telemetry(t: TelemetryIn):
    try:
        return store.ingest_telemetry(t.device_id, t.seq, t.features, t.verdict, t.score)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/incidents")
def incidents(status: str | None = None):
    return store.list_incidents(status)


@app.get("/devices/{device_id}/impact")
def impact(device_id: str):
    try:
        return store.device_impact(device_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/devices/{device_id}/status")
def set_status(device_id: str, body: StatusIn):
    try:
        return store.set_device_status(device_id, body.status)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
