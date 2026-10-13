import logging
import threading
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.config import Settings
from app.generation import default_prompts_dir
from app.main import create_app
from app.models import Call, CallStatus, Draft, DraftStatus
from app.settings_store import LLM_MODEL, get_setting, set_setting
from tests.fake_llm import PROFILE, ScriptedLLM, draft_json, item, llm_error, note, notes_json
from tests.fakes import FakeDecoder, FakeTranscriber, wait_until
from tests.helpers import TRANSCRIPT, add_done_call, app_of, draft_status, generate, section

# -- profile ------------------------------------------------------------------------------------


def test_profile_is_created_read_and_replaced(client: TestClient) -> None:
    assert client.get("/profile").status_code == 404
    saved = client.put("/profile", json={**PROFILE, "services": [" Web ", ""]}).json()
    assert saved["services"] == ["Web"]
    assert client.get("/profile").json()["hourly_rate"] == "650 MXN por hora"
    client.put("/profile", json={"name": "Otra persona"})
    replaced = client.get("/profile").json()
    assert replaced["name"] == "Otra persona" and replaced["hourly_rate"] is None


def test_profile_validation(client: TestClient) -> None:
    assert client.put("/profile", json={**PROFILE, "name": ""}).status_code == 422
    assert (
        client.put("/profile", json={**PROFILE, "sections": ["summary", "gossip"]}).status_code
        == 422
    )


# -- the happy path -----------------------------------------------------------------------------


def test_notes_and_draft_with_sources(ready: TestClient, llm: ScriptedLLM) -> None:
    llm.responses = [notes_json(), draft_json()]
    draft = generate(ready)

    assert draft["status"] == "done" and draft["progress"] == 1.0
    assert draft["model"] == "test-model" and draft["language"] == "es"
    assert draft["warnings"] == []

    req = draft["notes"]["groups"]["requirements"][0]
    assert req["sources"] == [
        {"segment_id": 2, "start": 12.0, "end": 16.0, "text": TRANSCRIPT[2][1]}
    ]

    sections = draft["proposal"]["sections"]
    assert [s["id"] for s in sections] == [
        "summary", "problem", "scope", "deliverables", "out_of_scope",
        "timeline", "open_questions", "investment", "terms",
    ]  # fmt: skip
    assert section(draft, "scope")["title"] == "Alcance"
    scope = section(draft, "scope")["items"][0]
    assert scope["assumption"] is False and scope["sources"][0]["segment_id"] == 2
    assert section(draft, "terms")["text"] == PROFILE["payment_terms"]


def test_prices_come_from_the_profile_and_the_model_never_sees_them(
    ready: TestClient, llm: ScriptedLLM
) -> None:
    llm.responses = [notes_json(), draft_json()]
    draft = generate(ready)
    investment = section(draft, "investment")
    assert investment["lines"] == [PROFILE["hourly_rate"], PROFILE["project_rates"][0]]
    assert investment["text"] == "El precio final depende del alcance acordado."
    assert "650" not in llm.calls[1][1] and "24,000" not in llm.calls[1][1]
    assert "650" not in llm.calls[1][0] and "24,000" not in llm.calls[1][0]


def test_summary_has_no_price_and_pricing_follows_the_scope(
    ready: TestClient, llm: ScriptedLLM
) -> None:
    ready.put("/profile", json={**PROFILE, "sections": ["investment", "summary", "scope", "terms"]})
    llm.responses = [notes_json(), draft_json()]
    draft = generate(ready)
    assert [s["id"] for s in draft["proposal"]["sections"]] == [
        "summary",
        "scope",
        "investment",
        "terms",
    ]
    assert "MXN" not in section(draft, "summary")["text"]


def test_a_client_budget_is_shown_as_a_note_not_as_the_price(
    ready: TestClient, llm: ScriptedLLM
) -> None:
    llm.responses = [notes_json(budget=[note("Tenemos unos 8 mil pesos", [1])]), draft_json()]
    investment = section(generate(ready), "investment")
    assert investment["lines"] == [PROFILE["hourly_rate"], PROFILE["project_rates"][0]]
    assert investment["items"][0]["text"] == "Tenemos unos 8 mil pesos"
    assert "no es el precio" in investment["items_label"]


