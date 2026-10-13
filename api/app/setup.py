"""First-launch setup and model management: get the models, verify them, check they work.

One run goes through six steps: prepare the engine, download the language model, download the speech
model, verify both, check the language model can do the app's task, ready. A run can be paused and
resumed, and a run cut short by closing the app is offered again on the next launch (it is never
resumed silently, because downloading is the user's decision).
"""

import logging
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy.engine import Engine
from sqlmodel import Session

from app.catalog import Catalog, validate_model_name
from app.compat import CompatChecker, CompatError
from app.downloads import DownloadError, SpeedMeter, WhisperDownloader
from app.errors import Cancelled
from app.models import SetupRun, SetupState
from app.ollama import InstalledModel, ModelEngine, OllamaError
from app.settings_store import LLM_MODEL, compat_key, delete_setting, get_setting, set_setting
from app.system import free_disk_bytes

log = logging.getLogger("scopewise.setup")

MARGIN_BYTES = 1 << 30  # working room kept free on top of the downloads
ENGINE_WAIT_SECONDS = 30
PERSIST_EVERY = 2.0

STEP_IDS = ("engine", "llm", "whisper", "verify", "compat", "ready")
LABELS = {
    "engine": "Preparing the local AI engine",
    "llm": "Downloading the language model",
    "whisper": "Downloading the speech model",
    "verify": "Verifying the downloads",
    "compat": "Checking that the model works",
    "ready": "Ready",
}
# How much of the overall bar each step is worth. A step that has nothing to do counts as 1.
WEIGHTS = {"engine": 3, "llm": 50, "whisper": 15, "verify": 5, "compat": 27, "ready": 0}


