"""Ricalcolo in sfondo dei pannelli pronti: i pannelli dei fascicoli aperti di recente la cui impronta è cambiata.

Si ricalcolano solo i pannelli già richiesti almeno una volta, più quelli della prima apertura (dettaglio, quadro,
scadenze, documenti, Lettura, regia, obblighi di notifica) per i profili che hanno aperto il fascicolo. Il calcolo
rifà la stessa richiesta GET dell'avvocato dentro l'app (stessi controlli di accesso, stesso motore, stesso
salvataggio): nessun documento si rilegge, i motori consultano i dati già consolidati.

Il controllo (quali voci sono superate) è leggero e gira nel lavoro dello scheduler; il calcolo gira in un
processo separato a bassa priorità (``web.services.pannelli_pronti_calcolatore``), un lotto alla volta.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Iterator
from urllib.parse import urlsplit

from pct.pannelli_pronti import impronta as impronta_fonti
from pct.pannelli_pronti.archivio import ArchivioPannelli
from web.services.pannelli_pronti_catalogo import PANNELLI, PRIMA_APERTURA, VERSIONE_PANNELLI

logger = logging.getLogger(__name__)
ORE_APERTURA_RECENTE = 72.0
MINUTI_ATTESA_LETTURA = 5.0
PANNELLI_PRIORITARI = ("lettura", "passaggi", "quadro", "obblighi-notifica", "scadenze")
_NOMI_PANNELLI = frozenset(pannello.nome for pannello in PANNELLI)
# I pannelli che leggono la Lettura o la sintesi delle notifiche seguono le loro fonti.
_ORDINE = {nome: indice for indice, nome in enumerate(dict.fromkeys(
    ["dettaglio", "lettura", "passaggi", "obblighi-notifica", "quadro", "scadenze", "documenti", "regia"]
    + [p.nome for p in PANNELLI]))}



@dataclass(frozen=True)
class DaRicalcolare:
    fascicolo_id: str
    pannello: str
    percorso: str
    profilo: str
    motivo: str


def studi(app) -> Iterator[tuple[Any, dict]]:
    """(studio, data_paths) per ogni studio attivo; senza multi-studio un solo elemento."""
    from flask import g
    from pct.tenant import GestioneTenant, StatoTenant
    from web.services.fascicoli_presidi_runtime import _attach_tenant_context

    manager = GestioneTenant(registry_path=app.config["TENANTS_REGISTRY"]) if app.config.get("MULTI_TENANT") else None
    owners = [o for o in manager.lista() if o.stato != StatoTenant.SOSPESO] if manager else [None]
    for owner in owners:
        with app.test_request_context("/__scheduler/pannelli-pronti"):
            if owner is not None:
                _attach_tenant_context(manager, owner)
            data_paths = dict(getattr(g, "data_paths", {}) or {})
        if data_paths.get("STUDIO_DB"):
            yield owner, data_paths


def da_ricalcolare(archivio: ArchivioPannelli, fonti: impronta_fonti.FontiTenant, *,
                   ore: float = ORE_APERTURA_RECENTE, limite: int = 200,
                   solo_pannelli_prioritari: bool = False, fascicolo_richiesto: str = "") -> list[DaRicalcolare]:
    """Le voci superate (o mancanti per la prima apertura) dei fascicoli aperti di recente, in ordine di calcolo."""
    from web.services.pannelli_pronti_runtime import _chiave_pannello

    risultato: list[DaRicalcolare] = []
    if fascicolo_richiesto:
        in_attesa = (fascicolo_richiesto,)
        fascicoli = in_attesa
    else:
        in_attesa = archivio.fascicoli_in_attesa_di_lettura(minuti=MINUTI_ATTESA_LETTURA, pannelli=PANNELLI_PRIORITARI)
        fascicoli = in_attesa if solo_pannelli_prioritari else dict.fromkeys([*in_attesa, *archivio.fascicoli_aperti_dal(ore)])
    for fascicolo_id in fascicoli:
        attuale = impronta_fonti.impronta(fonti, fascicolo_id, generazione=archivio.generazione(fascicolo_id),
                                          versione=VERSIONE_PANNELLI)
        if attuale is None:
            return []  # trigger non preparati: nessun pannello si salva, niente da ricalcolare
        inizio = len(risultato)
        voci = archivio.voci_del_fascicolo(fascicolo_id)
        # Una vecchia versione della chiave può convivere con quella attuale.
        # Le richieste dello stesso pannello e profilo condividono un solo calcolo.
        stati = {chiave: (impronta_salvata, tentata) for chiave, _nome, _percorso, _profilo, impronta_salvata, tentata in voci}
        per_richiesta = {}
        for _chiave, pannello, percorso, profilo, impronta_salvata, tentata in voci:
            per_richiesta.setdefault((pannello, percorso, profilo), (impronta_salvata, tentata))
        presenti = {(pannello, profilo) for pannello, _percorso, profilo in per_richiesta}
        for (pannello, percorso, profilo), precedente in per_richiesta.items():
            if pannello not in _NOMI_PANNELLI or (solo_pannelli_prioritari and pannello not in PANNELLI_PRIORITARI):
                continue
            chiave_attuale = _chiave_pannello(fascicolo_id, pannello, urlsplit(percorso).query, profilo)
            impronta_salvata, tentata = stati.get(chiave_attuale, precedente)
            if impronta_salvata != attuale and tentata != attuale:
                risultato.append(DaRicalcolare(fascicolo_id, pannello, percorso, profilo,
                                               "mai calcolato" if not impronta_salvata else "fonti cambiate"))
        if solo_pannelli_prioritari:
            risultato[inizio:] = sorted(risultato[inizio:], key=lambda voce: PANNELLI_PRIORITARI.index(voce.pannello))
            if len(risultato) >= limite:
                break
            continue
        for profilo in archivio.profili_del_fascicolo(fascicolo_id):
            for pannello in PRIMA_APERTURA:
                percorso = pannello.percorso.format(fid=fascicolo_id)
                if (pannello.nome, profilo) not in presenti:
                    risultato.append(DaRicalcolare(fascicolo_id, pannello.nome, percorso, profilo, "prima apertura"))
        risultato[inizio:] = sorted(
            risultato[inizio:],
            key=lambda v: (v.pannello != "lettura" or fascicolo_id not in in_attesa, _ORDINE.get(v.pannello, 99)),
        )
        if len(risultato) >= limite:
            break
    return risultato[:limite]


def ricalcola(app, archivio: ArchivioPannelli, voci: list[DaRicalcolare]) -> dict[str, int]:
    """Rifà le richieste GET con la sessione del profilo: la vista calcola e salva come per l'avvocato."""
    from web.services.pannelli_pronti_runtime import AMBIENTE_RICALCOLO

    esiti = {"calcolati": 0, "non_salvati": 0, "errori": 0}
    client = app.test_client()
    sessione_corrente = None
    for voce in voci:
        sessione = archivio.sessione(voce.profilo)
        if not sessione:
            esiti["errori"] += 1
            continue
        if sessione != sessione_corrente:
            with client.session_transaction() as s:
                s.clear()
                s.update(sessione)
            sessione_corrente = sessione
        try:
            risposta = client.get(voce.percorso, headers={"Accept": "application/json"},
                                  environ_overrides={AMBIENTE_RICALCOLO: True, "REMOTE_ADDR": "127.0.0.1"})
        except Exception as exc:
            logger.warning("Pannello %s del fascicolo %s non ricalcolato: %s", voce.pannello, voce.fascicolo_id, exc)
            esiti["errori"] += 1
            continue
        if risposta.headers.get("X-Iusentra-Pannello") == "calcolato":
            esiti["calcolati"] += 1
        else:
            esiti["non_salvati"] += 1
    return esiti
