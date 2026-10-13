"""Downloading the Whisper model with resume and a checksum, and measuring speed."""

import hashlib
import os
import threading
import time
from collections import deque
from collections.abc import Callable
from pathlib import Path

import httpx

from app.catalog import WhisperModel
from app.errors import Cancelled

CHUNK = 1024 * 1024  # for hashing
READ_CHUNK = 64 * 1024  # small, so that what has arrived is written before a dropped connection


class DownloadError(Exception):
    """A failure with a stable `code` the UI turns into a plain-language message."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class SpeedMeter:
    """Download speed over the last few seconds, and the time left at that speed."""

    def __init__(self, window: float = 5.0, clock: Callable[[], float] = time.monotonic) -> None:
        self._window = window
        self._clock = clock
        self._samples: deque[tuple[float, int]] = deque()

    def add(self, completed: int) -> None:
        now = self._clock()
        self._samples.append((now, completed))
        while len(self._samples) > 2 and now - self._samples[1][0] >= self._window:
            self._samples.popleft()

    def speed(self) -> float | None:
        """Bytes per second, 0 when nothing arrived for a whole window, None before two samples."""
        if len(self._samples) < 2:
            return None
        now = self._clock()
        (t0, c0), (t1, c1) = self._samples[0], self._samples[-1]
        if now - t1 >= self._window:
            return 0.0
        elapsed = t1 - t0
        return (c1 - c0) / elapsed if elapsed > 0 else None

    def eta(self, remaining: int) -> float | None:
        speed = self.speed()
        return remaining / speed if speed else None


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


class WhisperDownloader:
    """Keeps the Whisper model file under `<models_dir>/whisper/`.

    The file is written to `<name>.part` and only renamed once its size and SHA-256 match the
    catalog, so a half-finished or corrupt file is never used. After an interruption the next
    attempt asks the server for the rest with an HTTP Range request.
    """

    def __init__(
        self,
        model: WhisperModel,
        models_dir: Path,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.model = model
        self.path = models_dir / "whisper" / model.file
        self.part_path = self.path.with_name(model.file + ".part")
        self._transport = transport  # tests inject a fake HTTP transport

    def state(self) -> tuple[str, int]:
        """("ready" | "partial" | "missing", bytes on disk)."""
        if self.path.is_file() and self.path.stat().st_size == self.model.size_bytes:
            return "ready", self.model.size_bytes
        if self.part_path.is_file() and self.part_path.stat().st_size > 0:
            return "partial", self.part_path.stat().st_size
        return "missing", 0

    def remaining_bytes(self) -> int:
        state, on_disk = self.state()
        return 0 if state == "ready" else self.model.size_bytes - on_disk

    def verify(self) -> bool:
        return self.path.is_file() and sha256_of(self.path) == self.model.sha256

    def delete(self) -> None:
        self.path.unlink(missing_ok=True)
        self.part_path.unlink(missing_ok=True)

    def download(self, on_progress: Callable[[int, int], None], cancel: threading.Event) -> None:
        total = self.model.size_bytes
        if self.state()[0] == "ready":
            on_progress(total, total)
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        offset = self.part_path.stat().st_size if self.part_path.is_file() else 0
        if offset > total:  # not a prefix of this file: start again
            self.part_path.unlink()
            offset = 0
        try:
            self._fetch(offset, on_progress, cancel)
        except (
            httpx.TransportError,
            httpx.DecodingError,
        ) as exc:  # the connection dropped or stalled
            raise DownloadError("network_error") from exc
        if self.part_path.stat().st_size != total:
            raise DownloadError("network_error")  # the server ended the stream early
        if sha256_of(self.part_path) != self.model.sha256:
            self.part_path.unlink()
            raise DownloadError("checksum_mismatch")
        os.replace(self.part_path, self.path)

    def _fetch(
        self, offset: int, on_progress: Callable[[int, int], None], cancel: threading.Event
    ) -> None:
        total = self.model.size_bytes
        headers = {"Range": f"bytes={offset}-"} if offset else {}
        timeout = httpx.Timeout(connect=10, read=30, write=30, pool=10)
        with (
            httpx.Client(
                timeout=timeout, follow_redirects=True, transport=self._transport
            ) as client,
            client.stream("GET", self.model.url, headers=headers) as response,
        ):
            if response.status_code == 416:  # nothing left to send after `offset`
                if offset != total:
                    self.part_path.unlink(missing_ok=True)
                    raise DownloadError("network_error")
                return
            if response.status_code == 206:
                start = response.headers.get("content-range", "").split(" ")[-1].split("-")[0]
                if start != str(offset):
                    raise DownloadError("download_failed")
                mode = "ab"
            elif response.status_code == 200:
                offset, mode = (
                    0,
                    "wb",
                )  # the server ignored the Range header: start from the beginning
            else:
                raise DownloadError("download_failed")
            expected = response.headers.get("content-length")
            if expected is not None and offset + int(expected) != total:
                raise DownloadError("download_failed")  # not the file the catalog describes
            completed = offset
            with self.part_path.open(mode) as out:
                on_progress(completed, total)
                for chunk in response.iter_bytes(READ_CHUNK):
                    if cancel.is_set():
                        raise Cancelled  # the partial file stays for the next attempt
                    out.write(chunk)
                    completed += len(chunk)
                    on_progress(completed, total)
