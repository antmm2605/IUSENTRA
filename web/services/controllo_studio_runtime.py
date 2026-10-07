"""Controllo Studio: raccolta delle voci dagli archivi dello studio e riepilogo per area.

Ogni fonte è letta per conto suo: se una non risponde, le altre restano e la pagina lo dice
(«Notifiche non disponibili»), invece di sparire tutta.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from pct.controllo_studio.fonti import (
    indice_rg,
    riepilogo_incassi,
    voci_agenda,
    voci_comunicazioni,
    voci_incassi,
    voci_notifiche,
    voci_scadenze,
)
from pct.controllo_studio.voce import AREE, FASCE, ordina

LOG = logging.getLogger(__name__)
ROMA = ZoneInfo("Europe/Rome")
GIORNI_MESSAGGI = 14


def oggi_roma() -> date:
    return datetime.now(ROMA).date()


def _prova(nome: str, funzione: Callable[[], list], mancanti: list[str]) -> list:
    try:
        return funzione()
    except Exception:  # una fonte guasta non deve svuotare il quadro
        LOG.warning("Controllo Studio: fonte %s non disponibile", nome, exc_info=True)
        mancanti.append(nome)
        return []


def costruisci(helpers: dict[str, Callable[[], Any]], *, presidi_notifiche: Callable[[], list[dict]], oggi: date | None = None,
               puo: Callable[[str], bool] = lambda _p: True) -> dict[str, Any]:
    giorno = oggi or oggi_roma()
    mancanti: list[str] = []
    fascicoli = _prova("Fascicoli", lambda: list(helpers["fascicoli"]().tutti()), mancanti) if puo("fascicoli.leggi") else []
    per_id = {str(f.id): f for f in fascicoli}
    voci = []
    if puo("scadenziario.leggi"):
        voci += _prova("Scadenze", lambda: voci_scadenze(list(helpers["scadenziario"]().tutte(solo_aperte=False)), per_id, giorno), mancanti)
    if puo("agenda.leggi"):
        def agenda() -> list:
            sessioni = {str(s.id_appuntamento): s for s in helpers["wizard_pro"]().lista() if getattr(s, "id_appuntamento", "")
                        and getattr(s, "stato", "") != "archiviato"}
            return voci_agenda(list(helpers["agenda"]().tutti()), indice_rg(fascicoli), sessioni, giorno)
        voci += _prova("Agenda", agenda, mancanti)
    if puo("messaggi.leggi"):
        voci += _prova("Notifiche", lambda: voci_notifiche(presidi_notifiche(), giorno, per_id), mancanti)
    if puo("messaggi.leggi"):
        def comunicazioni() -> list:
            # La casella applica la deduplica primaria; la pagina React pagina
            # l'elenco senza tagliare ricerca e conteggi delle PEC da leggere.
            from pct.email_sql_client import GestioneEmailSQL
            mailbox = helpers["email_pec"]()
            pec = list(mailbox.tutte(cartella="INBOX", solo_non_lette=True))
            dal = giorno - timedelta(days=GIORNI_MESSAGGI)
            falliti = [m for m in helpers["messaggi"]().tutti() if str(getattr(getattr(m, "stato", ""), "value", "")) == "FALLITO"
                       and str(getattr(m, "creato_il", ""))[:10] >= dal.isoformat()]
            from web.services.controllo_studio_pec_context import collegamenti_pec

            collegamenti = {}
            if puo("fascicoli.leggi"):
                try:
                    collegamenti = collegamenti_pec(pec, per_id)
                except Exception:
                    LOG.warning("Controllo Studio: collegamenti PEC non disponibili", exc_info=True)
                    mancanti.append("Collegamenti PEC ai fascicoli")
            if not isinstance(mailbox, GestioneEmailSQL):
                from web.services.controllo_studio_letture import repository as letture
                lette = letture().pec_lette()
                pec = [e for e in pec if str(e.id) not in lette]
            return voci_comunicazioni(pec, falliti, giorno, per_id, collegamenti)
        voci += _prova("Comunicazioni", comunicazioni, mancanti)
    incassi = {"da_incassare": 0.0, "scaduto": 0.0, "parcelle_scadute": 0, "incassato_mese": 0.0}
    if puo("fatturazione.leggi"):
        parcelle = _prova("Incassi", lambda: list(helpers["fatturazione"]().tutte()), mancanti)
        clienti = {str(c.id): c for c in _prova("Clienti", lambda: list(helpers["clienti"]().tutti()), mancanti)}
        voci += voci_incassi(parcelle, clienti, giorno, per_id)
        incassi = riepilogo_incassi(parcelle, giorno)
    ordinate = ordina(voci, giorno)
    aree = []
    for area, etichetta in AREE.items():
        della_area = [v for v in ordinate if v.area == area]
        aree.append({"area": area, "etichetta": etichetta, "totale": len(della_area),
                     "urgenti": sum(1 for v in della_area if v.fascia in {"scaduto", "oggi"} or v.gravita == "critica")})
    urgenti = sum(1 for v in ordinate if v.fascia in {"scaduto", "oggi"})
    return {
        "ok": True, "oggi": giorno.isoformat(), "voci": [v.to_dict() for v in ordinate], "aree": aree,
        "fasce": [{"fascia": k, "etichetta": v} for k, v in FASCE.items()], "incassi": incassi,
        "fonti_non_disponibili": mancanti, "riepilogo": _frase(ordinate, incassi), "urgenti": urgenti,
    }


def _frase(voci: list, incassi: dict[str, Any]) -> str:
    scadute = sum(1 for v in voci if v.area == "scadenze" and v.fascia == "scaduto")
    oggi = sum(1 for v in voci if v.fascia == "oggi")
    udienze_domani = sum(1 for v in voci if v.area == "agenda" and v.etichetta.startswith("Udienza") and v.fascia in {"oggi", "domani"})
    parti = []
    if scadute:
        parti.append(f"{scadute} {'termine scaduto' if scadute == 1 else 'termini scaduti'} da verificare")
    if oggi:
        parti.append(f"{oggi} {'cosa' if oggi == 1 else 'cose'} da fare oggi")
    if udienze_domani:
        parti.append(f"{udienze_domani} {'udienza' if udienze_domani == 1 else 'udienze'} fra oggi e domani")
    if incassi.get("parcelle_scadute"):
        n = int(incassi["parcelle_scadute"])
        parti.append(f"{n} {'parcella scaduta' if n == 1 else 'parcelle scadute'}")
    da_leggere = sum(1 for v in voci if v.fascia == "da_leggere")
    da_esaminare = sum(1 for v in voci if v.area == "notifiche" and not v.data)
    if da_leggere:
        parti.append(f"{da_leggere} {'comunicazione da leggere' if da_leggere == 1 else 'comunicazioni da leggere'}")
    if da_esaminare:
        parti.append(f"{da_esaminare} {'presidio senza termine da verificare' if da_esaminare == 1 else 'presidi senza termine da verificare'}")
    if not parti:
        return "Niente di urgente: lo studio è in ordine."
    frase = ", ".join(parti[:-1]) + (" e " if len(parti) > 1 else "") + parti[-1] + "."
    return frase[0].upper() + frase[1:]


__all__ = ["costruisci", "oggi_roma"]
