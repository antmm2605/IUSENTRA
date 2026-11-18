"""Raccoglie in sfondo le fonti del ragionamento di un fascicolo: dati già letti, mai una nuova lettura.

Le fonti vengono dall'archivio delle letture (fatti collaudati e testi dell'indice documentale), dal catalogo
documenti, dai depositi, dalla fatturazione, dal presidio economico, dallo scadenziario e dall'agenda. Nessun
documento si rilegge qui (regola del registro delle letture): se un testo non c'è, il ragionamento lo dichiara.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from pct.ragionamento import FontiCausa
from pct.registro_letture.lettori import LETTORE_PERCORSO_CONCLUSO


def _testo(valore: Any) -> str:
    return " ".join(str(valore or "").split()).strip()


def _enum(valore: Any) -> str:
    return _testo(getattr(valore, "value", valore))


def _sicuro(funzione, riserva):
    try:
        return funzione()
    except Exception:
        return riserva


def _documenti(fascicolo: Any) -> list[dict[str, Any]]:
    from web.services.archivio_letture_runtime import testi_indice_archivio
    from web.services.react_fascicoli_bridge import _sql_document_catalog_by_id

    catalogo = _sicuro(lambda: _sql_document_catalog_by_id(fascicolo), {})
    testi = _sicuro(lambda: testi_indice_archivio(fascicolo), {})
    righe = []
    for documento in list(getattr(fascicolo, "documenti", []) or []):
        oid = _testo(getattr(documento, "id", ""))
        voce = catalogo.get(oid)
        righe.append({
            "id": oid,
            "nome": _testo(getattr(documento, "nome", "") or getattr(documento, "nome_file", "")),
            "data_documento": _testo(getattr(documento, "data_documento", ""))[:10],
            "natura": _testo(getattr(voce, "document_nature", "")) if voce else "",
            "etichetta": _testo(getattr(voce, "document_label", "")) if voce else "",
            "testo": testi.get(oid, ""),
            "sha256": _testo(getattr(documento, "hash_contenuto_sha256", "") or getattr(documento, "hash_sha256", "")),
        })
    return righe


def _fatti(fascicolo_id: str) -> list[dict[str, Any]]:
    from web.services.registro_letture_runtime import registro_corrente, tenant_corrente

    registro = registro_corrente()
    return [f.to_dict() for f in registro.fatti(tenant_corrente(), fascicolo_id, verifiche=None)]


def _depositi(fascicolo: Any) -> list[dict[str, Any]]:
    from web.services.correlazioni_ricevute_archivio import depositi_da_archivio

    return [{"id": _testo(d.id), "tipo_atto": _testo(getattr(d, "tipo_atto", "")), "stato": _enum(getattr(d, "stato", "")),
             "data": _testo(getattr(d, "timestamp", ""))[:10], "numero_rg": "",
             "nome_atto_principale": _testo(getattr(d, "nome_atto_principale", "")),
             "data_accettazione": _testo(getattr(d, "data_accettazione", "")),
             "id_deposito_esterno": _testo(getattr(d, "id_deposito_esterno", "")),
             "documenti_ids": list(getattr(d, "documenti_ids", []) or []),
             "consegne_archivio": list(getattr(d, "consegne_archivio", ()) or ())} for d in depositi_da_archivio(fascicolo)]


def _economia(fascicolo: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    from web.helpers import get_fatturazione
    from web.services.react_fascicoli_bridge import payment_summary_for_fascicolo_fast

    parcelle = list(get_fatturazione().per_fascicolo(fascicolo.id))
    righe_parcelle = [{
        "id": _testo(p.id), "numero": _testo(getattr(p, "numero", "")), "tipo": _enum(getattr(p, "tipo", "")),
        "stato": _enum(getattr(p, "stato", "")), "totale": float(getattr(p, "totale", 0) or 0),
        "data": _testo(getattr(p, "data_emissione", "")), "descrizione": _testo(getattr(p, "descrizione", "") or getattr(p, "oggetto", "")),
        "data_pagamento": _testo(getattr(p, "data_pagamento", "")), "metodo": _enum(getattr(p, "metodo_pagamento", "")),
    } for p in parcelle]
    presidio = dict(payment_summary_for_fascicolo_fast(fascicolo, parcelle=parcelle) or {})
    return righe_parcelle, _pagamenti(presidio), _stato_contributo(presidio)


def _stato_contributo(presidio: dict[str, Any]) -> dict[str, Any]:
    voce = (presidio.get("items") or {}).get("contributo_unificato") or {}
    return dict(voce.get("statoContributo") or {})


def _pagamenti(presidio: dict[str, Any]) -> list[dict[str, Any]]:
    return [{
        "voce": chiave, "stato": _testo(voce.get("status")), "importo": voce.get("importo"), "origine": _testo(voce.get("origine")),
        "documento": _testo(voce.get("documentoFonteRaw") or voce.get("documentoFonte")),
        "data": _testo(voce.get("dataPagamentoIso")), "note": _testo(voce.get("note")),
        "proforma_id": _testo(voce.get("proformaId")), "autore": _testo(voce.get("updatedBy")),
        "storico": list(voce.get("history") or []),
    } for chiave, voce in (presidio.get("items") or {}).items()]


def _scadenze(fascicolo_id: str) -> list[dict[str, Any]]:
    from web.helpers import get_scadenziario

    return [{"titolo": _testo(s.titolo), "data": _testo(getattr(s, "data_scadenza", "") or getattr(s, "data", ""))[:10],
             "stato": _enum(getattr(s, "stato", ""))} for s in get_scadenziario().tutte(id_fascicolo=fascicolo_id, solo_aperte=False)]


def _studio() -> dict[str, Any]:
    """Gli avvocati e la PEC dello studio dalla configurazione dello studio (riconoscono il nostro lato negli atti)."""
    from flask import current_app, g

    from pct.config_studio import GestioneConfigStudio
    from web.services.archivio_letture_runtime import _avvocati_dello_studio

    paths = getattr(g, "data_paths", {}) or {}
    percorso = next((_testo(paths.get(k) or current_app.config.get(k)) for k in ("CONFIG_STUDIO_DB", "STUDIO_CONFIG")
                     if _testo(paths.get(k) or current_app.config.get(k))), "./config/studio.json")
    config = _sicuro(lambda: GestioneConfigStudio(config_path=percorso).config, None)
    avvocati = list(_sicuro(_avvocati_dello_studio, []))
    pec = []
    if config is not None:
        avvocati.append(_testo(getattr(config.studio, "avvocato", "")))
        pec.append(_testo(getattr(getattr(config, "pec", None), "indirizzo", "")))
    return {"nome": _testo(getattr(getattr(config, "studio", None), "nome", "")), "avvocati": [a for a in dict.fromkeys(avvocati) if a],
            "pec": [p for p in pec if p]}


def _consegne_verificate(fascicolo_id: str) -> dict[str, dict[str, str]]:
    from pct.notification_proof_matrix import validate_notification_proof_bundle
    from web.helpers import _studio_db
    from web.services.notification_presidia_runtime import _tenant_id

    db = _studio_db("FASCICOLI_DB")
    if db is None:
        return {}
    conn = db.conn
    tenant = _tenant_id()
    casi = db.fetchall_readonly(
        """SELECT c.id, c.act_document_id, b.bundle_id
           FROM notification_cases c JOIN notification_proof_bundles b
             ON b.notification_case_id=c.id AND b.tenant_id=c.tenant_id AND b.fascicolo_id=c.fascicolo_id
           WHERE c.tenant_id=? AND c.fascicolo_id=? AND b.validation_status='VERIFIED'
             AND c.act_document_id IS NOT NULL AND c.act_document_id <> ''""",
        (tenant, fascicolo_id),
    )
    per_atto: dict[str, dict[str, str]] = {}
    ambigui = set()
    for caso in casi:
        try:
            validate_notification_proof_bundle(conn, fascicolo_id=fascicolo_id, proof_bundle_id=caso["bundle_id"])
        except ValueError:
            continue
        ricevute = conn.execute(
            """SELECT n.event_time
               FROM notification_recipients r
               LEFT JOIN notification_receipts n
                 ON n.recipient_id=r.id AND n.notification_case_id=r.notification_case_id
                AND n.tenant_id=r.tenant_id AND n.fascicolo_id=r.fascicolo_id
                AND n.receipt_type='AVVENUTA_CONSEGNA' AND n.verification_status='VERIFIED'
                AND n.correlation_status='CORRELATED' AND COALESCE(n.raw_eml_document_id, '') <> ''
               WHERE r.tenant_id=? AND r.fascicolo_id=? AND r.notification_case_id=?
                 AND r.status<>'CANCELLED'""",
            (tenant, fascicolo_id, caso["id"]),
        ).fetchall()
        date = set()
        # La vista dell'atto ha una sola decorrenza. La si espone solo
        # se tutte le consegne del fascicolo sono provate nello stesso giorno.
        for ricevuta in ricevute:
            try:
                istante = datetime.fromisoformat(str(ricevuta["event_time"] or ""))
            except ValueError:
                break
            if istante.utcoffset() is None:
                break
            date.add(istante.astimezone(ZoneInfo("Europe/Rome")).date().isoformat())
        else:
            if len(date) != 1:
                continue
            atto, giorno = str(caso["act_document_id"]), next(iter(date))
            if atto in per_atto and per_atto[atto]["data"] != giorno:
                ambigui.add(atto)
            per_atto[atto] = {"data": giorno, "riferimento": str(caso["bundle_id"])}
    return {atto: prova for atto, prova in per_atto.items() if atto not in ambigui}


_MASSIMO_COLLEGATI = 8
_DOCUMENTO_DELLA_VICENDA = ("decret", "ingiun", "precett", "pignor", "esecutor", "titolo")


def _cliente(fascicolo: Any) -> str:
    return " ".join(_testo(getattr(fascicolo, "nome_cliente", "") or getattr(fascicolo, "cliente", "")).casefold().split())


def _collegati(fascicolo: Any) -> list[dict[str, Any]]:
    """I fascicoli dello stesso cliente con i soli documenti della vicenda esecutiva (decreto, esecutorietà, precetto,
    pignoramento), dai testi già salvati: la regola `pct/ragionamento/collegamenti` decide se sono collegati."""
    from web.helpers import get_fascicoli
    from web.services.archivio_letture_runtime import testi_indice_archivio

    cliente = _cliente(fascicolo)
    if not cliente:
        return []
    repo = get_fascicoli()
    indice = getattr(repo, "identita_per_confronto_fascicoli", None) or getattr(repo, "indice_leggero", None)
    righe = indice() if callable(indice) else repo.tutti()
    fid = _testo(getattr(fascicolo, "id", ""))
    candidati = [_testo(getattr(r, "id", "")) for r in righe
                 if _testo(getattr(r, "id", "")) != fid and _cliente(r) == cliente][:_MASSIMO_COLLEGATI]
    esito = []
    for cid in candidati:
        altro = _sicuro(lambda cid=cid: repo.get(cid), None)
        if altro is None:
            continue
        testi = _sicuro(lambda altro=altro: testi_indice_archivio(altro), {})
        documenti = []
        for documento in list(getattr(altro, "documenti", []) or []):
            oid = _testo(getattr(documento, "id", ""))
            testo = testi.get(oid, "")
            nome = _testo(getattr(documento, "nome", "") or getattr(documento, "nome_file", ""))
            if testo and any(p in (nome + " " + testo[:600]).casefold() for p in _DOCUMENTO_DELLA_VICENDA):
                documenti.append({"id": oid, "nome": nome, "data": _testo(getattr(documento, "data_documento", ""))[:10],
                                  "testo": testo})
        if documenti:
            numero, anno = _testo(getattr(altro, "numero_rg", "")), _testo(getattr(altro, "anno_rg", ""))
            esito.append({"id": cid, "rg": f"{numero}/{anno}" if numero and anno else "",
                          "ufficio": _testo(getattr(altro, "tribunale", "")),
                          "codice_oggetto": _testo(getattr(altro, "codice_oggetto_pst", "")), "documenti": documenti})
    return esito


def _appuntamenti(righe: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{"tipo": _testo(a.get("tipo")), "data": _testo(a.get("data_ora") or a.get("data"))[:10], "stato": _testo(a.get("stato"))}
            for a in righe or [] if isinstance(a, dict)]


def fonti_da_lettura(fascicolo: Any, dati: Any, fatti: list[dict[str, Any]]) -> FontiCausa:
    """Le fonti del ragionamento dai dati che la Lettura ha già raccolto: si aggiungono solo i testi dell'indice."""
    from web.services.archivio_letture_runtime import testi_indice_archivio

    testi = _sicuro(lambda: testi_indice_archivio(fascicolo), {})
    catalogo = {str(c.get("document_id")): c for c in dati.catalogo}
    estranei = set(dati.archivio.get("documenti_ufficio_incompatibile") or ())
    documenti = [{
        "id": d["id"], "nome": d.get("nome", ""), "data_documento": d.get("data_documento", ""),
        "natura": _testo((catalogo.get(d["id"]) or {}).get("document_nature")),
        "etichetta": _testo((catalogo.get(d["id"]) or {}).get("document_label")),
        "testo": testi.get(d["id"], ""), "sha256": d.get("content_sha256", ""),
    } for d in dati.documenti if d["id"] not in estranei]
    economico = dati.economico or {}
    pagamenti = _pagamenti(economico.get("presidio") or {})
    parcelle = [{"id": p.get("id"), "numero": p.get("numero"), "stato": p.get("stato"), "totale": p.get("totale"),
                 "data": p.get("data_emissione"), "data_pagamento": p.get("data_pagamento"), "origine": p.get("origine")}
                for p in economico.get("parcelle") or []]
    depositi = [{"id": d.get("id"), "tipo_atto": d.get("tipo_atto"), "stato": d.get("stato"), "data": _testo(d.get("timestamp"))[:10], "data_accettazione": _testo(d.get("data_accettazione")),
                 "nome_atto_principale": _testo(d.get("nome_atto_principale")),
                 "id_deposito_esterno": _testo(d.get("id_deposito_esterno")),
                 "documenti_ids": list(d.get("documenti_ids") or []),
                 "consegne_archivio": list(d.get("consegne_archivio") or [])}
                for d in dati.depositi]
    return FontiCausa(
        fascicolo=dict(dati.fascicolo), studio=_sicuro(_studio, {}), documenti=documenti,
        fatti=[f for f in fatti if f.get("tipo") != "documento" or f.get("oggetto_id") not in estranei],
        depositi=depositi,
        parcelle=parcelle, pagamenti=pagamenti,
        contributo=_stato_contributo(economico.get("presidio") or {}),
        consegne_verificate=_sicuro(lambda: _consegne_verificate(str(fascicolo.id)), {}),
        scadenze=[{"titolo": x.get("titolo"), "data": x.get("data"), "stato": x.get("stato")} for x in dati.scadenze],
        appuntamenti=_appuntamenti(list(getattr(dati, "appuntamenti", []) or [])),
        collegati=_sicuro(lambda: _collegati(fascicolo), []),
    )


