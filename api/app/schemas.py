from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app import i18n
from app.catalog import LlmModel, WhisperModel
from app.drafting import DraftItem, ProposalDraft
from app.errors import ERROR_MESSAGES
from app.models import Call, CallStatus, Draft, DraftStatus, Profile, Segment, SetupState
from app.notes import GROUPS, Notes


class CallRead(BaseModel):
    id: str
    title: str
    created_at: datetime
    status: CallStatus
    progress: float
    error_code: str | None
    error_message: str | None
    language: str | None
    duration_s: float | None
    keep_audio: bool
    audio_available: bool

    @classmethod
    def from_call(cls, call: Call, audio_available: bool) -> "CallRead":
        return cls(
            id=call.id,
            title=call.title,
            created_at=call.created_at,
            status=call.status,
            progress=call.progress,
            error_code=call.error_code,
            error_message=ERROR_MESSAGES.get(call.error_code, "Something went wrong.")
            if call.error_code
            else None,
            language=call.language,
            duration_s=call.duration_s,
            keep_audio=call.keep_audio,
            audio_available=audio_available,
        )


class SegmentRead(BaseModel):
    """`id` is the segment id that notes and proposals cite as their source."""

    id: int
    start: float
    end: float
    text: str

    @classmethod
    def from_segment(cls, segment: Segment) -> "SegmentRead":
        return cls(id=segment.idx, start=segment.start, end=segment.end, text=segment.text)


class TranscriptRead(BaseModel):
    call_id: str
    language: str | None
    duration_s: float | None
    segments: list[SegmentRead]


def error_message(code: str | None) -> str | None:
    return ERROR_MESSAGES.get(code, "Something went wrong.") if code else None


class ProfileIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    services: list[str] = []
    hourly_rate: str | None = None
    project_rates: list[str] = []
    payment_terms: str = ""
    sections: list[str] = []
    tone: str = ""

    @field_validator("name", "payment_terms", "tone")
    @classmethod
    def _strip(cls, value: str) -> str:
        return value.strip()

    @field_validator("sections")
    @classmethod
    def _known_sections(cls, value: list[str]) -> list[str]:
        unknown = [s for s in value if s not in i18n.SECTION_IDS]
        if unknown:
            raise ValueError(f"Unknown sections: {unknown}")
        return value


class ProfileRead(ProfileIn):
    @classmethod
    def from_profile(cls, profile: Profile) -> "ProfileRead":
        return cls(
            name=profile.name,
            services=profile.services,
            hourly_rate=profile.hourly_rate,
            project_rates=profile.project_rates,
            payment_terms=profile.payment_terms,
            sections=profile.sections,
            tone=profile.tone,
        )


class DraftRequest(BaseModel):
    """`language` is a two- or three-letter code; when omitted the call's own language is used."""

    language: str | None = Field(default=None, pattern=r"^[a-z]{2,3}$")


class SourceRead(BaseModel):
    """The transcript excerpt behind an item: shown when the user clicks its source link."""

    segment_id: int
    start: float
    end: float
    text: str


class ItemRead(BaseModel):
    text: str
    assumption: bool
    sources: list[SourceRead]


class SectionRead(BaseModel):
    id: str
    title: str
    text: str = ""
    lines: list[str] = []
    items: list[ItemRead] = []
    items_label: str | None = None


class NotesRead(BaseModel):
    client: str
    groups: dict[str, list[ItemRead]]
    open_questions: list[str]


class ProposalRead(BaseModel):
    language: str
    sections: list[SectionRead]


class DraftRead(BaseModel):
    call_id: str
    status: DraftStatus
    progress: float
    stage_detail: str | None
    error_code: str | None
    error_message: str | None
    language: str
    model: str | None
    warnings: list[str]
    updated_at: datetime
    notes: NotesRead | None
    proposal: ProposalRead | None

    @classmethod
    def from_draft(cls, draft: Draft, segments: dict[int, Segment]) -> "DraftRead":
        notes_read = None
        if draft.notes is not None:
            notes = Notes.model_validate(draft.notes)
            notes_read = NotesRead(
                client=notes.client,
                groups={
                    group: [
                        _item(segments, n.text, n.segment_ids, False) for n in getattr(notes, group)
                    ]
                    for group in GROUPS
                },
                open_questions=notes.open_questions,
            )
        proposal_read = None
        if draft.proposal is not None:
            proposal = ProposalDraft.model_validate(draft.proposal)
            proposal_read = ProposalRead(
                language=proposal.language, sections=_sections(proposal, segments)
            )
        return cls(
            call_id=draft.call_id,
            status=draft.status,
            progress=draft.progress,
            stage_detail=draft.stage_detail,
            error_code=draft.error_code,
            error_message=error_message(draft.error_code),
            language=draft.language,
            model=draft.model,
            warnings=draft.warnings,
            updated_at=draft.updated_at,
            notes=notes_read,
            proposal=proposal_read,
        )


