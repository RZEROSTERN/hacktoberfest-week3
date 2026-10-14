"""Refusals carry a stable `code` (and the values for its message) next to the English `detail`,
so the web app can show them in the user's language."""

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from httpx import Response

from app import i18n
from app.errors import ERROR_MESSAGES
from tests.fake_llm import ScriptedLLM, draft_json, item, notes_json
from tests.helpers import generate, section

APP = Path(__file__).resolve().parents[1] / "app"
NEW_LANGUAGES = ["ja", "zh", "ru", "hi", "ar"]


def answer(response: Response) -> tuple[str, dict[str, str], str]:
    body = response.json()
    return body["code"], body["params"], body["detail"]


def test_a_refusal_has_a_code_params_and_the_english_text(client: TestClient) -> None:
    response = client.get("/calls/nope")
    assert response.status_code == 404
    assert answer(response) == ("call_not_found", {}, "Call not found.")


def test_every_code_the_source_raises_has_an_english_message() -> None:
    raised = set()
    for path in APP.glob("*.py"):
        text = path.read_text()
        raised |= set(re.findall(r'ApiError\(\s*\d+,\s*"([a-z_]+)"', text))
        raised |= set(re.findall(r'EditError\(\s*"([a-z_]+)"', text))
    assert raised, "the scan found nothing, so it is looking in the wrong place"
    assert raised <= set(ERROR_MESSAGES), raised - set(ERROR_MESSAGES)


def test_an_unsupported_upload_is_refused_with_its_code(client: TestClient) -> None:
    response = client.post("/calls", files={"file": ("notes.txt", b"hello")})
    assert response.status_code == 415
    assert answer(response)[0] == "unsupported_file_type"


def test_model_name_refusals_have_codes(client: TestClient) -> None:
    cloud = client.post("/setup/start", json={"model": "gemma4:cloud"})
    assert cloud.status_code == 422 and answer(cloud)[0] == "cloud_model"
    invalid = client.post("/setup/start", json={"model": "bad name!"})
    assert invalid.status_code == 422 and answer(invalid)[0] == "invalid_model_name"


@pytest.fixture
def drafted(ready: TestClient, llm: ScriptedLLM) -> TestClient:
    llm.responses = [notes_json(), draft_json(scope=[item("Reservaciones", [2])])]
    assert generate(ready)["status"] == "done"
    return ready


def edit(client: TestClient, *sections: dict[str, object]) -> Response:
    response: Response = client.put(
        "/calls/call1/draft/proposal", json={"sections": list(sections)}
    )
    return response


def test_edit_refusals_carry_the_values_their_message_needs(drafted: TestClient) -> None:
    summary = edit(drafted, {"id": "summary", "text": "Cuesta $5,000 en total."})
    assert answer(summary) == ("edit_summary_prices", {}, "The summary never includes prices.")

    scope = edit(drafted, {"id": "scope", "items": [{"text": "Tienda por 20,000 pesos"}]})
    code, params, detail = answer(scope)
    assert (code, params) == ("edit_prices_outside_investment", {"where": "scope"})
    assert detail == "Prices belong in the investment section only, not in scope."

    unknown = edit(drafted, {"id": "scope", "items": [{"text": "x", "segment_ids": [99]}]})
    assert answer(unknown)[:2] == ("edit_unknown_segments", {"where": "scope", "segments": "99"})

    gossip = edit(drafted, {"id": "gossip", "text": "x"})
    assert answer(gossip)[:2] == ("edit_unknown_section", {"section": "gossip"})


def test_a_pdf_that_cannot_be_drawn_has_a_code(drafted: TestClient) -> None:
    edit(drafted, {"id": "summary", "text": "Zażółć gęślą jaźń"})
    pdf = drafted.get("/calls/call1/draft/export?format=pdf")
    assert pdf.status_code == 422 and answer(pdf)[0] == "pdf_unsupported_characters"


def test_every_language_has_every_piece_of_proposal_wording() -> None:
    reference = set(i18n._TEXT["en"])
    for code, texts in i18n._TEXT.items():
        assert set(texts) == reference, code
        assert all(value.strip() for value in texts.values()), code
        assert code in i18n.LANGUAGE_NAMES


@pytest.mark.parametrize("language", NEW_LANGUAGES)
def test_a_proposal_in_a_new_language_uses_its_own_wording(
    ready: TestClient, llm: ScriptedLLM, language: str
) -> None:
    llm.responses = [notes_json(), draft_json(scope=[item("x", [2])])]
    assert generate(ready, language=language)["status"] == "done"
    draft = ready.get("/calls/call1/draft").json()
    assert draft["proposal"]["language"] == language
    assert section(draft, "scope")["title"] == i18n.text(language, "scope")
    assert section(draft, "investment")["title"] == i18n.text(language, "investment")

    markdown = ready.get("/calls/call1/draft/export?format=md")
    assert markdown.status_code == 200
    assert f"## {i18n.text(language, 'summary')}" in markdown.text
    assert markdown.text.startswith(f"# {i18n.text(language, 'proposal')}")

    # The built-in PDF font cannot draw these scripts: the export says so instead of printing boxes.
    pdf = ready.get("/calls/call1/draft/export?format=pdf")
    assert pdf.status_code == 422 and answer(pdf)[0] == "pdf_unsupported_characters"
