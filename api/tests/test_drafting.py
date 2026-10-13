import pytest

from app.drafting import (
    DraftItem,
    DraftOut,
    assemble,
    check_draft,
    contains_money,
    repair_draft,
    resolve_sections,
)
from app.models import Profile
from app.notes import NoteItem, Notes


def out(**fields: object) -> DraftOut:
    base: dict[str, object] = {
        "summary": "Kevin necesita un sistema.",
        "problem": "Usan Facebook.",
        "scope": [],
        "deliverables": [],
        "out_of_scope": [],
        "timeline": "Sin fechas.",
        "open_questions": [],
    }
    base.update(fields)
    return DraftOut.model_validate(base)


def notes(**fields: object) -> Notes:
    base: dict[str, object] = {
        "client": "Kevin",
        "client_context": [],
        "problem": [{"text": "p", "segment_ids": [1]}],
        "goals": [],
        "requirements": [],
        "constraints": [],
        "budget": [],
        "deadlines": [],
        "next_steps": [],
        "risks": [],
        "open_questions": [],
    }
    base.update(fields)
    return Notes.model_validate(base)


def profile(
    hourly_rate: str | None = "650 MXN por hora",
    project_rates: list[str] | None = None,
    sections: list[str] | None = None,
) -> Profile:
    return Profile(
        name="Ana",
        hourly_rate=hourly_rate,
        project_rates=["Sitio web de hasta 5 secciones: 24,000 MXN"]
        if project_rates is None
        else project_rates,
        payment_terms="50% de anticipo.",
        sections=sections or [],
    )


@pytest.mark.parametrize(
    "text",
    [
        "$500",
        "USD 1,200",
        "5,000 pesos",
        "24000",
        "€ 90",
        "10.000 euros",
        "la tarifa es de 1500",
        "dos mil dólares",
    ],
)
def test_money_is_detected(text: str) -> None:
    assert contains_money(text)


@pytest.mark.parametrize(
    "text",
    [
        "Supermanzana 316",
        "hasta 5 secciones",
        "en 2026 y 2027",
        "dos locales",
        "50% de anticipo",
        "en 3 semanas",
    ],
)
def test_ordinary_numbers_are_not_money(text: str) -> None:
    assert not contains_money(text)


def test_prices_in_narrative_sections_are_a_hard_problem() -> None:
    problems = check_draft(out(summary="Cuesta $5,000 en total."), {1, 2})
    assert any(p.hard for p in problems)
    assert any(
        p.hard
        for p in check_draft(
            out(scope=[DraftItem(text="Tienda por 1500", segment_ids=[1], assumption=False)]), {1}
        )
    )


def test_empty_summary_is_a_hard_problem() -> None:
    assert any(p.hard for p in check_draft(out(summary="  "), {1}))


def test_unsourced_items_must_be_flagged_as_assumptions() -> None:
    bad = out(scope=[DraftItem(text="Blog", segment_ids=[], assumption=False)])
    assert len(check_draft(bad, {1})) == 1
    ok = out(scope=[DraftItem(text="Blog", segment_ids=[], assumption=True)])
    assert check_draft(ok, {1}) == []


def test_unknown_source_ids_are_flagged() -> None:
    problems = check_draft(
        out(scope=[DraftItem(text="x", segment_ids=[1, 77], assumption=False)]), {1}
    )
    assert len(problems) == 1 and not problems[0].hard


def test_repair_flags_unsourced_items_and_removes_unknown_ids() -> None:
    draft = out(
        scope=[
            DraftItem(text="ok", segment_ids=[1], assumption=False),
            DraftItem(text="no source", segment_ids=[], assumption=False),
            DraftItem(text="bad id", segment_ids=[77], assumption=False),
            DraftItem(text="   ", segment_ids=[1], assumption=False),
        ]
    )
    fixed, removed, flagged = repair_draft(draft, {1})
    assert [(i.text, i.segment_ids, i.assumption) for i in fixed.scope] == [
        ("ok", [1], False),
        ("no source", [], True),
        ("bad id", [], True),
    ]
    assert (removed, flagged) == (1, 2)
    assert check_draft(fixed, {1}) == []  # nothing unsourced is left unflagged


