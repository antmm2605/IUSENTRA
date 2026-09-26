"""Allinea lo scadenziario quando l'avvocato sposta o elimina un'udienza in agenda.

La scadenza «udienza» collegata all'appuntamento (`id_appuntamento`) segue la
nuova data; i termini calcolati a ritroso dall'udienza (per esempio le memorie
dell'art. 171-ter c.p.c.) non si ricalcolano da soli: restano dove sono e
ricevono una nota che chiede di verificarli, perché il nuovo termine dipende dal
provvedimento di rinvio. Se l'appuntamento viene eliminato le scadenze non si
cancellano: si scollegano e si annota il motivo, così nessun termine sparisce
senza una decisione dell'avvocato.

Base normativa: artt. 171-ter e 127-ter c.p.c.; art. 82 disp. att. c.p.c.
(rinvio d'udienza e decorrenza dei termini).
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)
ROME_TZ = ZoneInfo("Europe/Rome")

_STATI_CHIUSI = {"COMPLETATO", "ANNULLATO"}


def _giorno(valore: Any) -> str:
    return str(valore or "").strip()[:10]


def _stato(scadenza: Any) -> str:
    stato = getattr(scadenza, "stato", "")
    return str(getattr(stato, "value", stato) or "")


def _tipo(scadenza: Any) -> str:
    tipo = getattr(scadenza, "tipo", "")
    return str(getattr(tipo, "value", tipo) or "")


def _collegate(scadenziario: Any, id_appuntamento: str) -> list[Any]:
    try:
        tutte = scadenziario.tutte(solo_aperte=False)
    except Exception:
        logger.exception("Scadenziario non leggibile per l'appuntamento %s", id_appuntamento)
        return []
    return [
        s for s in tutte
        if str(getattr(s, "id_appuntamento", "") or "") == id_appuntamento and _stato(s) not in _STATI_CHIUSI
    ]


def _con_nota(scadenza: Any, nota: str) -> str:
    esistente = str(getattr(scadenza, "note", "") or "").strip()
    if nota in esistente:
        return esistente
    return f"{esistente}\n{nota}".strip()


def allinea_dopo_spostamento(scadenziario: Any, id_appuntamento: str, data_prima: str, data_dopo: str) -> dict[str, int]:
    """L'udienza collegata segue la nuova data; gli altri termini ricevono una nota da verificare."""
    prima, dopo = _giorno(data_prima), _giorno(data_dopo)
    esito = {"spostate": 0, "da_verificare": 0}
    if not id_appuntamento or not prima or not dopo or prima == dopo:
        return esito
    oggi = datetime.now(ROME_TZ).strftime("%d/%m/%Y")
    for scadenza in _collegate(scadenziario, id_appuntamento):
        try:
            if _tipo(scadenza) == "UDIENZA" or _giorno(getattr(scadenza, "data_scadenza", "")) == prima:
                scadenziario.aggiorna(
                    scadenza.id,
                    data_scadenza=dopo,
                    note=_con_nota(scadenza, f"Data allineata all'agenda il {oggi}: udienza spostata dal {prima} al {dopo}."),
                )
                esito["spostate"] += 1
            else:
                scadenziario.aggiorna(
                    scadenza.id,
                    note=_con_nota(
                        scadenza,
                        f"Udienza collegata spostata dal {prima} al {dopo} il {oggi}: verificare se il termine va ricalcolato.",
                    ),
                )
                esito["da_verificare"] += 1
        except Exception:
            logger.exception("Scadenza %s non allineata allo spostamento dell'udienza", getattr(scadenza, "id", ""))
    return esito


def allinea_dopo_eliminazione(scadenziario: Any, id_appuntamento: str, *, evento: str = "eliminato dall'agenda") -> dict[str, int]:
    """Le scadenze restano, scollegate e annotate: nessun termine sparisce senza decisione."""
    esito = {"scollegate": 0}
    if not id_appuntamento:
        return esito
    oggi = datetime.now(ROME_TZ).strftime("%d/%m/%Y")
    for scadenza in _collegate(scadenziario, id_appuntamento):
        try:
            scadenziario.aggiorna(
                scadenza.id,
                id_appuntamento="",
                note=_con_nota(scadenza, f"Appuntamento collegato {evento} il {oggi}: verificare se la scadenza resta valida."),
            )
            esito["scollegate"] += 1
        except Exception:
            logger.exception("Scadenza %s non scollegata dall'appuntamento eliminato", getattr(scadenza, "id", ""))
    return esito
