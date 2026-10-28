"""Behaviour that must be the same on macOS, Linux and Windows.

These run on every system; the Windows-only branches themselves can only be exercised on Windows, so
what is pinned here is the contract: no signals to test for a process, graceful shutdown by flag,
paths with awkward characters, and a flag that is zero where it must be.
"""

import ast
import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlmodel import Session, text

from app import __main__ as entry
from app.config import Settings
from app.db import make_engine
from app.lifecycle import pid_alive
from app.proc import NO_WINDOW
from app.system import total_ram_bytes


def test_the_app_package_uses_no_unix_only_process_or_system_calls() -> None:
    """A guard, because these calls exist on Unix only or mean something else on Windows.

    `os.kill` terminates its target on Windows, `os.killpg` and `os.sysconf` do not exist there. The
    right calls live in psutil, which picks the right one for each system.
    """
    banned = {
        ("os", "kill"),
        ("os", "killpg"),
        ("os", "sysconf"),
        ("os", "getpgid"),
        ("os", "fork"),
    }
    found = []
    for path in sorted(Path(entry.__file__).parent.glob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and (node.func.value.id, node.func.attr) in banned
            ):
                found.append(f"{path.name}:{node.lineno} os.{node.func.attr}")
    assert found == []


def test_a_finished_process_is_not_alive() -> None:
    child = subprocess.Popen([sys.executable, "-c", "pass"])
    child.wait()
    assert not pid_alive(child.pid)


def test_the_server_binds_the_loopback_address_it_is_given(settings: Settings) -> None:
    server = entry.build_server(settings)
    assert (server.config.host, server.config.port) == ("127.0.0.1", 8000)


def test_shutdown_is_a_flag_not_a_signal(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbidden(*args: object) -> None:
        raise AssertionError("shutdown must not signal the process")

    monkeypatch.setattr(os, "kill", forbidden)
    server = entry.build_server(settings)
    assert not server.should_exit
    entry.request_shutdown(server)
    assert server.should_exit


def test_main_watches_the_desktop_app_and_stops_the_server_when_it_goes(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    watched: dict[str, object] = {}

    class FakeServer:
        should_exit = False
        ran = False

        def run(self) -> None:
            FakeServer.ran = True

    server = FakeServer()
    monkeypatch.setattr(entry, "Settings", lambda: settings.model_copy(update={"parent_pid": 4321}))
    monkeypatch.setattr(entry, "build_server", lambda _settings: server)

    def fake_watch(pid: int, on_gone: object) -> None:
        watched["pid"] = pid
        watched["on_gone"] = on_gone

    monkeypatch.setattr(entry, "watch_parent", fake_watch)
    entry.main()
    assert FakeServer.ran and watched["pid"] == 4321
    assert callable(watched["on_gone"])
    watched["on_gone"]()  # the desktop app disappeared
    assert server.should_exit


def test_the_database_opens_in_a_folder_with_awkward_characters(tmp_path: Path) -> None:
    # Windows user names can hold spaces, accents, `#` and `%`; a URL string would misread them.
    folder = tmp_path / "Marco Ramírez #1 100%"
    folder.mkdir()
    engine = make_engine(folder)
    with Session(engine) as session:
        assert session.exec(text("select 1")).scalar() == 1  # type: ignore[call-overload]
    assert (folder / "postcall.db").is_file()


def test_total_memory_is_reported() -> None:
    assert total_ram_bytes() > 256 << 20


def test_the_hidden_window_flag_is_zero_except_on_windows() -> None:
    assert (NO_WINDOW == 0) == (sys.platform != "win32")
