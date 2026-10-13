import threading
from collections.abc import Callable

from app.errors import Cancelled
from app.ollama import InstalledModel, OllamaError


class FakeOllama:
    """A scripted model engine: models it has, and what a pull does."""

    def __init__(self, installed: list[str] | None = None) -> None:
        self.models: dict[str, InstalledModel] = {
            n: InstalledModel(n, 1000, None) for n in installed or []
        }
        self.up = True
        self.pulled: list[str] = []
        self.deleted: list[str] = []
        # A pull sends these (completed, total) pairs and then adds the model.
        self.steps: list[tuple[int, int]] = [(100, 1000), (600, 1000), (1000, 1000)]
        self.fail_after: int | None = None  # raise after this many steps, once
        self.fail_with = "network_error"
        self.gate: threading.Event | None = None  # blocks the pull until set (or cancelled)
        self.remote_host: str | None = None  # make the pulled model a cloud model
        self.start_at = 0  # resume from this step, as a re-pull continues from the layers on disk

    def add(self, name: str, size: int = 1000, remote_host: str | None = None) -> None:
        self.models[name] = InstalledModel(name, size, remote_host)

    def reachable(self) -> bool:
        return self.up

    def list_models(self) -> list[InstalledModel]:
        if not self.up:
            raise OllamaError("ollama_unreachable")
        return list(self.models.values())

    def installed(self, name: str) -> InstalledModel | None:
        wanted = name if ":" in name else f"{name}:latest"
        return next((m for m in self.list_models() if m.name == wanted), None)

    def delete(self, name: str) -> None:
        self.models.pop(name, None)
        self.deleted.append(name)

    def pull(
        self, name: str, on_progress: Callable[[int, int], None], cancel: threading.Event
    ) -> None:
        self.pulled.append(name)
        for index in range(self.start_at, len(self.steps)):
            if cancel.is_set():
                raise Cancelled
            if self.gate is not None and index == 1:
                while not self.gate.wait(timeout=0.05):
                    if cancel.is_set():
                        raise Cancelled
            on_progress(*self.steps[index])
            if self.fail_after is not None and index + 1 >= self.fail_after:
                self.fail_after = None
                self.start_at = index  # the next attempt continues from here
                raise OllamaError(self.fail_with)
        self.models[name] = InstalledModel(name, self.steps[-1][1], self.remote_host)
