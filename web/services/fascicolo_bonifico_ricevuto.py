"""Compatibilità consultiva del vecchio comando: gli incassi usano il registro SQL nativo."""

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
    from pct.fatturazione import parcella_revision
    from web.services.react_fascicoli_bridge import (
        _resolve_fascicolo,
        _amount_label,
    )

    payload = dict(payload or {})
    revision = payload.get("parcella_revision")
    if revision is not None and (not isinstance(revision, str) or len(revision) != 64
                                 or any(char not in "0123456789abcdef" for char in revision)
                                 or not _text(payload.get("parcella_id") or payload.get("parcellaId"))):
        return {"ok": False, "message": "Revisione del documento non valida."}, 400
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
    _, errore_data = _data_iso(payload.get("data_pagamento") or payload.get("dataPagamento") or payload.get("data"))
    if errore_data:
        return {"ok": False, "message": errore_data, "errors": {"dataPagamento": errore_data}}, 400

    manager = get_fatturazione()
    tutte = list(manager.per_fascicolo(fid) or [])
    parcelle = [voce for voce in tutte if _stato(voce) in STATI_PARCELLA_APERTA]
    richiesta = _text(payload.get("parcella_id") or payload.get("parcellaId"))
    parcella = None
    if richiesta:
        parcella = next((voce for voce in tutte if _text(getattr(voce, "id", "")) == richiesta
                         and _stato(voce) in STATI_PARCELLA_APERTA | {"PAGATA"}), None)
        if parcella is None:
            return {"ok": False, "message": "Parcella non trovata nel fascicolo o annullata.", "errors": {"parcella_id": "Parcella non disponibile per questo fascicolo."}}, 404
    elif len(parcelle) == 1:
        parcella = parcelle[0]
    elif len(parcelle) > 1:
        stesso_importo = [voce for voce in parcelle if round(float(voce.netto_a_pagare), 2) == importo]
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
        return {"ok": False, "code": "receipt_required",
                "message": "Crea esplicitamente il documento economico, poi registra l'incasso nella sezione Incassi.",
                "redirectHref": f"/fatturazione/nuova?id_fascicolo={fid}"}, 409
    parcella_id = _text(getattr(parcella, "id", ""))
    if (not _text(getattr(fascicolo, "id_cliente", ""))
            or _text(getattr(parcella, "id_cliente", "")) != _text(getattr(fascicolo, "id_cliente", ""))):
        return {"ok": False, "conflict": True,
                "message": "Cliente del documento non concordante con il fascicolo: verifica il collegamento prima dell'incasso."}, 409
    if revision is not None and parcella_revision(parcella) != revision:
        return {"ok": False, "conflict": True,
                "message": "Il documento è cambiato: ricarica le parcelle prima di confermare. I dati inseriti sono conservati."}, 409
    expected_amount = round(float(parcella.netto_a_pagare), 2)
    if _stato(parcella) != "PAGATA" and importo != expected_amount:
        return {"ok": False, "conflict": True,
                "message": f"Versamento {_amount_label(importo)} diverso dal netto della parcella {_amount_label(expected_amount)}: saldo non confermato, importi e stati conservati.",
                "errors": {"importo": "Il versamento non dimostra il saldo della parcella."},
                "discordanza": {"parcellaId": parcella_id, "importoRicevuto": importo, "nettoParcella": expected_amount}}, 409
    # Nessuna creazione di proforme, cambio di stato o conferma della liquidazione:
    # solo un movimento del registro incassi può dimostrare l'evento di cassa.
    return {"ok": False, "code": "receipt_required", "parcellaId": parcella_id,
            "message": "Registra il pagamento effettivo nella sezione Incassi del documento economico.",
            "redirectHref": f"/fatturazione?id_documento={parcella_id}"}, 409
