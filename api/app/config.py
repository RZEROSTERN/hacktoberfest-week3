from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All configuration comes from SCOPEWISE_* environment variables.

    Nothing is defaulted except the loopback bind address: the desktop shell (or
    `make dev`) decides ports, directories and the Ollama URL.
    """

    model_config = SettingsConfigDict(env_prefix="SCOPEWISE_")

    host: str = "127.0.0.1"
    port: int = Field(ge=1, le=65535)
    data_dir: Path
    models_dir: Path
    ollama_url: str
    cors_origins: list[str] = []
