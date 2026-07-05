# AEGIS — Control Plane (FastAPI + SQLAlchemy + SQLite)

The system of record. Ingests scored telemetry from the gateway, stores devices /
telemetry / incidents, auto-opens an incident on any suspicious verdict, and
exposes the knowledge-graph "blast radius" check through the API. This is the hub
the AI agent and the dashboard will both read from.

## Files

| File | Role |
|------|------|
| `db.py` | SQLAlchemy 2.0 models + engine (Device, Telemetry, Incident) → `aegis.db`. |
| `store.py` | Service layer (business logic); also where `kg.py` plugs in. |
| `schemas.py` | Pydantic request/response shapes. |
| `main.py` | FastAPI app (thin web layer over `store.py`). |
| `demo.py` | End-to-end: gateway → ingest → incidents → graph check → quarantine. |

## Run

> Use the venv that has the deps: `..\..\.venv\Scripts\python.exe`
> (Python 3.14 + FastAPI 0.136 + SQLAlchemy 2.0, already installed there).

```powershell
# End-to-end demo (no server needed)
..\..\.venv\Scripts\python.exe demo.py

# Or run the live API + interactive docs at http://127.0.0.1:8000/docs
..\..\.venv\Scripts\python.exe -m uvicorn main:app --reload
```

## Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET  | `/health` | liveness |
| GET  | `/stats` | row counts |
| GET  | `/devices` | list devices + status |
| POST | `/telemetry` | gateway ingests a scored reading (auto-opens incident if suspicious) |
| GET  | `/incidents?status=open` | incidents the agent will triage |
| GET  | `/devices/{id}/impact` | blast radius via the knowledge graph (safe to quarantine?) |
| POST | `/devices/{id}/status` | quarantine / reactivate |
| GET  | `/investigations` | AI-agent investigation audit records (diagnosis, proposal, decision, transcript) |
| GET  | `/approvals` | the approval queue — investigations awaiting a human decision |
| POST | `/investigations/{id}/decision` | approve/reject a queued investigation (executes if approved + safe) |

## What it proves

- Gateway verdicts now have a home; suspicious ones **auto-open incidents** with a
  human-readable cause ("large sequence gap", "high packet rate", ...).
- The **knowledge graph is served through the API**: `GET /devices/pi/impact`
  returns *not safe — breaks control-plane, dashboard, fpga-scorer*; a sensor
  returns *safe to quarantine*. That is the exact pre-remediation check the AI
  agent will run.

## Next

- The **LangGraph AI agent + MCP tools** wrapping these endpoints (`list_incidents`,
  `device_impact`, `set_device_status`) with a human approval gate.
- RBAC / audit logging / OAuth / MFA on top (the hardening pass).
