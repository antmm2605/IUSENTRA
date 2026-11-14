"""I passi per le note scritte che sostituiscono l'udienza (art. 127-ter c.p.c.).

Nascono dalla scadenza «Deposito note scritte ex art. 127-ter c.p.c.» del fascicolo (proposta
in bozza o confermata): la lista è quella di ``pct/note_127_ter/adempimenti.py`` — sole istanze e
conclusioni, i dati che identificano causa e udienza e il provvedimento atteso. Le prescrizioni
specifiche sulla prova della notifica richiedono il decreto e la prova riferita alla causa.
L'opposizione (art. 127-ter, comma 2) è seguita dal presidio PEC.
"""

from __future__ import annotations

import re
from typing import Any

from pct.note_127_ter.adempimenti import adempimenti_note
from pct.note_127_ter.proposta import CODICE_NOTE_127_TER, TITOLO_NOTE_127_TER

from ._testo import data_da, data_it, pulisci
from .modello import Passo

HREF_SCADENZE = "#udienze"
_RE_ORA = re.compile(r"entro le ore (\d{2}:\d{2})")
_RE_ESTINZIONE = re.compile(r"\bart\.\s*(631|181)\b.{0,40}estingu", re.I)
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


def passi_note_127_ter(
    scadenze: list[dict[str, Any]],
    *,
    intestazione: dict[str, Any],
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
            ora_limite=ora.group(1) if ora else "",
        )
        vicino = 1 if (giorno - giorno_oggi).days <= 7 else 2
        bozza = "; termine proposto in bozza: confermarlo nello scadenziario" if stato == "BOZZA" else ""
        entro = data_it(giorno)
        rischio = _RE_ESTINZIONE.search(pulisci(scadenza.get("titolo")))
        if rischio:
            # Seconda diserzione: senza note il processo si estingue (art. 631 c.p.c. nell'esecuzione,
            # art. 181 c.p.c. nella cognizione; art. 127-ter, quarto comma, c.p.c.).
            norma, fonte_norma = f"art. {rischio.group(1)} c.p.c.", f"cpc_{rischio.group(1)}"
            passi.append(Passo(1, f"Depositare le note entro il {entro}: se nessuna parte le deposita il processo si estingue ({norma})",
                               "il giudice ha già rinviato per la mancata comparizione di tutte le parti; il termine è perentorio "
                               "(art. 127-ter, secondo comma, c.p.c.) e non si proroga (art. 153 c.p.c.)",
                               entro, "provvedimento di rinvio", (fonte_norma, "cpc_127ter", "cpc_153"), HREF_SCADENZE))
        for voce in voci:
            if voce.codice == "contenuto":
                # Il termine è la data scritta dal giudice (art. 127-ter, secondo comma): «entro il …», non «udienza del …».
                passi.append(Passo(vicino, f"Depositare le note scritte entro il {entro} (termine perentorio): sole istanze e conclusioni",
                                   voce.dettaglio + bozza, entro, "decreto di trattazione scritta", voce.fonti, HREF_SCADENZE))
            elif voce.codice == "indicazioni":
                # Il decreto qui non è riletto: non si può dire che le chieda proprio lui (collaudo 08/11/2026, Tribunale
                # di Vicenza: il decreto chiedeva altro). Sono i dati che identificano la causa e l'udienza sostituita.
                passi.append(Passo(vicino, "Riportare nelle note i dati che identificano la causa e l'udienza sostituita",
                                   voce.dettaglio + "; verificare nel decreto le indicazioni specifiche che chiede",
                                   entro, "decreto di trattazione scritta", voce.fonti, HREF_SCADENZE))
            elif voce.codice == "prova_notifica":
                passi.append(Passo(
                    vicino, "Verificare se il decreto richiede la prova della notifica con le note",
                    "Consultare il decreto e il deposito della prova nel fascicolo. Se il decreto lo richiede e "
                    "la prova non è già depositata, usare la ricevuta di avvenuta consegna (.eml) della notifica "
                    "di questi atti o la copia della notifica cartacea con attestazione di conformità.",
                    entro, "checklist di preparazione", voce.fonti, "#comunicazioni-notifica",
                ))
            elif voce.codice == "decisione":
                passi.append(Passo(3, f"Attendere il provvedimento sulle note del {entro}", voce.dettaglio, "",
                                   "decreto di trattazione scritta", voce.fonti, HREF_SCADENZE))
    return passi


__all__ = ["passi_note_127_ter"]
