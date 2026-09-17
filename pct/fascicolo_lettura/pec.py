"""Il presidio PEC del fascicolo: i messaggi che riguardano la pratica e ciò che chiedono.

Le PEC arrivano al presidio (pct/pec_pipeline) e vengono collegate al fascicolo
dal linker; ma una comunicazione di cancelleria può citare il numero di ruolo
o il nome dell'assistito senza essere ancora collegata. La lettura considera
tutte e tre le vie — collegamento, numero di ruolo, nome del cliente — e dice
per ognuna da dove viene la corrispondenza, che cosa il presidio ha già
estratto (termini, udienze, eventi) e che cosa resta da controllare.

Base normativa: le comunicazioni e notificazioni dell'ufficio arrivano via PEC
(art. 136 c.p.c.; D.M. 44/2011, art. 16; Specifiche tecniche DGSIA 7/8/2024,
art. 21) e i termini che contengono decorrono dalla consegna: per questo una
PEC non controllata è un rischio, non una casella piena.
"""

from __future__ import annotations

from typing import Any

from ._testo import data_da, data_it, dataora_it, pulisci

QUALITA_DA_CONTROLLARE = {"rosso", "giallo", "da_controllare"}
FIRMA_NON_VALIDA = {"non_valida", "invalida", "errore"}
CORRISPONDENZE = {
    "collegamento": "collegata al fascicolo",
    "rg": "cita il numero di ruolo",
    "cliente": "cita il nome dell'assistito",
}


def _leggi_termine(termine: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": pulisci(termine.get("id")),
        "tipo": pulisci(termine.get("deadline_type")).replace("_", " "),
        "norma": pulisci(termine.get("norm_ref")),
        "decorrenza": data_it(termine.get("dies_a_quo_date")),
        "scadenza": data_it(termine.get("deadline") or termine.get("deadline_date") or termine.get("calculated_date")),
        "stato": pulisci(termine.get("deterministic_status")),
        "registrato": bool(pulisci(termine.get("scadenziario_id"))),
        "perentorio": bool(termine.get("peremptory")),
        "da_rivedere": bool(termine.get("human_review_required")),
    }


def _leggi_udienza(udienza: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": pulisci(udienza.get("id")),
        "data": data_it(udienza.get("hearing_date")),
        "ora": pulisci(udienza.get("hearing_time")),
        "modalita": pulisci(udienza.get("mode")),
        "registrata": bool(pulisci(udienza.get("agenda_id"))),
        "da_rivedere": bool(udienza.get("human_review_required")),
    }


def leggi_messaggio(messaggio: dict[str, Any]) -> dict[str, Any]:
    qualita = pulisci(messaggio.get("quality_status")).lower()
    firma = pulisci(messaggio.get("signature_status")).lower()
    eventi = [
        {
            "evento": pulisci(voce.get("primary_event")).replace("_", " "),
            "famiglia": pulisci(voce.get("family")).replace("_", " "),
            "priorita": pulisci(voce.get("priority")).lower(),
            "da_rivedere": bool(voce.get("human_review_required")),
        }
        for voce in list(messaggio.get("eventi") or [])
    ]
    termini = [_leggi_termine(voce) for voce in list(messaggio.get("termini") or [])]
    udienze = [_leggi_udienza(voce) for voce in list(messaggio.get("udienze") or [])]
    motivi: list[str] = []
    for issue in messaggio.get("issues") or []:
        if issue.get("blocking"):
            motivi.append(pulisci(issue.get("title") or issue.get("code")))
    if firma in FIRMA_NON_VALIDA:
        motivi.append("firma non valida")
    if messaggio.get("event_type") != "pct_deposito" and any(voce["da_rivedere"] for voce in eventi):
        motivi.append("evento da confermare")
    if not messaggio.get("collegata"):
        motivi.append("non collegata al fascicolo")
    corrispondenza = pulisci(messaggio.get("corrispondenza")) or ("collegamento" if messaggio.get("collegata") else "")
    return {
        "id": pulisci(messaggio.get("id")),
        "oggetto": pulisci(messaggio.get("subject"))[:160] or "(senza oggetto)",
        "mittente": pulisci(messaggio.get("from"))[:120],
        "data": data_it(messaggio.get("received_at")),
        "data_ora": dataora_it(messaggio.get("received_at")),
        "ordine": (data_da(messaggio.get("received_at")) or data_da("1900-01-01")).isoformat(),
        "stato": pulisci(messaggio.get("status")),
        "qualita": qualita,
        "firma": firma,
        "collegata": bool(messaggio.get("collegata")),
        "corrispondenza": corrispondenza,
        "corrispondenza_etichetta": CORRISPONDENZE.get(corrispondenza, ""),
        "eventi": eventi,
        "termini": termini,
        "udienze": udienze,
        "da_controllare": bool(motivi),
        "motivi_controllo": motivi,
    }


def pec(messaggi: list[dict[str, Any]]) -> dict[str, Any]:
    letti = [leggi_messaggio(voce) for voce in messaggi]
    letti.sort(key=lambda voce: voce["ordine"])
    termini_da_registrare = [
        {**termine, "oggetto": voce["oggetto"], "data_pec": voce["data"], "messaggio_id": voce["id"]}
        for voce in letti for termine in voce["termini"] if not termine["registrato"]
    ]
    udienze_da_registrare = [
        {**udienza, "oggetto": voce["oggetto"], "data_pec": voce["data"], "messaggio_id": voce["id"]}
        for voce in letti for udienza in voce["udienze"] if udienza["data"] and not udienza["registrata"]
    ]
    return {
        "tutte": letti,
        "totale": len(letti),
        "collegate": sum(1 for voce in letti if voce["collegata"]),
        "per_corrispondenza": {
            chiave: sum(1 for voce in letti if voce["corrispondenza"] == chiave) for chiave in CORRISPONDENZE
        },
        "da_controllare": [voce for voce in letti if voce["da_controllare"]],
        "termini_da_registrare": termini_da_registrare,
        "udienze_da_registrare": udienze_da_registrare,
        "ultima": letti[-1] if letti else None,
    }


__all__ = ["CORRISPONDENZE", "leggi_messaggio", "pec"]
