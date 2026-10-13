from datetime import datetime

from pydantic import BaseModel

from app.models import Call, CallStatus, Segment

ERROR_MESSAGES = {
    "engine_missing": "The transcription engine is not available.",
    "model_missing": "The speech model has not been downloaded yet.",
    "decoder_missing": "The macOS audio converter is missing, so audio files cannot be read.",
    "decode_failed": "The audio file could not be read. Try exporting it again as mp3, m4a or wav.",
    "transcribe_failed": "Something went wrong while transcribing. You can try again.",
    "interrupted": "The app was closed while transcribing. You can try again.",
    "audio_missing": "The audio file is no longer available. Please upload it again.",
}


class CallRead(BaseModel):
    id: str
    title: str
    created_at: datetime
    status: CallStatus
    progress: float
    error_code: str | None
    error_message: str | None
    language: str | None
    duration_s: float | None
    keep_audio: bool
    audio_available: bool

    @classmethod
    def from_call(cls, call: Call, audio_available: bool) -> "CallRead":
        return cls(
            id=call.id,
            title=call.title,
            created_at=call.created_at,
            status=call.status,
            progress=call.progress,
            error_code=call.error_code,
            error_message=ERROR_MESSAGES.get(call.error_code, "Something went wrong.")
            if call.error_code
            else None,
            language=call.language,
            duration_s=call.duration_s,
            keep_audio=call.keep_audio,
            audio_available=audio_available,
        )


class SegmentRead(BaseModel):
    """`id` is the segment id that notes and proposals cite as their source."""

    id: int
    start: float
    end: float
    text: str

    @classmethod
    def from_segment(cls, segment: Segment) -> "SegmentRead":
        return cls(id=segment.idx, start=segment.start, end=segment.end, text=segment.text)


class TranscriptRead(BaseModel):
    call_id: str
    language: str | None
    duration_s: float | None
    segments: list[SegmentRead]
