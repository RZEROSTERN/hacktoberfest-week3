from collections.abc import AsyncIterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.audio import AfconvertDecoder, Decoder
from app.config import Settings
from app.db import make_engine
from app.generation import GenerationManager, default_prompts_dir
from app.jobs import TranscriptionManager
from app.llm import LLM, OllamaChat
from app.routes import router
from app.routes_draft import router as draft_router
from app.settings_store import LLM_MODEL, llm_model_getter, seed_setting
from app.storage import Storage
from app.transcribe import Transcriber, WhisperCppTranscriber


def create_app(
    settings: Settings | None = None,
    transcriber: Transcriber | None = None,
    decoder: Decoder | None = None,
    llm: LLM | None = None,
) -> FastAPI:
    """`transcriber`, `decoder` and `llm` can be swapped in tests; the defaults are real."""
    settings = settings or Settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.models_dir.mkdir(parents=True, exist_ok=True)

    engine = make_engine(settings.data_dir)
    storage = Storage(settings.data_dir)
    seed_setting(engine, LLM_MODEL, settings.llm_model)
    # One worker for all heavy jobs: transcription and drafting never run at the same time.
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="job")
    manager = TranscriptionManager(
        engine,
        storage,
        transcriber
        or WhisperCppTranscriber(
            settings.whisper_cli, settings.whisper_model, settings.whisper_threads
        ),
        decoder or AfconvertDecoder(),
        executor,
    )
    manager.recover()
    generation = GenerationManager(
        engine,
        llm or OllamaChat(settings.ollama_url, llm_model_getter(engine)),
        executor,
        settings.prompts_dir or default_prompts_dir(),
    )
    generation.recover()

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        yield
        manager.stop()
        generation.stop()
        executor.shutdown(wait=True, cancel_futures=True)

    app = FastAPI(title="Scopewise API", lifespan=lifespan)
    app.state.settings = settings
    app.state.engine = engine
    app.state.storage = storage
    app.state.manager = manager
    app.state.generation = generation
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)
    app.include_router(draft_router)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