def ragionamento_per_lettura(fascicolo: Any, dati: Any, fatti: list[dict[str, Any]]) -> dict[str, Any]:
    """Il modello della causa per la Lettura; un errore non ferma la Lettura, che resta con i suoi calcoli."""
    from pct.ragionamento import ragiona

    try:
        fonti = fonti_da_lettura(fascicolo, dati, fatti)
        modello = ragiona(fonti)
        esito = modello.come_dizionario()
        if _enum(getattr(fascicolo, "stato", "")).upper() in STATI_PERCORSO_CONCLUSO:
            esito["stile_ricorsi"] = _stile_ricorsi(fonti, modello)
        return esito
    except Exception:  # pragma: no cover - la Lettura resta disponibile
        import logging

        logging.getLogger(__name__).exception("ragionamento non disponibile per %s", getattr(fascicolo, "id", ""))
        return {}



STATI_PERCORSO_CONCLUSO = frozenset({"DEFINITO", "ARCHIVIATO"})


def _stile_ricorsi(fonti, modello) -> list[dict[str, Any]]:
    from pct.editor_ai.stile_studio import tratti_del_ricorso

    depositati = {str(oid) for deposito in fonti.depositi if deposito.get("stato") == "ACCETTATO_CANCELLERIA"
                  for oid in deposito.get("documenti_ids") or ()}
    esempi = []
    for atto in modello.atti:
        if (atto.appartenenza != "causa" or not atto.dello_studio or atto.natura != "atto_principale"
                or not {atto.id, *atto.copie} & depositati or "ricorso" not in atto.etichetta.casefold()):
            continue
        tratti = tratti_del_ricorso(atto.testo)
        if tratti:
            esempi.append(tratti)
    return esempi


