"""Documenti di riconoscimento collegati alla cliente dal catalogo SQL corrente.

Solo letture del contenuto con titolare riscontrato; nessun file viene copiato.
La medesima impronta nel medesimo tenant compare una sola volta.
"""
from __future__ import annotations
from typing import Any

def documenti_identita_cliente(cliente_id: str, fascicoli: list[Any]) -> list[dict[str, Any]]:
    from web.services.react_fascicoli_bridge import _sql_document_catalog_by_id
    result: dict[str, dict[str, Any]] = {}
    for fascicolo in fascicoli:
        if str(getattr(fascicolo, "id_cliente", "")) != str(cliente_id):
            continue
        for assignment in _sql_document_catalog_by_id(fascicolo).values():
            meta = assignment.metadata or {}
            if assignment.status not in {"confirmed", "manual_override"} and not (assignment.status in {"catalogued", "proposed"} and meta.get("automatic_classification")):
                continue
            if assignment.document_nature != "documento_identita" or meta.get("identity_client_id") != str(cliente_id) or not meta.get("identity_holder"):
                continue
            key = str(meta.get("identity_content_sha256") or "") or assignment.document_sha256 or f"{fascicolo.id}:{assignment.document_id}"
            if key in result:
                result[key]["sourceCount"] += 1
                continue
            result[key] = {
                "id": f"{fascicolo.id}:{assignment.document_id}",
                "title": assignment.document_label,
                "subtitle": "Titolare riscontrato nel contenuto: " + str(meta["identity_holder"]),
                "href": f"/fascicoli/{fascicolo.id}/documenti/{assignment.document_id}/visualizza?viewer=mobile",
                "tone": "info", "status": "Catalogato dal contenuto", "sourceCount": 1,
            }
    return list(result.values())
