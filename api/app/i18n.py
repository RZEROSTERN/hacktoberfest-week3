"""Fixed wording that the code (not the language model) puts into a proposal.

Anything the model writes is already in the proposal language. These strings are the section
titles and a few sentences built from the freelancer's profile; unsupported languages fall back
to English.
"""

LANGUAGE_NAMES = {
    "en": "English",
    "es": "Spanish",
    "pt": "Portuguese",
    "fr": "French",
    "de": "German",
    "it": "Italian",
}

SECTION_IDS = (
    "summary",
    "problem",
    "scope",
    "deliverables",
    "out_of_scope",
    "timeline",
    "open_questions",
    "investment",
    "terms",
)

_TEXT: dict[str, dict[str, str]] = {
    "en": {
        "summary": "Summary",
        "problem": "Understanding of the problem",
        "scope": "Scope",
        "deliverables": "Deliverables",
        "out_of_scope": "Out of scope",
        "timeline": "Timeline",
        "open_questions": "Open questions",
        "investment": "Investment",
        "terms": "Terms",
        "proposal": "Proposal",
        "to_confirm": "to be confirmed",
        "price_depends": "The final price depends on the agreed scope.",
        "client_budget": "Budget mentioned by the client (a note, not the price):",
        "no_timeline": "The call did not cover a timeline.",
        "ask_budget": "What budget does the client have in mind?",
        "ask_deadline": "What delivery date or deadline does the client need?",
    },
    "es": {
        "summary": "Resumen",
        "problem": "Comprensión del problema",
        "scope": "Alcance",
        "deliverables": "Entregables",
        "out_of_scope": "Fuera de alcance",
        "timeline": "Cronograma",
        "open_questions": "Preguntas abiertas",
        "investment": "Inversión",
        "terms": "Términos",
        "proposal": "Propuesta",
        "to_confirm": "por confirmar",
        "price_depends": "El precio final depende del alcance acordado.",
        "client_budget": "Presupuesto mencionado por el cliente (solo una nota, no es el precio):",
        "no_timeline": "En la llamada no se habló de un cronograma.",
        "ask_budget": "¿Qué presupuesto tiene en mente el cliente?",
        "ask_deadline": "¿Qué fecha de entrega o plazo necesita el cliente?",
    },
    "pt": {
        "summary": "Resumo",
        "problem": "Entendimento do problema",
        "scope": "Escopo",
        "deliverables": "Entregáveis",
        "out_of_scope": "Fora do escopo",
        "timeline": "Cronograma",
        "open_questions": "Perguntas em aberto",
        "investment": "Investimento",
        "terms": "Termos",
        "proposal": "Proposta",
        "to_confirm": "a confirmar",
        "price_depends": "O preço final depende do escopo acordado.",
        "client_budget": "Orçamento mencionado pelo cliente (apenas uma nota, não é o preço):",
        "no_timeline": "A chamada não tratou de um cronograma.",
        "ask_budget": "Que orçamento o cliente tem em mente?",
        "ask_deadline": "Que data de entrega ou prazo o cliente precisa?",
    },
    "fr": {
        "summary": "Résumé",
        "problem": "Compréhension du problème",
        "scope": "Périmètre",
        "deliverables": "Livrables",
        "out_of_scope": "Hors périmètre",
        "timeline": "Calendrier",
        "open_questions": "Questions ouvertes",
        "investment": "Investissement",
        "terms": "Conditions",
        "proposal": "Proposition",
        "to_confirm": "à confirmer",
        "price_depends": "Le prix final dépend du périmètre convenu.",
        "client_budget": "Budget mentionné par le client (une simple note, pas le prix) :",
        "no_timeline": "L'appel n'a pas abordé de calendrier.",
        "ask_budget": "Quel budget le client envisage-t-il ?",
        "ask_deadline": "Quelle date de livraison ou échéance le client souhaite-t-il ?",
    },
    "de": {
        "summary": "Zusammenfassung",
        "problem": "Verständnis des Problems",
        "scope": "Leistungsumfang",
        "deliverables": "Liefergegenstände",
        "out_of_scope": "Nicht im Leistungsumfang",
        "timeline": "Zeitplan",
        "open_questions": "Offene Fragen",
        "investment": "Investition",
        "terms": "Konditionen",
        "proposal": "Angebot",
        "to_confirm": "zu bestätigen",
        "price_depends": "Der Endpreis hängt vom vereinbarten Leistungsumfang ab.",
        "client_budget": "Vom Kunden genanntes Budget (nur ein Hinweis, nicht der Preis):",
        "no_timeline": "Im Gespräch wurde kein Zeitplan besprochen.",
        "ask_budget": "Welches Budget hat der Kunde im Sinn?",
        "ask_deadline": "Welchen Liefertermin oder welche Frist braucht der Kunde?",
    },
    "it": {
        "summary": "Riepilogo",
        "problem": "Comprensione del problema",
        "scope": "Ambito",
        "deliverables": "Deliverable",
        "out_of_scope": "Fuori ambito",
        "timeline": "Tempistiche",
        "open_questions": "Domande aperte",
        "investment": "Investimento",
        "terms": "Condizioni",
        "proposal": "Proposta",
        "to_confirm": "da confermare",
        "price_depends": "Il prezzo finale dipende dall'ambito concordato.",
        "client_budget": "Budget menzionato dal cliente (solo una nota, non il prezzo):",
        "no_timeline": "Nella chiamata non si è parlato di tempistiche.",
        "ask_budget": "Quale budget ha in mente il cliente?",
        "ask_deadline": "Quale data di consegna o scadenza serve al cliente?",
    },
}


def language_name(code: str) -> str:
    """Name used in prompts; unknown codes are passed through as written."""
    return LANGUAGE_NAMES.get(code, code)


def text(language: str, key: str) -> str:
    return _TEXT.get(language, _TEXT["en"])[key]
