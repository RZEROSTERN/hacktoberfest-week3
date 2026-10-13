import os
import threading
from pathlib import Path

import pytest

from app.catalog import WhisperModel
from app.downloads import DownloadError, SpeedMeter, WhisperDownloader
from app.errors import Cancelled
from app.ollama import LayerProgress
from tests.range_server import RangeServer

DATA = os.urandom(3 * 1024 * 1024 + 123)  # a little over three chunks


def model_for(server: RangeServer, **overrides: object) -> WhisperModel:
    fields = {
        "id": "test",
        "title": "Test model",
        "file": "test.bin",
        "url": server.url,
        "size_bytes": len(server.data),
        "sha256": server.sha256,
        "license": "MIT",
        "note": "",
    }
    fields.update(overrides)
    return WhisperModel.model_validate(fields)


class Recorder:
    def __init__(self) -> None:
        self.values: list[int] = []

    def __call__(self, completed: int, total: int) -> None:
        self.values.append(completed)


def test_full_download_is_verified_and_put_in_place(tmp_path: Path) -> None:
    with RangeServer(DATA) as server:
        downloader = WhisperDownloader(model_for(server), tmp_path)
        assert downloader.state() == ("missing", 0)
        seen = Recorder()
        downloader.download(seen, threading.Event())
    assert downloader.path.read_bytes() == DATA
    assert not downloader.part_path.exists()
    assert downloader.state() == ("ready", len(DATA)) and downloader.verify()
    assert seen.values == sorted(seen.values) and seen.values[-1] == len(DATA)  # only moves forward


def test_a_dropped_connection_keeps_the_partial_file_and_the_next_attempt_resumes(
    tmp_path: Path,
) -> None:
    with RangeServer(DATA) as server:
        downloader = WhisperDownloader(model_for(server), tmp_path)
        server.drop_after = 1_500_000
        with pytest.raises(DownloadError) as err:
            downloader.download(Recorder(), threading.Event())
        assert err.value.code == "network_error"
        state, on_disk = downloader.state()
        assert state == "partial" and 0 < on_disk < len(DATA) and not downloader.path.exists()

        seen = Recorder()
        downloader.download(seen, threading.Event())
        assert server.requests[-1] == f"bytes={on_disk}-"  # it asked only for the rest
        assert seen.values[0] == on_disk  # and progress continued from where it stopped
    assert downloader.path.read_bytes() == DATA


def test_a_server_that_ignores_range_restarts_from_the_beginning(tmp_path: Path) -> None:
    with RangeServer(DATA) as server:
        downloader = WhisperDownloader(model_for(server), tmp_path)
        downloader.part_path.parent.mkdir(parents=True)
        downloader.part_path.write_bytes(DATA[:1000])
        server.ignore_range = True
        downloader.download(Recorder(), threading.Event())
    assert downloader.path.read_bytes() == DATA


def test_pausing_keeps_the_partial_file_and_resuming_finishes_it(tmp_path: Path) -> None:
    with RangeServer(DATA) as server:
        downloader = WhisperDownloader(model_for(server), tmp_path)
        pause = threading.Event()

        def pause_after_first_chunk(completed: int, total: int) -> None:
            if completed >= 1024 * 1024:
                pause.set()

        with pytest.raises(Cancelled):
            downloader.download(pause_after_first_chunk, pause)
        assert downloader.state()[0] == "partial"
        downloader.download(Recorder(), threading.Event())
    assert downloader.path.read_bytes() == DATA


def test_a_wrong_checksum_throws_the_file_away(tmp_path: Path) -> None:
    with RangeServer(DATA) as server:
        downloader = WhisperDownloader(model_for(server, sha256="0" * 64), tmp_path)
        with pytest.raises(DownloadError) as err:
            downloader.download(Recorder(), threading.Event())
    assert err.value.code == "checksum_mismatch"
    assert downloader.state() == ("missing", 0) and not downloader.path.exists()  # never used


