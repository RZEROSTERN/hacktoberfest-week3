from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Body, Query, Request, Response
from sqlmodel import Session, col, delete, select

from app import export
from app.drafting import EditError, ProposalDraft, ProposalEdit, apply_edit
from app.errors import ApiError
from app.generation import GenerationManager
from app.models import ACTIVE_DRAFT_STATUSES, Call, CallStatus, Draft, DraftStatus, Profile, Segment
from app.notes import Notes
from app.routes import SessionDep
from app.schemas import DraftRead, DraftRequest, ProfileIn, ProfileRead

router = APIRouter(tags=["draft"])


def _generation(request: Request) -> GenerationManager:
    manager: GenerationManager = request.app.state.generation
    return manager


def _read(session: Session, draft: Draft) -> DraftRead:
    segments = session.exec(select(Segment).where(Segment.call_id == draft.call_id)).all()
    return DraftRead.from_draft(draft, {s.idx: s for s in segments})


@router.get("/profile")
def get_profile(session: SessionDep) -> ProfileRead:
    profile = session.get(Profile, 1)
    if profile is None:
        raise ApiError(404, "profile_not_set_up")
    return ProfileRead.from_profile(profile)


@router.put("/profile")
def put_profile(session: SessionDep, body: ProfileIn) -> ProfileRead:
    profile = session.get(Profile, 1) or Profile(id=1, name=body.name)
    profile.name = body.name
    profile.services = [s.strip() for s in body.services if s.strip()]
    profile.hourly_rate = (body.hourly_rate or "").strip() or None
    profile.project_rates = [r.strip() for r in body.project_rates if r.strip()]
    profile.payment_terms = body.payment_terms
    profile.sections = body.sections
    profile.tone = body.tone
    session.add(profile)
    session.commit()
    return ProfileRead.from_profile(profile)


@router.post("/calls/{call_id}/draft", status_code=202)
def create_draft(
    request: Request,
    session: SessionDep,
    call_id: str,
    body: Annotated[DraftRequest | None, Body()] = None,
) -> DraftRead:
    call = session.get(Call, call_id)
    if call is None:
        raise ApiError(404, "call_not_found")
    if call.status != CallStatus.DONE:
        raise ApiError(409, "transcribe_first")
    if session.get(Profile, 1) is None:
        raise ApiError(409, "profile_missing")
    existing = session.get(Draft, call_id)
    if existing is not None and existing.status in ACTIVE_DRAFT_STATUSES:
        raise ApiError(409, "draft_in_progress")
    session.exec(delete(Draft).where(col(Draft.call_id) == call_id))
    language = (body.language if body and body.language else None) or call.language or "en"
    draft = Draft(call_id=call_id, language=language)
    session.add(draft)
    session.commit()
    _generation(request).submit(call_id)
    session.refresh(draft)
    return _read(session, draft)


@router.get("/calls/{call_id}/draft")
def get_draft(session: SessionDep, call_id: str) -> DraftRead:
    draft = session.get(Draft, call_id)
    if draft is None:
        raise ApiError(404, "no_draft")
    return _read(session, draft)


@router.post("/calls/{call_id}/draft/cancel")
def cancel_draft(request: Request, session: SessionDep, call_id: str) -> DraftRead:
    draft = session.get(Draft, call_id)
    if draft is None:
        raise ApiError(404, "no_draft")
    if draft.status not in ACTIVE_DRAFT_STATUSES:
        raise ApiError(409, "draft_not_running")
    _generation(request).cancel(call_id)
    return _read(session, draft)


def _finished_draft(session: Session, call_id: str) -> tuple[Draft, ProposalDraft]:
    draft = session.get(Draft, call_id)
    if draft is None:
        raise ApiError(404, "no_draft")
    if draft.status != DraftStatus.DONE or draft.proposal is None:
        raise ApiError(409, "draft_not_ready")
    return draft, ProposalDraft.model_validate(draft.proposal)


@router.put("/calls/{call_id}/draft/proposal")
def edit_proposal(session: SessionDep, call_id: str, body: ProposalEdit) -> DraftRead:
    """Save the user's edits. Sources, the no-prices rule and the assumption flags are enforced."""
    draft, current = _finished_draft(session, call_id)
    segments = session.exec(select(Segment).where(Segment.call_id == call_id)).all()
    try:
        edited = apply_edit(current, body, {s.idx for s in segments})
    except EditError as exc:
        raise ApiError(422, exc.code, str(exc), **exc.params) from exc
    draft.proposal = edited.model_dump()
    draft.updated_at = datetime.now(UTC)
    session.add(draft)
    session.commit()
    return _read(session, draft)


@router.get("/calls/{call_id}/draft/export")
def export_proposal(
    session: SessionDep, call_id: str, fmt: Annotated[Literal["md", "pdf"], Query(alias="format")]
) -> Response:
    """Download the saved proposal as Markdown or PDF."""
    draft, proposal = _finished_draft(session, call_id)
    profile = session.get(Profile, 1)
    notes = Notes.model_validate(draft.notes) if draft.notes else None
    document = export.build_document(proposal, notes, profile.name if profile else "")
    try:
        if fmt == "md":
            body, media_type = export.to_markdown(document).encode(), "text/markdown; charset=utf-8"
        else:
            body, media_type = export.to_pdf(document), "application/pdf"
    except export.ExportError as exc:
        raise ApiError(422, exc.code) from exc
    name = export.filename(document, fmt)
    return Response(
        body,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )
