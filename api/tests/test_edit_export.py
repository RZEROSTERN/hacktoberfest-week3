import io
import threading
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader

from tests.fake_llm import PROFILE, ScriptedLLM, draft_json, item, note, notes_json
from tests.fakes import wait_until
from tests.helpers import draft_status, generate, section


@pytest.fixture
def drafted(ready: TestClient, llm: ScriptedLLM) -> TestClient:
    llm.responses = [
        notes_json(),
        draft_json(
            scope=[
                item("Reservaciones en línea", [2]),
                item("Blog corporativo", [], assumption=True),
            ],
            out_of_scope=[],
        ),
    ]
    assert generate(ready)["status"] == "done"
    return ready


def put(client: TestClient, *sections: dict[str, Any]) -> Any:
    return client.put("/calls/call1/draft/proposal", json={"sections": list(sections)})


def pdf_text(response_content: bytes) -> str:
    reader = PdfReader(io.BytesIO(response_content))
    return "\n".join(page.extract_text() for page in reader.pages)


# -- editing ------------------------------------------------------------------------------------


def test_edits_are_saved_and_keep_their_sources(drafted: TestClient) -> None:
    before = drafted.get("/calls/call1/draft").json()
    scope = section(before, "scope")["items"]
    kept = {
        "text": "Reservaciones en línea con calendario",
        "assumption": False,
        "segment_ids": [2],
    }
    response = put(
        drafted,
        {"id": "summary", "text": "Resumen corregido."},
        {"id": "scope", "items": [kept, {"text": "Galería de fotos"}]},
        {"id": "open_questions", "lines": ["¿Hay logotipo?", "  ", "¿Quién da las fotos?"]},
        {"id": "investment", "lines": ["700 MXN por hora"]},
    )
    assert response.status_code == 200, response.text
    after = drafted.get("/calls/call1/draft").json()
    assert section(after, "summary")["text"] == "Resumen corregido."
    items = section(after, "scope")["items"]
    assert [i["text"] for i in items] == [
        "Reservaciones en línea con calendario",
        "Galería de fotos",
    ]
    assert items[0]["sources"][0]["segment_id"] == 2 and not items[0]["assumption"]  # source kept
    assert (
        items[1]["assumption"] is True and items[1]["sources"] == []
    )  # the user's own item: flagged
    assert section(after, "open_questions")["lines"] == ["¿Hay logotipo?", "¿Quién da las fotos?"]
    assert section(after, "investment")["lines"] == ["700 MXN por hora"]
    assert after["updated_at"] > before["updated_at"]
    assert len(scope) == 2  # the original draft had two items; the edit replaced them


def test_only_the_parts_that_are_sent_change(drafted: TestClient) -> None:
    before = drafted.get("/calls/call1/draft").json()
    assert put(drafted, {"id": "summary", "text": "Solo esto."}).status_code == 200
    after = drafted.get("/calls/call1/draft").json()
    assert section(after, "summary")["text"] == "Solo esto."
    for other in ("problem", "scope", "deliverables", "timeline", "investment", "terms"):
        assert section(after, other) == section(before, other)


def test_an_item_without_a_source_can_never_be_unflagged(drafted: TestClient) -> None:
    sent = {"text": "Blog corporativo", "assumption": False, "segment_ids": []}
    put(drafted, {"id": "scope", "items": [sent]})
    assert (
        section(drafted.get("/calls/call1/draft").json(), "scope")["items"][0]["assumption"] is True
    )


def test_a_sourced_item_can_be_flagged_as_an_assumption(drafted: TestClient) -> None:
    sent = {"text": "Reservaciones", "assumption": True, "segment_ids": [2]}
    put(drafted, {"id": "scope", "items": [sent]})
    flagged = section(drafted.get("/calls/call1/draft").json(), "scope")["items"][0]
    assert flagged["assumption"] is True and flagged["sources"][0]["segment_id"] == 2


