"""Guard che blocca/riscrive output tecnico nelle risposte all'utente.

Impedisce che nomi di workflow, provider, JSON raw o frasi tecniche interne
raggiungano l'utente finale.
"""

from __future__ import annotations

import re

_FORBIDDEN_PHRASES = (
    "Risposta deterministica per workflow",
    "workflow '",
    "provider '",
    "provider_hint",
    "evidence_pack",
    "ProviderDraft",
    "DeterministicProvider",
    "OllamaProvider",
    "evidence_sufficient",
)

_TECHNICAL_WORKFLOWS = frozenset({
    "giurisprudenza_specifica",
    "studio_data_lookup",
    "telematico_status",
    "compliance",
    "next_action",
    "cabina",
})

_JSON_OBJECT_RE = re.compile(r'^\s*\{.*\}\s*$', re.DOTALL)
_CIAO_LEX_RE = re.compile(r'(?i)ciao[,.]?\s*(sono\s+)?lex[.!]?\s*')

_OPERATIONAL_KEYWORDS = frozenset({
    "sentenza", "ordinanza", "decreto", "massima", "cassazione", "tribunale",
    "cliente", "fascicolo", "rg", "pratica", "scadenza", "agenda", "appuntamento",
    "deposito", "pec", "udienza", "atto", "norma", "normativa", "legge",
    "diffida", "preventivo", "parcella", "fattura",
})


def _is_operational_query(question: str) -> bool:
    text = question.lower()
    return any(kw in text for kw in _OPERATIONAL_KEYWORDS)


def contains_forbidden_technical_output(text: str) -> bool:
    """Verifica se la risposta contiene frasi tecniche interne vietate."""
    for phrase in _FORBIDDEN_PHRASES:
        if phrase in text:
            return True
    return False


def sanitize_user_output(text: str, *, workflow: str = "", question: str = "") -> str:
    """Rimuove o sostituisce frasi tecniche vietate nel testo risposta.

    Se il testo è interamente JSON, lo sostituisce con un messaggio neutro.
    Se contiene frasi tecniche, le rimuove.
    """
    if not text or not text.strip():
        return text

    # Blocca risposte JSON raw all'utente
    stripped = text.strip()
    if stripped.startswith("{") and stripped.endswith("}") and _JSON_OBJECT_RE.match(stripped):
        return (
            "Non ho trovato informazioni sufficienti per rispondere a questa domanda "
            "con i dati disponibili. Prova a riformulare la richiesta."
        )

    # Blocca "Risposta deterministica per workflow '...'"
    cleaned = re.sub(
        r"Risposta deterministica per workflow '[^']*'\.\s*",
        "",
        text,
    )
    cleaned = re.sub(
        r"Evidenza principale:[^\n]*\n?",
        "",
        cleaned,
    )
    cleaned = re.sub(
        r"Sintesi:[^\n]*\n?",
        "",
        cleaned,
    )

    # Per workflow tecnici: rimuovi "Ciao, sono Lex." se c'è una domanda operativa
    if workflow in _TECHNICAL_WORKFLOWS or _is_operational_query(question):
        cleaned = _CIAO_LEX_RE.sub("", cleaned)

    return cleaned.strip()


def check_output_safety(text: str, *, workflow: str = "", question: str = "") -> tuple[bool, str]:
    """Controlla e sanitizza una risposta utente.

    Returns:
        (is_safe, sanitized_text): is_safe=True se non c'era nulla da correggere.
    """
    if not text:
        return True, text

    has_forbidden = contains_forbidden_technical_output(text)
    sanitized = sanitize_user_output(text, workflow=workflow, question=question)
    return not has_forbidden, sanitized
