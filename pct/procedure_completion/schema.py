"""Validazione e normalizzazione leggera per il Procedure Completion Engine."""

from __future__ import annotations

import re
from typing import Any

from pct.procedure_completion.models import (
    CARD_STATUSES,
    ProcedureCompletionCard,
    ProcedureCompletionRequest,
)

_CODICE_RE = re.compile(r"^(?:\d{3,8}|[A-Z]\d{5})$")
_SPAZI_RE = re.compile(r"\s+")

# Chiavi che il client non puo' mai imporre (gestione server-side).
FORBIDDEN_CLIENT_KEYS = frozenset(
    {
        "tenant_id", "tenantid", "tenant",
        "studio_id", "studioid",
        "user_id", "userid",
        "path", "db_path",
        "token", "api_key", "apikey", "secret",
        "trust_score", "source_trust_score", "trust_class",
        "status", "confidence", "reviewer",
    }
)


def _clean(value: Any) -> str:
    return _SPAZI_RE.sub(" ", str(value or "")).strip()


def forbidden_keys_in_payload(payload: Any) -> list[str]:
    """Chiavi vietate presenti nel payload client (ricorsivo, primo livello + nested)."""
    trovate: set[str] = set()

    def _walk(value: Any) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if str(key).strip().lower() in FORBIDDEN_CLIENT_KEYS:
                    trovate.add(str(key))
                _walk(item)
        elif isinstance(value, list):
            for item in value:
                _walk(item)

    _walk(payload)
    return sorted(trovate)


def normalize_request(payload: dict[str, Any] | None) -> ProcedureCompletionRequest:
    payload = payload if isinstance(payload, dict) else {}
    codice = _clean(payload.get("codice")).upper().replace(" ", "")
    return ProcedureCompletionRequest(
        codice=codice,
        denominazione=_clean(payload.get("denominazione")),
        categoria=_clean(payload.get("categoria")),
        rito=_clean(payload.get("rito")),
        competenza=_clean(payload.get("competenza")),
        template_code=_clean(payload.get("template_code") or payload.get("templateCode")),
        note=_clean(payload.get("note"))[:2000],
    )


def validate_request(request: ProcedureCompletionRequest) -> list[str]:
    errori: list[str] = []
    if not request.codice and not request.denominazione:
        errori.append("Indica almeno il codice oggetto o la denominazione della procedura.")
    if request.codice and not _CODICE_RE.match(request.codice):
        errori.append("Formato codice non riconosciuto: atteso codice oggetto PST (3-8 cifre).")
    if request.denominazione and len(request.denominazione) < 5:
        errori.append("Denominazione troppo breve per una ricerca affidabile.")
    return errori


def is_valid_status(status: str) -> bool:
    return status in CARD_STATUSES


def publish_blockers(card: ProcedureCompletionCard, report: dict[str, Any] | None = None) -> list[str]:
    """Motivi che impediscono la pubblicazione (fail-closed)."""
    blockers: list[str] = []
    if card.status != "approved":
        blockers.append("La scheda deve essere in stato approved prima della pubblicazione.")
    if not card.fonti_ufficiali_o_tecniche:
        blockers.append("Nessuna fonte ufficiale o tecnica collegata alla scheda.")
    if not card.citazioni_verificabili:
        blockers.append("Nessuna citazione verificabile collegata alla scheda.")
    if not card.review_avvocato.get("reviewer"):
        blockers.append("Manca la review dell'avvocato.")
    if report:
        blockers.extend(str(item) for item in report.get("blocking_errors") or [])
        if report.get("publishable") is False and not report.get("blocking_errors"):
            blockers.append("Il report di validazione non consente la pubblicazione.")
    return blockers


__all__ = [
    "FORBIDDEN_CLIENT_KEYS",
    "forbidden_keys_in_payload",
    "normalize_request",
    "validate_request",
    "is_valid_status",
    "publish_blockers",
]
