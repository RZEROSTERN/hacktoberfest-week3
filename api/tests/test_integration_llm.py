"""Runs the real language model through Ollama on the sample call's transcript.

Opt-in because it loads a model into memory: `make test-llm` (sets POSTCALL_RUN_LLM_TESTS=1).
The model tag comes from POSTCALL_LLM_MODEL, which seeds the local settings.
"""

import json
import os
import time
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.config import Settings
from app.main import create_app
from app.models import Call, CallStatus, Segment
from tests.fake_llm import PROFILE
from tests.fakes import FakeDecoder, FakeTranscriber, wait_until

OLLAMA = os.environ.get("POSTCALL_OLLAMA_URL", "")
MODEL = os.environ.get("POSTCALL_LLM_MODEL", "")
TRANSCRIPT = (
    Path(__file__).resolve().parents[2]
    / "spike"
    / "results"
    / "transcripts"
    / "cpp-turbo-q5-5min-mc0.json"
)
# Things nobody said in the sample call: any of these in the proposal is an invented requirement.
FORBIDDEN = [
    "whatsapp",
    "stripe",
    "paypal",
    "mercado pago",
    "seo",
    "app móvil",
    "delivery",
    "inventario",
]


def model_installed() -> bool:
    try:
        tags = httpx.get(f"{OLLAMA}/api/tags", timeout=3).json()
    except (httpx.HTTPError, ValueError):
        return False
    return any(m["name"] == MODEL for m in tags.get("models", []))


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("POSTCALL_RUN_LLM_TESTS") != "1"
        or not OLLAMA
        or not MODEL
        or not TRANSCRIPT.is_file(),
        reason="opt-in: needs POSTCALL_RUN_LLM_TESTS=1, POSTCALL_OLLAMA_URL, POSTCALL_LLM_MODEL",
    ),
]


def test_real_model_on_the_sample_call(tmp_path: Path) -> None:
    if not model_installed():
        pytest.skip(f"the model {MODEL} is not installed in Ollama")
    settings = Settings(
        port=8000,
        data_dir=tmp_path / "data",
        models_dir=tmp_path / "models",
        ollama_url=OLLAMA,
        llm_model=MODEL,
    )
    app = create_app(
        settings, transcriber=FakeTranscriber(), decoder=FakeDecoder()
    )  # real OllamaChat
    segments = json.loads(TRANSCRIPT.read_text())
    with Session(app.state.engine) as session:
        session.add(
            Call(
                id="sample",
                title="interview.mp3",
                audio_ext=".mp3",
                status=CallStatus.DONE,
                language="es",
            )
        )
        for idx, seg in enumerate(segments):
            session.add(
                Segment(
                    call_id="sample", idx=idx, start=seg["start"], end=seg["end"], text=seg["text"]
                )
            )
        session.commit()
    client = TestClient(app)
    assert client.put("/profile", json=PROFILE).status_code == 200

    started = time.monotonic()
    assert client.post("/calls/sample/draft").status_code == 202
    wait_until(
        lambda: client.get("/calls/sample/draft").json()["status"] in ("done", "failed"),
        timeout=400,
    )
    elapsed = time.monotonic() - started
    draft: dict[str, Any] = client.get("/calls/sample/draft").json()
    print(
        f"\nreal model {MODEL}: {draft['status']} in {elapsed:.0f} s, warnings={draft['warnings']}"
    )

    if dump := os.environ.get("POSTCALL_DUMP_DRAFT"):  # lets a person read the real output
        Path(dump).write_text(json.dumps(draft, ensure_ascii=False, indent=1))
    assert draft["status"] == "done", draft
    assert draft["model"] == MODEL
    sections = {s["id"]: s for s in draft["proposal"]["sections"]}

    # Accuracy rules, checked in code on the real model's output.
    for name in ("scope", "deliverables", "out_of_scope"):
        for entry in sections[name]["items"]:
            assert entry["sources"] or entry["assumption"], (
                entry
            )  # a source, or flagged as an assumption
            assert all(s["text"] for s in entry["sources"])  # the quote behind the link exists
    assert sections["scope"]["items"], "the call has clear requirements: the scope cannot be empty"
    assert not any(ch.isdigit() for ch in sections["summary"]["text"] if ch in "$€£")
    assert sections["investment"]["lines"] == [PROFILE["hourly_rate"], PROFILE["project_rates"][0]]
    assert sections["terms"]["text"] == PROFILE["payment_terms"]
    assert sections["timeline"]["text"].strip()
    questions = " ".join(sections["open_questions"]["lines"]).lower()
    assert (
        "presupuesto" in questions and "plazo" in questions
    )  # budget and deadline were never discussed

    text = json.dumps(draft["proposal"], ensure_ascii=False).lower()
    assert not [word for word in FORBIDDEN if word in text], "an invented feature appeared"
    requirements = " ".join(n["text"] for n in draft["notes"]["groups"]["requirements"]).lower()
    assert "reserv" in requirements and "galer" in requirements  # key facts of the sample

    assert elapsed < 180, f"notes + proposal took {elapsed:.0f} s, the target is under 3 minutes"
