"""Conto economico del fascicolo per la vista economica: raccoglie i dati già letti e li passa al modulo di dominio.

Fonti consultate, senza rileggere documenti nella richiesta:
- crediti da sentenza: eventi del controllo economico delle sentenze della causa (le sentenze di altri procedimenti,
  allegate come precedenti, sono escluse da `build_sentenza_economic_payload`), con il documento da cui nascono;
  in mancanza, le spese lette dal dispositivo dal motore documenti nell'archivio delle letture
  (`pct/archivio_letture/spese_sentenza.py`), anche quando la sentenza le compensa o condanna il cliente;
- contributo unificato: lo stato unico di `web/services/contributo_stato_runtime.py` (voce economica + catalogo);
- parcella, spese, anticipazioni e incassi: documenti economici del fascicolo e registro degli incassi.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

_CREDITI = {"apri_credito_cliente": False, "apri_credito_avvocato_antistatario": True}


def _testo(valore: Any) -> str:
    return " ".join(str(valore or "").split())


def _href_documento(fascicolo_id: str, documento_id: str) -> str:
    return f"/fascicoli/{quote(fascicolo_id, safe='')}/documenti/{quote(documento_id, safe='')}/visualizza"


def crediti_da_sentenza(fascicolo_id: str) -> list[dict[str, Any]]:
    from pct.archivio_letture.spese_sentenza import accessori_nel_capo_spese
    from pct.spese_liquidate_lettura import esborsi_inclusi_nel_liquidato
    from web.services.registro_letture_runtime import registro_corrente
    from web.services.sentenza_economic_runtime import _tenant_id, build_sentenza_economic_payload, fonte_audit

    payload = build_sentenza_economic_payload(fascicolo_id)
    if not payload.get("ok"):
        return []
    audits = {str(a["id"]): a for a in payload.get("audits") or []}
    inventario = registro_corrente().oggetti(_tenant_id(), fascicolo_id)
    crediti = []
    for evento in payload.get("eventi") or []:
        tipo = evento.get("event_type")
        if tipo not in _CREDITI or evento.get("status") not in {"to_review", "confirmed"}:
            continue
        audit = audits.get(str(evento.get("source_id") or ""))
        fonte = fonte_audit(audit, inventario, fascicolo_id) if audit else None
        sentenza = ((audit or {}).get("audit") or {}).get("sentenza") or {}
        capo_spese = (sentenza.get("spese_liquidate") or {}).get("testo_capo_spese")
        esborsi, esborsi_cu = esborsi_inclusi_nel_liquidato(_testo(capo_spese), evento.get("amount")) if fonte else (None, False)
        crediti.append({"esborsi_inclusi": esborsi, "esborsi_contributo": esborsi_cu, "importo": evento.get("amount"), "distrazione": _CREDITI[tipo], "confermato": evento.get("status") == "confirmed",
                        "accessori": bool(fonte and accessori_nel_capo_spese(_testo(capo_spese))),
                        "fonti": [{"label": fonte["label"], "href": fonte["href"], "norma": "sentenza della causa"}] if fonte else []})
    return crediti


def credito_da_liquidazione_registrata(fascicolo: Any) -> list[dict[str, Any]]:
    """Credito dalla liquidazione già registrata dal controllo della sentenza nella voce del fascicolo.

    Serve quando gli eventi del controllo economico non ci sono (sentenze lette prima del registro eventi):
    la voce «liquidazione_giudice» scritta dalla lettura della sentenza porta importo, distrazione
    (art. 93 c.p.c.) e documento fonte. Resta da confermare dall'avvocato.
    """
    voce = (getattr(fascicolo, "pagamenti", {}) or {}).get("liquidazione_giudice")
    if not isinstance(voce, dict) or _testo(voce.get("origine")) != "lex_ai_sentenza_tribunale":
        return []
    try:
        importo = round(float(voce.get("importo") or 0), 2)
    except (TypeError, ValueError):
        return []
    if importo <= 0:
        return []
    evidenza = voce.get("evidenza_dispositivo") if isinstance(voce.get("evidenza_dispositivo"), dict) else {}
    distrazione = _testo(voce.get("beneficiario_credito")) == "avvocato" or evidenza.get("distraction_granted") is True
    fid = _testo(getattr(fascicolo, "id", ""))
    documento_id = _testo(voce.get("documento_fonte")).removeprefix("document_id:")
    documenti = {_testo(getattr(d, "id", "")): d for d in getattr(fascicolo, "documenti", []) or []}
    fonti = []
    if documento_id in documenti:
        nome = _testo(getattr(documenti[documento_id], "nome", "")) or "Sentenza"
        fonti.append({"label": nome, "href": _href_documento(fid, documento_id), "norma": "sentenza della causa"})
    from pct.incasso_provato import pagato_senza_prova

    # «Pagato» scritto da un automatismo senza prova d'incasso non conferma nulla (pct.incasso_provato, G-4).
    confermato = _testo(voce.get("status")) in {"pagato", "parziale"} and not pagato_senza_prova(voce)
    return [{"importo": importo, "distrazione": distrazione, "confermato": confermato, "fonti": fonti}]


def _lato_del_cliente(fascicolo: Any) -> str:
    """«attivo» se il cliente ha promosso la causa, «passivo» se resiste, vuoto se le parti non lo dicono."""
    from pct.fascicolo_lettura.passi_note_127_ter import _ruolo_cliente
    from web.helpers import get_soggetti

    parti: dict[str, list[str]] = {}
    try:
        for parte, soggetto in get_soggetti().parti_fascicolo(_testo(getattr(fascicolo, "id", ""))):
            ruolo = _testo(getattr(getattr(parte, "ruolo", ""), "value", getattr(parte, "ruolo", ""))).replace("_", " ").lower()
            nome = _testo(getattr(soggetto, "nome_completo", "") or getattr(soggetto, "denominazione", "") or getattr(soggetto, "nome", ""))
            if ruolo and nome:
                parti.setdefault(ruolo, []).append(nome)
    except Exception:
        return ""
    attivo = _ruolo_cliente({"cliente": _testo(getattr(fascicolo, "nome_cliente", "")), "parti": parti})
    return "" if attivo is None else ("attivo" if attivo else "passivo")


def sentenze_dall_archivio(fascicolo: Any, *, lettura: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Le spese regolate dalla sentenza della causa, lette dal motore documenti e conservate nell'archivio.

    Serve quando il controllo economico non ha registrato né eventi né liquidazione (identità della parte non
    dimostrata in altri documenti, sentenza letta dopo): il dispositivo già letto basta a dire che cosa ha deciso
    il giudice sulle spese, con il documento come fonte. Nessuna lettura del PDF nella richiesta.
    """
    from pct.archivio_letture.spese_sentenza import spese_lette
    from web.services.obblighi_notifica_runtime import _impronte_testo_atti
    from web.services.registro_letture_runtime import registro_corrente, tenant_corrente

    fid = _testo(getattr(fascicolo, "id", ""))
    numero, anno = _testo(getattr(fascicolo, "numero_rg", "")), _testo(getattr(fascicolo, "anno_rg", ""))
    rg = f"{numero}/{anno}" if numero and anno not in {"", "0"} else numero
    identita_verificate = None
    tipo = getattr(fascicolo, "tipo", "")
    if _testo(getattr(tipo, "value", tipo)).casefold() == "amministrativo":
        from web.services.riscontri_processuali_runtime import lettura_materializzata

        corrente = lettura if lettura is not None else lettura_materializzata(fid)
        ids = frozenset(voce["id"] for voce in ((corrente or {}).get("documenti") or {}).get("sentenze") or () if voce.get("id"))
        if ids:
            identita_verificate = ids
    fatti = [f for f in registro_corrente().fatti(tenant_corrente(), fid, verifiche=None)
             if f.tipo == "documento" and (f.categoria == "ruolo" or f.campo in {"spese_sentenza", "data_atto", "impronta_testo_atto"})]
    lette = spese_lette(fatti, rg=rg, sentenze_pertinenti=identita_verificate)
    if not lette:
        return []
    nomi = {_testo(getattr(d, "id", "")): _testo(getattr(d, "nome", "")) for d in getattr(fascicolo, "documenti", []) or []}
    documenti = {_testo(d.id): d for d in getattr(fascicolo, "documenti", []) or []}
    identita = _impronte_testo_atti(documenti, fatti)
    lato = _lato_del_cliente(fascicolo)
    for voce in lette:
        documento_id = voce["documento_id"]
        voce["identita_atto"] = identita.get(documento_id, "")
        voce["fonti"] = [{"label": nomi.get(documento_id) or "Sentenza", "norma": "sentenza della causa",
                          "href": _href_documento(fid, documento_id) if documento_id in nomi else ""}]
        voce["a_favore_del_cliente"] = None if not (lato and voce["beneficiario"]) else lato == voce["beneficiario"]
    return lette


