"""«Registra bonifico ricevuto» dal controllo economico del fascicolo.

Quando la somma liquidata dal giudice (o comunque dovuta) arriva sul conto
dello studio, l'avvocato la registra in un passaggio solo dal fascicolo: la
parcella aperta del fascicolo viene segnata pagata con metodo bonifico e data;
se non c'è, viene creata dal presidio economico (bozza da completare
fiscalmente) e subito segnata pagata; la voce «Liquidazione giudice» del
controllo pagamenti passa a «Pagato» con la stessa data. Fatturazione e
fascicolo leggono lo stesso record: nessuna doppia registrazione.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Callable

METODO_BONIFICO = "Bonifico bancario"
STATI_PARCELLA_APERTA = {"EMESSA", "SCADUTA", "BOZZA"}


def _text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _importo(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return round(float(str(value).replace("€", "").replace(".", "").replace(",", ".")) if isinstance(value, str) and "," in str(value) else float(value), 2)
    except (TypeError, ValueError):
        return None


def _data_iso(value: Any) -> tuple[str, str]:
    testo = _text(value)
    if not testo:
        return date.today().isoformat(), ""
    for formato in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            giorno = datetime.strptime(testo[:10], formato).date()
        except ValueError:
            continue
        if giorno > date.today():
            return "", "La data del bonifico non può essere futura."
        return giorno.isoformat(), ""
    return "", "Data del bonifico non valida: usa gg/mm/aaaa."


def _stato(voce: Any) -> str:
    return _text(getattr(getattr(voce, "stato", None), "value", getattr(voce, "stato", ""))).upper()


def _liquidazione(fascicolo: Any) -> dict[str, Any]:
    from web.services.react_fascicoli_bridge import _payment_source_for_kind

    return _payment_source_for_kind(getattr(fascicolo, "pagamenti", {}) or {}, "liquidazione_giudice")


def registra_bonifico_ricevuto(
    *,
    get_fascicoli: Callable[[], Any],
    get_fatturazione: Callable[[], Any],
    id_fasc: str,
    payload: dict[str, Any] | None,
    actor: str = "IUSENTRA",
) -> tuple[dict[str, Any], int]:
    from pct.fatturazione import StatoParcella
    from web.services.react_fascicoli_bridge import (
        _create_review_proforma_from_fascicolo_amount,
        _resolve_fascicolo,
        update_react_fascicolo_payment,
    )

    payload = dict(payload or {})
    fascicoli = get_fascicoli()
    fascicolo = _resolve_fascicolo(fascicoli, id_fasc)
    if fascicolo is None:
        return {"ok": False, "message": "Fascicolo non trovato.", "errors": {"fascicolo": "Fascicolo non trovato."}}, 404
    fid = _text(getattr(fascicolo, "id", ""))
    liquidazione = _liquidazione(fascicolo)
    importo = _importo(payload.get("importo") if "importo" in payload else payload.get("amount"))
    if importo is None:
        importo = _importo(liquidazione.get("importo"))
    if importo is None or importo <= 0:
        return {"ok": False, "message": "Indica l'importo ricevuto.", "errors": {"importo": "Indica l'importo ricevuto (maggiore di zero)."}}, 400
    data_iso, errore_data = _data_iso(payload.get("data_pagamento") or payload.get("dataPagamento") or payload.get("data"))
    if errore_data:
        return {"ok": False, "message": errore_data, "errors": {"dataPagamento": errore_data}}, 400
    nota = _text(payload.get("note"))[:400]

    manager = get_fatturazione()
    parcelle = [voce for voce in list(manager.per_fascicolo(fid) or []) if _stato(voce) in STATI_PARCELLA_APERTA]
    richiesta = _text(payload.get("parcella_id") or payload.get("parcellaId"))
    parcella = None
    creata = False
    if richiesta:
        parcella = next((voce for voce in parcelle if _text(getattr(voce, "id", "")) == richiesta), None)
        if parcella is None:
            return {"ok": False, "message": "Parcella non trovata o già pagata.", "errors": {"parcella_id": "Parcella non trovata o già pagata."}}, 404
    elif len(parcelle) == 1:
        parcella = parcelle[0]
    elif len(parcelle) > 1:
        stesso_importo = [voce for voce in parcelle if abs(float(getattr(voce, "totale", 0.0) or 0.0) - importo) < 0.01]
        if len(stesso_importo) == 1:
            parcella = stesso_importo[0]
        else:
            return {
                "ok": False,
                "message": "Più parcelle aperte per questo fascicolo: scegli quella pagata.",
                "errors": {"parcella_id": "Scegli la parcella pagata."},
                "parcelle": [{"id": _text(getattr(voce, "id", "")), "numero": _text(getattr(voce, "numero", "")), "totale": float(getattr(voce, "totale", 0.0) or 0.0), "stato": _stato(voce)} for voce in parcelle],
            }, 409
    if parcella is None:
        fonte = "bonifico ricevuto" + (f" a fronte della liquidazione del giudice" if liquidazione.get("importo") else "")
        esito = _create_review_proforma_from_fascicolo_amount(
            fascicoli_repository=fascicoli, fatturazione_repository=manager, fascicolo=fascicolo,
            amount=importo, amount_source=fonte, actor=actor,
        )
        if not esito.get("created"):
            return {"ok": False, "message": f"Parcella non creata: {esito.get('reason') or 'cliente o importo mancanti'}", "errors": {"parcella": _text(esito.get("reason"))}}, 400
        parcella = manager.get(_text(esito.get("proformaId") or esito.get("id")))
        creata = True
        if parcella is None:
            return {"ok": False, "message": "Parcella creata ma non rileggibile.", "errors": {"parcella": "non rileggibile"}}, 500
    parcella_id = _text(getattr(parcella, "id", ""))
    manager.cambia_stato(parcella_id, StatoParcella.PAGATA, data_pagamento=data_iso, metodo_pagamento=METODO_BONIFICO)

    # La voce «Liquidazione giudice» del controllo pagamenti segue il bonifico.
    numero = _text(getattr(manager.get(parcella_id), "numero", "")) or parcella_id
    nota_presidio = f"Bonifico ricevuto il {datetime.strptime(data_iso, '%Y-%m-%d').strftime('%d/%m/%Y')} (parcella {numero})" + (f": {nota}" if nota else "")
    esito_presidio: dict[str, Any] = {}
    stato_presidio = 200
    if liquidazione.get("importo") is not None or payload.get("aggiorna_liquidazione"):
        esito_presidio, stato_presidio = update_react_fascicolo_payment(
            get_fascicoli=get_fascicoli, get_fatturazione=get_fatturazione, id_fasc=fid, kind="liquidazione_giudice",
            payload={"status": "pagato", "importo": _importo(liquidazione.get("importo")) or importo, "dataPagamento": data_iso, "metodo": METODO_BONIFICO, "note": nota_presidio[:400], "proforma_id": parcella_id, "proformaId": parcella_id},
            actor=actor,
        )
    else:
        esito_presidio, stato_presidio = update_react_fascicolo_payment(
            get_fascicoli=get_fascicoli, get_fatturazione=get_fatturazione, id_fasc=fid, kind="parcella",
            payload={"status": "pagato", "importo": importo, "dataPagamento": data_iso, "metodo": METODO_BONIFICO, "note": nota_presidio[:400], "proforma_id": parcella_id, "proformaId": parcella_id},
            actor=actor,
        )
    if stato_presidio >= 400:
        return {"ok": False, "message": f"Bonifico registrato sulla parcella {numero}, ma il controllo economico non è stato aggiornato: {esito_presidio.get('message')}", "errors": esito_presidio.get("errors") or {}, "parcellaId": parcella_id}, stato_presidio
    messaggio = (
        f"Bonifico di € {importo:,.2f}".replace(",", "\x00").replace(".", ",").replace("\x00", ".")
        + f" registrato: parcella {numero} {'creata e ' if creata else ''}segnata pagata il {datetime.strptime(data_iso, '%Y-%m-%d').strftime('%d/%m/%Y')}; controllo economico aggiornato."
    )
    return {
        "ok": True,
        "message": messaggio,
        "parcellaId": parcella_id,
        "parcellaNumero": numero,
        "parcellaCreata": creata,
        "importo": importo,
        "dataPagamento": data_iso,
        "metodo": METODO_BONIFICO,
        "paymentSummary": esito_presidio.get("paymentSummary") or esito_presidio.get("payment_summary") or {},
        "redirectHref": f"/fatturazione?id_documento={parcella_id}",
    }, 200


__all__ = ["METODO_BONIFICO", "registra_bonifico_ricevuto"]
