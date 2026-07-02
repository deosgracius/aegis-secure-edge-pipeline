"""
store.py -- the service layer (business logic), kept separate from the web layer.

Everything here works on plain data (dicts), so it can be driven directly from a
demo/test OR from the FastAPI endpoints in main.py -- no HTTP required to verify
the logic. This is also where the knowledge graph plugs into the control plane.
"""

import os
import sys

from db import Device, Incident, SessionLocal, Telemetry, init_db

# pull in the knowledge-graph queries from the sibling folder
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "knowledge-graph"))
import kg          # noqa: E402
import topology    # noqa: E402


# ---------------------------------------------------------------------------
# setup / seeding
# ---------------------------------------------------------------------------
def setup():
    """Create tables and seed devices from the topology (idempotent)."""
    init_db()
    with SessionLocal() as s:
        for did, a in topology.DEVICES.items():
            if s.get(Device, did) is None:
                s.add(Device(id=did, name=a["name"], type=a["type"],
                             criticality=a["criticality"], status="active"))
        s.commit()


# ---------------------------------------------------------------------------
# ingest -- the gateway calls this for every reading
# ---------------------------------------------------------------------------
def ingest_telemetry(device_id, seq, features, verdict, score):
    """Store one reading. If suspicious, auto-open an incident. Returns a summary."""
    with SessionLocal() as s:
        dev = s.get(Device, device_id)
        if dev is None:
            raise ValueError("unknown device: %s" % device_id)
        t = Telemetry(device_id=device_id, seq=seq,
                      f0=features[0], f1=features[1], f2=features[2], f3=features[3],
                      verdict=int(verdict), score=int(score))
        s.add(t)
        incident_id = None
        if verdict:
            summary = ("Suspicious telemetry from %s (score %d): %s"
                       % (dev.name, score, _explain(features)))
            inc = Incident(device_id=device_id, score=int(score),
                           status="open", summary=summary)
            s.add(inc)
            s.flush()
            incident_id = inc.id
        s.commit()
        return {"telemetry_id": t.id, "incident_id": incident_id}


def _explain(f):
    """Cheap human hint about which feature looks off (pkt_rate,size,seq_gap*100,iat_var*100)."""
    hints = []
    if f[0] > 800:
        hints.append("high packet rate")
    if f[2] > 1000:
        hints.append("large sequence gap")
    if f[3] > 3000:
        hints.append("bursty timing")
    if f[1] < 200:
        hints.append("undersized packets")
    return ", ".join(hints) or "pattern outside learned-normal"


# ---------------------------------------------------------------------------
# reads -- what the dashboard and the agent query
# ---------------------------------------------------------------------------
def list_devices():
    with SessionLocal() as s:
        return [_dev_dict(d) for d in s.query(Device).order_by(Device.id)]


def list_incidents(status=None):
    with SessionLocal() as s:
        q = s.query(Incident)
        if status:
            q = q.filter(Incident.status == status)
        return [_inc_dict(i) for i in q.order_by(Incident.id.desc())]


def counts():
    with SessionLocal() as s:
        return {
            "devices": s.query(Device).count(),
            "telemetry": s.query(Telemetry).count(),
            "incidents": s.query(Incident).count(),
            "open_incidents": s.query(Incident).filter(Incident.status == "open").count(),
        }


# ---------------------------------------------------------------------------
# the knowledge graph, exposed through the control plane
# ---------------------------------------------------------------------------
def device_impact(device_id):
    """What breaks if we quarantine this device? (used before remediation)"""
    if device_id not in topology.DEVICES:
        raise ValueError("unknown device: %s" % device_id)
    impacted = sorted(topology.DEVICES[i]["name"] for i in kg.impact_of_failure(device_id))
    return {
        "device": topology.DEVICES[device_id]["name"],
        "breaks_if_quarantined": impacted,
        "is_single_point_of_failure": bool(impacted),
        "safe_to_quarantine": not impacted,
    }


def set_device_status(device_id, status):
    with SessionLocal() as s:
        dev = s.get(Device, device_id)
        if dev is None:
            raise ValueError("unknown device: %s" % device_id)
        dev.status = status
        s.commit()
        return _dev_dict(dev)


# ---------------------------------------------------------------------------
# serializers
# ---------------------------------------------------------------------------
def _dev_dict(d):
    return {"id": d.id, "name": d.name, "type": d.type,
            "criticality": d.criticality, "status": d.status}


def _inc_dict(i):
    return {"id": i.id, "device_id": i.device_id, "score": i.score,
            "status": i.status, "summary": i.summary, "ts": i.ts.isoformat()}
