"""Le notifiche: presidi, attività e prove di perfezionamento.

Una notifica in proprio a mezzo PEC (L. 53/1994, art. 3-bis; art. 147 c.p.c.)
è perfezionata per il notificante al momento della ricevuta di accettazione e
per il destinatario con la ricevuta di avvenuta consegna (se generata fra le 21
e le 7, alle ore 7). Senza la consegna, la notifica non è provata: la lettura
lo dice senza giri di parole e colloca ogni presidio nella fase della scheda
di `pct/procedura_fasi/notifiche.py`, con le norme che la governano.
"""

from __future__ import annotations

from typing import Any

from pct.procedura_fasi.notifiche import canale_notifica, fase_notifica

from ._testo import data_it, dataora_it, elenco, pulisci

STATI_APERTI = {
    "DETECTED", "NEEDS_REVIEW", "ORIGINAL_TO_ACQUIRE", "NOTIFICATION_CONFIRMED", "RECIPIENTS_TO_VERIFY",
    "READY_FOR_RELATA", "RELATA_DRAFTED", "RELATA_SIGNED", "READY_TO_SEND", "SENT_WAITING_RAC", "RAC_RECEIVED",
    "PARTIAL_DELIVERY", "DELIVERY_FAILED", "PROOF_TO_DEPOSIT", "LEGACY_REVIEW_REQUIRED",
}
STATI_PERFEZIONATE = {"DELIVERY_COMPLETE", "PROOF_DEPOSITED", "CLOSED"}
ESITI_ATTIVITA = {
    "FAVOREVOLE": "perfezionata",
    "PARZIALE": "perfezionata in parte",
    "SFAVOREVOLE": "non andata a buon fine",
    "IN_ATTESA": "in attesa di riscontro",
    "RINVIATO": "rinviata",
    "ANNULLATO": "annullata",
}


def _leggi_presidio(presidio: dict[str, Any]) -> dict[str, Any]:
    stato = pulisci(presidio.get("status")).upper()
    destinatari = [pulisci(voce.get("name")) for voce in list(presidio.get("recipients") or []) if pulisci(voce.get("name"))]
    documento = presidio.get("document") or {}
    canale = canale_notifica(presidio.get("channel") or presidio.get("channel_label")) or "pec"
    fase = fase_notifica(canale, stato)
    return {
        "id": pulisci(presidio.get("id")),
        "origine": "presidio",
        "canale_codice": canale,
        "fase_procedurale": fase.get("nome", ""),
        "prova_attesa": fase.get("prova", ""),
        "fonti_procedurali": list(fase.get("fonti") or []),
        "atto": pulisci((documento or {}).get("name") or (documento or {}).get("label") or presidio.get("notification_case_label")) or "atto da notificare",
        "canale": pulisci(presidio.get("channel_label")),
        "destinatari": destinatari,
        "stato": stato,
        "stato_etichetta": pulisci(presidio.get("status_label")),
        "aperta": stato in STATI_APERTI,
        "perfezionata": stato in STATI_PERFEZIONATE,
        "prossima_azione": pulisci(presidio.get("next_action")),
        "data": data_it(presidio.get("source_effective_at") or presidio.get("updated_at")),
        "scadenza": data_it(presidio.get("explicit_due_at")),
        "fonti": [pulisci(voce) for voce in list(presidio.get("legal_sources") or []) if pulisci(voce)][:3],
    }


def _leggi_attivita(attivita: dict[str, Any]) -> dict[str, Any]:
    esito = pulisci(attivita.get("esito")).upper()
    return {
        "id": pulisci(attivita.get("id")),
        "origine": "attivita",
        "canale_codice": "",
        "fase_procedurale": "",
        "prova_attesa": "",
        "fonti_procedurali": [],
        "atto": pulisci(attivita.get("titolo")) or "notifica",
        "canale": "",
        "destinatari": [],
        "stato": esito,
        "stato_etichetta": ESITI_ATTIVITA.get(esito, esito.lower()),
        "aperta": esito in {"IN_ATTESA", "RINVIATO"},
        "perfezionata": esito in {"FAVOREVOLE", "PARZIALE"},
        "prossima_azione": "",
        "data": data_it(attivita.get("data")),
        "scadenza": "",
        "fonti": [],
        "descrizione": pulisci(attivita.get("descrizione"))[:200],
    }


def notifiche(presidi: list[dict[str, Any]], attivita: list[dict[str, Any]]) -> dict[str, Any]:
    letture = [_leggi_presidio(voce) for voce in presidi]
    letture.extend(_leggi_attivita(voce) for voce in attivita if pulisci(voce.get("tipo")).upper() == "NOTIFICA")
    letture.sort(key=lambda voce: voce["data"][6:] + voce["data"][3:5] + voce["data"][:2] if voce["data"] else "")
    return {
        "tutte": letture,
        "totale": len(letture),
        "aperte": [voce for voce in letture if voce["aperta"]],
        "perfezionate": [voce for voce in letture if voce["perfezionata"]],
        "fallite": [voce for voce in letture if voce["stato"] in {"DELIVERY_FAILED", "SFAVOREVOLE"}],
    }


def descrivi(notifica: dict[str, Any]) -> str:
    pezzi = [notifica["atto"]]
    if notifica["destinatari"]:
        pezzi.append(f"a {elenco(notifica['destinatari'])}")
    if notifica["canale"]:
        pezzi.append(f"via {notifica['canale']}")
    if notifica["data"]:
        pezzi.append(f"del {notifica['data']}")
    return " ".join(pezzi) + (f": {notifica['stato_etichetta']}" if notifica["stato_etichetta"] else "")


__all__ = ["ESITI_ATTIVITA", "STATI_APERTI", "STATI_PERFEZIONATE", "dataora_it", "descrivi", "notifiche"]
