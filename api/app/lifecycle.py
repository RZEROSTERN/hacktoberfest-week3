import contextlib
import threading
import time
from collections.abc import Callable

import psutil


def pid_alive(pid: int) -> bool:
    """Whether a process with this id exists, on any system.

    Not `os.kill(pid, 0)`: that only tests for existence on Unix. On Windows every signal except the
    two console ones terminates the process, so the watcher would have killed the desktop app.
    """
    return psutil.pid_exists(pid)


def watch_parent(
    pid: int,
    on_gone: Callable[[], None],
    interval: float = 2.0,
    alive: Callable[[int], bool] = pid_alive,
) -> threading.Thread:
    """Call `on_gone` once the desktop app (`pid`) has disappeared, even if it was killed outright.

    The api then shuts itself down, which also stops any `whisper-cli` it started, so a crashed app
    never leaves work running in the background.
    """

    def run() -> None:
        while True:
            time.sleep(interval)
            if not alive(pid):
                with contextlib.suppress(Exception):
                    on_gone()
                return

    thread = threading.Thread(target=run, name="parent-watch", daemon=True)
    thread.start()
    return thread
