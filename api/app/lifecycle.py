import contextlib
import os
import threading
import time
from collections.abc import Callable


def pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)  # signal 0 only checks that the process exists
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # it exists, it just is not ours
    return True


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
