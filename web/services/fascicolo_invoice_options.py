"""Consultazione SQL mirata dei documenti ammissibili per un incasso.

Solo lettura indicizzata: nessuna inizializzazione o importazione storica.
"""

from __future__ import annotations

import json
import math
from datetime import date

from pct.fatturazione import Parcella, parcella_revision


def invoice_options(database, case_id: str, *, cursor: str = "", limit: int = 50):
    if not isinstance(case_id, str) or not case_id.strip() or len(case_id) > 128:
        raise ValueError("Fascicolo non valido.")
    if not isinstance(cursor, str) or len(cursor) > 128:
        raise ValueError("Riferimento della pagina non valido.")
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("Dimensione della pagina non valida.")
    case_rows = database.fetchall_readonly("SELECT id,id_cliente,dati_json FROM fascicoli WHERE id=?", (case_id,))
    if not case_rows:
        raise KeyError(case_id)
    case_data = json.loads(case_rows[0]["dati_json"])
    if not isinstance(case_data, dict):
        raise ValueError("Dati economici del fascicolo non leggibili.")
    from web.services.react_fascicoli_bridge import (
        _payment_source_for_kind,
        _normalise_payment_status,
        _payment_amount_value,
        _payment_date_iso,
    )

    payments = case_data.get("pagamenti", {})
    sources = [_payment_source_for_kind(payments, kind) for kind in ("parcella", "liquidazione_giudice")]
    rows = database.fetchall_readonly(
        "SELECT id,id_fascicolo,stato,dati_json FROM parcelle "
        "WHERE id_fascicolo=? AND id>? AND stato IN (?,?,?,?) ORDER BY id LIMIT ?",
        (case_id, cursor, "BOZZA", "EMESSA", "SCADUTA", "PAGATA", limit + 1),
    )
    items = []
    for row in rows[:limit]:
        try:
            invoice = Parcella.from_dict(json.loads(row["dati_json"]))
        except (ValueError, TypeError, KeyError) as exc:
            raise ValueError("Documento economico non leggibile: nessuna selezione automatica.") from exc
        if invoice.id != row["id"] or invoice.id_fascicolo != case_id or invoice.stato.value != row["stato"]:
            raise ValueError("Documento economico discordante dal collegamento SQL: riallineamento richiesto.")
        amount = float(invoice.netto_a_pagare)
        if not math.isfinite(amount):
            raise ValueError("Importo del documento non valido: verifica richiesta.")
        reason = "" if amount > 0 else "Il documento non ha un importo positivo da incassare."
        if not case_rows[0]["id_cliente"] or invoice.id_cliente != case_rows[0]["id_cliente"]:
            reason = "Cliente del documento non concordante con il fascicolo: verifica il collegamento."
        paid_date = str(invoice.data_pagamento or "")
        registered_amount = None
        if invoice.stato.value == "PAGATA":
            amounts = []
            for source in sources:
                status = _normalise_payment_status(source.get("status") or source.get("stato"))
                if not status and (source.get("pagato") is True or source.get("pagata") is True):
                    status = "pagato"
                if status != "pagato" or str(source.get("proforma_id") or source.get("proformaId") or "") != invoice.id:
                    continue
                historical_date, date_error = _payment_date_iso(
                    source.get("data_pagamento") or source.get("dataPagamento") or source.get("date")
                )
                if date_error or (historical_date and historical_date != paid_date):
                    reason = "Data del pagamento storico discordante: verifica il versamento registrato."
                value = _payment_amount_value(source.get("incasso_importo"))
                if (
                    isinstance(value, bool)
                    or not isinstance(value, (int, float))
                    or not math.isfinite(value)
                    or value <= 0
                ):
                    continue
                amounts.append(round(float(value), 2))
            if amounts and len(set(amounts)) == 1:
                registered_amount = amounts[0]
            else:
                reason = "Importo storico non riscontrato o discordante: verifica la prova del versamento."
            try:
                if not paid_date or date.fromisoformat(paid_date).isoformat() != paid_date:
                    raise ValueError("Data non canonica")
            except ValueError:
                reason = "Data del pagamento storico mancante o non valida: verifica il documento."
        items.append(
            {
                "id": invoice.id,
                "numero": str(invoice.numero or invoice.id),
                "totale": round(amount, 2),
                "registeredAmount": registered_amount,
                "stato": invoice.stato.value,
                "dataPagamento": paid_date,
                "metodoPagamento": str(invoice.metodo_pagamento or ""),
                "revision": parcella_revision(invoice),
                "canRegister": not reason,
                "reason": reason,
            }
        )
    more = len(rows) > limit
    return {"ok": True, "items": items, "hasMore": more, "nextCursor": items[-1]["id"] if more and items else ""}
