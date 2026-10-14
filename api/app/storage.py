import shutil
from pathlib import Path

from app.models import Call


class Storage:
    """File locations under the data directory. Names come from ids, never from user input."""

    def __init__(self, data_dir: Path) -> None:
        self._data_dir = data_dir

    def audio_dir(self, call_id: str) -> Path:
        return self._data_dir / "audio" / call_id

    def original(self, call: Call) -> Path:
        return self.audio_dir(call.id) / f"original{call.audio_ext}"

    def tmp_dir(self, call_id: str) -> Path:
        return self._data_dir / "tmp" / call_id

    def audio_exists(self, call: Call) -> bool:
        return self.original(call).is_file()

    def remove_audio(self, call_id: str) -> None:
        shutil.rmtree(self.audio_dir(call_id), ignore_errors=True)

    def remove_tmp(self, call_id: str) -> None:
        shutil.rmtree(self.tmp_dir(call_id), ignore_errors=True)
