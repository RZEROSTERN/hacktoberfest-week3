from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app import i18n
from app.drafting import DraftItem, ProposalDraft
from app.models import Call, CallStatus, Draft, DraftStatus, Profile, Segment
from app.notes import GROUPS, Notes

ERROR_MESSAGES = {
    "engine_missing": "The transcription engine is not available.",
    "model_missing": "The speech model has not been downloaded yet.",
    "decoder_missing": "The macOS audio converter is missing, so audio files cannot be read.",
    "decode_failed": "The audio file could not be read. Try exporting it again as mp3, m4a or wav.",
    "transcribe_failed": "Something went wrong while transcribing. You can try again.",
    "interrupted": "The app was closed while transcribing. You can try again.",
    "audio_missing": "The audio file is no longer available. Please upload it again.",
    "llm_model_not_set": "No language model is selected yet.",
    "llm_model_missing": "The selected language model is not installed.",
    "llm_unreachable": "The language model engine is not running.",
    "llm_timeout": "The language model took too long to answer. Try again.",
    "llm_failed": "The language model returned an error. Try again.",
    "invalid_model_output": "The model's answer could not be understood, even after a retry.",
    "draft_invalid": "The draft broke a rule (it contained prices), even after a retry.",
    "not_enough_information": "The call did not contain enough information to draft a proposal.",
    "profile_missing": "Set up your profile first.",
    "empty_transcript": "The transcript is empty, so there is nothing to draft from.",
    "generation_failed": "Something went wrong while drafting. You can try again.",
}


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
