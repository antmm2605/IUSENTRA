"""Classificatore contributo unificato per il presidio PEC.

Riconosce nelle PEC (corpo + OCR allegati) le tre evidenze economiche del
contributo unificato previste dal D.P.R. 115/2002:

- ricevuta telematica di pagamento (PagoPA/RT, F23/F24) → CU pagato;
- autocertificazione/esenzione (art. 9 c. 1-bis, art. 76 D.P.R. 115/2002,
  patrocinio a spese dello Stato, prenotazione a debito) → CU non dovuto;
- richiesta/avviso di versamento (invito al pagamento dell'ufficio) → CU
  da pagare.

L'estrazione riusa `extract_contributo_unificato_document_evidence` di
`pct.fascicolo_sentenza_economica`: stessa fonte deterministica usata dalla
vista economica dei fascicoli, nessuna regex duplicata.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

CATEGORIA_RICEVUTA_PAGAMENTO = "ricevuta_pagamento"
CATEGORIA_ESENZIONE = "esenzione_autocertificazione"
CATEGORIA_RICHIESTA_VERSAMENTO = "richiesta_versamento"

_CATEGORIA_PRIORITA = {
    CATEGORIA_RICEVUTA_PAGAMENTO: 0,
    CATEGORIA_ESENZIONE: 1,
    CATEGORIA_RICHIESTA_VERSAMENTO: 2,
}


@dataclass(slots=True)
class ClassificazioneContributoUnificato:
    """Esito della classificazione CU su una PEC del presidio."""

    categoria: str
    importo: float | None = None
    natura: str = ""
    label: str = ""
    titolo: str = ""
    fonte: str = ""
    origine: str = ""
    esente: bool = False
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "categoria": self.categoria,
            "importo": self.importo,
            "natura": self.natura,
            "label": self.label,
            "titolo": self.titolo,
            "fonte": self.fonte,
            "origine": self.origine,
            "esente": self.esente,
            "warnings": list(self.warnings),
        }


def _testo(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _categoria_da_evidenza(evidence: dict[str, Any]) -> str:
    natura = _testo(evidence.get("natura"))
    if evidence.get("esente") is True or natura == "esenzione_contributo_unificato":
        return CATEGORIA_ESENZIONE
    if natura == "richiesta_versamento_contributo_unificato" or _testo(evidence.get("status")) == "da_registrare":
        return CATEGORIA_RICHIESTA_VERSAMENTO
    return CATEGORIA_RICEVUTA_PAGAMENTO


def _classificazione_da_evidenza(evidence: dict[str, Any], fonte: str) -> ClassificazioneContributoUnificato:
    importo_raw = evidence.get("importo")
    try:
        importo = round(float(importo_raw), 2) if importo_raw is not None else None
    except (TypeError, ValueError):
        importo = None
    return ClassificazioneContributoUnificato(
        categoria=_categoria_da_evidenza(evidence),
        importo=importo,
        natura=_testo(evidence.get("natura")),
        label=_testo(evidence.get("label")),
        titolo=_testo(evidence.get("titolo")),
        fonte=fonte,
        origine=_testo(evidence.get("origine")),
        esente=evidence.get("esente") is True,
    )


def _iter_sorgenti(
    body_text: str,
    attachments: Iterable[dict[str, Any]] | None,
) -> Iterable[tuple[str, dict[str, Any], str]]:
    """Produce coppie (testo, metadata, fonte leggibile) da corpo e allegati."""

    for item in attachments or []:
        if not isinstance(item, dict):
            continue
        ocr_text = _testo(item.get("ocr_text"))
        if not ocr_text:
            continue
        filename = _testo(item.get("filename") or item.get("nome") or item.get("nome_file"))
        metadata = {
            "filename": filename,
            "document_id": _testo(item.get("sha256") or item.get("id")),
            "sha256": _testo(item.get("sha256")),
            "classification": _testo(item.get("classification")),
        }
        yield ocr_text, metadata, filename or "allegato PEC"
    body = _testo(body_text)
    if body:
        yield body, {}, "testo PEC"


def classifica_contributo_unificato_pec(
    body_text: str,
    attachments: Iterable[dict[str, Any]] | None = None,
) -> ClassificazioneContributoUnificato | None:
    """Classifica l'evidenza CU più affidabile presente nella PEC.

    Ordine di preferenza (coerente con la vista economica dei fascicoli):
    ricevuta di pagamento con importo, poi esenzione/autocertificazione,
    poi richiesta di versamento. Ritorna ``None`` se la PEC non contiene
    alcuna evidenza CU classificabile.
    """

    try:
        from pct.fascicolo_sentenza_economica import extract_contributo_unificato_document_evidence
    except Exception:
        return None

    candidati: list[ClassificazioneContributoUnificato] = []
    for testo, metadata, fonte in _iter_sorgenti(body_text, attachments):
        try:
            evidence = extract_contributo_unificato_document_evidence(testo, metadata)
        except Exception:
            continue
        if not evidence:
            continue
        candidati.append(_classificazione_da_evidenza(evidence, fonte))
    if not candidati:
        return None
    candidati.sort(
        key=lambda item: (
            _CATEGORIA_PRIORITA.get(item.categoria, 9),
            0 if item.importo is not None else 1,
        )
    )
    return candidati[0]


__all__ = [
    "CATEGORIA_ESENZIONE",
    "CATEGORIA_RICEVUTA_PAGAMENTO",
    "CATEGORIA_RICHIESTA_VERSAMENTO",
    "ClassificazioneContributoUnificato",
    "classifica_contributo_unificato_pec",
]