def test_a_promised_next_step_reaches_the_timeline_but_the_delivery_date_is_still_asked(
    ready: TestClient, llm: ScriptedLLM
) -> None:
    llm.responses = [
        notes_json(
            next_steps=[note("El freelancer enviará un prototipo en las próximas semanas", [2])]
        ),
        draft_json(timeline="El prototipo se enviará en las próximas semanas."),
    ]
    draft = generate(ready)
    assert draft["notes"]["groups"]["next_steps"][0]["sources"][0]["segment_id"] == 2
    assert section(draft, "timeline")["text"] == "El prototipo se enviará en las próximas semanas."
    assert (
        "¿Qué fecha de entrega o plazo necesita el cliente?"
        in section(draft, "open_questions")["lines"]
    )


def test_missing_budget_and_deadline_are_added_to_the_open_questions(
    ready: TestClient, llm: ScriptedLLM
) -> None:
    llm.responses = [notes_json(), draft_json(timeline="Entregamos el 5 de marzo.")]
    draft = generate(ready)
    questions = section(draft, "open_questions")["lines"]
    assert "¿Quién proveerá las fotos?" in questions
    assert "¿Qué presupuesto tiene en mente el cliente?" in questions
    assert "¿Qué fecha de entrega o plazo necesita el cliente?" in questions
    assert section(draft, "timeline")["text"] == "En la llamada no se habló de un cronograma."


def test_the_proposal_can_be_written_in_another_language(
    ready: TestClient, llm: ScriptedLLM
) -> None:
    llm.responses = [notes_json(), draft_json()]
    draft = generate(ready, language="en")
    assert draft["language"] == "en"
    assert section(draft, "scope")["title"] == "Scope"
    assert "English" in llm.calls[1][0]
    assert ready.post("/calls/call1/draft", json={"language": "Spanish"}).status_code == 422


def test_long_calls_are_read_in_chunks_and_merged(client: TestClient, llm: ScriptedLLM) -> None:
    add_done_call(app_of(client), count=20)  # one segment a minute: 3 chunks of 8 minutes
    client.put("/profile", json=PROFILE)
    # Every chunk may only cite its own segments: ids 0-7, 8-15 and 16-19.
    empty: dict[str, Any] = {"client_context": [], "problem": [], "goals": []}
    llm.responses = [
        notes_json(
            **{
                **empty,
                "problem": [note("Problema", [0])],
                "requirements": [note("Reservas en línea", [1])],
            }
        ),
        notes_json(**{**empty, "requirements": [note("Galería de fotos", [9])]}),
        notes_json(**{**empty, "requirements": [note("reservas en línea.", [17])]}),
        draft_json(),
    ]
    draft = generate(client)
    assert draft["status"] == "done" and len(llm.calls) == 4
    assert "[S9 @ 540s]" in llm.calls[1][1] and "[S1 @" not in llm.calls[1][1]
    requirements = draft["notes"]["groups"]["requirements"]
    assert [r["text"] for r in requirements] == ["Reservas en línea", "Galería de fotos"]
    assert [s["segment_id"] for s in requirements[0]["sources"]] == [1, 17]


# -- preconditions ------------------------------------------------------------------------------


def test_preconditions(client: TestClient) -> None:
    assert client.post("/calls/nope/draft").status_code == 404
    with Session(app_of(client).state.engine) as session:
        session.add(
            Call(id="busy", title="x.mp3", audio_ext=".mp3", status=CallStatus.TRANSCRIBING)
        )
        session.commit()
    assert client.post("/calls/busy/draft").status_code == 409  # not transcribed yet
    add_done_call(app_of(client))
    assert client.post("/calls/call1/draft").status_code == 409  # no profile yet
    assert client.get("/calls/call1/draft").status_code == 404


def test_only_one_draft_per_call_at_a_time_and_regenerating_replaces_it(
    ready: TestClient, llm: ScriptedLLM
) -> None:
    llm.gate = threading.Event()
    llm.responses = [notes_json(), draft_json()]
    assert ready.post("/calls/call1/draft").status_code == 202
    assert ready.post("/calls/call1/draft").status_code == 409
    llm.gate.set()
    wait_until(lambda: draft_status(ready, "call1") == "done")

    llm.responses = [notes_json(client="Otro"), draft_json(summary="Segunda versión.")]
    second = generate(ready)
    assert section(second, "summary")["text"] == "Segunda versión."
    assert second["notes"]["client"] == "Otro"


