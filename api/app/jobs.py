import logging
import threading
import wave
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy.engine import Engine
from sqlmodel import Session, col, delete, select

from app.audio import Decoder, TranscriptionError, wav_duration
from app.errors import Cancelled
from app.models import ACTIVE_STATUSES, Call, CallStatus, Segment
from app.storage import Storage
from app.transcribe import Transcriber, TranscriptResult

# Only ids and statuses are logged here, never file names, transcript text or notes.
log = logging.getLogger("scopewise.jobs")


class TranscriptionManager:
    """Queues transcriptions on the shared worker thread and tracks their cancellation."""

    def __init__(
        self,
        engine: Engine,
        storage: Storage,
        transcriber: Transcriber,
        decoder: Decoder,
        executor: ThreadPoolExecutor,
    ) -> None:
        self._engine = engine
        self._storage = storage
        self._transcriber = transcriber
        self._decoder = decoder
        self._executor = executor
        self._cancels: dict[str, threading.Event] = {}
        self._lock = threading.Lock()
        self._stopping = False

    def recover(self) -> None:
        """Jobs left running by a previous session cannot continue: mark them as interrupted."""
        with Session(self._engine) as session:
            for call in session.exec(
                select(Call).where(col(Call.status).in_(ACTIVE_STATUSES))
            ).all():
                call.status = CallStatus.FAILED
                call.error_code = "interrupted"
                session.add(call)
                self._storage.remove_tmp(call.id)
            session.commit()

    def is_active(self, call_id: str) -> bool:
        with self._lock:
            return call_id in self._cancels

    def submit(self, call_id: str) -> None:
        with self._lock:
            if call_id in self._cancels:
                return
            self._cancels[call_id] = threading.Event()
        self._executor.submit(self._run, call_id)

    def cancel(self, call_id: str) -> None:
        with self._lock:
            event = self._cancels.get(call_id)
        if event is not None:
            event.set()

    def stop(self) -> None:
        """Stop the running job but keep its audio, so it shows as interrupted next time."""
        self._stopping = True
        with self._lock:
            for event in self._cancels.values():
                event.set()

    def _run(self, call_id: str) -> None:
        with self._lock:
            cancel = self._cancels[call_id]
        try:
            self._execute(call_id, cancel)
        except Cancelled:
            if not self._stopping:
                self._storage.remove_audio(call_id)
                self._update(call_id, status=CallStatus.CANCELLED)
        except TranscriptionError as exc:
            # The original stays on disk so the user can retry without uploading again.
            self._update(call_id, status=CallStatus.FAILED, error_code=exc.code)
        except Exception:
            log.exception("unexpected failure in job %s", call_id)
            self._update(call_id, status=CallStatus.FAILED, error_code="transcribe_failed")
        finally:
            self._storage.remove_tmp(call_id)
            with self._lock:
                self._cancels.pop(call_id, None)

    def _execute(self, call_id: str, cancel: threading.Event) -> None:
        if cancel.is_set():
            raise Cancelled
        with Session(self._engine) as session:
            call = session.get(Call, call_id)
            if call is None:
                return
            source = self._storage.original(call)
            keep_audio = call.keep_audio
        if not source.is_file():
            raise TranscriptionError("audio_missing")

        self._update(call_id, status=CallStatus.CONVERTING, progress=0.0, error_code=None)
        tmp = self._storage.tmp_dir(call_id)
        tmp.mkdir(parents=True, exist_ok=True)
        wav = tmp / "audio.wav"
        self._decoder.to_wav(source, wav)
        try:
            duration = wav_duration(wav)
        except (wave.Error, EOFError, OSError) as exc:
            raise TranscriptionError("decode_failed") from exc
        if cancel.is_set():
            raise Cancelled

        self._update(call_id, status=CallStatus.TRANSCRIBING, duration_s=duration)
        last = [0.0]

        def on_progress(value: float) -> None:
            value = min(value, 0.99)  # 100% is reserved for "saved"
            if value - last[0] >= 0.01:
                last[0] = value
                self._advance(call_id, value)

        result = self._transcriber.transcribe(wav, tmp, on_progress, cancel)
        if cancel.is_set():
            raise Cancelled
        self._save(call_id, result)
        if not keep_audio:
            self._storage.remove_audio(call_id)

    def _update(self, call_id: str, **fields: object) -> None:
        with Session(self._engine) as session:
            call = session.get(Call, call_id)
            if call is None:
                return
            for key, value in fields.items():
                setattr(call, key, value)
            session.add(call)
            session.commit()

    def _advance(self, call_id: str, value: float) -> None:
        """Progress only moves forward, even when a second pass restarts the engine."""
        with Session(self._engine) as session:
            call = session.get(Call, call_id)
            if call is not None and value > call.progress:
                call.progress = value
                session.add(call)
                session.commit()

    def _save(self, call_id: str, result: TranscriptResult) -> None:
        with Session(self._engine) as session:
            call = session.get(Call, call_id)
            if call is None:
                return
            session.exec(delete(Segment).where(col(Segment.call_id) == call_id))
            for idx, seg in enumerate(result.segments):
                session.add(
                    Segment(call_id=call_id, idx=idx, start=seg.start, end=seg.end, text=seg.text)
                )
            call.language = result.language
            call.status = CallStatus.DONE
            call.progress = 1.0
            call.error_code = None
            session.add(call)
            session.commit()
