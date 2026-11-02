"""I passi per le note scritte che sostituiscono l'udienza (art. 127-ter c.p.c.).

Nascono dalla scadenza «Deposito note scritte ex art. 127-ter c.p.c.» del fascicolo (proposta
in bozza o confermata): la lista è quella di ``pct/note_127_ter/adempimenti.py`` — sole istanze e
conclusioni, le cinque indicazioni del decreto, la prova della notifica quando il cliente è il
ricorrente e la resistente non risulta costituita (Specifiche DGSIA art. 26, già art. 19-bis
Provv. DGSIA 16/04/2014; art. 196-undecies disp. att. c.p.c., già artt. 16-decies e 16-undecies
D.L. 179/2012), il provvedimento atteso nei trenta giorni successivi. L'opposizione (art.
127-ter, comma 2) la propone già il presidio PEC: qui non si ripete.
"""

from __future__ import annotations

import re
from typing import Any

from pct.note_127_ter.adempimenti import adempimenti_note
from pct.note_127_ter.proposta import CODICE_NOTE_127_TER, TITOLO_NOTE_127_TER

from ._testo import data_da, data_it, pulisci
from .modello import Passo

HREF_SCADENZE = "#udienze"
HREF_DOCUMENTI = "#documenti"
_RE_ORA = re.compile(r"entro le ore (\d{2}:\d{2})")
_RE_PROVA = re.compile(
    r"avvenuta[\s_-]*consegna|\brdac\b|ricevuta[\s_-]*(?:di[\s_-]*)?consegna|attestazione[\s_-]*di[\s_-]*conformit|\.eml\b",
    re.I,
)
_RUOLI_ATTIVI = {"ricorrente", "attore", "opponente", "reclamante"}
_RUOLI_PASSIVI = {"resistente", "convenuto", "opposto", "reclamato"}


def _e_termine_note(scadenza: dict[str, Any]) -> bool:
    return f":{CODICE_NOTE_127_TER}" in pulisci(scadenza.get("note")) or pulisci(scadenza.get("titolo")).startswith(TITOLO_NOTE_127_TER)


def _ruolo_cliente(intestazione: dict[str, Any]) -> bool | None:
    """True se il cliente è il ricorrente, False se è la parte resistente, None se non si sa."""
    cliente = set(pulisci(intestazione.get("cliente")).lower().split())
    if not cliente:
        return None
    for ruolo, nomi in dict(intestazione.get("parti") or {}).items():
        if any(cliente <= set(pulisci(nome).lower().split()) or set(pulisci(nome).lower().split()) <= cliente for nome in nomi):
            if ruolo in _RUOLI_ATTIVI:
                return True
            if ruolo in _RUOLI_PASSIVI:
                return False
    return None


def _resistente_costituita(pec_letto: dict[str, Any]) -> bool | None:
    """Una comunicazione di cancelleria di costituzione di parte collegata alla pratica."""
    for voce in pec_letto.get("tutte") or []:
        if re.search(r"costituzion|costituit", f"{pulisci(voce.get('oggetto'))} {pulisci(voce.get('evento'))}", re.I):
            return True
    return None


def _documento_prova(documenti_letti: dict[str, Any]) -> str:
    for voce in documenti_letti.get("tutti") or []:
        nome = pulisci(voce.get("nome"))
        if _RE_PROVA.search(f"{nome} {pulisci(voce.get('etichetta'))}"):
            return nome
    return ""


def passi_note_127_ter(
    scadenze: list[dict[str, Any]],
    *,
    intestazione: dict[str, Any],
    documenti_letti: dict[str, Any],
    pec_letto: dict[str, Any],
    giorno_oggi: Any,
) -> list[Passo]:
    if not giorno_oggi:
        return []
    passi: list[Passo] = []
    visti: set[Any] = set()
    for scadenza in scadenze or []:
        stato = pulisci(scadenza.get("stato")).upper()
        giorno = data_da(scadenza.get("data") or scadenza.get("data_scadenza"))
        if stato not in {"APERTO", "BOZZA"} or not _e_termine_note(scadenza) or not giorno or giorno < giorno_oggi or giorno in visti:
            continue
        visti.add(giorno)
        ruolo = _ruolo_cliente(intestazione)
        ora = _RE_ORA.search(pulisci(scadenza.get("note")) + " " + pulisci(scadenza.get("descrizione")))
        avvocato, cliente = pulisci(intestazione.get("avvocato")), pulisci(intestazione.get("cliente"))
        voci = adempimenti_note(
            None, giorno, rg=pulisci(intestazione.get("rg")), giudice=pulisci(intestazione.get("giudice")),
            ufficio=pulisci(intestazione.get("ufficio")),
            difensori=f"{avvocato} per {cliente}" if avvocato and cliente else "",
            cliente_ricorrente=ruolo, resistente_costituita=_resistente_costituita(pec_letto) if ruolo else None,
            documento_prova=_documento_prova(documenti_letti), ora_limite=ora.group(1) if ora else "",
        )
        vicino = 1 if (giorno - giorno_oggi).days <= 7 else 2
        bozza = "; termine proposto in bozza: confermarlo nello scadenziario" if stato == "BOZZA" else ""
        entro = data_it(giorno)
        for voce in voci:
            if voce.codice == "contenuto":
                passi.append(Passo(vicino, f"Preparare le note scritte per l'udienza del {entro}: sole istanze e conclusioni",
                                   voce.dettaglio + bozza, entro, "decreto di trattazione scritta", voce.fonti, HREF_SCADENZE))
            elif voce.codice == "indicazioni":
                passi.append(Passo(vicino, "Riportare nelle note le cinque indicazioni richieste dal decreto", voce.dettaglio,
                                   entro, "decreto di trattazione scritta", voce.fonti, HREF_SCADENZE))
            elif voce.codice == "prova_notifica":
                passi.append(Passo(1, voce.testo[:1].upper() + voce.testo[1:], voce.dettaglio, entro,
                                   "decreto di trattazione scritta", voce.fonti, HREF_DOCUMENTI))
            elif voce.codice == "decisione":
                passi.append(Passo(3, f"Attendere il provvedimento sulle note del {entro}", voce.dettaglio, "",
                                   "decreto di trattazione scritta", voce.fonti, HREF_SCADENZE))
    return passi


__all__ = ["passi_note_127_ter"]
