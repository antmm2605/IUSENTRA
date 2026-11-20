"""Le notificazioni eseguite, nel modello: quale atto è stato notificato, quando inviato e quando consegnato.

La regola è una sola nel software: `pct/notifica_atto_l53.py` (art. 3-bis L. 53/1994). La prova appartiene
all'atto elencato nella relata, le ricevute si legano alla spedizione con il suo «Notifica_ID», una PEC
senza oggetto di notificazione (una diffida, una richiesta di pagamento) non è una notifica, e la notifica
non precede l'atto (G-3, G-5). Qui le spedizioni diventano eventi del modello, collegati agli atti.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Iterable

from pct.notifica_atto_l53 import documenti_dell_atto, e_notificazione_l53, notifiche_pec

from .modello import Atto
from .testo import data_it, semplice


@dataclass
class NotificaEseguita:
    notifica_id: str
    data_invio: str = ""
    data_consegna: str = ""
    allegati: list[str] = field(default_factory=list)  # i file elencati nella relata
    atti: list[str] = field(default_factory=list)  # gli atti del fascicolo notificati
    fonti: list[str] = field(default_factory=list)  # messaggio e ricevute
    destinatari: list[str] = field(default_factory=list)
    perfezionata: bool = False


def leggi_notifiche(atti: Iterable[Atto]) -> list[NotificaEseguita]:
    atti = list(atti)
    nomi = {a.id: a.nome for a in atti}
    date_atti = {a.id: a.data for a in atti if a.data}
    esito = []
    for spedizione in notifiche_pec({a.id: a.testo for a in atti}, nomi):
        notificati: list[str] = []
        for voce in spedizione.atti:
            for documento in documenti_dell_atto(voce["file"], nomi):
                data_atto = date_atti.get(documento, "")
                if data_atto and spedizione.data and spedizione.data < data_atto:
                    continue
                if documento not in notificati:
                    notificati.append(documento)
        esito.append(NotificaEseguita(
            notifica_id=spedizione.spedizione, data_invio=spedizione.data, data_consegna=spedizione.data_consegna,
            allegati=[v["file"] for v in spedizione.atti], atti=notificati, fonti=list(spedizione.documenti),
            destinatari=list(spedizione.destinatari), perfezionata=spedizione.perfezionata,
        ))
    return esito


def notifiche_di(atto_id: str, notifiche: Iterable[NotificaEseguita], atti: Iterable[Atto] = ()) -> list[NotificaEseguita]:
    """Le notificazioni che portano nella relata quell'atto o una sua copia identica."""
    copie = {atto_id}
    for atto in atti:
        if atto.id == atto_id:
            copie.update(atto.copie)
        if atto_id in atto.copie:
            copie.add(atto.id)
    return [n for n in notifiche if copie & set(n.atti)]


# L'atto con cui la controparte si costituisce: comparsa (artt. 166-167 c.p.c.), memoria difensiva (art. 416 c.p.c.),
# memoria di costituzione; nel monitorio l'atto di opposizione (art. 645 c.p.c.).
_COSTITUZIONE = re.compile(r"\b(?:comparsa\s+di\s+(?:costituzione|risposta)|costituzione\s+e\s+risposta|memoria\s+difensiva|"
                           r"memoria\s+di\s+costituzione|si\s+costituisce|costituzione\s+in\s+giudizio)\b")
_OPPOSIZIONE = re.compile(r"\bopposizione\s+(?:al|a)\s+decreto\s+ingiuntivo\b|\bpropone\s+opposizione\b")


def costituzione_controparte(atti: Iterable[Atto], *, dal: str = "", opposizione: bool = False) -> Atto | None:
    """L'atto di costituzione della controparte nella causa, non anteriore all'atto da notificare.

    La costituzione del destinatario dimostra che l'atto introduttivo gli è pervenuto: la notifica ha raggiunto
    lo scopo a cui è destinata e un suo vizio non può più essere pronunciato (art. 156, terzo comma, c.p.c.; per
    l'atto di citazione, art. 164, terzo comma, c.p.c.). Vale per tutti i riti: comparsa, memoria difensiva del
    rito del lavoro (art. 416 c.p.c.) e, con ``opposizione``, l'atto di opposizione al decreto ingiuntivo
    (art. 645 c.p.c.). Solo atti della causa scritti dalla controparte: un precedente o un atto di altro
    procedimento non prova nulla (G-8). Un atto senza data letta vale se appartiene alla causa: la costituzione
    presuppone l'atto introduttivo già pervenuto.
    """
    candidati = []
    for atto in atti:
        if atto.appartenenza != "causa" or atto.autore != "controparte" or (dal and atto.data and atto.data < dal):
            continue
        testo = semplice(f"{atto.etichetta} {atto.nome} {atto.testo[:2500]}")
        if atto.natura == "atto_difensivo" and _COSTITUZIONE.search(testo):
            candidati.append(atto)
        elif opposizione and atto.natura == "atto_principale" and _OPPOSIZIONE.search(testo):
            candidati.append(atto)
    return min(candidati, key=lambda a: a.data or "9999") if candidati else None


def scopo_raggiunto(costituzione: Atto) -> str:
    """La prova scritta per l'avvocato: quale atto, di quando, e la norma."""
    quando = f" del {data_it(costituzione.data)}" if costituzione.data else ""
    return (f"La controparte si è costituita con «{costituzione.nome}»{quando}: la notifica ha raggiunto il suo scopo "
            "e un suo eventuale vizio è sanato (art. 156, terzo comma, c.p.c.).")


__all__ = ["NotificaEseguita", "costituzione_controparte", "e_notificazione_l53", "leggi_notifiche", "notifiche_di", "scopo_raggiunto"]
