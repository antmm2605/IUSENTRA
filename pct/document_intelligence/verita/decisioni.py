"""Le etichette decise dall'avvocato: correzioni e conferme singole, mai le conferme massive."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from .modello import LIVELLO_AVVOCATO, EtichettaCerta

FONTE_CORREZIONE = "correzione_avvocato"
FONTE_CONFERMA = "conferma_avvocato"
FONTE_RIFIUTO = "rifiuto_avvocato"


def _testo(valore: Any) -> str:
    return " ".join(str(valore or "").split()).strip()


def etichette_dalle_decisioni(assegnazioni: Iterable[Any], *, conferme_massive: set[str] = frozenset()) -> list[EtichettaCerta]:
    """Una etichetta per documento deciso dall'avvocato.

    `conferme_massive` sono i documenti la cui ultima conferma è arrivata dal pannello «Conferma tutto»: valgono
    come attestazione della prova, non come lettura del documento, e restano fuori.
    """
    esito: list[EtichettaCerta] = []
    for assegnazione in assegnazioni:
        documento = _testo(getattr(assegnazione, "document_id", ""))
        etichetta = _testo(getattr(assegnazione, "document_label", ""))
        stato = _testo(getattr(assegnazione, "status", ""))
        origine = _testo(getattr(assegnazione, "source_state", ""))
        if not documento or not etichetta:
            continue
        if origine == "manual_override":
            fonte, negativa = FONTE_CORREZIONE, False
        elif stato == "confirmed" and documento not in conferme_massive:
            fonte, negativa = FONTE_CONFERMA, False
        elif stato == "rejected":
            fonte, negativa = FONTE_RIFIUTO, True
        else:
            continue
        esito.append(EtichettaCerta(
            fascicolo_id=_testo(getattr(assegnazione, "fascicolo_id", "")), document_id=documento, etichetta=etichetta,
            sezione=_testo(getattr(assegnazione, "document_section", "")), livello=LIVELLO_AVVOCATO, fonte=fonte,
            sha256=_testo(getattr(assegnazione, "document_sha256", "")), negativa=negativa,
        ))
    return esito


__all__ = ["FONTE_CONFERMA", "FONTE_CORREZIONE", "FONTE_RIFIUTO", "etichette_dalle_decisioni"]
