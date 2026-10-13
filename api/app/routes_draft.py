from typing import Annotated

from fastapi import APIRouter, Body, HTTPException, Request
from sqlmodel import Session, col, delete, select

from app.generation import GenerationManager
from app.models import ACTIVE_DRAFT_STATUSES, Call, CallStatus, Draft, Profile, Segment
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
        raise HTTPException(404, "The profile has not been set up yet.")
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
        raise HTTPException(404, "Call not found.")
    if call.status != CallStatus.DONE:
        raise HTTPException(409, "Transcribe the call before drafting a proposal.")
    if session.get(Profile, 1) is None:
        raise HTTPException(409, "Set up your profile first.")
    existing = session.get(Draft, call_id)
    if existing is not None and existing.status in ACTIVE_DRAFT_STATUSES:
        raise HTTPException(409, "A draft is already being written for this call.")
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
        raise HTTPException(404, "There is no draft for this call yet.")
    return _read(session, draft)


@router.post("/calls/{call_id}/draft/cancel")
def cancel_draft(request: Request, session: SessionDep, call_id: str) -> DraftRead:
    draft = session.get(Draft, call_id)
    if draft is None:
        raise HTTPException(404, "There is no draft for this call yet.")
    if draft.status not in ACTIVE_DRAFT_STATUSES:
        raise HTTPException(409, "Only a draft in progress can be cancelled.")
    _generation(request).cancel(call_id)
    return _read(session, draft)
