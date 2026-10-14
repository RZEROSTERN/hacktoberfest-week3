"""The proposal draft: schemas, the accuracy checks, and the parts the code writes itself.

The language model writes the narrative sections only. The investment section is built from the
freelancer's profile rates and the terms are the profile's payment terms, so a price can never
come from the model.
"""

import re
from typing import Annotated, Any

from pydantic import BaseModel, Field

from app import i18n
from app.models import Profile
from app.notes import NoteItem, Notes, Problem

# Currency signs and names, numbers with thousands separators, and any 4+ digit number that is not
# a year. Street numbers and similar short numbers are fine.
MONEY_RE = re.compile(
    r"[$€£]"
    r"|\b(?:usd|mxn|eur|gbp|brl|cop|ars|clp|pesos?|d[oó]lares?|euros?|reales?)\b"
    r"|\b\d{1,3}(?:[.,]\d{3})+\b"
    r"|\b(?!(?:19|20)\d{2}\b)\d{4,}\b",
    re.IGNORECASE,
)


class DraftItem(BaseModel):
    text: str
    segment_ids: list[int]
    assumption: bool


class DraftOut(BaseModel):
    """What the language model returns."""

    summary: str
    problem: str
    scope: list[DraftItem]
    deliverables: list[DraftItem]
    out_of_scope: list[DraftItem]
    timeline: str
    open_questions: list[str]


ITEM_FIELDS = ("scope", "deliverables", "out_of_scope")


class Investment(BaseModel):
    rates: list[str]  # copied from the profile, never written by the model
    note: str
    client_budget_label: str
    client_budget: list[DraftItem]  # what the client said about budget: a note, never the price


class ProposalDraft(BaseModel):
    """What is stored and shown (and edited in the editor)."""

    language: str
    section_order: list[str]
    summary: str
    problem: str
    scope: list[DraftItem]
    deliverables: list[DraftItem]
    out_of_scope: list[DraftItem]
    timeline: str
    open_questions: list[str]
    investment: Investment
    terms: str


def contains_money(text: str) -> bool:
    return MONEY_RE.search(text) is not None


def check_draft(out: DraftOut, valid_ids: set[int]) -> list[Problem]:
    problems: list[Problem] = []
    texts = {"summary": out.summary, "problem": out.problem, "timeline": out.timeline}
    for field in ITEM_FIELDS:
        for item in getattr(out, field):
            texts[field] = f"{texts.get(field, '')} {item.text}"
    texts["open_questions"] = " ".join(out.open_questions)
    for field, value in texts.items():
        if contains_money(value):
            problems.append(
                Problem(
                    f"The '{field}' section contains an amount of money or a price. Remove every "
                    "amount: "
                    "prices come only from the freelancer's profile and are added by the app.",
                    hard=True,
                )
            )
    if not out.summary.strip() or not out.problem.strip():
        problems.append(
            Problem("The summary and the problem section must not be empty.", hard=True)
        )
    for field in ITEM_FIELDS:
        for item in getattr(out, field):
            bad = [i for i in item.segment_ids if i not in valid_ids]
            if bad:
                problems.append(
                    Problem(f"In '{field}', \"{item.text[:60]}\" cites unknown segment ids {bad}.")
                )
            if not item.segment_ids and not item.assumption:
                problems.append(
                    Problem(
                        f"In '{field}', \"{item.text[:60]}\" has no source segment ids. "
                        "Cite the segments it comes from, or set assumption to true."
                    )
                )
    return problems


def repair_draft(out: DraftOut, valid_ids: set[int]) -> tuple[DraftOut, int, int]:
    """Make item sources trustworthy: remove unknown ids, and flag unsourced items as assumptions.

    Returns the draft, how many ids were removed and how many items were flagged.
    """
    removed = flagged = 0
    fixed = out.model_copy(deep=True)
    for field in ITEM_FIELDS:
        items = []
        for item in getattr(fixed, field):
            if not item.text.strip():
                continue
            ids = sorted({i for i in item.segment_ids if i in valid_ids})
            removed += len(item.segment_ids) - len(ids)
            item.segment_ids = ids
            if not ids and not item.assumption:
                item.assumption = True
                flagged += 1
            items.append(item)
        setattr(fixed, field, items)
    return fixed, removed, flagged


def resolve_sections(preferred: list[str]) -> list[str]:
    """The freelancer's preferred sections in order. Pricing always comes after the scope."""
    order: list[str] = []
    for section in preferred:
        if section in i18n.SECTION_IDS and section not in order:
            order.append(section)
    if not order:
        order = list(i18n.SECTION_IDS)
    if (
        "investment" in order
        and "scope" in order
        and order.index("investment") < order.index("scope")
    ):
        order.remove("investment")
        order.insert(order.index("scope") + 1, "investment")
    return order