def test_prices_are_refused_everywhere_except_the_investment_and_terms(drafted: TestClient) -> None:
    summary = put(drafted, {"id": "summary", "text": "Cuesta $5,000 en total."})
    assert (
        summary.status_code == 422 and "summary never includes prices" in summary.json()["detail"]
    )
    scope = put(drafted, {"id": "scope", "items": [{"text": "Tienda por 20,000 pesos"}]})
    assert scope.status_code == 422 and "investment section only" in scope.json()["detail"]
    assert (
        put(drafted, {"id": "open_questions", "lines": ["¿Aceptan pagar 5000?"]}).status_code == 422
    )
    assert put(drafted, {"id": "investment", "lines": ["Sitio web: 24,000 MXN"]}).status_code == 200
    assert put(drafted, {"id": "terms", "text": "Anticipo de $5,000."}).status_code == 200


def test_sources_must_exist_and_sections_must_be_known(drafted: TestClient) -> None:
    unknown_source = put(drafted, {"id": "scope", "items": [{"text": "x", "segment_ids": [99]}]})
    assert (
        unknown_source.status_code == 422
        and "not in the transcript" in unknown_source.json()["detail"]
    )
    assert put(drafted, {"id": "gossip", "text": "x"}).status_code == 422
    after = drafted.get("/calls/call1/draft").json()
    assert (
        section(after, "scope")["items"][0]["text"] == "Reservaciones en línea"
    )  # nothing was saved


def test_a_failed_edit_does_not_save_the_good_parts(drafted: TestClient) -> None:
    response = put(
        drafted,
        {"id": "summary", "text": "Nuevo resumen."},
        {"id": "scope", "items": [{"text": "x", "segment_ids": [99]}]},
    )
    assert response.status_code == 422
    assert section(drafted.get("/calls/call1/draft").json(), "summary")["text"] != "Nuevo resumen."


def test_only_a_finished_draft_can_be_edited_or_exported(
    ready: TestClient, llm: ScriptedLLM
) -> None:
    assert put(ready, {"id": "summary", "text": "x"}).status_code == 404
    assert ready.get("/calls/call1/draft/export?format=md").status_code == 404
    llm.gate = threading.Event()
    llm.responses = [notes_json(), draft_json()]
    ready.post("/calls/call1/draft")
    assert put(ready, {"id": "summary", "text": "x"}).status_code == 409
    assert ready.get("/calls/call1/draft/export?format=pdf").status_code == 409
    llm.gate.set()
    wait_until(lambda: draft_status(ready, "call1") == "done")


# -- Markdown export ----------------------------------------------------------------------------

EXPECTED_MARKDOWN = """# Propuesta — Kevin, pizzería Trevos

*Ana Pérez (Studio Demo)*

## Resumen

Kevin necesita un sistema en línea para su pizzería.

## Comprensión del problema

Hoy gestionan todo por Facebook y eso les limita.

## Alcance

- Reservaciones en línea
- Blog corporativo (por confirmar)

## Entregables

- Sistema de reservaciones

## Cronograma

En la llamada no se habló de un cronograma.

## Preguntas abiertas

- ¿Quién proveerá las fotos?
- ¿Qué presupuesto tiene en mente el cliente?
- ¿Qué fecha de entrega o plazo necesita el cliente?

## Inversión

El precio final depende del alcance acordado.

- 650 MXN por hora
- Sitio web de hasta 5 secciones: 24,000 MXN

## Términos

50% de anticipo y 50% a la entrega.
"""


def test_markdown_export(drafted: TestClient) -> None:
    response = drafted.get("/calls/call1/draft/export?format=md")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/markdown")
    assert (
        response.headers["content-disposition"]
        == 'attachment; filename="propuesta-kevin-pizzeria-trevos.md"'
    )
    assert (
        response.text == EXPECTED_MARKDOWN
    )  # empty sections are left out, assumptions are labelled