# -- validation, retry and repair ---------------------------------------------------------------


def test_invalid_json_is_retried_once_with_the_problem_listed(
    ready: TestClient, llm: ScriptedLLM
) -> None:
    llm.responses = ["this is not json", notes_json(), draft_json()]
    assert generate(ready)["status"] == "done"
    assert "Your previous answer had problems" not in llm.calls[0][1]
    assert "Your previous answer had problems" in llm.calls[1][1]


def test_two_invalid_answers_give_a_clear_error(ready: TestClient, llm: ScriptedLLM) -> None:
    llm.responses = ["nope", '{"client": 3}']
    draft = generate(ready)
    assert draft["status"] == "failed" and draft["error_code"] == "invalid_model_output"
    assert "could not be understood" in draft["error_message"]
    assert draft["proposal"] is None


def test_notes_with_unknown_sources_are_retried_then_dropped(
    ready: TestClient, llm: ScriptedLLM
) -> None:
    bad = notes_json(requirements=[note("Reservas", [2]), note("Inventado", [99])])
    llm.responses = [bad, bad, draft_json()]
    draft = generate(ready)
    assert draft["status"] == "done"
    assert [r["text"] for r in draft["notes"]["groups"]["requirements"]] == ["Reservas"]
    assert draft["warnings"] == ["dropped_unsourced_notes:1"]
    assert "cite" in llm.calls[1][1]  # the retry named the problem


def test_a_price_in_the_summary_is_retried_and_can_be_fixed(
    ready: TestClient, llm: ScriptedLLM
) -> None:
    llm.responses = [notes_json(), draft_json(summary="Costará 20,000 pesos."), draft_json()]
    draft = generate(ready)
    assert draft["status"] == "done" and len(llm.calls) == 3
    assert "pesos" not in section(draft, "summary")["text"]
    assert "amount of money" in llm.calls[2][1]


def test_a_price_that_survives_the_retry_fails_the_draft(
    ready: TestClient, llm: ScriptedLLM
) -> None:
    priced = draft_json(summary="Son $5,000 en total.")
    llm.responses = [notes_json(), priced, priced]
    draft = generate(ready)
    assert draft["status"] == "failed" and draft["error_code"] == "draft_invalid"
    assert draft["proposal"] is None  # nothing priced by the model is ever stored


def test_scope_items_without_a_source_are_flagged_as_assumptions(
    ready: TestClient, llm: ScriptedLLM
) -> None:
    unsourced = draft_json(scope=[item("Reservaciones", [2]), item("Blog corporativo", [])])
    llm.responses = [notes_json(), unsourced, unsourced]
    draft = generate(ready)
    assert draft["status"] == "done"
    items = section(draft, "scope")["items"]
    assert [(i["text"], i["assumption"], len(i["sources"])) for i in items] == [
        ("Reservaciones", False, 1),
        ("Blog corporativo", True, 0),
    ]
    assert draft["warnings"] == ["flagged_assumptions:1"]
    assert "no source" in llm.calls[2][1]  # the retry asked for sources first


def test_a_call_without_substance_is_not_drafted(ready: TestClient, llm: ScriptedLLM) -> None:
    llm.responses = [notes_json(problem=[], goals=[], requirements=[])]
    draft = generate(ready)
    assert draft["status"] == "failed" and draft["error_code"] == "not_enough_information"
    assert len(llm.calls) == 1  # no proposal was attempted


@pytest.mark.parametrize(
    ("code", "text"),
    [
        ("llm_unreachable", "not running"),
        ("llm_model_missing", "not installed"),
        ("llm_model_not_set", "No language model"),
        ("llm_timeout", "too long"),
    ],
)
def test_language_model_errors_are_explained(
    ready: TestClient, llm: ScriptedLLM, code: str, text: str
) -> None:
    llm.responses = [llm_error(code)]
    draft = generate(ready)
    assert draft["status"] == "failed" and draft["error_code"] == code
    assert text in draft["error_message"]


# -- cancel, lifecycle and cleanup --------------------------------------------------------------


def test_cancel_stops_a_running_draft(ready: TestClient, llm: ScriptedLLM) -> None:
    llm.gate = threading.Event()
    llm.responses = [notes_json(), draft_json()]
    ready.post("/calls/call1/draft")
    wait_until(lambda: draft_status(ready, "call1") == "extracting")
    assert ready.post("/calls/call1/draft/cancel").status_code == 200
    wait_until(lambda: draft_status(ready, "call1") == "cancelled")
    assert ready.post("/calls/call1/draft/cancel").status_code == 409


