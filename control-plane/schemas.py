"""schemas.py -- request/response shapes (Pydantic) for the REST API."""

from pydantic import BaseModel, Field


class TelemetryIn(BaseModel):
    """What the Raspberry Pi gateway POSTs for each scored reading."""
    device_id: str
    seq: int
    features: list[int] = Field(min_length=4, max_length=4)  # f0..f3 (16-bit)
    verdict: int = Field(ge=0, le=1)
    score: int = Field(ge=0, le=255)


class StatusIn(BaseModel):
    status: str  # "active" | "quarantined"