def crediti_dalle_sentenze_lette(sentenze: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Il credito per le spese liquidate in favore del cliente (o distratte al difensore); mai una condanna del cliente."""
    return [{"importo": voce["importo"], "distrazione": voce["distrazione"], "confermato": False, "fonti": voce["fonti"],
             "distrazione_condizionata": voce.get("distrazione_condizionata", False), "accessori": voce.get("accessori", False),
             "identita_atto": voce.get("identita_atto", ""),
             "esborsi_inclusi": voce.get("esborsi_inclusi"),
             "esborsi_contributo": voce.get("esborsi_contributo", False)}
            for voce in sentenze
            if voce["regolazione"] == "condanna" and voce["importo"] and voce.get("a_favore_del_cliente") is not False]


def crediti_pertinenti(fascicolo: Any, crediti: list[dict[str, Any]], sentenze: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Collega i crediti registrati alla decisione amministrativa della stessa causa."""
    tipo = getattr(fascicolo, "tipo", "")
    if _testo(getattr(tipo, "value", tipo)).casefold() != "amministrativo" or not sentenze:
        return crediti
    fonti = {f["href"] for s in sentenze for f in s.get("fonti") or () if f.get("href")}
    return [c for c in crediti if any(f.get("href") in fonti for f in c.get("fonti") or ())]


def crediti_da_provvedimenti(fascicolo: Any) -> list[dict[str, Any]]:
    """Le spese liquidate dai provvedimenti della causa diversi dalla sentenza (decreto ingiuntivo, ordinanze, decreti).

    Solo i provvedimenti di questa causa (``pct.atto_della_causa``) ottenuti dalla parte assistita (il lato «attivo»
    del cliente): nel decreto ingiuntivo le spese le paga l'ingiunto al ricorrente (art. 641 c.p.c.). Fonte: i testi
    già salvati nell'indice documentale e la voce del catalogo; nessuna lettura di file nella richiesta (G-14).
    """
    from pct.atto_della_causa import provvedimento_della_causa, ruoli_in_intestazione
    from pct.spese_liquidate_provvedimento import natura_provvedimento, spese_liquidate
    from web.services.archivio_letture_runtime import testi_indice_archivio
    from web.services.obblighi_notifica_runtime import _catalogo

    if _lato_del_cliente(fascicolo) == "passivo":
        return []
    fid = _testo(getattr(fascicolo, "id", ""))
    nomi = {_testo(getattr(d, "id", "")): _testo(getattr(d, "nome", "")) for d in getattr(fascicolo, "documenti", []) or []}
    try:
        etichette, testi = _catalogo(fascicolo), testi_indice_archivio(fascicolo)
    except Exception:
        return []
    crediti, visti = [], set()
    for documento_id, etichetta in etichette.items():
        natura = natura_provvedimento(etichetta)
        if natura is None or documento_id not in testi or documento_id not in nomi:
            continue
        esito, _motivo = provvedimento_della_causa(ruoli=ruoli_in_intestazione(testi[documento_id]), date_atto=(),
                                                   numero_rg=getattr(fascicolo, "numero_rg", ""), anno_rg=getattr(fascicolo, "anno_rg", ""))
        letto = spese_liquidate(testi[documento_id]) if esito is not False else None
        if not letto or (letto["compensi"], letto["esborsi"]) in visti:
            continue  # la copia notificata dello stesso decreto non è un secondo credito
        visti.add((letto["compensi"], letto["esborsi"]))
        crediti.append({"importo": letto["compensi"], "distrazione": letto["distrazione"], "confermato": False,
                        "accessori": letto["accessori"], "esborsi": letto["esborsi"], "provvedimento": natura[0],
                        "fonti": [{"label": nomi[documento_id], "href": _href_documento(fid, documento_id),
                                   "norma": f"{natura[0]} della causa ({natura[1]})"}]})
    return crediti


def documenti_contributo(fascicolo: Any) -> list[dict[str, Any]]:
    from web.services.contributo_stato_runtime import documenti_contributo as _documenti

    return _documenti(fascicolo)


def parcelle_del_fascicolo(fascicolo_id: str) -> list[dict[str, Any]]:
    from pct.parcella_incassi_views import balance_amount, balances_for_invoices
    from web.helpers import get_fatturazione

    gestione = get_fatturazione()
    parcelle = list(gestione.per_fascicolo(fascicolo_id) or [])
    saldi = balances_for_invoices(getattr(gestione, "_studio_db", None), {p.id: p for p in parcelle})
    righe = []
    for p in parcelle:
        stato = _testo(getattr(p.stato, "value", p.stato)).upper()
        documento = (p.dati_personalizzati or {}).get("document") if isinstance(p.dati_personalizzati, dict) else {}
        operativo = _testo((documento or {}).get("documento_operativo")).upper() or ("FATTURA" if stato in {"EMESSA", "PAGATA"} else "PROFORMA")
        try:
            incassato = balance_amount(p, saldi, "paid_cents", p.totale if stato == "PAGATA" else 0)
        except ValueError:
            incassato = 0
        ricevute = (saldi.get(p.id) or {}).get("receipts") or []
        data_pagamento = max((str(r.get("paid_on") or "") for r in ricevute), default="") or _testo(p.data_pagamento)
        righe.append({"id": p.id, "numero": p.numero, "data": _testo(p.data_emissione)[:10], "stato": stato, "operativo": operativo, "totale": p.totale,
                      "netto_a_pagare": p.netto_a_pagare, "bollo": float(getattr(p, "bollo", 0) or 0), "onorari": p.totale_competenze, "spese": p.totale_spese_imponibili, "anticipazioni": p.totale_anticipazioni,
                      "incassato": incassato, "data_pagamento": data_pagamento, "sdi_stato": _testo(p.sdi_stato),
                      "superata": (p.dati_personalizzati or {}).get("superata") if isinstance(p.dati_personalizzati, dict) else None})
    return righe


def _esecuzione_pa(lettura: dict[str, Any] | None) -> dict[str, Any] | None:
    """Riprende i 120 giorni dalla Lettura preparata per la notifica provata del titolo alla P.A."""
    quadro = (lettura or {}).get("ragionamento") or {}
    date = [v["termine"]["scadenza_iso"] for v in quadro.get("conclusioni") or ()
            if v.get("codice") == "esecuzione_pa" and not v.get("dubbi")
            and (v.get("termine") or {}).get("scadenza_iso")]
    return {"deadline": date[0]} if len(date) == 1 else None


def conto_economico_fascicolo(fascicolo_id: str, *, lettura: dict[str, Any] | None = None) -> dict[str, Any]:
    from pct.fascicolo_conto_economico import conto_economico
    from pct.percorso_pratica.giurisdizioni import AMMINISTRATIVO, giurisdizione_e_grado
    from web.services.sentenza_economic_runtime import _fascicoli_repository_mirato

    # Un fascicolo solo: lettura per chiave, non tutto l'archivio dello studio.
    fascicolo = _fascicoli_repository_mirato().get(fascicolo_id)
    if fascicolo is None:
        return {"ok": False, "message": "Fascicolo non trovato."}
    voci = dict(getattr(fascicolo, "pagamenti", {}) or {})
    for chiave in ("spese_esborsi", "fondo_spese", "contributo_unificato"):
        voce = dict(voci.get(chiave) or {})
        documento_id = _testo(voce.get("documento_id") or voce.get("documentoId")) or next(
            (_testo(d.id) for d in getattr(fascicolo, "documenti", []) or []
             if voce.get("documento_fonte") and _testo(getattr(d, "nome", "")) == _testo(voce.get("documento_fonte"))), "")
        if documento_id:
            voce["href"] = _href_documento(fascicolo_id, documento_id)
        voci[chiave] = voce
    from web.helpers import regime_fiscale_studio

    from web.services.contributo_stato_runtime import stato_contributo_fascicolo
    from web.services.riscontri_processuali_runtime import lettura_materializzata, stato_contributo_da_lettura

    if lettura is None:
        lettura = lettura_materializzata(fascicolo_id)
    contributo = stato_contributo_da_lettura(lettura)
    crediti = crediti_da_sentenza(fascicolo_id) or credito_da_liquidazione_registrata(fascicolo)
    sentenze = sentenze_dall_archivio(fascicolo, lettura=lettura or {})
    crediti = crediti_pertinenti(fascicolo, crediti, sentenze) or crediti_dalle_sentenze_lette(sentenze)
    if not crediti and not sentenze:
        crediti = crediti_da_provvedimenti(fascicolo)

    tipo = getattr(fascicolo, "tipo", "")
    giurisdizione, _ = giurisdizione_e_grado(tipo=getattr(tipo, "value", tipo), ufficio=getattr(fascicolo, "tribunale", ""))

    # Lo stesso stato del contributo della card e della finestra del presidio economico (stessa voce, stesso catalogo).
    risultato = conto_economico(voci=voci, crediti=crediti, sentenze=sentenze, regime=regime_fiscale_studio(),
                                documenti_contributo=[], stato_contributo=contributo or stato_contributo_fascicolo(fascicolo),
                                parcelle=parcelle_del_fascicolo(fascicolo_id), esecuzione=_esecuzione_pa(lettura),
                                amministrativo=giurisdizione == AMMINISTRATIVO)
    allinea_contributo_al_modello(risultato.get("righe") or [], lettura, voci.get("contributo_unificato") or {})
    from pct.fascicolo_conto_economico import bollo_contro_lo_stato

    bollo_contro_lo_stato(risultato.get("righe") or [], parcelle_del_fascicolo(fascicolo_id),
                          contro_lo_stato=_controparte_statale(lettura))
    return {"ok": True, "fascicoloId": fascicolo_id, **risultato}


def _controparte_statale(lettura: dict[str, Any] | None) -> bool:
    """L'amministrazione condannata è dello Stato: difesa dall'Avvocatura dello Stato (art. 1 R.D. 1611/1933)."""
    from pct.bozze_passi.contesto import contesto_della_lettura

    try:
        return bool(lettura) and contesto_della_lettura(lettura).pubblica_amministrazione
    except Exception:
        return False


def allinea_contributo_al_modello(righe: list[dict[str, Any]], lettura: dict[str, Any] | None, voce: dict[str, Any]) -> None:
    """La riga del contributo dice la conclusione del modello della causa, la stessa del Quadro e dei prossimi passi.

    Il presidio resta la fonte del modello (stato condiviso, `pct/ragionamento/regole/economia.py`); qui si mostra il
    suo esito giuridico: versato, non dovuto con la norma, o il dubbio come il modello lo scrive (19/11/2026).
    """
    from pct.quadro_economia import contributo

    conclusione = next((c for c in ((lettura or {}).get("ragionamento") or {}).get("conclusioni") or []
                        if c.get("codice") == "contributo_unificato"), None)
    riga = next((r for r in righe if r.get("voce") == "contributo_unificato"), None)
    if not conclusione or riga is None:
        return
    testo, dubbio = contributo(conclusione, voce)
    riga.update(stato=testo[:1].upper() + testo[1:], tono="warning" if dubbio else "success",
                dettaglio=_testo(conclusione.get("prova_o_motivo")) or riga.get("dettaglio", ""),
                fonteGiuridica="modello della causa")


__all__ = ["allinea_contributo_al_modello", "conto_economico_fascicolo", "credito_da_liquidazione_registrata", "crediti_da_provvedimenti", "crediti_da_sentenza", "crediti_dalle_sentenze_lette",
           "documenti_contributo", "parcelle_del_fascicolo", "sentenze_dall_archivio"]
