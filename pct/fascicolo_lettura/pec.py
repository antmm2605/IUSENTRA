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

from datetime import date
from types import SimpleNamespace
from typing import Any

from pct.proposte_decorse import SUPERATA, classifica, e_127_ter
from pct.pec_legal_event_understanding import ricevuta_pec_strutturata
from pct.pec_oggetti_ufficiali import classifica_ricevuta_pec

from ._testo import data_da, data_it, dataora_it, pulisci

QUALITA_DA_CONTROLLARE = {"rosso", "giallo", "da_controllare"}
FIRMA_NON_VALIDA = {"non_valida", "invalida", "errore"}
CORRISPONDENZE = {
    "collegamento": "collegata al fascicolo",
    "rg": "cita il numero di ruolo",
    "cliente": "cita il nome dell'assistito",
}


def _profilo_da_ufficio_giudiziario(messaggio: dict[str, Any]) -> bool:
    profilo = dict(messaggio.get("procedural_profile") or {})
    testo = " ".join(
        pulisci(profilo.get(chiave)).lower()
        for chiave in (
            "ufficio",
            "codice_ufficio",
            "cancelleria",
            "giudice",
            "numero_rg",
            "oggetto_evento",
            "descrizione_evento",
        )
    )
    if not pulisci(profilo.get("numero_rg")):
        return False
    ha_ufficio = bool(
        pulisci(profilo.get("codice_ufficio"))
        or "ufficio giudiziario" in testo
        or "tribunale" in testo
        or "corte" in testo
        or "giudice" in testo
        or "cancelleria" in testo
    )
    ha_atto_processuale = bool(
        pulisci(profilo.get("giudice"))
        or pulisci(profilo.get("cancelleria"))
        or pulisci(profilo.get("oggetto_evento"))
        or pulisci(profilo.get("descrizione_evento"))
    )
    return ha_ufficio and ha_atto_processuale


