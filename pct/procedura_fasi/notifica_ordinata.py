"""La notifica ordinata dal giudice non si «valuta»: si esegue nel termine assegnato.

Nel rito del lavoro il ricorso e il decreto di fissazione dell'udienza sono notificati al convenuto, a cura
dell'attore, entro dieci giorni dalla data di pronuncia del decreto e almeno trenta giorni prima dell'udienza (art.
415, quarto e quinto comma, c.p.c.); in genere, quando un provvedimento del giudice ordina la notificazione a una
parte (art. 137 c.p.c.), la notifica è un adempimento dovuto e non una scelta del difensore. Se lo scadenziario del
fascicolo porta il termine per notificare «ricorso e decreto», la Lettura non chiede di confermare «se la notifica è
necessaria»: indica l'adempimento e il termine.

Collaudo 10/11/2026 (Tribunale di Vicenza, lavoro): «Esamina e conferma se la notifica è necessaria» accanto al
termine «Notifica di ricorso e decreto - almeno 30 giorni prima dell'udienza» dell'08/01/2027.
"""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import date, datetime
from typing import Any, Iterable

_RE_ORDINATA = re.compile(r"\bnotific\w*\s+(?:di\s+|del\s+)?ricorso\s+e\s+(?:del\s+)?decreto|\bnotific\w*\s+.*ordinat\w*\s+dal\s+giudice", re.I)
STATI_DA_VALUTARE = {"DETECTED", "NEEDS_REVIEW"}
PROFILI_NOTIFICA_415 = frozenset({"LAV_415_NOTIFICA_DIECI_GIORNI", "LAV_415_NOTIFICA_TRENTA_GIORNI"})
MARCATORE_NOTIFICA_415 = "OBBLIGO_NOTIFICA:lavoro_415:"


def _giorno(valore: Any) -> date | None:
    testo = " ".join(str(valore or "").split())[:10]
    for formato in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(testo, formato).date()
        except ValueError:
            continue
    return None


def termine_di_notifica_ordinata(scadenze: Iterable[dict[str, Any]], oggi: date | None = None) -> dict[str, Any] | None:
    """La scadenza aperta (o in bozza) che dice di notificare ricorso e decreto: titolo e data; None se non c'è."""
    candidati = []
    for scadenza in scadenze or ():
        if " ".join(str(scadenza.get("stato") or "").split()).upper() not in {"APERTO", "APERTA", "BOZZA", ""}:
            continue
        if not _RE_ORDINATA.search(str(scadenza.get("titolo") or "")):
            continue
        giorno = _giorno(scadenza.get("data") or scadenza.get("data_scadenza"))
        if giorno and (oggi is None or giorno >= oggi):
            candidati.append((giorno, scadenza))
    if not candidati:
        return None
    giorno, scadenza = min(candidati, key=lambda voce: voce[0])
    return {"data": giorno, "titolo": str(scadenza.get("titolo") or ""), "bozza": str(scadenza.get("stato") or "").upper() == "BOZZA"}


def proposte_notifica_415_equivalenti(scadenze: Iterable[Any], documenti: Iterable[Any]) -> dict[str, str]:
    """Abbina le due proposte automatiche solo con la stessa PEC e lo stesso giorno."""
    pec_per_documento = {
        str(documento.id): str(getattr(documento, "msg_id_portale", "") or "").partition("#")[0]
        for documento in documenti
    }
    da_pec = defaultdict(list)
    da_obbligo = defaultdict(list)
    for scadenza in scadenze:
        stato = getattr(scadenza, "stato", "")
        if getattr(stato, "value", stato) != "BOZZA" or not scadenza.id:
            continue
        giorno = _giorno(scadenza.data_scadenza)
        if not giorno:
            continue
        pec = str(getattr(scadenza, "source_message_id", "") or "")
        if getattr(scadenza, "deadline_profile_code", "") in PROFILI_NOTIFICA_415 and pec:
            da_pec[pec, giorno].append(scadenza.id)
            continue
        provenienze = {
            pec_per_documento.get(riga.removeprefix(MARCATORE_NOTIFICA_415))
            for riga in str(getattr(scadenza, "note", "") or "").splitlines()
            if riga.startswith(MARCATORE_NOTIFICA_415)
        }
        if len(provenienze) == 1 and (origine := next(iter(provenienze))):
            da_obbligo[origine, giorno].append(scadenza.id)
    return {
        ids[0]: da_pec[gruppo][0]
        for gruppo, ids in da_obbligo.items()
        if len(ids) == len(da_pec[gruppo]) == 1
    }


__all__ = ["STATI_DA_VALUTARE", "termine_di_notifica_ordinata"]