class SetupError(Exception):
    """A failure with a stable `code` the UI turns into a plain-language message."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass
class Step:
    id: str
    state: str = "pending"  # pending | running | done | failed
    completed: int = 0
    total: int = 0
    detail: str | None = None
    skipped: bool = False  # nothing to do: already on this computer
    meter: SpeedMeter = field(default_factory=SpeedMeter)


class SetupManager:
    def __init__(
        self,
        engine: Engine,
        catalog: Catalog,
        ollama: ModelEngine,
        whisper: WhisperDownloader,
        compat: CompatChecker,
        executor: ThreadPoolExecutor,
        models_dir: Path,
        whisper_override: Path | None = None,
        free_disk: Callable[[Path], int] | None = None,
    ) -> None:
        self._engine = engine
        self.catalog = catalog
        self.ollama = ollama
        self.whisper = whisper
        self._compat = compat
        self._executor = executor
        self._models_dir = models_dir
        self._whisper_override = (
            whisper_override  # development/test file used instead of the download
        )
        self._free_disk = free_disk or (lambda path: free_disk_bytes(path))  # looked up when called
        self._lock = threading.Lock()
        self._cancel = threading.Event()
        self._stopping = False
        self._state = SetupState.IDLE
        self._model: str | None = None
        self._error: str | None = None
        self._fraction = 0.0
        self._steps = self._new_steps()
        self._last_persist = 0.0

    # -- lifecycle -------------------------------------------------------------------------------

    def recover(self) -> None:
        """Load the last run. One that was running when the app closed is now interrupted."""
        with Session(self._engine) as session:
            run = session.get(SetupRun, 1)
        if run is None:
            return
        self._model, self._error, self._fraction = (
            run.llm_model,
            run.error_code,
            run.overall_fraction,
        )
        self._state = SetupState.INTERRUPTED if run.state == SetupState.RUNNING else run.state
        if run.steps:
            self._steps = [
                Step(
                    s["id"],
                    s["state"],
                    s["completed"],
                    s["total"],
                    s.get("detail"),
                    s.get("skipped", False),
                )
                for s in run.steps
            ]
        # The file on disk is the truth about a partly downloaded speech model, not the last save.
        state, on_disk = self.whisper.state()
        if state == "partial":
            step = self._step("whisper")
            step.completed = max(step.completed, on_disk)
            step.total = max(step.total, self.whisper.model.size_bytes)
            self._update_fraction()
        self._persist()

    def stop(self) -> None:
        self._stopping = True
        self._cancel.set()

    def start(self, model: str) -> None:
        """Begin a run for `model` (first launch, a switch, or a new download)."""
        name = validate_model_name(model)
        with self._lock:
            if self._state == SetupState.RUNNING:
                raise SetupError("setup_busy")
            keep = self._fraction if name == self._model and self._state != SetupState.DONE else 0.0
            self._begin(name, keep)
        self._executor.submit(self._run, name)

    def resume(self) -> None:
        with self._lock:
            if self._state == SetupState.RUNNING:
                raise SetupError("setup_busy")
            if self._state == SetupState.DONE or self._model is None:
                raise SetupError("nothing_to_resume")
            name = self._model
            self._begin(name, self._fraction)
        self._executor.submit(self._run, name)

    def pause(self) -> None:
        if self._state == SetupState.RUNNING:
            self._cancel.set()

    def _begin(self, name: str, keep_fraction: float) -> None:
        self._cancel = threading.Event()
        self._model, self._error, self._state = name, None, SetupState.RUNNING
        self._fraction = keep_fraction
        self._steps = self._new_steps()
        self._persist()

    @staticmethod
    def _new_steps() -> list[Step]:
        return [Step(step_id) for step_id in STEP_IDS]

    # -- the run ---------------------------------------------------------------------------------

    def _run(self, model: str) -> None:
        cancel = self._cancel
        try:
            self._pipeline(model, cancel)
            self._finish(SetupState.DONE)
        except Cancelled:
            self._finish(SetupState.INTERRUPTED if self._stopping else SetupState.PAUSED)
        except CompatError as exc:
            self._finish(SetupState.COMPAT_FAILED, exc.code, fail_step="compat")
        except (OllamaError, DownloadError, SetupError) as exc:
            self._finish(SetupState.FAILED, exc.code)
        except Exception:
            log.exception("unexpected failure in the model setup")
            self._finish(SetupState.FAILED, "setup_failed")

    def _pipeline(self, model: str, cancel: threading.Event) -> None:
        self._plan(model)

        self._begin_step("engine")
        deadline = time.monotonic() + ENGINE_WAIT_SECONDS
        while not self.ollama.reachable():
            if cancel.is_set():
                raise Cancelled
            if time.monotonic() > deadline:
                raise SetupError("ollama_unreachable")
            cancel.wait(1)
        self._end_step("engine")

        installed = self.ollama.installed(model)
        self._require_local(installed)
        known = self.catalog.find(model)
        whisper_needed = 0 if self._whisper_ready() else self.whisper.remaining_bytes()
        llm_needed = 0 if installed else (known.size_bytes if known else 0)
        if (
            llm_needed + whisper_needed
            and self._free_disk(self._models_dir) < llm_needed + whisper_needed + MARGIN_BYTES
        ):
            raise SetupError("not_enough_disk")

        # 2. language model
        if installed:
            self._end_step("llm", skipped=True, detail="Already on this computer")
        else:
            self._begin_step("llm", detail=model, total=known.size_bytes if known else 0)
            disk_checked = [known is not None]

            def on_llm(completed: int, total: int) -> None:
                self._progress("llm", completed, total)
                if (
                    not disk_checked[0] and total > 0
                ):  # a model that is not in the catalog: its size is now known
                    disk_checked[0] = True
                    needed = total - completed + whisper_needed + MARGIN_BYTES
                    if self._free_disk(self._models_dir) < needed:
                        raise SetupError("not_enough_disk")

            self.ollama.pull(model, on_llm, cancel)
            installed = self.ollama.installed(model)
            if installed is None:
                raise SetupError("model_not_installed")
            if installed.remote_host:  # it turned out to be a cloud model: remove it, never use it
                self.ollama.delete(model)
                raise SetupError("cloud_model")
            self._end_step("llm")

        # 3. speech model
        if self._whisper_ready():
            self._end_step("whisper", skipped=True, detail="Already on this computer")
        else:
            self._begin_step(
                "whisper", detail=self.catalog.whisper.title, total=self.catalog.whisper.size_bytes
            )
            self.whisper.download(lambda c, t: self._progress("whisper", c, t), cancel)
            self._end_step("whisper")

        # 4. verify
        self._begin_step("verify")
        if self._whisper_override is None and not self.whisper.verify():
            self.whisper.delete()
            raise DownloadError("checksum_mismatch")
        if self.ollama.installed(model) is None:
            raise SetupError("model_not_installed")
        self._end_step("verify")

        # 5. does the model do the app's task?
        self._begin_step("compat", detail=model)
        self._compat.check(model, cancel)
        set_setting(self._engine, LLM_MODEL, model)
        set_setting(self._engine, compat_key(model), "1")
        self._end_step("compat")
        self._end_step("ready")

    @staticmethod
    def _require_local(model: InstalledModel | None) -> None:
        if model is not None and model.remote_host:
            raise SetupError("cloud_model")

    def _whisper_ready(self) -> bool:
        if self._whisper_override is not None:
            return self._whisper_override.is_file()
        return self.whisper.state()[0] == "ready"

    def _plan(self, model: str) -> None:
        """Mark the steps that will have nothing to do, so the overall bar does not jump later."""
        try:
            installed = self.ollama.installed(model) is not None
        except OllamaError:
            installed = False
        with self._lock:
            self._step("llm").skipped = installed
            self._step("whisper").skipped = self._whisper_ready()
            self._update_fraction()

    # -- progress bookkeeping --------------------------------------------------------------------

    def _step(self, step_id: str) -> Step:
        return next(s for s in self._steps if s.id == step_id)

    def _begin_step(self, step_id: str, detail: str | None = None, total: int = 0) -> None:
        with self._lock:
            step = self._step(step_id)
            step.state, step.detail, step.total = "running", detail, total
            step.completed, step.skipped = 0, False
            self._update_fraction()
            self._persist()

    def _end_step(self, step_id: str, skipped: bool = False, detail: str | None = None) -> None:
        with self._lock:
            step = self._step(step_id)
            step.state, step.skipped = "done", skipped
            if detail:
                step.detail = detail
            if not skipped and step.total:
                step.completed = step.total
            self._update_fraction()
            self._persist()

    def _progress(self, step_id: str, completed: int, total: int) -> None:
        with self._lock:
            step = self._step(step_id)
            step.completed = max(step.completed, completed)  # the bar never moves backwards
            step.total = max(step.total, total)
            step.meter.add(step.completed)
            self._update_fraction()
            if time.monotonic() - self._last_persist >= PERSIST_EVERY:
                self._persist()

    def _update_fraction(self) -> None:
        weight_sum = gained = 0.0
        for step in self._steps:
            weight = 1.0 if step.skipped else float(WEIGHTS[step.id])
            if step.state == "done":
                part = 1.0
            elif step.state == "running":
                part = step.completed / step.total if step.total else 0.5
            else:
                part = 0.0
            weight_sum += weight
            gained += weight * part
        self._fraction = (
            max(self._fraction, min(gained / weight_sum, 0.999)) if weight_sum else self._fraction
        )

    def _finish(
        self, state: SetupState, error: str | None = None, fail_step: str | None = None
    ) -> None:
        with self._lock:
            self._state, self._error = state, error
            if state == SetupState.DONE:
                self._fraction = 1.0
            if state in (SetupState.FAILED, SetupState.COMPAT_FAILED):
                for step in self._steps:
                    if step.state == "running" or step.id == fail_step:
                        step.state = "failed"
            self._persist()

    def _persist(self) -> None:
        self._last_persist = time.monotonic()
        steps: list[dict[str, Any]] = [
            {
                "id": s.id,
                "state": s.state,
                "completed": s.completed,
                "total": s.total,
                "detail": s.detail,
                "skipped": s.skipped,
            }
            for s in self._steps
        ]
        with Session(self._engine) as session:
            run = session.get(SetupRun, 1) or SetupRun(id=1)
            run.state, run.llm_model, run.steps = self._state, self._model, steps
            run.overall_fraction, run.error_code = self._fraction, self._error
            run.updated_at = datetime.now(UTC)
            session.add(run)
            session.commit()

    # -- reading state ---------------------------------------------------------------------------

    def snapshot(self) -> dict[str, Any]:
        """Everything the progress screen shows, as plain data."""
        with self._lock:
            steps = []
            for s in self._steps:
                remaining = max(s.total - s.completed, 0)
                running = s.state == "running" and s.total > 0
                steps.append(
                    {
                        "id": s.id,
                        "label": LABELS[s.id],
                        "state": s.state,
                        "detail": s.detail,
                        "skipped": s.skipped,
                        "completed": s.completed,
                        "total": s.total,
                        "speed_bps": s.meter.speed() if running else None,
                        "eta_s": s.meter.eta(remaining) if running else None,
                    }
                )
            downloads = [s for s in self._steps if not s.skipped and s.id in ("llm", "whisper")]
            return {
                "state": self._state,
                "llm_model": self._model,
                "steps": steps,
                "error_code": self._error,
                "overall": {
                    "fraction": self._fraction,
                    "completed_bytes": sum(s.completed for s in downloads),
                    "total_bytes": sum(s.total for s in downloads),
                },
            }

    def active_model(self) -> str | None:
        return get_setting(self._engine, LLM_MODEL)

    def status(self) -> dict[str, Any]:
        """Is the app ready to use, and if not, what is missing?"""
        reachable = self.ollama.reachable()
        active = self.active_model()
        installed = self.ollama.installed(active) if reachable and active else None
        llm_ready = installed is not None and installed.remote_host is None
        whisper_state, whisper_bytes = self.whisper.state()
        if self._whisper_override is not None and self._whisper_override.is_file():
            whisper_state, whisper_bytes = "ready", self.whisper.model.size_bytes
        compat_ok = bool(active) and get_setting(self._engine, compat_key(active or "")) == "1"
        llm_state = "not_selected" if not active else ("ready" if llm_ready else "missing")
        with self._lock:
            partial = self._state in (
                SetupState.PAUSED,
                SetupState.FAILED,
                SetupState.INTERRUPTED,
            ) and any(s.completed > 0 for s in self._steps)
            run = {"state": self._state, "llm_model": self._model, "fraction": self._fraction}
        if partial and llm_state != "ready" and run["llm_model"] is not None:
            llm_state = "partial"
        return {
            "ready": reachable and llm_ready and compat_ok and whisper_state == "ready",
            "problem": None if reachable else "ollama_unreachable",
            "ollama_reachable": reachable,
            "llm": {"model": active, "state": llm_state},
            "whisper": {
                "state": whisper_state,
                "bytes": whisper_bytes,
                "expected_bytes": self.whisper.model.size_bytes,
            },
            "compat_ok": compat_ok,
            "run": run,
        }

    # -- managing models -------------------------------------------------------------------------

    def models(self) -> list[dict[str, Any]]:
        """The language models on this computer, with what the app knows about each."""
        active = self.active_model()
        out = []
        for model in self.ollama.list_models():
            info = self.catalog.find(model.name)
            out.append(
                {
                    "name": model.name,
                    "size_bytes": model.size_bytes,
                    "cloud": model.remote_host is not None,
                    "active": model.name == active,
                    "compat_ok": get_setting(self._engine, compat_key(model.name)) == "1",
                    "catalog": info,
                }
            )
        return out

    def activate(self, model: str) -> None:
        installed = self.ollama.installed(model)
        if installed is None:
            raise SetupError("model_not_installed")
        self._require_local(installed)
        if get_setting(self._engine, compat_key(installed.name)) != "1":
            raise SetupError(
                "compat_needed"
            )  # not checked on this computer yet: run the setup for it
        set_setting(self._engine, LLM_MODEL, installed.name)

    def delete_llm(self, model: str) -> None:
        self._refuse_while_running()
        installed = self.ollama.installed(model)
        if installed is None:
            raise SetupError("model_not_installed")
        if installed.name == self.active_model():
            raise SetupError("model_in_use")
        self.ollama.delete(installed.name)
        delete_setting(self._engine, compat_key(installed.name))

    def delete_whisper(self) -> None:
        self._refuse_while_running()
        self.whisper.delete()

    def _refuse_while_running(self) -> None:
        if self._state == SetupState.RUNNING:
            raise SetupError("setup_busy")
