from datetime import UTC, datetime
from enum import StrEnum

from sqlmodel import Field, SQLModel


class CallStatus(StrEnum):
    QUEUED = "queued"
    CONVERTING = "converting"
    TRANSCRIBING = "transcribing"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


ACTIVE_STATUSES = (CallStatus.QUEUED, CallStatus.CONVERTING, CallStatus.TRANSCRIBING)


def utcnow() -> datetime:
    return datetime.now(UTC)


class Call(SQLModel, table=True):
    """A recorded client call and the state of its transcription job."""

    id: str = Field(primary_key=True)
    title: str  # original file name, shown to the user, never used as a path
    created_at: datetime = Field(default_factory=utcnow)
    status: CallStatus = CallStatus.QUEUED
    progress: float = 0.0  # 0 to 1, never goes backwards
    error_code: str | None = None
    language: str | None = None
    duration_s: float | None = None
    keep_audio: bool = False
    audio_ext: str  # e.g. ".mp3"


class Segment(SQLModel, table=True):
    """One transcript segment. `idx` is the segment id other features cite as a source."""

    call_id: str = Field(foreign_key="call.id", primary_key=True)
    idx: int = Field(primary_key=True)
    start: float
    end: float
    text: str