def test_a_file_of_the_wrong_size_is_refused(tmp_path: Path) -> None:
    with RangeServer(DATA) as server:
        downloader = WhisperDownloader(model_for(server, size_bytes=len(DATA) + 5), tmp_path)
        with pytest.raises(DownloadError) as err:
            downloader.download(Recorder(), threading.Event())
    assert err.value.code == "download_failed"


def test_a_finished_but_unrenamed_part_file_is_completed_without_downloading(
    tmp_path: Path,
) -> None:
    with RangeServer(DATA) as server:
        downloader = WhisperDownloader(model_for(server), tmp_path)
        downloader.part_path.parent.mkdir(parents=True)
        downloader.part_path.write_bytes(
            DATA
        )  # everything arrived, the app closed before the rename
        downloader.download(
            Recorder(), threading.Event()
        )  # the server answers 416: nothing left to send
    assert downloader.path.read_bytes() == DATA


def test_nothing_is_downloaded_when_the_model_is_already_there(tmp_path: Path) -> None:
    with RangeServer(DATA) as server:
        downloader = WhisperDownloader(model_for(server), tmp_path)
        downloader.path.parent.mkdir(parents=True)
        downloader.path.write_bytes(DATA)
        seen = Recorder()
        downloader.download(seen, threading.Event())
        assert server.requests == [] and seen.values == [len(DATA)]
        assert downloader.remaining_bytes() == 0


def test_unreachable_server_is_a_network_error(tmp_path: Path) -> None:
    with RangeServer(DATA) as server:
        model = model_for(server)
    downloader = WhisperDownloader(model, tmp_path)  # the server is stopped now
    with pytest.raises(DownloadError) as err:
        downloader.download(Recorder(), threading.Event())
    assert err.value.code == "network_error"


def test_delete_removes_the_file_and_any_partial(tmp_path: Path) -> None:
    with RangeServer(DATA) as server:
        downloader = WhisperDownloader(model_for(server), tmp_path)
        downloader.download(Recorder(), threading.Event())
        downloader.part_path.write_bytes(b"x")
        downloader.delete()
    assert downloader.state() == ("missing", 0)


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def test_speed_and_time_left() -> None:
    clock = FakeClock()
    meter = SpeedMeter(window=5, clock=clock)
    assert meter.speed() is None and meter.eta(100) is None
    meter.add(0)
    clock.now = 2
    meter.add(20_000_000)
    assert meter.speed() == pytest.approx(10_000_000)
    assert meter.eta(50_000_000) == pytest.approx(5)


def test_speed_uses_only_the_recent_window_and_drops_to_zero_when_stalled() -> None:
    clock = FakeClock()
    meter = SpeedMeter(window=5, clock=clock)
    meter.add(0)
    for second in range(1, 11):  # fast for 10 seconds, then slow
        clock.now = second
        meter.add(second * 10_000_000 if second <= 5 else 50_000_000 + (second - 5) * 1_000_000)
    assert meter.speed() == pytest.approx(
        1_000_000, rel=0.3
    )  # the slow recent speed, not the average
    clock.now = 30
    assert meter.speed() == 0.0 and meter.eta(1000) is None  # nothing arrived for a while


def test_layer_progress_sums_layers_and_never_goes_backwards() -> None:
    progress = LayerProgress()
    assert progress.update("a", 1000, 400) == (400, 1000)
    assert progress.update("a", 1000, 1000) == (1000, 1000)
    completed, total = progress.update("b", 50, 0)  # a new layer starts at 0 and adds to the total
    assert completed >= 1000 and total == 1050
    assert progress.update("a", 1000, 1000)[0] >= 1000
    assert progress.finish() == (1050, 1050)


def test_layer_progress_never_reports_less_than_before_even_if_ollama_restarts_a_layer() -> None:
    progress = LayerProgress()
    progress.update("a", 1000, 800)
    assert (
        progress.update("a", 1000, 300)[0] == 800
    )  # after a retry the layer count may restart lower
