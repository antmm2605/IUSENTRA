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

from datetime import datetime
import math
from typing import Any, Callable

from web.services.react_dashboard_time import oggi_rome

METODO_BONIFICO = "Bonifico bancario"
STATI_PARCELLA_APERTA = {"EMESSA", "SCADUTA", "BOZZA"}


def _text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _importo(value: Any) -> float | None:
    if value is None or value == "" or isinstance(value, bool):
        return None
    try:
        amount = float(str(value).replace("€", "").replace(".", "").replace(",", ".")) if isinstance(value, str) and "," in str(value) else float(value)
        return round(amount, 2) if math.isfinite(amount) else None
    except (TypeError, ValueError, OverflowError):
        return None


def _data_iso(value: Any) -> tuple[str, str]:
    testo = _text(value)
    if not testo:
        return oggi_rome().isoformat(), ""
    for formato in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            giorno = datetime.strptime(testo[:10], formato).date()
        except ValueError:
            continue
        if giorno > oggi_rome():
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
    metodo_pagamento: str = METODO_BONIFICO,
) -> tuple[dict[str, Any], int]:
    from pct.fatturazione import StatoParcella
    from web.services.react_fascicoli_bridge import (
        _create_review_proforma_from_fascicolo_amount,
        _resolve_fascicolo,
        update_react_fascicolo_payment,
        _amount_label,
    )

    payload = dict(payload or {})
    fascicoli = get_fascicoli()
    fascicolo = _resolve_fascicolo(fascicoli, id_fasc)
    if fascicolo is None:
        return {"ok": False, "message": "Fascicolo non trovato.", "errors": {"fascicolo": "Fascicolo non trovato."}}, 404
    fid = _text(getattr(fascicolo, "id", ""))
    liquidazione = _liquidazione(fascicolo)
    raw_importo = payload.get("importo") if "importo" in payload else payload.get("amount")
    importo = _importo(raw_importo)
    if importo is None and (raw_importo is None or raw_importo == ""):
        importo = _importo(liquidazione.get("importo"))
    if importo is None or importo <= 0:
        return {"ok": False, "message": "Indica l'importo ricevuto.", "errors": {"importo": "Indica l'importo ricevuto (maggiore di zero)."}}, 400
    data_iso, errore_data = _data_iso(payload.get("data_pagamento") or payload.get("dataPagamento") or payload.get("data"))
    if errore_data:
        return {"ok": False, "message": errore_data, "errors": {"dataPagamento": errore_data}}, 400
    nota = _text(payload.get("note"))[:400]

    manager = get_fatturazione()
    tutte = list(manager.per_fascicolo(fid) or [])
    parcelle = [voce for voce in tutte if _stato(voce) in STATI_PARCELLA_APERTA]
    richiesta = _text(payload.get("parcella_id") or payload.get("parcellaId"))
    parcella = None
    creata = False
    if richiesta:
        parcella = next((voce for voce in tutte if _text(getattr(voce, "id", "")) == richiesta
                         and _stato(voce) in STATI_PARCELLA_APERTA | {"PAGATA"}), None)
        if parcella is None:
            return {"ok": False, "message": "Parcella non trovata nel fascicolo o annullata.", "errors": {"parcella_id": "Parcella non disponibile per questo fascicolo."}}, 404
    elif len(parcelle) == 1:
        parcella = parcelle[0]
    elif len(parcelle) > 1:
        stesso_importo = [voce for voce in parcelle if abs(float(voce.netto_a_pagare) - importo) < 0.01]
        if len(stesso_importo) == 1:
            parcella = stesso_importo[0]
        else:
            return {
                "ok": False,
                "message": "Più parcelle aperte per questo fascicolo: scegli quella pagata.",
                "errors": {"parcella_id": "Scegli la parcella pagata."},
                "parcelle": [{"id": _text(getattr(voce, "id", "")), "numero": _text(getattr(voce, "numero", "")), "totale": float(voce.netto_a_pagare), "stato": _stato(voce)} for voce in parcelle],
            }, 409
    elif not parcelle and any(_stato(voce) == "PAGATA" for voce in tutte):
        return {
            "ok": False, "message": "Ci sono documenti già pagati: scegli quello da collegare al controllo economico; non viene creata una seconda parcella.",
            "errors": {"parcella_id": "Scegli il documento economico già pagato."},
            "parcelle": [{"id": _text(voce.id), "numero": _text(voce.numero),
                          "totale": float(voce.netto_a_pagare), "stato": _stato(voce), "dataPagamento": _text(voce.data_pagamento)}
                         for voce in tutte if _stato(voce) == "PAGATA"],
        }, 409
    if parcella is None:
        fonte = "bonifico ricevuto" + (" a fronte della liquidazione del giudice" if liquidazione.get("importo") else "")
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
    expected_amount = round(float(parcella.netto_a_pagare), 2)
    if _stato(parcella) != "PAGATA" and abs(importo - expected_amount) > 0.01:
        return {"ok": False, "conflict": True,
                "message": f"Versamento {_amount_label(importo)} diverso dal netto della parcella {_amount_label(expected_amount)}: saldo non confermato, importi e stati conservati.",
                "errors": {"importo": "Il versamento non dimostra il saldo della parcella."},
                "discordanza": {"parcellaId": parcella_id, "importoRicevuto": importo, "nettoParcella": expected_amount}}, 409
    metodo = _text(metodo_pagamento) or METODO_BONIFICO
    if _stato(parcella) == "PAGATA":
        data_iso = _text(getattr(parcella, "data_pagamento", "")) or data_iso
        metodo = _text(getattr(parcella, "metodo_pagamento", "")) or metodo
        importo = float(parcella.netto_a_pagare)
        from web.services.react_fascicoli_bridge import _payment_source_for_kind
        for kind in ("parcella", "liquidazione_giudice"):
            saved = _payment_source_for_kind(getattr(fascicolo, "pagamenti", {}) or {}, kind)
            if saved.get("status") == "pagato" and _text(saved.get("proforma_id") or saved.get("proformaId")) == parcella_id:
                registered = _importo(saved.get("incasso_importo"))
                if registered is not None:
                    importo = registered
                    break
    gia_collegato = not creata and _stato(parcella) == "PAGATA"
    if _stato(parcella) != "PAGATA" or getattr(parcella, "data_pagamento", "") != data_iso or getattr(parcella, "metodo_pagamento", "") != metodo:
        gia_collegato = False
        manager.cambia_stato(parcella_id, StatoParcella.PAGATA, data_pagamento=data_iso, metodo_pagamento=metodo)

    # La voce «Liquidazione giudice» del controllo pagamenti segue il bonifico.
    numero = _text(getattr(manager.get(parcella_id), "numero", "")) or parcella_id
    operazione = "Bonifico" if "bonifico" in metodo.casefold() else "Incasso"
    nota_presidio = f"{operazione} ricevuto il {datetime.strptime(data_iso, '%Y-%m-%d').strftime('%d/%m/%Y')} (parcella {numero})" + (f": {nota}" if nota else "")
    esito_presidio: dict[str, Any] = {}
    stato_presidio = 200
    from web.services.react_fascicoli_bridge import _payment_source_for_kind, payment_summary_for_fascicolo

    voci = ["parcella"]
    if liquidazione.get("importo") is not None:
        voci.insert(0, "liquidazione_giudice")
    for kind in voci:
        corrente = get_fascicoli().get(fid)
        raw = _payment_source_for_kind(getattr(corrente, "pagamenti", {}) or {}, kind)
        # Il totale dell'incasso non sostituisce il capo liquidato dal giudice
        # o un importo della parcella già registrato dall'avvocato.
        amount = _importo(raw.get("importo")) or importo
        gia_presente = (raw.get("status") == "pagato" and raw.get("data_pagamento") == data_iso
                        and raw.get("metodo") == metodo
                        and _text(raw.get("proforma_id") or raw.get("proformaId")) == parcella_id)
        if gia_presente:
            esito_presidio = {"paymentSummary": payment_summary_for_fascicolo(corrente)}
            continue
        gia_collegato = False
        esito_presidio, stato_presidio = update_react_fascicolo_payment(
            get_fascicoli=get_fascicoli, get_fatturazione=get_fatturazione, id_fasc=fid, kind=kind,
            payload={"status": "pagato", "importo": amount, "dataPagamento": data_iso, "metodo": metodo,
                     "note": nota_presidio[:400], "proforma_id": parcella_id}, actor=actor,
        )
        if stato_presidio >= 400:
            break
    if stato_presidio >= 400:
        return {"ok": False, "message": f"Bonifico registrato sulla parcella {numero}, ma il controllo economico non è stato aggiornato: {esito_presidio.get('message')}", "errors": esito_presidio.get("errors") or {}, "parcellaId": parcella_id}, stato_presidio
    messaggio = (
        f"{operazione} di € {importo:,.2f}".replace(",", "\x00").replace(".", ",").replace("\x00", ".")
        + f" registrato: parcella {numero} {'creata e ' if creata else ''}segnata pagata il {datetime.strptime(data_iso, '%Y-%m-%d').strftime('%d/%m/%Y')}; controllo economico aggiornato."
    )
    if gia_collegato:
        messaggio = f"Incasso già collegato alla parcella {numero}: importo e data originali conservati, nessun doppione."
    return {
        "ok": True,
        "message": messaggio,
        "parcellaId": parcella_id,
        "parcellaNumero": numero,
        "parcellaCreata": creata,
        "alreadyPresent": gia_collegato,
        "importo": importo,
        "dataPagamento": data_iso,
        "metodo": metodo,
        "paymentSummary": esito_presidio.get("paymentSummary") or esito_presidio.get("payment_summary") or {},
        "redirectHref": f"/fatturazione?id_documento={parcella_id}",
    }, 200


__all__ = ["METODO_BONIFICO", "registra_bonifico_ricevuto"]