def stile_ricorsi_per_editor(fascicolo: Any, tipo_atto: str) -> dict[str, Any]:
    from pct.editor_ai.stile_studio import aggrega_stile
    from pct.ragionamento import VERSIONE
    from pct.ragionamento.rito import determina_rito
    from web.services.registro_letture_runtime import registro_corrente, tenant_corrente

    if "ricorso" not in str(tipo_atto or "").casefold():
        return {}
    from lex.context.fascicolo_lettura_context import _fascicolo_dict

    rito = determina_rito(_fascicolo_dict(fascicolo), []).codice
    if not rito or rito == "ignoto":
        return {}
    registro, tenant = registro_corrente(sola_lettura=True), tenant_corrente()
    esempi = []
    for riga in registro.righe_fascicoli(tenant, lettore=LETTORE_PERCORSO_CONCLUSO):
        if riga["fascicolo_id"] == str(fascicolo.id) or riga.get("versione_lettore") != VERSIONE:
            continue
        try:
            esito = json.loads(riga.get("esito_json") or "{}")
        except (ValueError, TypeError):
            continue
        if (esito.get("rito") or {}).get("codice") == rito:
            esempi.extend(esito.get("stile_ricorsi") or [])
    return aggrega_stile(esempi)


def salva_percorso_concluso(fascicolo_id: str, lettura: dict[str, Any]) -> bool:
    """Memorizza l'esperienza nello stesso archivio SQL delle letture dello studio."""
    from web.services.registro_letture_runtime import registro_corrente, tenant_corrente

    registro, tenant = registro_corrente(), tenant_corrente()
    stato = (lettura.get("intestazione") or {}).get("stato_codice")
    ragionamento = lettura.get("ragionamento") or {}
    impronta = ragionamento.get("impronta")
    percorso = ragionamento.get("percorso") or []
    if stato not in STATI_PERCORSO_CONCLUSO or not impronta:
        return False
    versione = ragionamento["versione"]
    precedente = registro.impronta_fascicolo(tenant, fascicolo_id, LETTORE_PERCORSO_CONCLUSO)
    if precedente.get("impronta") == impronta and precedente.get("versione_lettore") == versione:
        return False
    registro.segna_fascicolo(
        tenant, fascicolo_id, LETTORE_PERCORSO_CONCLUSO, impronta=impronta,
        versione=versione, oggetti_totali=len(percorso), oggetti_letti=len(percorso),
        esito={campo: ragionamento.get(campo) for campo in (
            "rito", "posizione", "fase", "percorso", "conclusioni", "contraddizioni", "dubbi", "stile_ricorsi",
        )} | {"stato_fascicolo": stato},
    )
    return True


