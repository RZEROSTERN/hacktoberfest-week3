import shutil
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlmodel import Session, col, delete, select

from app.audio import SUPPORTED_EXTENSIONS
from app.jobs import TranscriptionManager
from app.models import ACTIVE_STATUSES, Call, CallStatus, Segment
from app.schemas import CallRead, SegmentRead, TranscriptRead
from app.storage import Storage

router = APIRouter(prefix="/calls", tags=["calls"])


def get_session(request: Request) -> Iterator[Session]:
    with Session(request.app.state.engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]


def _manager(request: Request) -> TranscriptionManager:
    manager: TranscriptionManager = request.app.state.manager
    return manager


def _storage(request: Request) -> Storage:
    storage: Storage = request.app.state.storage
    return storage


def _get_call(session: Session, call_id: str) -> Call:
    call = session.get(Call, call_id)
    if call is None:
        raise HTTPException(404, "Call not found.")
    return call


def _read(request: Request, call: Call) -> CallRead:
    return CallRead.from_call(call, _storage(request).audio_exists(call))


@router.post("", status_code=202)
def create_call(
    request: Request,
    session: SessionDep,
    file: Annotated[UploadFile, File()],
    keep_audio: Annotated[bool, Form()] = False,
) -> CallRead:
    name = Path(file.filename or "recording").name
    ext = Path(name).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(415, "Unsupported file type. Use mp3, m4a, wav or mp4.")
    call = Call(id=uuid.uuid4().hex, title=name[:200], keep_audio=keep_audio, audio_ext=ext)
    storage = _storage(request)
    dest = storage.original(call)
    dest.parent.mkdir(parents=True)
    with dest.open("wb") as out:
        shutil.copyfileobj(file.file, out, 1024 * 1024)  # streamed: recordings can be large
    if dest.stat().st_size == 0:
        storage.remove_audio(call.id)
        raise HTTPException(400, "The file is empty.")
    session.add(call)
    session.commit()
    _manager(request).submit(call.id)
    session.refresh(call)
    return _read(request, call)


@router.get("")
def list_calls(request: Request, session: SessionDep) -> list[CallRead]:
    calls = session.exec(select(Call).order_by(col(Call.created_at).desc())).all()
    return [_read(request, call) for call in calls]


@router.get("/{call_id}")
def get_call(request: Request, session: SessionDep, call_id: str) -> CallRead:
    return _read(request, _get_call(session, call_id))


@router.get("/{call_id}/transcript")
def get_transcript(session: SessionDep, call_id: str) -> TranscriptRead:
    call = _get_call(session, call_id)
    if call.status != CallStatus.DONE:
        raise HTTPException(409, "The transcript is not ready yet.")
    segments = session.exec(
        select(Segment).where(Segment.call_id == call_id).order_by(col(Segment.idx))
    ).all()
    return TranscriptRead(
        call_id=call.id,
        language=call.language,
        duration_s=call.duration_s,
        segments=[SegmentRead.from_segment(s) for s in segments],
    )


@router.post("/{call_id}/cancel")
def cancel_call(request: Request, session: SessionDep, call_id: str) -> CallRead:
    call = _get_call(session, call_id)
    if call.status not in ACTIVE_STATUSES:
        raise HTTPException(409, "Only a running transcription can be cancelled.")
    _manager(request).cancel(call_id)
    return _read(request, call)


@router.post("/{call_id}/retry", status_code=202)
def retry_call(request: Request, session: SessionDep, call_id: str) -> CallRead:
    call = _get_call(session, call_id)
    if call.status != CallStatus.FAILED or not _storage(request).audio_exists(call):
        raise HTTPException(
            409, "Only a failed transcription with its audio still on disk can be retried."
        )
    call.status = CallStatus.QUEUED
    call.progress = 0.0
    call.error_code = None
    session.add(call)
    session.commit()
    _manager(request).submit(call_id)
    session.refresh(call)
    return _read(request, call)


@router.delete("/{call_id}", status_code=204)
def delete_call(request: Request, session: SessionDep, call_id: str) -> None:
    call = _get_call(session, call_id)
    if call.status in ACTIVE_STATUSES:
        raise HTTPException(409, "Cancel the transcription before deleting it.")
    session.exec(delete(Segment).where(col(Segment.call_id) == call_id))
    session.delete(call)
    session.commit()
    _storage(request).remove_audio(call_id)
    _storage(request).remove_tmp(call_id)