def test_pricing_always_comes_after_the_scope() -> None:
    assert resolve_sections(["investment", "summary", "scope"]) == [
        "summary",
        "scope",
        "investment",
    ]
    assert resolve_sections(["summary", "scope", "investment"]) == [
        "summary",
        "scope",
        "investment",
    ]


def test_sections_ignore_unknown_and_repeated_ids_and_default_to_all() -> None:
    assert resolve_sections(["summary", "nonsense", "summary", "terms"]) == ["summary", "terms"]
    assert len(resolve_sections([])) == 9
    assert resolve_sections([])[:3] == ["summary", "problem", "scope"]


def test_investment_and_terms_come_from_the_profile_only() -> None:
    draft = assemble(out(), notes(), profile(), "es")
    assert draft.investment.rates == [
        "650 MXN por hora",
        "Sitio web de hasta 5 secciones: 24,000 MXN",
    ]
    assert draft.terms == "50% de anticipo."
    assert draft.investment.client_budget == []


def test_a_budget_from_the_client_is_only_a_note() -> None:
    n = notes(budget=[NoteItem(text="Tenemos unos 8 mil pesos", segment_ids=[5]).model_dump()])
    draft = assemble(out(), n, profile(hourly_rate=None, project_rates=[]), "es")
    assert draft.investment.rates == []  # never filled in from what the client said
    assert [(b.text, b.segment_ids) for b in draft.investment.client_budget] == [
        ("Tenemos unos 8 mil pesos", [5])
    ]
    assert "no es el precio" in draft.investment.client_budget_label
    assert "¿Qué presupuesto" not in " ".join(draft.open_questions)  # the budget was discussed


def test_missing_budget_and_deadline_become_open_questions_and_timeline_says_so() -> None:
    draft = assemble(out(timeline="Entregamos en marzo."), notes(), profile(), "es")
    assert "¿Qué presupuesto tiene en mente el cliente?" in draft.open_questions
    assert "¿Qué fecha de entrega o plazo necesita el cliente?" in draft.open_questions
    assert (
        draft.timeline == "En la llamada no se habló de un cronograma."
    )  # the model's invented date is dropped


def test_a_discussed_deadline_keeps_the_models_timeline() -> None:
    n = notes(
        deadlines=[{"text": "Prototipo en dos semanas", "segment_ids": [3]}],
        budget=[{"text": "x", "segment_ids": [3]}],
    )
    draft = assemble(out(timeline="Prototipo en dos semanas."), n, profile(), "es")
    assert draft.timeline == "Prototipo en dos semanas."
    assert not any("plazo" in q for q in draft.open_questions)


def test_a_promised_next_step_is_not_a_delivery_date() -> None:
    n = notes(next_steps=[{"text": "Enviaré un prototipo en dos semanas", "segment_ids": [3]}])
    draft = assemble(out(timeline="Prototipo en dos semanas."), n, profile(), "es")
    assert draft.timeline == "Prototipo en dos semanas."  # the next step can appear in the timeline
    assert (
        "¿Qué fecha de entrega o plazo necesita el cliente?" in draft.open_questions
    )  # but the date is still asked


def test_open_questions_come_from_the_model_without_duplicates() -> None:
    # The notes' own open questions stay in the notes: the model carries the useful ones over.
    n = notes(open_questions=["Who provides the photos?"])
    draft = assemble(
        out(open_questions=["¿Quién da las fotos?", "¿quién da las fotos?", "¿Hay logo?"]),
        n,
        profile(),
        "en",
    )
    assert draft.open_questions[:2] == ["¿Quién da las fotos?", "¿Hay logo?"]
    assert "Who provides the photos?" not in draft.open_questions
    assert draft.open_questions.count("What budget does the client have in mind?") == 1


def test_unsupported_languages_fall_back_to_english_wording() -> None:
    draft = assemble(out(), notes(), profile(), "ja")
    assert draft.investment.note == "The final price depends on the agreed scope."
    assert draft.language == "ja"
