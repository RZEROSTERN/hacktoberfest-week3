"""Turns a proposal draft into a Markdown or PDF document.

The document is client-facing: no timestamps or quotes. Items the call did not support carry a
"to be confirmed" label so an assumption is never presented as something the client said.
"""

import io
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer

from app import i18n
from app.drafting import DraftItem, ProposalDraft
from app.notes import Notes


class ExportError(Exception):
    """A failure with a stable `code` the UI turns into a plain-language message."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass
class ExportSection:
    title: str
    paragraphs: list[str] = field(default_factory=list)
    bullets: list[str] = field(default_factory=list)
    # A second group after the bullets: used for the client's budget note in the investment section.
    after: list[str] = field(default_factory=list)
    after_label: str = ""

    def is_empty(self) -> bool:
        return not (self.paragraphs or self.bullets or self.after)


@dataclass
class Document:
    title: str
    subtitle: str
    sections: list[ExportSection]


def _paragraphs(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def _item_text(item: DraftItem, language: str) -> str:
    text = " ".join(item.text.split())
    return f"{text} ({i18n.text(language, 'to_confirm')})" if item.assumption else text


def build_document(proposal: ProposalDraft, notes: Notes | None, freelancer: str) -> Document:
    lang = proposal.language
    client = notes.client.strip() if notes else ""
    title = i18n.text(lang, "proposal") + (f" — {client}" if client else "")
    sections: list[ExportSection] = []
    for section_id in proposal.section_order:
        section = ExportSection(title=i18n.text(lang, section_id))
        match section_id:
            case "summary":
                section.paragraphs = _paragraphs(proposal.summary)
            case "problem":
                section.paragraphs = _paragraphs(proposal.problem)
            case "scope":
                section.bullets = [_item_text(i, lang) for i in proposal.scope]
            case "deliverables":
                section.bullets = [_item_text(i, lang) for i in proposal.deliverables]
            case "out_of_scope":
                section.bullets = [_item_text(i, lang) for i in proposal.out_of_scope]
            case "timeline":
                section.paragraphs = _paragraphs(proposal.timeline)
            case "open_questions":
                section.bullets = [" ".join(q.split()) for q in proposal.open_questions]
            case "investment":
                section.paragraphs = _paragraphs(proposal.investment.note)
                section.bullets = [" ".join(r.split()) for r in proposal.investment.rates]
                section.after_label = proposal.investment.client_budget_label
                section.after = [
                    " ".join(i.text.split()) for i in proposal.investment.client_budget
                ]
            case "terms":
                section.paragraphs = _paragraphs(proposal.terms)
        if not section.is_empty():
            sections.append(section)
    return Document(title=title, subtitle=freelancer.strip(), sections=sections)


def filename(document: Document, extension: str) -> str:
    """ASCII-only file name such as `proposal-trevos.pdf`."""
    folded = unicodedata.normalize("NFKD", document.title).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", folded.lower()).strip("-")
    return f"{slug or 'proposal'}.{extension}"


# -- Markdown ------------------------------------------------------------------------------------


def _md(line: str) -> str:
    """Stop a line from turning into a heading, list or quote by accident."""
    line = " ".join(line.split())
    return re.sub(r"^(\s*)([#>+\-*]|\d+[.)])(\s)", r"\1\\\2\3", line)


def to_markdown(document: Document) -> str:
    out = [f"# {_md(document.title)}", ""]
    if document.subtitle:
        out += [f"*{_md(document.subtitle)}*", ""]
    for section in document.sections:
        out += [f"## {_md(section.title)}", ""]
        for paragraph in section.paragraphs:
            out += [_md(paragraph), ""]
        if section.bullets:
            out += [f"- {_md(b)}" for b in section.bullets] + [""]
        if section.after:
            out += [_md(section.after_label), ""] + [f"- {_md(b)}" for b in section.after] + [""]
    return "\n".join(out).rstrip() + "\n"


# -- PDF -----------------------------------------------------------------------------------------


def _check_drawable(document: Document) -> None:
    """The built-in PDF font covers Western European text. Anything else would print as a box."""
    texts = [document.title, document.subtitle]
    for s in document.sections:
        texts += [s.title, s.after_label, *s.paragraphs, *s.bullets, *s.after]
    for text in texts:
        try:
            text.encode("cp1252")
        except UnicodeEncodeError as exc:
            raise ExportError("pdf_unsupported_characters") from exc


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    body = ParagraphStyle(
        "body", parent=base["Normal"], fontName="Helvetica", fontSize=10.5, leading=15
    )
    return {
        "title": ParagraphStyle(
            "title", parent=body, fontName="Helvetica-Bold", fontSize=20, leading=25
        ),
        "subtitle": ParagraphStyle(
            "subtitle", parent=body, fontName="Helvetica-Oblique", textColor=colors.grey
        ),
        "heading": ParagraphStyle(
            "heading",
            parent=body,
            fontName="Helvetica-Bold",
            fontSize=14,
            leading=18,
            spaceBefore=16,
            spaceAfter=6,
        ),
        "body": ParagraphStyle("body2", parent=body, spaceAfter=6),
    }


def to_pdf(document: Document) -> bytes:
    _check_drawable(document)
    styles = _styles()

    def bullets(items: list[str]) -> ListFlowable:
        return ListFlowable(
            [ListItem(Paragraph(escape(i), styles["body"]), leftIndent=14) for i in items],
            bulletType="bullet",
            start="•",
            leftIndent=14,
        )

    story: list[Any] = [Paragraph(escape(document.title), styles["title"])]
    if document.subtitle:
        story.append(Paragraph(escape(document.subtitle), styles["subtitle"]))
    story.append(Spacer(1, 6))
    for section in document.sections:
        story.append(Paragraph(escape(section.title), styles["heading"]))
        story += [Paragraph(escape(p), styles["body"]) for p in section.paragraphs]
        if section.bullets:
            story.append(bullets(section.bullets))
        if section.after:
            story.append(Spacer(1, 4))
            story.append(Paragraph(escape(section.after_label), styles["body"]))
            story.append(bullets(section.after))

    def footer(canvas: Any, doc: Any) -> None:
        canvas.saveState()
        canvas.setFont("Helvetica", 9)
        canvas.setFillColor(colors.grey)
        canvas.drawCentredString(A4[0] / 2, 1.2 * cm, str(doc.page))
        canvas.restoreState()

    buffer = io.BytesIO()
    SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=2.2 * cm,
        rightMargin=2.2 * cm,
        topMargin=2.2 * cm,
        bottomMargin=2.2 * cm,
        title=document.title,
        author=document.subtitle,
    ).build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()