def test_deleting_a_call_removes_its_draft_but_not_while_drafting(
    ready: TestClient, llm: ScriptedLLM
) -> None:
    llm.gate = threading.Event()
    llm.responses = [notes_json(), draft_json()]
    ready.post("/calls/call1/draft")
    assert ready.delete("/calls/call1").status_code == 409
    llm.gate.set()
    wait_until(lambda: draft_status(ready, "call1") == "done")
    assert ready.delete("/calls/call1").status_code == 204
    assert ready.get("/calls/call1/draft").status_code == 404


def test_drafts_left_running_are_marked_interrupted_on_start(settings: Settings) -> None:
    first = create_app(
        settings, transcriber=FakeTranscriber(), decoder=FakeDecoder(), llm=ScriptedLLM([])
    )
    add_done_call(first)
    with Session(first.state.engine) as session:
        session.add(Draft(call_id="call1", language="es", status=DraftStatus.EXTRACTING))
        session.commit()
    restarted = TestClient(
        create_app(
            settings, transcriber=FakeTranscriber(), decoder=FakeDecoder(), llm=ScriptedLLM([])
        )
    )
    draft = restarted.get("/calls/call1/draft").json()
    assert draft["status"] == "failed" and draft["error_code"] == "interrupted"


def test_the_model_in_use_comes_from_the_settings_table(settings: Settings) -> None:
    seeded = settings.model_copy(update={"llm_model": "from-env:1b"})
    app = create_app(seeded, transcriber=FakeTranscriber(), decoder=FakeDecoder())
    assert (
        get_setting(app.state.engine, LLM_MODEL) == "from-env:1b"
    )  # the environment only seeds it
    set_setting(app.state.engine, LLM_MODEL, "chosen-in-settings:2b")
    again = create_app(seeded, transcriber=FakeTranscriber(), decoder=FakeDecoder())
    assert (
        get_setting(again.state.engine, LLM_MODEL) == "chosen-in-settings:2b"
    )  # and never overrides it
    assert again.state.generation._llm.model == "chosen-in-settings:2b"


def test_nothing_from_the_call_is_logged(
    ready: TestClient, llm: ScriptedLLM, caplog: pytest.LogCaptureFixture
) -> None:
    llm.responses = [notes_json(), draft_json()]
    with caplog.at_level(logging.DEBUG):
        generate(ready)
        ready.get("/calls/call1/draft")
    logged = " ".join(r.getMessage() for r in caplog.records)
    assert all(text not in logged for _, text in TRANSCRIPT)
    assert "pizzería" not in logged


# -- prompts ------------------------------------------------------------------------------------


@pytest.mark.parametrize("name", ["notes_v3.md", "proposal_v1.md"])
def test_prompts_are_versioned_files_and_work_with_any_model(name: str) -> None:
    text = (default_prompts_dir() / name).read_text()
    assert (
        "gemma" not in text.lower() and "qwen" not in text.lower() and "mistral" not in text.lower()
    )
    assert "never invent" in text.lower() or "never infer" in text.lower()


def test_the_proposal_prompt_forbids_prices_and_asks_for_sources() -> None:
    text = (default_prompts_dir() / "proposal_v1.md").read_text()
    assert "{language}" in text
    assert "amount of money" in text and "assumption" in text


def test_a_custom_prompts_folder_is_used(settings: Settings, tmp_path: Path) -> None:
    (tmp_path / "notes_v3.md").write_text("CUSTOM NOTES PROMPT")
    (tmp_path / "proposal_v1.md").write_text("CUSTOM DRAFT PROMPT {language}")
    llm = ScriptedLLM([notes_json(), draft_json()])
    client = TestClient(
        create_app(
            settings.model_copy(update={"prompts_dir": tmp_path}),
            transcriber=FakeTranscriber(),
            decoder=FakeDecoder(),
            llm=llm,
        )
    )
    add_done_call(app_of(client))
    client.put("/profile", json=PROFILE)
    generate(client)
    assert llm.calls[0][0] == "CUSTOM NOTES PROMPT"
    assert llm.calls[1][0].startswith("CUSTOM DRAFT PROMPT Spanish")