def assemble(out: DraftOut, notes: Notes, profile: Profile, language: str) -> ProposalDraft:
    """Combine the model's sections with the parts built from the profile and the notes."""
    rates = (
        [profile.hourly_rate.strip()] if profile.hourly_rate and profile.hourly_rate.strip() else []
    ) + [rate.strip() for rate in profile.project_rates if rate.strip()]
    questions: list[str] = []
    seen: set[str] = set()
    # The model was given the notes' own open questions and writes them in the proposal language.
    for question in out.open_questions:
        key = question.strip().lower()
        if key and key not in seen:
            seen.add(key)
            questions.append(question.strip())
    # The call is the only source for these two answers: when it gave none, ask for them.
    if not notes.budget:
        questions.append(i18n.text(language, "ask_budget"))
    if not notes.deadlines:
        questions.append(i18n.text(language, "ask_deadline"))
    # Promised next steps are timing information, but only a deadline settles the delivery date.
    has_timing = bool(notes.deadlines or notes.next_steps)
    timeline = out.timeline.strip() if has_timing and out.timeline.strip() else ""
    if not timeline:
        timeline = i18n.text(language, "no_timeline")
    return ProposalDraft(
        language=language,
        section_order=resolve_sections(profile.sections),
        summary=out.summary.strip(),
        problem=out.problem.strip(),
        scope=out.scope,
        deliverables=out.deliverables,
        out_of_scope=out.out_of_scope,
        timeline=timeline,
        open_questions=questions,
        investment=Investment(
            rates=rates,
            note=i18n.text(language, "price_depends"),
            client_budget_label=i18n.text(language, "client_budget"),
            client_budget=[to_draft_item(item) for item in notes.budget],
        ),
        terms=profile.payment_terms.strip(),
    )


def to_draft_item(item: NoteItem) -> DraftItem:
    return DraftItem(text=item.text, segment_ids=item.segment_ids, assumption=False)


def notes_for_model(notes: Notes) -> dict[str, Any]:
    """The notes as the drafting prompt sees them: text and sources only."""
    return notes.model_dump()


# -- Editing -------------------------------------------------------------------------------------


class EditError(Exception):
    """An edit that breaks a rule. `code` and `params` let the web app say it in the user's
    language; the message is the English text."""

    def __init__(self, code: str, message: str, **params: object) -> None:
        super().__init__(message)
        self.code = code
        self.params = params


class ItemEdit(BaseModel):
    text: str = Field(max_length=1000)
    assumption: bool = False
    segment_ids: list[int] = Field(default_factory=list, max_length=50)


class SectionEdit(BaseModel):
    """Only the parts that are present are changed. `id` is one of the nine section ids."""

    id: str
    text: str | None = Field(default=None, max_length=10000)
    lines: list[Annotated[str, Field(max_length=1000)]] | None = Field(default=None, max_length=100)
    items: list[ItemEdit] | None = Field(default=None, max_length=100)


class ProposalEdit(BaseModel):
    sections: list[SectionEdit] = Field(max_length=20)


def _no_money(where: str, text: str) -> None:
    if contains_money(text):
        if where == "summary":
            raise EditError("edit_summary_prices", "The summary never includes prices.")
        raise EditError(
            "edit_prices_outside_investment",
            f"Prices belong in the investment section only, not in {where}.",
            where=where,
        )


def _edited_items(
    values: list[ItemEdit], valid_ids: set[int], where: str, *, flag_unsourced: bool
) -> list[DraftItem]:
    items = []
    for value in values:
        text = " ".join(value.text.split())
        if not text:
            continue
        if where != "investment":
            _no_money(where, text)
        unknown = [i for i in value.segment_ids if i not in valid_ids]
        if unknown:
            raise EditError(
                "edit_unknown_segments",
                f"An item in {where} cites segments that are not in the transcript: {unknown}.",
                where=where,
                segments=", ".join(str(i) for i in unknown),
            )
        ids = sorted(set(value.segment_ids))
        # An item with no source in the call is an assumption, whoever wrote it.
        items.append(
            DraftItem(
                text=text,
                segment_ids=ids,
                assumption=flag_unsourced and (value.assumption or not ids),
            )
        )
    return items


def apply_edit(current: ProposalDraft, edit: ProposalEdit, valid_ids: set[int]) -> ProposalDraft:
    """Apply the user's edits, keeping the accuracy rules: no prices outside the investment section,
    real sources only, and unsourced items stay flagged as assumptions."""
    data = current.model_copy(deep=True)
    for section in edit.sections:
        match section.id:
            case "summary" | "problem" | "timeline":
                if section.text is not None:
                    _no_money(section.id, section.text)
                    setattr(data, section.id, section.text.strip())
            case "terms":
                if section.text is not None:
                    data.terms = section.text.strip()
            case "scope" | "deliverables" | "out_of_scope":
                if section.items is not None:
                    setattr(
                        data,
                        section.id,
                        _edited_items(section.items, valid_ids, section.id, flag_unsourced=True),
                    )
            case "open_questions":
                if section.lines is not None:
                    lines = [" ".join(line.split()) for line in section.lines if line.strip()]
                    for line in lines:
                        _no_money(section.id, line)
                    data.open_questions = lines
            case "investment":
                if section.text is not None:
                    data.investment.note = section.text.strip()
                if section.lines is not None:
                    data.investment.rates = [line.strip() for line in section.lines if line.strip()]
                if section.items is not None:
                    data.investment.client_budget = _edited_items(
                        section.items, valid_ids, "investment", flag_unsourced=False
                    )
            case _:
                raise EditError(
                    "edit_unknown_section", f"Unknown section: {section.id}", section=section.id
                )
    return data
