"""
store.py -- the service layer (business logic), kept separate from the web layer.

Everything here works on plain data (dicts), so it can be driven directly from a
demo/test OR from the FastAPI endpoints in main.py -- no HTTP required to verify
the logic. This is also where the knowledge graph plugs into the control plane.
"""

import json
import os
import secrets
import sys
from datetime import datetime, timedelta

import pyotp

from db import (AuditLog, Device, Incident, Investigation, Session,
                SessionLocal, Telemetry, User, init_db)

# Demo users. Each has a static service token (machine clients: gateway,
# dashboard) AND a TOTP secret for interactive MFA login. In production these
# come from an identity provider (OAuth/OIDC); the role checks stay identical.
DEMO_USERS = [
    {"name": "viewer",   "role": "viewer",   "token": "viewer-demo-token",
     "totp": "JBSWY3DPEHPK3PXA"},
    {"name": "operator", "role": "operator", "token": "operator-demo-token",
     "totp": "JBSWY3DPEHPK3PXB"},
    {"name": "admin",    "role": "admin",    "token": "admin-demo-token",
     "totp": "JBSWY3DPEHPK3PXC"},
]

SESSION_TTL_SECONDS = 3600   # MFA session lifetime

# pull in the knowledge-graph queries from the sibling folder
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "knowledge-graph"))
import kg          # noqa: E402
import topology    # noqa: E402


# ---------------------------------------------------------------------------
# setup / seeding
# ---------------------------------------------------------------------------
def setup():
    """Create tables and seed devices + users (idempotent)."""
    init_db()
    with SessionLocal() as s:
        for did, a in topology.DEVICES.items():
            if s.get(Device, did) is None:
                s.add(Device(id=did, name=a["name"], type=a["type"],
                             criticality=a["criticality"], status="active"))
        for u in DEMO_USERS:
            if not s.query(User).filter(User.name == u["name"]).first():
                s.add(User(name=u["name"], role=u["role"], token=u["token"],
                           totp_secret=u.get("totp")))
        s.commit()


# ---------------------------------------------------------------------------
# auth + audit
# ---------------------------------------------------------------------------
def get_user_by_token(token):
    """Resolve a static service token to a user (machine clients)."""
    with SessionLocal() as s:
        u = s.query(User).filter(User.token == token).first()
        return {"name": u.name, "role": u.role} if u else None


def resolve_token(token):
    """Resolve a bearer token to a user: a static service token OR a live
    MFA session token (unexpired, not revoked). Returns None if neither."""
    u = get_user_by_token(token)
    if u:
        return u
    with SessionLocal() as s:
        sess = (s.query(Session)
                 .filter(Session.token == token, Session.revoked == False)  # noqa: E712
                 .first())
        if sess is None or sess.expires_at < datetime.utcnow():
            return None
        user = s.query(User).filter(User.name == sess.user_name).first()
        return {"name": user.name, "role": user.role} if user else None


# ---------------------------------------------------------------------------
# MFA (TOTP) login
# ---------------------------------------------------------------------------
def verify_totp(username, code):
    """Check a TOTP code for a user. Returns the user dict on success, else None."""
    with SessionLocal() as s:
        u = s.query(User).filter(User.name == username).first()
        if u is None or not u.totp_secret:
            return None
        if pyotp.TOTP(u.totp_secret).verify(str(code), valid_window=1):
            return {"name": u.name, "role": u.role}
        return None


def create_session(user_name):
    """Issue a short-lived session token after a successful MFA login."""
    token = "sess-" + secrets.token_urlsafe(24)
    expires = datetime.utcnow() + timedelta(seconds=SESSION_TTL_SECONDS)
    with SessionLocal() as s:
        s.add(Session(token=token, user_name=user_name, expires_at=expires))
        s.commit()
    return {"token": token, "expires_at": expires.isoformat() + "Z"}


def revoke_session(token):
    with SessionLocal() as s:
        sess = s.query(Session).filter(Session.token == token).first()
        if sess:
            sess.revoked = True
            s.commit()
            return True
        return False


def provisioning_uri(username):
    """otpauth:// URI to enroll a user's authenticator app (QR-code payload)."""
    with SessionLocal() as s:
        u = s.query(User).filter(User.name == username).first()
        if u is None or not u.totp_secret:
            return None
        return pyotp.TOTP(u.totp_secret).provisioning_uri(
            name=username, issuer_name="AEGIS")


def write_audit(actor, action, detail):
    with SessionLocal() as s:
        s.add(AuditLog(actor=actor, action=action, detail=detail))
        s.commit()


