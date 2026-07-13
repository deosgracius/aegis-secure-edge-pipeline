# AEGIS — Dashboard (React + TypeScript + Vite)

The security-operations UI over the control-plane API. Live topology + device
status, the anomaly feed, and the agent's **approval queue** with approve/reject
buttons and expandable agent reasoning.

## Files

| File | Role |
|------|------|
| `src/App.tsx` | The dashboard: three panels + header stats, polling every 3s. |
| `src/api.ts` | Typed fetch calls to the control plane (via the `/api` proxy). |
| `src/styles.css` | Warm dark security-ops theme. |
| `vite.config.ts` | Dev server (port 5174) + `/api` → `127.0.0.1:8000` proxy (no CORS). |

## Run (two terminals)

```powershell
# 1. Backend (control plane) — seed demo data, then serve on :8000
cd ..\control-plane
..\..\.venv\Scripts\python.exe seed_dashboard.py
..\..\.venv\Scripts\python.exe -m uvicorn main:app --port 8000

# 2. Frontend (this folder)
npm install     # first time only
npm run dev     # http://localhost:5174
```

The Vite dev server proxies `/api/*` to the backend, so the browser makes
same-origin calls and there is no CORS setup.

## Sign in

The dashboard gates on a login screen: **MFA** (username + a 6-digit TOTP code →
`/auth/login`), **Continue with Google** (OIDC, if configured), or a **demo
operator** shortcut. The session token is kept in `localStorage`; a 401 (expired
session) bounces back to the login screen. "Sign out" clears it.

## What it shows

- **Live Topology** — an SVG graph of the devices (nodes laid out by tier) and
  the knowledge-graph links between them, colored by status; a quarantined node
  turns red with an ✕. Fed by `GET /topology`.
- **Topology & Devices** — every device, its criticality (colored dot), and live
  status (active / quarantined).
- **Anomaly Feed** — incidents opened by suspicious FPGA verdicts.
- **Approval Queue** — the AI agent's proposals awaiting a human decision. Each
  card shows the diagnosis, the proposed action → target, and a toggle to read
  the agent's full reasoning + investigation transcript. **Approve** / **Reject**
  call `POST /investigations/{id}/decision`; on approve, a safe quarantine
  executes and the device flips to *quarantined* on the next refresh.

Verified end to end: clicking Approve on the `sn1` flood → backend quarantines
sensor-node-1 → the device row shows *quarantined* and the queue shrinks. The
gateway proposal stays *notify_operator* (the agent never proposes quarantining
a single point of failure).

## Next

- A live topology *graph* (nodes + edges) instead of the device list.
- Telemetry time-series charts per device.
- Auth (the control-plane RBAC/MFA work) gating the dashboard.
