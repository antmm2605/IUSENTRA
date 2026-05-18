from __future__ import annotations

from typing import Any


LOW_VALUE_AGCOM_PUBLIC_CONSULTATION_MARKERS: tuple[str, ...] = (
    "contributo alla consultazione pubblica",
    "contributo alla consultazione",
    "osservazioni alla consultazione",
    "consultazione pubblica agcom",
    "richiesta di pianificazione di una frequenza",
    "frequenza dab",
    "frequenza dab+",
    "dab+ locale",
    "associazione emittenti radio",
)

AGCOM_LEGAL_VALUE_MARKERS: tuple[str, ...] = (
    "delibera",
    "provvedimento",
    "procedimento sanzionatorio",
    "sanzion",
    "diffida",
    "ordinanza",
    "ingiunzione",
    "ordine",
    "regolamento",
    "contenzioso",
    "ricorso",
    "tar",
    "consiglio di stato",
    "sentenza",
    "impugnazione",
    "accesso agli atti",
    "diritto d'autore",
    "copyright",
    "tutela utenti",
    "corecom",
    "conciliazione",
    "risoluzione controversie",
    "inottemperanza",
    "violazione",
    "obblighi regolamentari",
)


def _clean_spaces(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def is_low_value_public_legal_record(
    *,
    source_code: Any = "",
    source_name: Any = "",
    title: Any = "",
    body_text: Any = "",
    url: Any = "",
    category: Any = "",
) -> bool:
    """Riconosce atti pubblici non utili come aggiornamenti di studio.

    Esempio governato: contributi di terzi a consultazioni AGCOM, come documenti
    di associazioni o operatori su pianificazione frequenze, non devono entrare
    nell'archivio Lex solo perche' il sito di provenienza e' istituzionale.
    """

    source_haystack = " ".join(
        _clean_spaces(value).lower()
        for value in (source_code, source_name, url)
        if _clean_spaces(value)
    )
    if "agcom" not in source_haystack:
        return False

    text = " ".join(
        _clean_spaces(value).lower()
        for value in (title, body_text, category)
        if _clean_spaces(value)
    )
    if not text:
        return False
    if not any(marker in text for marker in LOW_VALUE_AGCOM_PUBLIC_CONSULTATION_MARKERS):
        return False
    return not any(marker in text for marker in AGCOM_LEGAL_VALUE_MARKERS)
