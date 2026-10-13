import stat
import textwrap
import threading
from pathlib import Path

import pytest

from app.audio import TranscriptionError
from app.errors import Cancelled
from app.transcribe import (
    TranscribedSegment,
    WhisperCppTranscriber,
    looks_degenerate,
)

# A stand-in for whisper-cli: prints progress to stderr and writes <prefix>.json like the real one.
FAKE_CLI = textwrap.dedent(
    """\
    #!/usr/bin/env python3
    import json, sys, time
    args = sys.argv[1:]
    prefix = args[args.index("-of") + 1]
    mode = open(args[args.index("-m") + 1]).read().strip()
    if mode == "slow":
        for _ in range(100):
            time.sleep(0.1)
    if mode == "crash":
        sys.exit(3)
    if mode == "flood" and "-mc" not in args:
        texts = ["bueno", "y"] * 15
    else:
        texts = ["Hola, necesitamos un sistema de reservaciones para el negocio."]
    for pct in (10, 60, 100):
        print(f"whisper_print_progress_callback: progress = {pct}%", file=sys.stderr, flush=True)
    items = [
        {"offsets": {"from": i * 1000, "to": i * 1000 + 900}, "text": " " + t}
        for i, t in enumerate(texts)
    ]
    items.append({"offsets": {"from": 99000, "to": 99500}, "text": "  "})
    json.dump({"result": {"language": "es"}, "transcription": items}, open(prefix + ".json", "w"))
    """
)


def make_cli(tmp_path: Path, mode: str) -> WhisperCppTranscriber:
    cli = tmp_path / "whisper-cli"
    cli.write_text(FAKE_CLI)
    cli.chmod(cli.stat().st_mode | stat.S_IEXEC)
    model = tmp_path / "model.bin"
    model.write_text(mode)
    return WhisperCppTranscriber(cli, model, threads=1)


def segments(*texts: str) -> list[TranscribedSegment]:
    return [TranscribedSegment(i, i + 1, t) for i, t in enumerate(texts)]


def test_parses_segments_language_and_progress(tmp_path: Path) -> None:
    seen: list[float] = []
    result = make_cli(tmp_path, "ok").transcribe(
        tmp_path / "a.wav", tmp_path, seen.append, threading.Event()
    )
    assert result.language == "es"
    assert [s.text for s in result.segments] == [
        "Hola, necesitamos un sistema de reservaciones para el negocio."
    ]
    assert result.segments[0].start == 0.0 and result.segments[0].end == 0.9
    assert seen == [0.1, 0.6, 1.0]  # blank segments are dropped, progress comes from stderr


def test_missing_engine_or_model_gives_clear_errors(tmp_path: Path) -> None:
    no_cli = WhisperCppTranscriber(None, None, 1)
    with pytest.raises(TranscriptionError) as engine:
        no_cli.transcribe(tmp_path / "a.wav", tmp_path, lambda _p: None, threading.Event())
    assert engine.value.code == "engine_missing"

    make_cli(tmp_path, "ok")  # creates the fake whisper-cli next to a model file we do not use
    no_model = WhisperCppTranscriber(tmp_path / "whisper-cli", tmp_path / "absent.bin", 1)
    with pytest.raises(TranscriptionError) as model:
        no_model.transcribe(tmp_path / "a.wav", tmp_path, lambda _p: None, threading.Event())
    assert model.value.code == "model_missing"


def test_engine_crash_is_a_transcription_error(tmp_path: Path) -> None:
    with pytest.raises(TranscriptionError) as err:
        make_cli(tmp_path, "crash").transcribe(
            tmp_path / "a.wav", tmp_path, lambda _p: None, threading.Event()
        )
    assert err.value.code == "transcribe_failed"


def test_cancel_terminates_the_process(tmp_path: Path) -> None:
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(Cancelled):
        make_cli(tmp_path, "slow").transcribe(tmp_path / "a.wav", tmp_path, lambda _p: None, cancel)


def test_fragment_flood_is_rerun_with_no_context(tmp_path: Path) -> None:
    result = make_cli(tmp_path, "flood").transcribe(
        tmp_path / "a.wav", tmp_path, lambda _p: None, threading.Event()
    )
    assert len(result.segments) == 1  # the second pass (-mc 0) returned the healthy transcript


def test_looks_degenerate() -> None:
    flood = segments(*["bueno", "y"] * 15)
    healthy = segments(*["Necesitamos un menú más elegante para los clientes."] * 40)
    mostly_fine = segments(
        *(["sí"] * 5 + ["Quiero reservaciones en línea sin mandar mensajes."] * 25)
    )
    assert looks_degenerate(flood)
    assert not looks_degenerate(healthy)
    assert not looks_degenerate(mostly_fine)
    assert not looks_degenerate(segments("bueno", "y"))  # too few segments to judge
