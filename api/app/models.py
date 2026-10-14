from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import JSON, Column
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


class AppSetting(SQLModel, table=True):
    """Local settings (key/value). Holds the language model in use under `llm_model`."""

    key: str = Field(primary_key=True)
    value: str


class Profile(SQLModel, table=True):
    """The freelancer's profile. There is one row (id 1). Rates are free text in any currency."""

    id: int = Field(default=1, primary_key=True)
    name: str
    services: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    hourly_rate: str | None = None
    project_rates: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    payment_terms: str = ""
    sections: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    tone: str = ""


class DraftStatus(StrEnum):
    QUEUED = "queued"
    EXTRACTING = "extracting"
    DRAFTING = "drafting"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


ACTIVE_DRAFT_STATUSES = (DraftStatus.QUEUED, DraftStatus.EXTRACTING, DraftStatus.DRAFTING)


class Draft(SQLModel, table=True):
    """The call notes and proposal draft for one call, plus the state of the job that made them."""

    call_id: str = Field(foreign_key="call.id", primary_key=True)
    status: DraftStatus = DraftStatus.QUEUED
    progress: float = 0.0
    stage_detail: str | None = None  # e.g. "2/5": which part of the call is being read
    error_code: str | None = None
    language: str  # language the proposal is written in
    model: str | None = None  # language model that produced it
    notes: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    proposal: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    warnings: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class SetupState(StrEnum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"  # the user paused; resuming continues where it stopped
    FAILED = "failed"  # a download or check failed; trying again continues where it stopped
    COMPAT_FAILED = "compat_failed"  # the model downloaded but cannot do the app's task
    INTERRUPTED = "interrupted"  # the app was closed mid-run; the user is asked before resuming
    DONE = "done"


TERMINAL_SETUP_STATES = (
    SetupState.IDLE,
    SetupState.PAUSED,
    SetupState.FAILED,
    SetupState.COMPAT_FAILED,
    SetupState.INTERRUPTED,
    SetupState.DONE,
)


class SetupRun(SQLModel, table=True):
    """The last model setup (first launch or Settings), kept so it can resume after a restart."""

    id: int = Field(default=1, primary_key=True)
    state: SetupState = SetupState.IDLE
    llm_model: str | None = None
    steps: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    overall_fraction: float = 0.0
    error_code: str | None = None
    updated_at: datetime = Field(default_factory=utcnow)
