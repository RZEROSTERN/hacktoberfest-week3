from collections.abc import Callable

from sqlalchemy.engine import Engine
from sqlmodel import Session

from app.models import AppSetting

LLM_MODEL = "llm_model"


def get_setting(engine: Engine, key: str) -> str | None:
    with Session(engine) as session:
        row = session.get(AppSetting, key)
        return row.value if row else None


def set_setting(engine: Engine, key: str, value: str) -> None:
    with Session(engine) as session:
        session.merge(AppSetting(key=key, value=value))
        session.commit()


def seed_setting(engine: Engine, key: str, value: str | None) -> None:
    """Store `value` only if nothing is stored yet (used to seed the model from the environment)."""
    if value and get_setting(engine, key) is None:
        set_setting(engine, key, value)


def llm_model_getter(engine: Engine) -> Callable[[], str | None]:
    return lambda: get_setting(engine, LLM_MODEL)