def raccogli_fonti(fascicolo_id: str, *, oggi: date | None = None) -> FontiCausa | None:
    from lex.context.fascicolo_lettura_context import _fascicolo_dict
    from web.helpers import get_fascicoli
    fascicolo = _sicuro(lambda: get_fascicoli().get(fascicolo_id), None)
    if fascicolo is None:
        return None
    parcelle, pagamenti, contributo = _sicuro(lambda: _economia(fascicolo), ([], [], {}))
    return FontiCausa(
        fascicolo=_fascicolo_dict(fascicolo),
        studio=_sicuro(_studio, {}),
        documenti=_documenti(fascicolo),
        fatti=_sicuro(lambda: _fatti(str(fascicolo.id)), []),
        depositi=_sicuro(lambda: _depositi(fascicolo), []),
        parcelle=parcelle, pagamenti=pagamenti,
        contributo=contributo,
        consegne_verificate=_sicuro(lambda: _consegne_verificate(str(fascicolo.id)), {}),
        scadenze=_sicuro(lambda: _scadenze(str(fascicolo.id)), []),
        oggi=oggi,
        collegati=_sicuro(lambda: _collegati(fascicolo), []),
    )


__all__ = ["fonti_da_lettura", "raccogli_fonti", "ragionamento_per_lettura"]
