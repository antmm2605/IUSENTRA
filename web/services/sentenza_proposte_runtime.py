"""Dalla sentenza: definizione del fascicolo e crediti liquidati, automatici solo se certi.

Il lettore «proposta_definizione» del registro delle letture esamina, in
sfondo e solo sui testi già salvati, i documenti nuovi o letti con una regola
superata; se il testo è una sentenza del procedimento che decide la causa nel
grado (art. 132 c.p.c.; art. 88 c.p.a.) e il credito delle spese si legge con
certezza (`pct.sentenza_automatica`), registra credito e definizione con autore
«automatico dalla sentenza» (`sentenza_automatica_runtime`), annullabili
dall'avvocato. Negli altri casi registra una proposta che l'avvocato conferma
o respinge dal pannello «Letture e verifiche».

Il pannello mostra anche i crediti che il controllo economico ha letto nel
capo spese (art. 91 c.p.c. a favore del cliente, art. 93 c.p.c. distratti al
difensore antistatario): si confermano o si respingono con l'endpoint del
controllo economico e, confermati, diventano una parcella (D.M. 55/2014).

Nessuna lettura di file in una richiesta: la GET consulta il registro.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any
from urllib.parse import quote

from pct.archivio_letture.natura_provvedimento import e_provvedimento, tipo_normalizzato
from pct.fascicolo_sentenza_archiviazione import VERSIONE_PROPOSTA, verifica_sentenza_da_archiviare
from pct.ora_italiana import ROME_TZ

logger = logging.getLogger(__name__)

LETTORE = "proposta_definizione"
STATI_CHIUSI = frozenset({"DEFINITO", "ARCHIVIATO"})
EVENTI_CREDITO = {"apri_credito_cliente": "Spese liquidate a favore del cliente (art. 91 c.p.c.)",
                  "apri_credito_avvocato_antistatario": "Spese distratte al difensore antistatario (art. 93 c.p.c.)"}
_ETICHETTE_STATO = {"to_review": "Da confermare", "confirmed": "Confermato"}


def _testo(valore: Any) -> str:
    return str(getattr(valore, "value", valore) or "").strip()


def _stato(fascicolo: Any) -> str:
    return _testo(getattr(fascicolo, "stato", "")).upper()


def _euro(importo: Any) -> str:
    try:
        valore = float(importo)
    except (TypeError, ValueError):
        return ""
    intero, decimali = f"{valore:,.2f}".split(".")
    return f"€ {intero.replace(',', '.')},{decimali}"


def _catalogo(fascicolo_id: str) -> dict[str, tuple[str, str]]:
    """Etichetta e natura del catalogo dal contenuto, per documento (SQL, nessuna pipeline)."""
    try:
        from web.services.document_intelligence_runtime import build_document_ai_service, document_ai_tenant_id

        righe = build_document_ai_service().repository.list_catalog_assignments(document_ai_tenant_id(), fascicolo_id)
    except Exception:
        return {}
    return {_testo(getattr(r, "document_id", "")): (_testo(getattr(r, "document_label", "")), _testo(getattr(r, "document_nature", "")))
            for r in righe}


def _cliente(fascicolo: Any) -> dict[str, Any]:
    try:
        from web.helpers import get_clienti

        cliente = get_clienti().get(fascicolo.id_cliente) if getattr(fascicolo, "id_cliente", "") else None
        return cliente.to_dict() if cliente is not None else {}
    except Exception:
        return {}


def _estremi(testo: str) -> dict[str, str]:
    from pct.fascicolo_sentenza_economica import analyze_sentenza_tribunale_text

    try:
        estratto = analyze_sentenza_tribunale_text(testo)
    except Exception:
        return {}
    if not estratto.found:
        return {}
    return {"numero": _testo(estratto.sentence_number), "anno": _testo(estratto.sentence_year), "data": _testo(estratto.sentence_date)}


def _da_esaminare(registro: Any, tenant: str, fascicolo_id: str) -> list[Any]:
    nuovi = registro.da_leggere(tenant, fascicolo_id, LETTORE, tipi=("documento",))
    superati = registro.superati(tenant, fascicolo_id, LETTORE, versione=VERSIONE_PROPOSTA, tipi=("documento",))
    unici = {(o.tipo, o.oggetto_id, o.impronta): o for o in [*nuovi, *superati]}
    return list(unici.values())


def _passaggio_dispositivo(testo: str) -> str:
    """Le prime righe del dispositivo letto: la citazione che l'avvocato riscontra nella sentenza."""
    from pct.sentenza_conclusiva import valuta_sentenza

    return " ".join(valuta_sentenza(testo)["dispositivo"].split())[:300]


