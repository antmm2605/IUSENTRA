"""Le notificazioni eseguite, nel modello: quale atto è stato notificato, quando inviato e quando consegnato.

La regola è una sola nel software: `pct/notifica_atto_l53.py` (art. 3-bis L. 53/1994). La prova appartiene
all'atto elencato nella relata, le ricevute si legano alla spedizione con il suo «Notifica_ID», una PEC
senza oggetto di notificazione (una diffida, una richiesta di pagamento) non è una notifica, e la notifica
non precede l'atto (G-3, G-5). Qui le spedizioni diventano eventi del modello, collegati agli atti.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from pct.notifica_atto_l53 import documenti_dell_atto, e_notificazione_l53, notifiche_pec

from .modello import Atto


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


__all__ = ["NotificaEseguita", "e_notificazione_l53", "leggi_notifiche", "notifiche_di"]
