"""Regole condivise per ritirare vecchi presidi PEC non operativi.

Le funzioni qui sotto non toccano ricevute, MIME o audit forense: filtrano e,
quando richiesto dal worker, rimuovono solo voci agenda/scadenziario generate
automaticamente dalla vecchia logica e prive della nuova matrice cliente/parti.
"""

from __future__ import annotations

import re
from typing import Any


LEGACY_PEC_TITLES = (
    "classifica pec",
    "classifica pec e conferma adempimenti",
    "ricevuta protocollo",
    "protocollo nr",
    "presidio ricevute pec",
    "udienza da pec",
    "termine da pec",
    "presidio pec",
    "presidio anomalie pec",
    "valuta termini da notifica pec",
    "data processuale",
    "verifica comunicazione di cancelleria e termini",
)

LEGACY_PEC_BODY_MARKERS = (
    "sono presenti anomalie non bloccanti",
    "software registra un promemoria operativo",
    "udienza rilevata da pec",
    "ricevuta pec",
    "verificare provvedimento, fascicolo e attivit",
)

NEW_MATRIX_MARKERS = (
    "cliente:",
    "parte/soggetto:",
    "parte processuale:",
    "soggetti/parti:",
    "soggetti e parti:",
    "ufficio:",
    "giudice:",
    "collegamento remoto:",
    "link udienza audiovisiva:",
    "presidio documentale lex",
)


def _text(value: Any, limit: int = 2000) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def _enum_value(value: Any) -> str:
    return str(getattr(value, "value", value) or "")


def _blob(item: Any, names: tuple[str, ...]) -> str:
    return "\n".join(_text(getattr(item, name, "")) for name in names)


def has_new_pec_matrix_text(*values: Any) -> bool:
    text = _text(" ".join(str(value or "") for value in values), 6000).lower()
    return any(marker in text for marker in NEW_MATRIX_MARKERS)


def is_legacy_pec_deadline(item: Any) -> bool:
    title = _text(getattr(item, "titolo", "")).lower()
    description = _text(getattr(item, "descrizione", "")).lower()
    note = _text(getattr(item, "note", "")).lower()
    source_event = _text(getattr(item, "source_event_type", "")).lower()
    profile = _text(getattr(item, "deadline_profile_code", "")).upper()
    context = "\n".join((title, description, note, source_event, profile))
    generated_by_pec = (
        "pec_audit:" in context
        or profile.startswith("PEC_")
        or " da pec" in title
        or source_event in {"comunicazione", "comunicazione_cancelleria", "pct_deposito"}
    )
    if not generated_by_pec:
        return False
    if has_new_pec_matrix_text(context):
        return False
    return any(title.startswith(prefix) for prefix in LEGACY_PEC_TITLES) or any(marker in context for marker in LEGACY_PEC_BODY_MARKERS)


def is_legacy_pec_agenda_item(item: Any) -> bool:
    title = _text(getattr(item, "titolo", "")).lower()
    note = _blob(item, ("note", "descrizione", "procedimento", "tribunale", "cliente")).lower()
    uid = _text(getattr(item, "external_uid", "")).lower()
    provider = _text(getattr(item, "external_provider", "")).lower()
    context = "\n".join((title, note, uid, provider))
    generated_by_pec = uid.startswith("pec_audit:") or provider == "pec_audit" or "pec_audit:" in context or " da pec" in title
    if not generated_by_pec:
        return False
    if has_new_pec_matrix_text(context):
        return False
    return any(title.startswith(prefix) for prefix in LEGACY_PEC_TITLES) or any(marker in context for marker in LEGACY_PEC_BODY_MARKERS)


def is_legacy_pec_notification_item(item: Any) -> bool:
    getter = item.get if isinstance(item, dict) else lambda key, default=None: getattr(item, key, default)
    title = _text(getter("title", "") or getter("titolo", "")).lower()
    body = _text(getter("message", "") or getter("body", "") or getter("descrizione", "")).lower()
    source_type = _text(getter("source_type", "") or getter("type", "")).lower()
    source_id = _text(getter("source_id", "") or getter("id", "")).lower()
    href = _text(getter("href", "")).lower()
    context = "\n".join((title, body, source_type, source_id, href))
    generated_by_pec = (
        "pec" in context
        or source_type in {"pec_deadline", "comunicazione_cancelleria", "pct_deposito"}
        or "comunicazione di cancelleria" in title
    )
    if not generated_by_pec:
        return False
    if has_new_pec_matrix_text(context):
        return False
    return any(title.startswith(prefix) for prefix in LEGACY_PEC_TITLES) or any(marker in context for marker in LEGACY_PEC_BODY_MARKERS)


def cleanup_legacy_pec_operational_items(*, scadenziario: Any = None, agenda: Any = None) -> dict[str, int]:
    report = {"scadenziario_removed": 0, "agenda_removed": 0, "errors": 0}
    if scadenziario is not None:
        try:
            for item in list(scadenziario.tutte(solo_aperte=False)):
                if is_legacy_pec_deadline(item):
                    scadenziario.elimina(str(getattr(item, "id", "") or ""))
                    report["scadenziario_removed"] += 1
        except Exception:
            report["errors"] += 1
    if agenda is not None:
        try:
            for item in list(agenda.tutti()):
                if is_legacy_pec_agenda_item(item):
                    agenda.elimina(str(getattr(item, "id", "") or ""))
                    report["agenda_removed"] += 1
        except Exception:
            report["errors"] += 1
    return report