def list_audit(limit=100):
    with SessionLocal() as s:
        rows = s.query(AuditLog).order_by(AuditLog.id.desc()).limit(limit)
        return [{"id": a.id, "actor": a.actor, "action": a.action,
                 "detail": a.detail, "ts": a.ts.isoformat()} for a in rows]


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
# investigations + approval queue (the AI agent writes here; humans act here)
# ---------------------------------------------------------------------------
def save_investigation(device_id, proposal, transcript,
                       incident_id=None, decision=None, result=None):
    """Persist one agent investigation as an audit record. Returns its id.

    status is derived: proposed -> approved/rejected (decision) -> executed/blocked (result).
    """
    status = "proposed"
    if decision is not None:
        status = "approved" if decision.get("approved") else "rejected"
    if result is not None:
        status = result.get("action", status)
        if status == "quarantined":
            status = "executed"
    with SessionLocal() as s:
        inv = Investigation(
            incident_id=incident_id, device_id=device_id,
            diagnosis=proposal.get("diagnosis", ""),
            reasoning=proposal.get("reasoning", ""),
            runbook=proposal.get("runbook"),
            proposed_action=proposal.get("action", ""),
            target_device=proposal.get("target_device", device_id),
            status=status,
            decided_by=(decision or {}).get("by"),
            decision_note=(decision or {}).get("note"),
            result=json.dumps(result) if result is not None else None,
            transcript=json.dumps(transcript or []),
        )
        s.add(inv)
        s.commit()
        return inv.id


def list_investigations(status=None):
    with SessionLocal() as s:
        q = s.query(Investigation)
        if status:
            q = q.filter(Investigation.status == status)
        return [_inv_full(i) for i in q.order_by(Investigation.id.desc())]


def approval_queue():
    """Investigations still awaiting a human decision (what the dashboard shows)."""
    return list_investigations(status="proposed")


def get_investigation(inv_id):
    with SessionLocal() as s:
        inv = s.get(Investigation, inv_id)
        return _inv_full(inv) if inv else None


def decide_investigation(inv_id, approved, by, note=""):
    """Record a human decision on a queued investigation, and act if approved.

    This is the API-driven approval path (the dashboard calls it). Enforces the
    same guardrail as the agent: never quarantine a single point of failure.
    """
    with SessionLocal() as s:
        inv = s.get(Investigation, inv_id)
        if inv is None:
            raise ValueError("unknown investigation: %s" % inv_id)
        if inv.status != "proposed":
            raise ValueError("investigation %s already %s" % (inv_id, inv.status))
        inv.decided_by = by
        inv.decision_note = note
        if not approved:
            inv.status = "rejected"
            s.commit()
            return _inv_full(inv)
        inv.status = "approved"
        s.commit()

    if inv.proposed_action == "quarantine":
        impact = device_impact(inv.target_device)
        if not impact["safe_to_quarantine"]:
            _set_inv(inv_id, status="blocked",
                     result={"action": "blocked",
                             "reason": "guardrail: %s is a single point of failure"
                                       % inv.target_device})
        else:
            dev = set_device_status(inv.target_device, "quarantined")
            _set_inv(inv_id, status="executed",
                     result={"action": "quarantined", "device": dev["name"]})
    return get_investigation(inv_id)


def _set_inv(inv_id, status, result):
    with SessionLocal() as s:
        inv = s.get(Investigation, inv_id)
        inv.status = status
        inv.result = json.dumps(result)
        s.commit()


# ---------------------------------------------------------------------------
# serializers
# ---------------------------------------------------------------------------
def _inv_full(i):
    return {"id": i.id, "incident_id": i.incident_id, "device_id": i.device_id,
            "diagnosis": i.diagnosis, "reasoning": i.reasoning, "runbook": i.runbook,
            "proposed_action": i.proposed_action, "target_device": i.target_device,
            "status": i.status, "decided_by": i.decided_by,
            "decision_note": i.decision_note,
            "result": json.loads(i.result) if i.result else None,
            "transcript": json.loads(i.transcript) if i.transcript else [],
            "ts": i.ts.isoformat()}
def _dev_dict(d):
    return {"id": d.id, "name": d.name, "type": d.type,
            "criticality": d.criticality, "status": d.status}


def _inc_dict(i):
    return {"id": i.id, "device_id": i.device_id, "score": i.score,
            "status": i.status, "summary": i.summary, "ts": i.ts.isoformat()}