def test_the_export_is_client_facing_and_follows_the_saved_edits(drafted: TestClient) -> None:
    put(
        drafted,
        {"id": "summary", "text": "Texto editado."},
        {"id": "scope", "items": [{"text": "- Nueva cosa", "segment_ids": [2]}]},
    )
    text = drafted.get("/calls/call1/draft/export?format=md").text
    assert "Texto editado." in text
    assert "\\- Nueva cosa" in text  # a leading dash is escaped so it stays one bullet
    assert "Blog corporativo" not in text  # removed in the editor
    assert "0:12" not in text and "Queremos reservaciones" not in text  # no timestamps or quotes


def test_the_client_budget_is_a_labelled_note_in_the_export(
    ready: TestClient, llm: ScriptedLLM
) -> None:
    llm.responses = [notes_json(budget=[note("Tenemos unos 8 mil pesos", [1])]), draft_json()]
    generate(ready)
    text = ready.get("/calls/call1/draft/export?format=md").text
    assert text.index("650 MXN por hora") < text.index(
        "Presupuesto mencionado por el cliente (solo una nota, no es el precio):"
    )
    assert "- Tenemos unos 8 mil pesos" in text


def test_the_export_follows_the_profile_section_order_and_language(
    ready: TestClient, llm: ScriptedLLM
) -> None:
    ready.put("/profile", json={**PROFILE, "sections": ["terms", "investment", "scope"]})
    llm.responses = [notes_json(), draft_json(scope=[item("Reservations", [2], assumption=True)])]
    generate(ready, language="en")
    text = ready.get("/calls/call1/draft/export?format=md").text
    headings = [line for line in text.splitlines() if line.startswith("## ")]
    assert headings == ["## Terms", "## Scope", "## Investment"]  # pricing stays after the scope
    assert text.startswith("# Proposal — Kevin, pizzería Trevos")
    assert "- Reservations (to be confirmed)" in text


def test_the_browser_may_read_the_export_file_name(drafted: TestClient) -> None:
    response = drafted.get(
        "/calls/call1/draft/export?format=pdf", headers={"Origin": "http://localhost:3000"}
    )
    assert "Content-Disposition" in response.headers["access-control-expose-headers"]


def test_unknown_export_format(drafted: TestClient) -> None:
    assert drafted.get("/calls/call1/draft/export?format=docx").status_code == 422
    assert drafted.get("/calls/call1/draft/export").status_code == 422


# -- PDF export ---------------------------------------------------------------------------------


def test_pdf_export(drafted: TestClient) -> None:
    response = drafted.get("/calls/call1/draft/export?format=pdf")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert (
        response.headers["content-disposition"]
        == 'attachment; filename="propuesta-kevin-pizzeria-trevos.pdf"'
    )
    assert response.content.startswith(b"%PDF-")
    text = " ".join(pdf_text(response.content).split())  # one line, so wrapped text still matches
    expected_lines = [
        "Propuesta — Kevin, pizzería Trevos",
        "Comprensión del problema",
        "Inversión",
        "Términos",
        "Blog corporativo (por confirmar)",
        "650 MXN por hora",
        "Sitio web de hasta 5 secciones: 24,000 MXN",
    ]
    for expected in expected_lines:
        assert expected in text, expected
    assert "Ana Pérez (Studio Demo)" in text


def test_a_long_proposal_runs_over_several_pages(drafted: TestClient) -> None:
    items = [
        {"text": f"Requisito número {i}: " + "texto largo " * 12, "segment_ids": [2]}
        for i in range(100)
    ]
    assert put(drafted, {"id": "scope", "items": items}).status_code == 200
    reader = PdfReader(io.BytesIO(drafted.get("/calls/call1/draft/export?format=pdf").content))
    assert len(reader.pages) >= 3
    assert "Requisito número 99" in " ".join(page.extract_text() for page in reader.pages)


def test_characters_the_pdf_cannot_draw_are_refused_not_printed_as_boxes(
    drafted: TestClient,
) -> None:
    put(drafted, {"id": "summary", "text": "Zażółć gęślą jaźń"})
    pdf = drafted.get("/calls/call1/draft/export?format=pdf")
    assert pdf.status_code == 422 and "Markdown instead" in pdf.json()["detail"]
    assert (
        "Zażółć" in drafted.get("/calls/call1/draft/export?format=md").text
    )  # Markdown still works
