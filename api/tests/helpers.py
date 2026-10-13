from fastapi import FastAPI
from sqlmodel import Session

from app.models import Call, CallStatus, Segment

TRANSCRIPT = [
    (0.0, "Kevin tiene una pizzería con dos locales en Cancún."),
    (5.0, "El problema es que la manejamos por Facebook y tiene limitaciones."),
    (12.0, "Queremos reservaciones sin mandar mensajes por Facebook."),
]


def add_done_call(
    app: FastAPI, call_id: str = "call1", language: str = "es", count: int | None = None
) -> str:
    """Insert a finished call with a transcript, as if transcription had run."""
    with Session(app.state.engine) as session:
        session.add(
            Call(
                id=call_id,
                title="x.mp3",
                audio_ext=".mp3",
                status=CallStatus.DONE,
                language=language,
            )
        )
        segments = (
            TRANSCRIPT
            if count is None
            else [(i * 60.0, f"Segmento {i} del cliente.") for i in range(count)]
        )
        for idx, (start, text) in enumerate(segments):
            session.add(Segment(call_id=call_id, idx=idx, start=start, end=start + 4, text=text))
        session.commit()
    return call_id
