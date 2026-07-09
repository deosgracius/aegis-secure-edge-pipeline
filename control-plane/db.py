"""
db.py -- the control-plane database (SQLAlchemy 2.0 + SQLite).

Three tables, the system of record the AI agent will later reason over:
  Device     -- one row per device in the topology (+ live status)
  Telemetry  -- every reading the gateway forwards (features + the FPGA verdict)
  Incident   -- opened automatically whenever a suspicious verdict arrives
"""

import os
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import ForeignKey, String, Text, create_engine
from sqlalchemy.orm import (DeclarativeBase, Mapped, mapped_column,
                            relationship, sessionmaker)

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "aegis.db")
engine = create_engine("sqlite:///%s" % DB_PATH, echo=False)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def _now():
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Device(Base):
    __tablename__ = "devices"
    id:          Mapped[str] = mapped_column(String, primary_key=True)
    name:        Mapped[str]
    type:        Mapped[str]
    criticality: Mapped[str]
    status:      Mapped[str] = mapped_column(default="active")  # active | quarantined

    telemetry = relationship("Telemetry", back_populates="device")
    incidents = relationship("Incident", back_populates="device")


class Telemetry(Base):
    __tablename__ = "telemetry"
    id:        Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.id"))
    seq:       Mapped[int]
    f0:        Mapped[int]
    f1:        Mapped[int]
    f2:        Mapped[int]
    f3:        Mapped[int]
    verdict:   Mapped[int]   # 0 normal, 1 suspicious
    score:     Mapped[int]   # 0..255
    ts:        Mapped[datetime] = mapped_column(default=_now)

    device = relationship("Device", back_populates="telemetry")


class Incident(Base):
    __tablename__ = "incidents"
    id:        Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.id"))
    score:     Mapped[int]
    status:    Mapped[str] = mapped_column(default="open")  # open | ack | resolved
    summary:   Mapped[str]
    ts:        Mapped[datetime] = mapped_column(default=_now)

    device = relationship("Device", back_populates="incidents")


class User(Base):
    """An operator of the platform. Role gates what they can do (RBAC).

    `token` is a static service token (for machine clients: gateway, dashboard).
    `totp_secret` enables interactive MFA login → a short-lived session token.
    """
    __tablename__ = "users"
    id:          Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name:        Mapped[str] = mapped_column(unique=True)
    role:        Mapped[str]                          # viewer | operator | admin
    token:       Mapped[str] = mapped_column(unique=True)   # static service token
    totp_secret: Mapped[Optional[str]]                # base32 TOTP secret


class Session(Base):
    """A short-lived session issued after a successful MFA login."""
    __tablename__ = "sessions"
    id:         Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    token:      Mapped[str] = mapped_column(unique=True)
    user_name:  Mapped[str] = mapped_column(ForeignKey("users.name"))
    expires_at: Mapped[datetime]
    revoked:    Mapped[bool] = mapped_column(default=False)


class AuditLog(Base):
    """Append-only record of every security-relevant action (who did what)."""
    __tablename__ = "audit_log"
    id:     Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    actor:  Mapped[str]
    action: Mapped[str]
    detail: Mapped[str] = mapped_column(Text)
    ts:     Mapped[datetime] = mapped_column(default=_now)


class Investigation(Base):
    """An auditable record of the AI agent investigating an incident:
    what it concluded, what it proposed, the human decision, and the outcome."""
    __tablename__ = "investigations"
    id:              Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    incident_id:     Mapped[Optional[int]] = mapped_column(ForeignKey("incidents.id"))
    device_id:       Mapped[str] = mapped_column(ForeignKey("devices.id"))
    diagnosis:       Mapped[str]
    reasoning:       Mapped[str] = mapped_column(Text)
    runbook:         Mapped[Optional[str]]
    proposed_action: Mapped[str]                 # quarantine | notify_operator | no_action
    target_device:   Mapped[str]
    status:          Mapped[str] = mapped_column(default="proposed")
    #                proposed | approved | rejected | executed | blocked
    decided_by:      Mapped[Optional[str]]
    decision_note:   Mapped[Optional[str]]
    result:          Mapped[Optional[str]]
    transcript:      Mapped[str] = mapped_column(Text)   # JSON array of steps
    ts:              Mapped[datetime] = mapped_column(default=_now)


def init_db():
    Base.metadata.create_all(engine)
