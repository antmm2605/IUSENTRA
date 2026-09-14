"""A che punto siamo: la fase dedotta dai fatti, non dallo stato dichiarato.

Lo stato del fascicolo («aperto», «in corso») dice poco. La fase la dicono le
prove: una sentenza catalogata, un'udienza fissata, una CTU nominata, un
deposito perfezionato, una notifica consegnata. La lettura sceglie la fase più
avanzata sostenuta da una prova e dichiara quale prova la sostiene; se lo
stato dichiarato non è coerente con i fatti, lo dice.
"""

from __future__ import annotations

from typing import Any

from ._testo import data_da, data_it, pulisci

CODICE_FASE_STRAGIUDIZIALE = "stragiudiziale"
CODICE_FASE_PREPARATORIA = "preparatoria"
CODICE_FASE_NOTIFICATA = "atto_notificato"
CODICE_FASE_ISCRITTA = "iscritta_a_ruolo"
CODICE_FASE_TRATTAZIONE = "trattazione"
CODICE_FASE_ISTRUTTORIA = "istruttoria"
CODICE_FASE_DECISORIA = "decisoria"
CODICE_FASE_DECISA = "decisa"
CODICE_FASE_ESECUTIVA = "esecutiva"
CODICE_FASE_CHIUSA = "chiusa"

_ISTRUTTORIA = {"relazione_peritale_ctu", "perizia_di_parte"}


def fase(
    intestazione: dict[str, Any],
    documenti_letti: dict[str, Any],
    depositi_letti: dict[str, Any],
    notifiche_lette: dict[str, Any],
    cronologia_letta: list[dict[str, Any]],
    scadenze: list[dict[str, Any]],
    oggi: Any,
) -> dict[str, Any]:
    giorno_oggi = data_da(oggi)
    prove: list[str] = []
    codice = CODICE_FASE_STRAGIUDIZIALE
    descrizione = "fase preparatoria o stragiudiziale: nessun atto giudiziario risulta ancora notificato o depositato"
    incoerenze: list[str] = []

    atti = documenti_letti["tutti"]
    etichette = [voce["etichetta"].lower() for voce in atti]
    stato_codice = intestazione.get("stato_codice", "")

    if documenti_letti.get("atto_introduttivo") or any(voce["sezione"] == "atti" for voce in atti):
        codice = CODICE_FASE_PREPARATORIA
        descrizione = "atto di parte redatto, da notificare o depositare"
        atto = documenti_letti.get("atto_introduttivo") or documenti_letti.get("ultimo_atto_di_parte")
        if atto:
            prove.append(f"{atto['etichetta']} ({atto['nome']})")

    if notifiche_lette["perfezionate"]:
        codice = CODICE_FASE_NOTIFICATA
        ultima = notifiche_lette["perfezionate"][-1]
        descrizione = f"atto notificato ({ultima['atto']}, {ultima['data']}): in attesa di iscrizione a ruolo o costituzione"
        prove.append(f"notifica perfezionata: {ultima['atto']} del {ultima['data']}")

    if depositi_letti["perfezionati"] or intestazione.get("rg"):
        codice = CODICE_FASE_ISCRITTA
        descrizione = "causa iscritta a ruolo, in attesa della prima udienza"
        if depositi_letti["perfezionati"]:
            ultimo = depositi_letti["perfezionati"][-1]
            prove.append(f"deposito accettato dalla cancelleria: {ultimo['atto']} del {ultimo['data']}")
        if intestazione.get("rg"):
            prove.append(f"numero di ruolo {intestazione['rg']}")

    udienze_passate = [
        evento for evento in cronologia_letta
        if evento["categoria"] == "udienza" and data_da(evento["data"]) and giorno_oggi and data_da(evento["data"]) <= giorno_oggi
    ]
    if udienze_passate or any("comparsa" in etichetta or "memoria" in etichetta for etichetta in etichette):
        codice = CODICE_FASE_TRATTAZIONE
        descrizione = "fase di trattazione: le parti si sono costituite o si è tenuta udienza"
        if udienze_passate:
            prove.append(f"udienza del {udienze_passate[-1]['data_it']}: {udienze_passate[-1]['titolo']}")

    if any(voce["natura"] in _ISTRUTTORIA for voce in atti) or any(evento["categoria"] == "CTU" for evento in cronologia_letta) or any("prov" in etichetta and "ordinanza" in etichetta for etichetta in etichette):
        codice = CODICE_FASE_ISTRUTTORIA
        descrizione = "fase istruttoria: prove ammesse o consulenza tecnica in corso"
        ctu = next((voce for voce in atti if voce["natura"] == "relazione_peritale_ctu"), None)
        if ctu:
            prove.append(f"{ctu['etichetta']} ({ctu['data_it'] or 'senza data'})")

    if any("precisazione delle conclusioni" in etichetta or "comparsa conclusionale" in etichetta for etichetta in etichette):
        codice = CODICE_FASE_DECISORIA
        descrizione = "fase decisoria: conclusioni precisate, in attesa della decisione"
        prove.append("precisazione delle conclusioni o comparsa conclusionale depositata")

    if documenti_letti.get("sentenze"):
        sentenza = documenti_letti["sentenze"][-1]
        codice = CODICE_FASE_DECISA
        descrizione = f"causa decisa: {sentenza['etichetta']}" + (f" del {sentenza['data_it']}" if sentenza["data_it"] else "")
        prove.append(f"{sentenza['etichetta']} ({sentenza['nome']})")
        if stato_codice in {"APERTO", "IN_CORSO"}:
            incoerenze.append("è presente una sentenza ma lo stato del fascicolo è ancora «in corso»: valutare impugnazione, esecuzione o definizione")

    if any(voce["natura"] == "atto_esecutivo" for voce in atti):
        codice = CODICE_FASE_ESECUTIVA
        descrizione = "fase esecutiva: precetto o pignoramento in atto"
        esecutivo = next(voce for voce in atti if voce["natura"] == "atto_esecutivo")
        prove.append(f"{esecutivo['etichetta']} ({esecutivo['data_it'] or 'senza data'})")

    if stato_codice in {"DEFINITO", "CHIUSO", "ARCHIVIATO"}:
        codice = CODICE_FASE_CHIUSA
        descrizione = f"pratica {intestazione.get('stato')}"
        prove.append(f"stato dichiarato: {intestazione.get('stato')}")

    prossima_udienza = ""
    date_udienza = [data_da(intestazione.get("prossima_udienza"))] + [
        data_da(voce.get("data")) for voce in scadenze if "udienz" in pulisci(voce.get("titolo")).lower()
    ]
    future = sorted(giorno for giorno in date_udienza if giorno and giorno_oggi and giorno >= giorno_oggi)
    if future:
        prossima_udienza = data_it(future[0])
    return {
        "codice": codice,
        "descrizione": descrizione,
        "prove": prove[-4:],
        "incoerenze": incoerenze,
        "prossima_udienza": prossima_udienza,
        "stato_dichiarato": intestazione.get("stato"),
    }


__all__ = ["fase"]
