import asyncio
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.catalog import ModelNameError
from app.errors import ERROR_MESSAGES, ApiError
from app.models import TERMINAL_SETUP_STATES
from app.schemas import (
    InstalledModelRead,
    LlmChoiceRead,
    ModelsRead,
    RecommendedRead,
    SetupProgressRead,
    SetupStatusRead,
    StartSetupRequest,
    SystemRead,
    error_message,
    whisper_info,
)
from app.setup import MARGIN_BYTES, SetupError, SetupManager
from app.system import free_disk_bytes, total_ram_bytes

router = APIRouter(tags=["setup"])

LIBRARY_URL = "https://ollama.com/library"
_STATUS = {
    "setup_busy": 409,
    "nothing_to_resume": 409,
    "compat_needed": 409,
    "model_in_use": 409,
    "model_not_installed": 404,
    "cloud_model": 422,
}


def _manager(request: Request) -> SetupManager:
    manager: SetupManager = request.app.state.setup
    return manager


def _system(request: Request) -> SystemRead:
    return SystemRead(
        total_ram_bytes=total_ram_bytes(),
        free_disk_bytes=free_disk_bytes(request.app.state.settings.models_dir),
    )


def _refuse(code: str) -> ApiError:
    return ApiError(_STATUS.get(code, 422), code, ERROR_MESSAGES.get(code, "Something went wrong."))


@router.get("/system")
def get_system(request: Request) -> SystemRead:
    return _system(request)


@router.get("/setup/recommended")
def get_recommended(request: Request) -> RecommendedRead:
    manager = _manager(request)
    system = _system(request)
    state, on_disk = manager.whisper.state()
    try:
        installed = {m.name for m in manager.ollama.list_models()}
    except Exception:  # the engine may be off: the list is still useful
        installed = set()
    catalog = manager.catalog
    return RecommendedRead(
        version=catalog.version,
        updated=catalog.updated,
        system=system,
        whisper=whisper_info(catalog.whisper, state, on_disk),
        llm=[
            LlmChoiceRead.from_catalog(m, system.total_ram_bytes, m.model in installed)
            for m in catalog.llm
        ],
        margin_bytes=MARGIN_BYTES,
        library_url=LIBRARY_URL,
    )


@router.get("/setup/status")
def get_status(request: Request) -> SetupStatusRead:
    data = _manager(request).status()
    return SetupStatusRead(**data, problem_message=error_message(data["problem"]))


@router.get("/setup/progress")
def get_progress(request: Request) -> SetupProgressRead:
    return SetupProgressRead.from_snapshot(_manager(request).snapshot())


@router.post("/setup/start", status_code=202)
def start_setup(request: Request, body: StartSetupRequest) -> SetupProgressRead:
    manager = _manager(request)
    try:
        manager.start(body.model)
    except ModelNameError as exc:
        raise _refuse(exc.code) from exc
    except SetupError as exc:
        raise _refuse(exc.code) from exc
    return SetupProgressRead.from_snapshot(manager.snapshot())


@router.post("/setup/pause")
def pause_setup(request: Request) -> SetupProgressRead:
    manager = _manager(request)
    manager.pause()
    return SetupProgressRead.from_snapshot(manager.snapshot())


@router.post("/setup/resume", status_code=202)
def resume_setup(request: Request) -> SetupProgressRead:
    manager = _manager(request)
    try:
        manager.resume()
    except SetupError as exc:
        raise _refuse(exc.code) from exc
    return SetupProgressRead.from_snapshot(manager.snapshot())


@router.get("/setup/events")
async def setup_events(request: Request) -> StreamingResponse:
    """Server-Sent Events: the progress snapshot whenever it changes, until the run ends."""
    manager = _manager(request)

    async def stream() -> AsyncIterator[str]:
        last = ""
        while not await request.is_disconnected():
            snapshot = SetupProgressRead.from_snapshot(manager.snapshot())
            payload = snapshot.model_dump_json()
            if payload != last:
                last = payload
                yield f"event: progress\ndata: {payload}\n\n"
            if snapshot.state in TERMINAL_SETUP_STATES:
                break
            await asyncio.sleep(0.5)

    return StreamingResponse(
        stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"}
    )


# -- models on this computer ---------------------------------------------------------------------


@router.get("/models")
def get_models(request: Request) -> ModelsRead:
    manager = _manager(request)
    try:
        models = manager.models()
    except Exception as exc:
        raise ApiError(503, "ollama_unreachable") from exc
    state, on_disk = manager.whisper.state()
    llm: list[InstalledModelRead] = []
    for m in models:
        info: Any = m["catalog"]
        llm.append(
            InstalledModelRead(
                name=m["name"],
                size_bytes=m["size_bytes"],
                cloud=m["cloud"],
                active=m["active"],
                compat_ok=m["compat_ok"],
                title=info.title if info else None,
                note=info.note if info else None,
                license=info.license if info else None,
                recommended=bool(info and info.recommended),
            )  # fmt: skip
        )
    return ModelsRead(
        active_model=manager.active_model(),
        llm=llm,
        whisper=whisper_info(manager.catalog.whisper, state, on_disk),
        system=_system(request),
    )


@router.post("/models/llm/activate")
def activate_model(request: Request, body: StartSetupRequest) -> ModelsRead:
    try:
        _manager(request).activate(body.model)
    except SetupError as exc:
        raise _refuse(exc.code) from exc
    return get_models(request)


@router.delete("/models/llm/{name:path}", status_code=204)
def delete_model(request: Request, name: str) -> None:
    try:
        _manager(request).delete_llm(name)
    except SetupError as exc:
        raise _refuse(exc.code) from exc


@router.delete("/models/whisper", status_code=204)
def delete_whisper(request: Request) -> None:
    try:
        _manager(request).delete_whisper()
    except SetupError as exc:
        raise _refuse(exc.code) from exc