def _item(segments: dict[int, Segment], text: str, ids: list[int], assumption: bool) -> ItemRead:
    sources = [
        SourceRead(
            segment_id=i, start=segments[i].start, end=segments[i].end, text=segments[i].text
        )
        for i in ids
        if i in segments
    ]
    return ItemRead(text=text, assumption=assumption, sources=sources)


def _items(segments: dict[int, Segment], values: list[DraftItem]) -> list[ItemRead]:
    return [_item(segments, v.text, v.segment_ids, v.assumption) for v in values]


def _sections(p: ProposalDraft, segments: dict[int, Segment]) -> list[SectionRead]:
    sections = []
    for section_id in p.section_order:
        section = SectionRead(id=section_id, title=i18n.text(p.language, section_id))
        match section_id:
            case "summary":
                section.text = p.summary
            case "problem":
                section.text = p.problem
            case "scope":
                section.items = _items(segments, p.scope)
            case "deliverables":
                section.items = _items(segments, p.deliverables)
            case "out_of_scope":
                section.items = _items(segments, p.out_of_scope)
            case "timeline":
                section.text = p.timeline
            case "open_questions":
                section.lines = p.open_questions
            case "investment":
                section.text = p.investment.note
                section.lines = p.investment.rates
                section.items = _items(segments, p.investment.client_budget)
                section.items_label = (
                    p.investment.client_budget_label if p.investment.client_budget else None
                )
            case "terms":
                section.text = p.terms
        sections.append(section)
    return sections


# -- setup and models ----------------------------------------------------------------------------


class SystemRead(BaseModel):
    total_ram_bytes: int
    free_disk_bytes: int


class WhisperInfoRead(BaseModel):
    id: str
    title: str
    size_bytes: int
    license: str
    note: str
    state: str  # missing | partial | ready
    bytes_on_disk: int


class LlmChoiceRead(BaseModel):
    model: str
    title: str
    recommended: bool
    size_bytes: int
    size_exact: bool
    ram_gb: int
    license: str
    note: str
    not_recommended_for_this_computer: bool
    installed: bool

    @classmethod
    def from_catalog(cls, m: LlmModel, total_ram: int, installed: bool) -> "LlmChoiceRead":
        return cls(
            **m.model_dump(),
            not_recommended_for_this_computer=m.ram_gb * 2**30 > total_ram,
            installed=installed,
        )


class RecommendedRead(BaseModel):
    version: int
    updated: str
    system: SystemRead
    whisper: WhisperInfoRead
    llm: list[LlmChoiceRead]
    margin_bytes: int  # free space kept on top of the downloads
    library_url: str


class StepRead(BaseModel):
    id: str
    label: str
    state: str  # pending | running | done | failed
    detail: str | None
    skipped: bool
    completed: int
    total: int
    speed_bps: float | None
    eta_s: float | None


class OverallRead(BaseModel):
    fraction: float
    completed_bytes: int
    total_bytes: int


class SetupProgressRead(BaseModel):
    state: SetupState
    llm_model: str | None
    steps: list[StepRead]
    overall: OverallRead
    error_code: str | None
    error_message: str | None

    @classmethod
    def from_snapshot(cls, snap: dict) -> "SetupProgressRead":  # type: ignore[type-arg]
        return cls(**snap, error_message=error_message(snap["error_code"]))


class LlmStatusRead(BaseModel):
    model: str | None
    state: str  # not_selected | missing | partial | ready


class WhisperStatusRead(BaseModel):
    state: str
    bytes: int
    expected_bytes: int


class RunSummaryRead(BaseModel):
    state: SetupState
    llm_model: str | None
    fraction: float


class SetupStatusRead(BaseModel):
    ready: bool
    problem: str | None
    problem_message: str | None
    ollama_reachable: bool
    llm: LlmStatusRead
    whisper: WhisperStatusRead
    compat_ok: bool
    run: RunSummaryRead


class StartSetupRequest(BaseModel):
    model: str = Field(min_length=1, max_length=200)


class InstalledModelRead(BaseModel):
    name: str
    size_bytes: int
    cloud: bool
    active: bool
    compat_ok: bool
    title: str | None
    note: str | None
    license: str | None
    recommended: bool


class ModelsRead(BaseModel):
    active_model: str | None
    llm: list[InstalledModelRead]
    whisper: WhisperInfoRead
    system: SystemRead


def whisper_info(model: WhisperModel, state: str, on_disk: int) -> WhisperInfoRead:
    return WhisperInfoRead(
        id=model.id, title=model.title, size_bytes=model.size_bytes, license=model.license,
        note=model.note, state=state, bytes_on_disk=on_disk,
    )  # fmt: skip
