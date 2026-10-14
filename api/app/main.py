from collections.abc import AsyncIterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.audio import AfconvertDecoder, Decoder
from app.catalog import Catalog, load_catalog
from app.compat import CompatChecker, OllamaCompatChecker
from app.config import Settings
from app.db import make_engine
from app.downloads import WhisperDownloader
from app.errors import ApiError
from app.generation import GenerationManager, default_prompts_dir
from app.jobs import TranscriptionManager
from app.llm import LLM, OllamaChat
from app.ollama import ModelEngine, OllamaAdmin
from app.routes import router
from app.routes_draft import router as draft_router
from app.routes_setup import router as setup_router
from app.settings_store import LLM_MODEL, llm_model_getter, seed_setting
from app.setup import SetupManager
from app.storage import Storage
from app.transcribe import Transcriber, WhisperCppTranscriber


def create_app(
    settings: Settings | None = None,
    transcriber: Transcriber | None = None,
    decoder: Decoder | None = None,
    llm: LLM | None = None,
    catalog: Catalog | None = None,
    ollama: ModelEngine | None = None,
    whisper: WhisperDownloader | None = None,
    compat: CompatChecker | None = None,
) -> FastAPI:
    """The engines can be swapped in tests; the defaults are the real ones."""
    settings = settings or Settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.models_dir.mkdir(parents=True, exist_ok=True)

    engine = make_engine(settings.data_dir)
    storage = Storage(settings.data_dir)
    seed_setting(engine, LLM_MODEL, settings.llm_model)
    # One worker for all heavy jobs: transcription and drafting never run at the same time.
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="job")
    catalog = catalog or load_catalog()
    whisper = whisper or WhisperDownloader(catalog.whisper, settings.models_dir)
    override = (
        settings.whisper_model
    )  # development/tests: use this file instead of the downloaded one
    manager = TranscriptionManager(
        engine,
        storage,
        transcriber
        or WhisperCppTranscriber(
            settings.whisper_cli,
            (lambda: override) if override else (lambda: whisper.path),
            settings.whisper_threads,
        ),
        decoder or AfconvertDecoder(),
        executor,
    )
    manager.recover()
    prompts_dir = settings.prompts_dir or default_prompts_dir()
    generation = GenerationManager(
        engine,
        llm or OllamaChat(settings.ollama_url, llm_model_getter(engine)),
        executor,
        prompts_dir,
    )
    generation.recover()
    # Downloads are mostly waiting for the network, so they get their own worker.
    setup_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="setup")
    setup = SetupManager(
        engine,
        catalog,
        ollama or OllamaAdmin(settings.ollama_url),
        whisper,
        compat or OllamaCompatChecker(settings.ollama_url, prompts_dir),
        setup_executor,
        settings.models_dir,
        whisper_override=override,
    )
    setup.recover()

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        yield
        manager.stop()
        generation.stop()
        setup.stop()
        executor.shutdown(wait=True, cancel_futures=True)
        setup_executor.shutdown(wait=True, cancel_futures=True)

    app = FastAPI(title="PostCall API", lifespan=lifespan)

    @app.exception_handler(ApiError)
    async def refuse(_request: Request, exc: ApiError) -> JSONResponse:
        # `detail` is the English text, as FastAPI always sends it; a client translates by
        # `code` and `params`.
        return JSONResponse(
            {"detail": exc.detail, "code": exc.code, "params": exc.params},
            status_code=exc.status_code,
            headers=exc.headers,
        )

    app.state.settings = settings
    app.state.engine = engine
    app.state.storage = storage
    app.state.manager = manager
    app.state.generation = generation
    app.state.setup = setup
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Content-Disposition"],  # so the web app can read the export file name
    )
    app.include_router(router)
    app.include_router(draft_router)
    app.include_router(setup_router)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
