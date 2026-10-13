from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.audio import AfconvertDecoder, Decoder
from app.config import Settings
from app.db import make_engine
from app.jobs import TranscriptionManager
from app.routes import router
from app.storage import Storage
from app.transcribe import Transcriber, WhisperCppTranscriber


def create_app(
    settings: Settings | None = None,
    transcriber: Transcriber | None = None,
    decoder: Decoder | None = None,
) -> FastAPI:
    """`transcriber` and `decoder` can be replaced in tests; the defaults are the real engines."""
    settings = settings or Settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.models_dir.mkdir(parents=True, exist_ok=True)

    engine = make_engine(settings.data_dir)
    storage = Storage(settings.data_dir)
    manager = TranscriptionManager(
        engine,
        storage,
        transcriber
        or WhisperCppTranscriber(
            settings.whisper_cli, settings.whisper_model, settings.whisper_threads
        ),
        decoder or AfconvertDecoder(),
    )
    manager.recover()

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        yield
        manager.shutdown()

    app = FastAPI(title="Scopewise API", lifespan=lifespan)
    app.state.settings = settings
    app.state.engine = engine
    app.state.storage = storage
    app.state.manager = manager
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