def esamina_oggetto(*, fascicolo: Any, oggetto: Any, documento: Any, testo: str, catalogo: tuple[str, str] = ("", ""),
                    cliente: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """L'esito del lettore per un documento; None se il testo non c'è ancora e serve per decidere."""
    tipo = tipo_normalizzato(getattr(documento, "tipo", ""))
    etichetta, natura = catalogo
    if not testo.strip():
        return None
    if not e_provvedimento(tipo, testo=testo, etichetta_catalogo=etichetta, natura_catalogo=natura):
        return {"pertinente": False, "proposta": False, "motivo": "Il documento non è un provvedimento del giudice."}
    impronta = _testo(getattr(oggetto, "sha256", "") or getattr(oggetto, "sha256_archivio", "")).lower()
    verifica = verifica_sentenza_da_archiviare(
        fascicolo=fascicolo, testo=testo, cliente=cliente or {},
        fonte={"verified_original": True, "sha256": impronta, "name": _testo(getattr(oggetto, "nome", "")),
               "document_id": _testo(getattr(oggetto, "oggetto_id", ""))},
    )
    return {
        "pertinente": True, "proposta": bool(verifica.get("eligible")), "motivo": _testo(verifica.get("reason")),
        "grado": _testo(verifica.get("grado")), "importo": verifica.get("amount"), "capo_spese": _testo(verifica.get("quote"))[:400],
        "compensate": bool(verifica.get("compensate")), "estremi": _estremi(testo),
        "dispositivo": _passaggio_dispositivo(testo) if verifica.get("eligible") else "",
    }


def aggiorna_proposte_definizione(fascicolo: Any, registro: Any, tenant: str, *, limite: int = 50) -> dict[str, int]:
    """Lavoro di sfondo: esamina solo i documenti nuovi o letti con una regola superata."""
    from web.services.archivio_letture_runtime import testi_indice_archivio

    fascicolo_id = _testo(getattr(fascicolo, "id", ""))
    report = {"esaminati": 0, "proposte": 0, "automatiche": 0, "in_attesa_testo": 0, "errori": 0}
    if not fascicolo_id:
        return report
    pendenti = _da_esaminare(registro, tenant, fascicolo_id)
    precedenti = {(r.oggetto_id, r.sha256): r for r in registro.letture(tenant, fascicolo_id, lettore=LETTORE)}
    if pendenti:
        documenti = {_testo(getattr(d, "id", "")): d for d in getattr(fascicolo, "documenti", []) or []}
        # Un fascicolo già definito si esamina ancora: il credito certo della sentenza va registrato lo stesso.
        chiuso = _stato(fascicolo) == "ARCHIVIATO"
        testi = {} if chiuso else testi_indice_archivio(fascicolo)
        catalogo = {} if chiuso else _catalogo(fascicolo_id)
        cliente = {} if chiuso else _cliente(fascicolo)
        chiusi_dal_motore = {(r.oggetto_id, r.sha256) for r in registro.letture(tenant, fascicolo_id, lettore="motore_documenti")
                             if r.stato in {"letto", "non_leggibile"}}
        for oggetto in pendenti[:max(1, int(limite))]:
            documento = documenti.get(oggetto.oggetto_id)
            try:
                if documento is None:
                    registro.segna_letto(tenant, fascicolo_id, oggetto, LETTORE, versione=VERSIONE_PROPOSTA, stato="non_leggibile",
                                         esito={"pertinente": False, "motivo": "Documento non più presente nel fascicolo."})
                    continue
                if chiuso:
                    esito = {"pertinente": False, "proposta": False, "motivo": "Fascicolo archiviato."}
                else:
                    esito = esamina_oggetto(fascicolo=fascicolo, oggetto=oggetto, documento=documento,
                                            testo=testi.get(oggetto.oggetto_id, ""), catalogo=catalogo.get(oggetto.oggetto_id, ("", "")),
                                            cliente=cliente)
                if esito is None:
                    if (oggetto.oggetto_id, oggetto.impronta) in chiusi_dal_motore:
                        # Il motore documenti ha già chiuso la fonte senza un testo salvato: non resta «da leggere» per sempre.
                        registro.segna_letto(tenant, fascicolo_id, oggetto, LETTORE, versione=VERSIONE_PROPOSTA, stato="non_leggibile",
                                             esito={"pertinente": False, "motivo": "Testo del documento non disponibile."})
                    else:
                        report["in_attesa_testo"] += 1
                    continue
                vecchia = precedenti.get((oggetto.oggetto_id, oggetto.impronta))
                for chiave in ("decisione", "automatica"):
                    if vecchia is not None and vecchia.esito.get(chiave):
                        # Decisione dell'avvocato e registrazione automatica (anche annullata) restano con la regola nuova.
                        esito[chiave] = vecchia.esito[chiave]
                automatica = _registra_se_certa(fascicolo, oggetto, testi.get(oggetto.oggetto_id, ""), esito)
                registro.segna_letto(tenant, fascicolo_id, oggetto, LETTORE, versione=VERSIONE_PROPOSTA, esito=esito)
                if automatica:
                    _dopo_decisione(fascicolo_id, registro, esito["decisione"], oggetto.impronta,
                                    rationale="Registrazione automatica dalla sentenza: identità, dispositivo e credito certi")
                report["esaminati"] += 1
                report["automatiche"] += int(automatica)
                report["proposte"] += int(bool(esito.get("proposta")) and not esito.get("decisione"))
            except Exception as exc:
                report["errori"] += 1
                logger.warning("Proposta di definizione non esaminata per %s/%s: %s", fascicolo_id, oggetto.oggetto_id, exc)
    restano = len(pendenti) - report["esaminati"]
    try:
        registro.segna_fascicolo(tenant, fascicolo_id, LETTORE, impronta=VERSIONE_PROPOSTA, oggetti_totali=len(pendenti),
                                 oggetti_letti=report["esaminati"], stato="completa" if restano <= 0 else "parziale",
                                 versione=VERSIONE_PROPOSTA)
    except Exception as exc:
        logger.debug("Riga del lettore proposte non registrata per %s: %s", fascicolo_id, exc)
    return report


def _registra_se_certa(fascicolo: Any, oggetto: Any, testo: str, esito: dict[str, Any]) -> bool:
    """Caso certo: credito e definizione registrati in automatico; caso incerto: il motivo resta nell'esito."""
    if not esito.get("proposta") or esito.get("decisione") or esito.get("automatica"):
        return False
    from web.services.sentenza_automatica_runtime import registra_se_certa

    registrazione = registra_se_certa(fascicolo=fascicolo, oggetto=oggetto, testo=testo, esito=esito)
    if not registrazione.get("registrata"):
        esito["non_automatica"] = registrazione.get("motivi") or []
        return False
    esito["automatica"] = registrazione
    esito["decisione"] = {"esito": "automatica", "da": registrazione["da"], "il": registrazione["il"]}
    return True


def proposte_definizione(fascicolo: Any, registro: Any, tenant: str) -> list[dict[str, Any]]:
    """Le proposte aperte, sulle fonti ancora presenti con la stessa impronta."""
    fascicolo_id = _testo(getattr(fascicolo, "id", ""))
    if _stato(fascicolo) in STATI_CHIUSI:
        return []
    presenti = {(o.oggetto_id, o.impronta): o for o in registro.oggetti(tenant, fascicolo_id) if o.presente and o.tipo == "documento"}
    proposte = []
    for lettura in registro.letture(tenant, fascicolo_id, lettore=LETTORE):
        esito = lettura.esito or {}
        oggetto = presenti.get((lettura.oggetto_id, lettura.sha256))
        if lettura.stato != "letto" or not esito.get("proposta") or esito.get("decisione") or oggetto is None:
            continue
        estremi = esito.get("estremi") or {}
        proposte.append({
            "id": f"{lettura.oggetto_id}:{lettura.sha256}",
            "documentoId": lettura.oggetto_id,
            "documento": _testo(oggetto.nome) or "Sentenza",
            "anteprima": f"/fascicoli/{quote(fascicolo_id, safe='')}/documenti/{quote(lettura.oggetto_id, safe='')}/visualizza",
            "citazione": _testo(esito.get("dispositivo")) or _testo(esito.get("capo_spese")),
            "motivo": _testo(esito.get("motivo")),
            "nonAutomatica": [_testo(m) for m in esito.get("non_automatica") or [] if _testo(m)],
            "numero": _testo(estremi.get("numero")), "anno": _testo(estremi.get("anno")), "data": _testo(estremi.get("data")),
            "importo": esito.get("importo"), "importoLabel": _euro(esito.get("importo")) if esito.get("importo") is not None else "",
            "capoSpese": _testo(esito.get("capo_spese")), "compensate": bool(esito.get("compensate")),
        })
    return proposte


def _parcelle_per_evento(fascicolo_id: str) -> dict[str, str]:
    try:
        from web.helpers import get_fatturazione

        parcelle = get_fatturazione().per_fascicolo(fascicolo_id)
    except Exception:
        return {}
    esito = {}
    for parcella in parcelle:
        dati = getattr(parcella, "dati_personalizzati", {}) or {}
        if isinstance(dati, dict) and dati.get("event_id") and _testo(getattr(parcella, "stato", "")).upper() != "ANNULLATA":
            esito[_testo(dati["event_id"])] = _testo(getattr(parcella, "numero", "")) or _testo(getattr(parcella, "id", ""))
    return esito


def _fonti_crediti(fascicolo_id: str, audits: list[dict[str, Any]], registro: Any, tenant: str) -> dict[str, dict[str, Any]]:
    """Per ogni controllo economico: documento da visualizzare, passaggio del capo spese, numero e data della sentenza."""
    from web.services.sentenza_economic_runtime import fonte_audit

    try:
        inventario = registro.oggetti(tenant, fascicolo_id)
        estremi = {r.sha256.lower(): (r.esito or {}).get("estremi") or {}
                   for r in registro.letture(tenant, fascicolo_id, lettore=LETTORE) if r.stato == "letto"}
    except Exception:
        inventario, estremi = [], {}
    fonti = {}
    for audit in audits:
        fonte = fonte_audit(audit, inventario, fascicolo_id) or {}
        capo = (((audit.get("audit") or {}).get("sentenza") or {}).get("spese_liquidate") or {}).get("testo_capo_spese")
        dati = estremi.get(_testo(audit.get("document_hash_sha256")).lower()) or {}
        fonti[_testo(audit.get("id"))] = {"href": fonte.get("href", ""), "documento": fonte.get("label", ""),
                                         "citazione": _testo(capo)[:400], "numero": _testo(dati.get("numero")),
                                         "anno": _testo(dati.get("anno")), "data": _testo(dati.get("data"))}
    return fonti


def crediti_da_sentenza(fascicolo_id: str, registro: Any = None, tenant: str = "") -> tuple[bool, list[dict[str, Any]]]:
    """I crediti letti nel capo spese, una volta sola, da confermare o già confermati, con fonte e parcella.

    I crediti registrati in automatico si mostrano con la loro registrazione (`registrazioni_automatiche`).
    """
    from pct.sentenza_automatica import AUTORE

    try:
        from web.services.sentenza_economic_runtime import build_sentenza_economic_payload

        payload = build_sentenza_economic_payload(fascicolo_id)
    except Exception:
        logger.exception("Crediti da sentenza non disponibili per %s", fascicolo_id)
        return False, []
    if not payload.get("ok"):
        return False, []
    parcelle = _parcelle_per_evento(fascicolo_id)
    fonti = _fonti_crediti(fascicolo_id, payload.get("audits") or [], registro, tenant) if registro is not None else {}
    crediti = []
    for evento in payload.get("eventi") or []:
        tipo = _testo(evento.get("event_type"))
        stato = _testo(evento.get("status"))
        if tipo not in EVENTI_CREDITO or stato not in _ETICHETTE_STATO or _testo(evento.get("reviewed_by")) == AUTORE:
            continue
        evento_id = _testo(evento.get("id"))
        gemelli = [evento_id, *[_testo(e) for e in evento.get("duplicati") or []]]
        crediti.append({
            "eventId": evento_id, "tipo": tipo, "etichetta": EVENTI_CREDITO[tipo],
            "importo": evento.get("amount"), "importoLabel": _euro(evento.get("amount")) if evento.get("amount") is not None else "",
            "stato": stato, "statoLabel": _ETICHETTE_STATO[stato],
            "parcella": next((parcelle[e] for e in gemelli if e in parcelle), ""),
            **fonti.get(_testo(evento.get("source_id")), {"href": "", "documento": "", "citazione": "", "numero": "", "anno": "", "data": ""}),
        })
    return True, crediti


def proposte_sentenza_payload(fascicolo: Any) -> dict[str, Any]:
    from web.services.registro_letture_runtime import registro_corrente, tenant_corrente

    from web.services.sentenza_automatica_runtime import registrazioni_automatiche

    fascicolo_id = _testo(getattr(fascicolo, "id", ""))
    registro, tenant = registro_corrente(sola_lettura=True), tenant_corrente()
    attivo, crediti = crediti_da_sentenza(fascicolo_id, registro, tenant)
    return {"stato": _stato(fascicolo), "definizione": proposte_definizione(fascicolo, registro, tenant),
            "crediti": crediti, "automatiche": registrazioni_automatiche(fascicolo, registro, tenant, _parcelle_per_evento(fascicolo_id)),
            "controlloEconomicoAttivo": attivo}


def decidi_definizione(fascicolo: Any, proposta_id: str, *, esito: str, utente: str = "") -> dict[str, Any]:
    """Conferma (fascicolo definito, con la sentenza come fonte) o respingi la proposta; annulla una registrazione automatica."""
    from pct.fascicoli import StatoFascicolo
    from pct.stato_fascicolo import Prova, ammessa
    from web.helpers import get_fascicoli
    from web.services.registro_letture_runtime import registro_corrente, tenant_corrente

    if esito == "annulla":
        from web.services.sentenza_automatica_runtime import annulla_automatica

        return annulla_automatica(fascicolo, proposta_id, utente=utente)
    if esito not in {"conferma", "respingi"}:
        raise ValueError("Decisione non valida: conferma, respingi o annulla.")
    fascicolo_id = _testo(getattr(fascicolo, "id", ""))
    oggetto_id, _, impronta = _testo(proposta_id).rpartition(":")
    registro, tenant = registro_corrente(), tenant_corrente()
    lettura = next((r for r in registro.letture(tenant, fascicolo_id, lettore=LETTORE)
                    if r.oggetto_id == oggetto_id and r.sha256 == impronta and r.stato == "letto"), None)
    oggetto = registro.oggetto(tenant, fascicolo_id, "documento", oggetto_id)
    if lettura is None or not lettura.esito.get("proposta") or oggetto is None or not oggetto.presente or oggetto.impronta != impronta:
        raise ValueError("Proposta non più valida: il documento è cambiato o è stato rimosso.")
    if lettura.esito.get("decisione"):
        raise ValueError("Proposta già decisa.")
    if esito == "conferma":
        estremi = lettura.esito.get("estremi") or {}
        numero = f" n. {estremi['numero']}{'/' + estremi['anno'] if estremi.get('anno') else ''}" if estremi.get("numero") else ""
        norma = "art. 88 c.p.a." if lettura.esito.get("grado") == "amministrativo" else "art. 132 c.p.c."
        prova = Prova(StatoFascicolo.DEFINITO, f"Sentenza{numero} confermata dall'avvocato come decisione della causa",
                      f"documento «{_testo(oggetto.nome)}», SHA-256 {impronta}; {norma}", data=_testo(estremi.get("data")))
        if not ammessa(getattr(fascicolo, "stato", ""), prova):
            raise ValueError("Il fascicolo non può passare a «definito» dallo stato attuale.")
        get_fascicoli().cambia_stato(fascicolo_id, StatoFascicolo.DEFINITO,
                                     note=prova.nota() + " La definizione non attesta il passaggio in giudicato.",
                                     avvocato=utente or "avvocato")
    decisione = {"esito": "confermata" if esito == "conferma" else "respinta", "da": utente,
                 "il": datetime.now(ROME_TZ).isoformat(timespec="seconds")}
    registro.segna_letto(tenant, fascicolo_id, oggetto, LETTORE, versione=lettura.versione_lettore,
                         esito={**lettura.esito, "decisione": decisione})
    _dopo_decisione(fascicolo_id, registro, decisione, impronta)
    return {"proposta": proposta_id, **decisione}


def _dopo_decisione(fascicolo_id: str, registro: Any, decisione: dict[str, Any], impronta: str,
                    rationale: str = "Decisione dell'avvocato sulla proposta di definizione") -> None:
    """Traccia firmata della decisione, sintesi e cache allineate: errori qui non annullano la decisione."""
    try:
        from web.services.sentenza_economic_runtime import _repo, _tenant_id

        _repo().record_decision(tenant_id=_tenant_id(), actor_id=decisione["da"] or "avvocato", kind="definizione_da_sentenza",
                                subject_ref=fascicolo_id, decision=decisione["esito"],
                                rationale=rationale, evidence={"sha256": impronta})
    except Exception:
        logger.debug("Decisione sulla definizione non registrata nella traccia firmata", exc_info=True)
    try:
        from web.helpers import get_fascicoli
        from web.services.archivio_letture_runtime import _aggiorna_sintesi
        from web.services.react_dashboard_cache import clear_dashboard_payload_cache
        from web.services.react_fascicoli_cache import clear_react_fascicoli_list_cache

        fascicolo = get_fascicoli().get(fascicolo_id)
        if fascicolo is not None:
            _aggiorna_sintesi(fascicolo, registro)
        clear_react_fascicoli_list_cache()
        clear_dashboard_payload_cache()
    except Exception:
        logger.debug("Sintesi o cache non aggiornate dopo la decisione", exc_info=True)


__all__ = ["LETTORE", "aggiorna_proposte_definizione", "crediti_da_sentenza", "decidi_definizione", "esamina_oggetto",
           "proposte_definizione", "proposte_sentenza_payload"]
