from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All configuration comes from POSTCALL_* environment variables.

    Nothing is defaulted except the loopback bind address: the desktop shell (or
    `make dev`) decides ports, directories and the Ollama URL.
    """

    model_config = SettingsConfigDict(env_prefix="POSTCALL_")

    host: str = "127.0.0.1"
    port: int = Field(ge=1, le=65535)
    data_dir: Path
    models_dir: Path
    ollama_url: str
    cors_origins: list[str] = []

    # Transcription engine. Both are optional so the api still starts before the models are
    # downloaded; a transcription then fails with a clear "engine/model missing" error.
    whisper_cli: Path | None = None
    whisper_model: Path | None = None
    whisper_threads: int = Field(default=4, ge=1)

    # Language model. The tag is NOT hard-coded anywhere: the model in use is read from the local
    # settings table. This variable only seeds that table on start when nothing is stored yet
    # (development); the setup wizard writes it in the packaged app.
    llm_model: str | None = None

    # Folder with the versioned prompt files; defaults to the `prompts` folder next to the app
    # package (which is also where the packaged binary unpacks it).
    prompts_dir: Path | None = None

    # Process id of the desktop app that started this api. When it disappears the api shuts down.
    parent_pid: int | None = None
