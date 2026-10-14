import os
import subprocess
import sys
import threading
import time

from app.lifecycle import pid_alive, watch_parent


def test_a_running_process_is_alive_and_a_finished_one_is_not() -> None:
    assert pid_alive(os.getpid())
    child = subprocess.Popen([sys.executable, "-c", "pass"])
    child.wait()
    assert not pid_alive(child.pid)


def test_the_watch_fires_once_when_the_parent_disappears() -> None:
    answers = iter([True, True, False])
    fired = threading.Event()
    calls: list[int] = []

    def on_gone() -> None:
        calls.append(1)
        fired.set()

    watch_parent(123, on_gone, interval=0.01, alive=lambda pid: next(answers))
    assert fired.wait(2)
    time.sleep(0.05)
    assert calls == [1]  # and it does not keep firing


def test_the_watch_stays_quiet_while_the_parent_lives() -> None:
    fired = threading.Event()
    watch_parent(os.getpid(), fired.set, interval=0.01)
    assert not fired.wait(0.2)


def test_a_failing_callback_does_not_crash_the_watcher() -> None:
    def boom() -> None:
        raise RuntimeError("boom")

    thread = watch_parent(1, boom, interval=0.01, alive=lambda pid: False)
    thread.join(2)
    assert not thread.is_alive()