def _leggi_termine(termine: dict[str, Any], oggi: date | None) -> dict[str, Any]:
    data_proposta = termine.get("deadline") or termine.get("deadline_date") or termine.get("calculated_date")
    registrato = bool(pulisci(termine.get("scadenziario_id")))
    proposta = SimpleNamespace(
        stato="BOZZA", data_scadenza=data_proposta, deadline_profile_code=termine.get("deadline_profile_code"),
        titolo=f"{pulisci(termine.get('deadline_type'))} {pulisci(termine.get('norm_ref'))}",
    )
    superata = not registrato and e_127_ter(proposta) and classifica(proposta, oggi) == SUPERATA
    return {
        "id": pulisci(termine.get("id")),
        "tipo": pulisci(termine.get("deadline_type")).replace("_", " "),
        "norma": pulisci(termine.get("norm_ref")),
        "decorrenza": data_it(termine.get("dies_a_quo_date")),
        "scadenza": data_it(data_proposta),
        "stato": pulisci(termine.get("deterministic_status")),
        "registrato": registrato,
        "proposta_superata": superata,
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


def pec_con_valutazione_notifica(ragionamento: dict[str, Any], fonti_provvedimenti: dict[str, str]) -> set[str]:
    sentenze_per_pec: dict[str, set[str]] = {}
    for atto in ragionamento.get("atti") or ():
        if atto.get("sentenza") and atto.get("appartenenza") == "causa":
            for documento in (atto["id"], *atto.get("copie", ())):
                if fonte := fonti_provvedimenti.get(documento):
                    sentenze_per_pec.setdefault(fonte, set()).add(atto["id"])
    sentenze_con_conclusione = {
        (voce.get("letto") or {}).get("oggetto_id")
        for voce in ragionamento.get("conclusioni") or () if voce.get("codice") == "notifica_sentenza"
    }
    return {fonte for fonte, ids in sentenze_per_pec.items() if len(ids) == 1 and ids <= sentenze_con_conclusione}


def leggi_messaggio(messaggio: dict[str, Any], *, oggi: date | None = None, evento_riscontrato: bool = False,
                   sentenza_riscontrata: bool = False, notifica_valutata: bool = False) -> dict[str, Any]:
    qualita = pulisci(messaggio.get("quality_status")).lower()
    firma = pulisci(messaggio.get("signature_status")).lower()
    daticert = messaggio.get("pec_receipt") or {}
    tipo_ricevuta, _ = classifica_ricevuta_pec(messaggio.get("subject"), daticert_tipo=daticert.get("type"), usa_corpo=False)
    ricevuta = ricevuta_pec_strutturata(daticert) or bool(tipo_ricevuta)
    evento_ricevuta = {"accettazione": "ricevuta_accettazione_pec", "avvenuta_consegna": "ricevuta_consegna_pec"}.get(tipo_ricevuta)
    eventi = [
        {
            "evento": pulisci(voce.get("primary_event")).replace("_", " "),
            "famiglia": pulisci(voce.get("family")).replace("_", " "),
            "priorita": pulisci(voce.get("priority")).lower(),
            "da_rivedere": bool(voce.get("human_review_required")) and not (
                evento_riscontrato
                or evento_ricevuta and voce.get("primary_event") == evento_ricevuta
                or sentenza_riscontrata and voce.get("primary_event") in {"sentenza_a_verbale", "deposito_sentenza"}
            ),
        }
        for voce in list(messaggio.get("eventi") or [])
    ]
    termini = [_leggi_termine(voce, oggi) for voce in list(messaggio.get("termini") or [])
               if not ricevuta or voce.get("scadenziario_id")]
    if notifica_valutata:
        # Le vecchie proposte PEC sono promemoria senza termine, anteriori alla conclusione condivisa.
        termini = [termine for termine in termini if termine["registrato"] or termine["scadenza"]
                   or termine["perentorio"] or termine["tipo"].casefold() not in {
                       "valutare/preparare notifica sentenza",
                       "esame sentenza e valutazione notifica senza termine breve automatico",
                   }]
    udienze = [_leggi_udienza(voce) for voce in list(messaggio.get("udienze") or [])
               if not ricevuta or voce.get("agenda_id")]
    motivi: list[str] = []
    for issue in messaggio.get("issues") or []:
        if issue.get("blocking"):
            motivi.append(pulisci(issue.get("title") or issue.get("code")))
    if firma in FIRMA_NON_VALIDA:
        motivi.append("firma non valida")
    if not evento_riscontrato and messaggio.get("event_type") != "pct_deposito" and any(voce["da_rivedere"] for voce in eventi):
        motivi.append("evento da confermare")
    corrispondenza = pulisci(messaggio.get("corrispondenza")) or ("collegamento" if messaggio.get("collegata") else "")
    collegamento_mancante_da_rivedere = (
        not messaggio.get("collegata")
        and not (corrispondenza == "rg" and _profilo_da_ufficio_giudiziario(messaggio))
    )
    if collegamento_mancante_da_rivedere:
        motivi.append("non collegata al fascicolo")
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


def pec(
    messaggi: list[dict[str, Any]], *, oggi: date | None = None,
    eventi_riscontrati: frozenset[str] = frozenset(),
    sentenze_riscontrate: frozenset[str] = frozenset(),
    pec_sentenze_gia_lette: set[str] | None = None,
) -> dict[str, Any]:
    letti = [
        leggi_messaggio(voce, oggi=oggi, evento_riscontrato=pulisci(voce.get("id")) in eventi_riscontrati,
                       sentenza_riscontrata=pulisci(voce.get("id")) in sentenze_riscontrate,
                       notifica_valutata=pulisci(voce.get("id")) in (pec_sentenze_gia_lette or ()))
        for voce in messaggi
    ]
    letti.sort(key=lambda voce: voce["ordine"])
    termini_da_registrare = [
        {**termine, "oggetto": voce["oggetto"], "data_pec": voce["data"], "messaggio_id": voce["id"]}
        for voce in letti for termine in voce["termini"] if not (termine["registrato"] or termine["proposta_superata"])
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
