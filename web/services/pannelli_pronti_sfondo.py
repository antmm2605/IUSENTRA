"""Ricalcolo in sfondo dei pannelli pronti.

Due livelli, nell'ordine:
1. ``da_ricalcolare``: i pannelli dei fascicoli aperti di recente o appena chiesti dall'avvocato la cui impronta è
   cambiata (più quelli della prima apertura per i profili che hanno aperto il fascicolo);
2. ``copertura``: tutti i fascicoli non archiviati, per i profili attivi, tutti i pannelli del catalogo nella forma in
   cui l'interfaccia li chiede: prima i fascicoli con una fonte appena cambiata, poi gli aperti di recente, poi i
   termini più vicini, poi gli altri. Così anche un fascicolo non aperto da giorni si apre dal pronto.

Il calcolo rifà la stessa richiesta GET dell'avvocato dentro l'app (stessi controlli di accesso, stesso motore, stesso
salvataggio): nessun documento si rilegge, i motori consultano i dati già consolidati. Il sistema non conosce il
contenuto dei pannelli: elenco, percorsi e dipendenze vengono dal catalogo.

Il controllo (quali voci sono superate) è leggero e gira nel lavoro dello scheduler; il calcolo gira in un
processo separato a bassa priorità (``web.services.pannelli_pronti_calcolatore``), un lotto alla volta.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, Iterator
from urllib.parse import urlsplit

from pct.pannelli_pronti import impronta as impronta_fonti
from pct.pannelli_pronti.archivio import ArchivioPannelli
from web.services.pannelli_pronti_catalogo import PANNELLI, PRIMA_APERTURA, VERSIONE_PANNELLI

logger = logging.getLogger(__name__)
ORE_APERTURA_RECENTE = 72.0
# Profili che hanno consultato i pannelli di recente: i fascicoli si preparano con i loro permessi.
GIORNI_PROFILI_ATTIVI = 30.0
VARIANTI_PER_PANNELLO = 2
MINUTI_ATTESA_LETTURA = 5.0
PANNELLI_PRIORITARI = ("lettura", "passaggi", "quadro", "obblighi-notifica", "scadenze")
_NOMI_PANNELLI = frozenset(pannello.nome for pannello in PANNELLI)
# Ordine di calcolo: preferenza della prima apertura, ma ogni pannello dopo i pannelli che legge (``dipende_da`` del
# catalogo). Così nello stesso giro una fonte si calcola prima di chi la legge e il dipendente non va ricalcolato.
_PREFERENZA = ["dettaglio", "lettura", "passaggi", "obblighi-notifica", "conto-economico", "quadro", "scadenze",
               "documenti", "regia"]


def _ordine_con_dipendenze() -> dict[str, int]:
    dipendenze = {p.nome: set(p.dipende_da) for p in PANNELLI}
    da_ordinare = list(dict.fromkeys(_PREFERENZA + [p.nome for p in PANNELLI]))
    ordinati: list[str] = []
    while da_ordinare:
        pronto = next((n for n in da_ordinare if dipendenze.get(n, set()) <= set(ordinati)), da_ordinare[0])
        ordinati.append(pronto)
        da_ordinare.remove(pronto)
    return {nome: indice for indice, nome in enumerate(ordinati)}


_ORDINE = _ordine_con_dipendenze()


_PERCORSI = {p.nome: p.percorso for p in PANNELLI if p.percorso}
_PRIMA_APERTURA_NOMI = frozenset(p.nome for p in PRIMA_APERTURA)


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


def copertura(archivio: ArchivioPannelli, fonti: impronta_fonti.FontiTenant, *, limite: int = 8,
              giorni_profili: float = GIORNI_PROFILI_ATTIVI) -> list[DaRicalcolare]:
    """Tutti i fascicoli non archiviati: i pannelli mancanti o superati per i profili attivi, in ordine di urgenza.

    Prima i fascicoli con una fonte appena cambiata (avevano un pannello pronto e ora non vale più), poi quelli
    aperti di recente, poi i termini o le udienze più vicini, infine gli altri. Le voci si leggono dall'archivio a
    ogni giro: un'interruzione riprende dal primo pannello non ancora pronto, senza stato da conservare.
    """
    from web.services.pannelli_pronti_priorita import fascicoli_per_priorita
    from web.services.pannelli_pronti_runtime import _chiave_pannello

    profili = [p for p in archivio.profili_attivi(giorni=giorni_profili) if archivio.sessione(p)]
    if not profili:
        return []
    ordine = fascicoli_per_priorita(fonti, archivio.fascicoli_aperti_dal(ORE_APERTURA_RECENTE))
    if not ordine:
        return []
    generazioni = archivio.generazioni()
    attuali = impronta_fonti.impronte(fonti, {f: generazioni.get(f, 0) for f in ordine}, versione=VERSIONE_PANNELLI)
    if not attuali:
        return []  # trigger non preparati
    stati = archivio.stati()
    con_pronto_superato: set[str] = set()
    for _chiave, (fid, salvata, _tentata) in stati.items():
        if salvata and fid in attuali and salvata != attuali[fid]:
            con_pronto_superato.add(fid)
    ordine = [f for f in ordine if f in con_pronto_superato] + [f for f in ordine if f not in con_pronto_superato]
    richieste = {profilo: _richieste_del_profilo(archivio, profilo) for profilo in profili}
    risultato: list[DaRicalcolare] = []
    # Prima i pannelli della prima apertura di tutti i fascicoli, poi gli altri pannelli.
    giri = [(prima, fascicolo_id, profilo) for prima in (True, False) for fascicolo_id in ordine for profilo in profili]
    for prima_apertura, fascicolo_id, profilo in giri:
        attuale = attuali[fascicolo_id]
        for nome, parametri in richieste[profilo]:
            if (nome in _PRIMA_APERTURA_NOMI) != prima_apertura:
                continue
            _fid, salvata, tentata = stati.get(_chiave_pannello(fascicolo_id, nome, parametri, profilo), ("", "", ""))
            if salvata == attuale or tentata == attuale:
                continue
            percorso = _PERCORSI[nome].format(fid=fascicolo_id) + (f"?{parametri}" if parametri else "")
            risultato.append(DaRicalcolare(fascicolo_id, nome, percorso, profilo,
                                           "fonti cambiate" if salvata else "copertura"))
            if len(risultato) >= limite:
                return risultato
    return risultato


def _richieste_del_profilo(archivio: ArchivioPannelli, profilo: str) -> list[tuple[str, str]]:
    """Le richieste da preparare: ogni pannello del catalogo nella forma in cui l'interfaccia lo chiede davvero.

    Le varianti con parametri si prendono da quelle già chieste dal profilo (per esempio ``include`` del dettaglio);
    senza consultazioni si prepara la forma canonica. L'ordine segue la prima apertura della pagina.
    """
    viste: dict[str, list[str]] = {}
    for nome, parametri in archivio.varianti_richieste(profilo):
        if nome in _PERCORSI and len(viste.setdefault(nome, [])) < VARIANTI_PER_PANNELLO:
            viste[nome].append(parametri)
    richieste = []
    for nome in sorted(_PERCORSI, key=lambda n: _ORDINE.get(n, 99)):
        for parametri in viste.get(nome) or [""]:
            richieste.append((nome, parametri))
    return richieste


def ricalcola(app, archivio: ArchivioPannelli, voci: list[DaRicalcolare], *,
              interrompi: Callable[[], bool] | None = None) -> dict[str, int]:
    """Rifà le richieste GET con la sessione del profilo: la vista calcola e salva come per l'avvocato.

    ``interrompi`` (copertura in sfondo) si consulta prima di ogni pannello: una consultazione dell'avvocato in attesa
    ferma il lotto, il resto si riprende al giro successivo.
    """
    from web.services.pannelli_pronti_runtime import AMBIENTE_RICALCOLO

    esiti = {"calcolati": 0, "non_salvati": 0, "errori": 0}
    client = app.test_client()
    sessione_corrente = None
    for voce in voci:
        if interrompi is not None and interrompi():
            break
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
