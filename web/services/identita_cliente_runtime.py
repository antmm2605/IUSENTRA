"""Documenti di riconoscimento collegati alla cliente dal catalogo SQL corrente.

Solo letture del contenuto con titolare riscontrato; nessun file viene copiato.
La medesima impronta nel medesimo tenant compare una sola volta.
"""
from __future__ import annotations
from typing import Any

def identita_del_cliente(fascicolo: Any) -> dict[str, str]:
    """Nome, codice fiscale e data di nascita del cliente del fascicolo, per l'identità congiunta.

    Vuoto se la scheda non è disponibile: il catalogo non collega allora il documento in automatico.
    """
    cliente_id = str(getattr(fascicolo, "id_cliente", "") or "")
    dati = {"id": cliente_id, "nome": str(getattr(fascicolo, "nome_cliente", "") or ""), "codice_fiscale": "", "data_nascita": ""}
    if not cliente_id:
        return dati
    try:
        from web.helpers import get_clienti

        cliente = get_clienti().get(cliente_id)
    except Exception:
        return dati
    if cliente is None:
        return dati
    dati["nome"] = str(getattr(cliente, "nome_completo", "") or dati["nome"])
    dati["codice_fiscale"] = str(getattr(cliente, "codice_fiscale", "") or "")
    dati["data_nascita"] = str(getattr(cliente, "data_nascita", "") or "")
    return dati


def documenti_identita_cliente(cliente_id: str, fascicoli: list[Any]) -> list[dict[str, Any]]:
    from web.services.react_fascicoli_bridge import _sql_document_catalog_by_id
    result: dict[str, dict[str, Any]] = {}
    for fascicolo in fascicoli:
        if str(getattr(fascicolo, "id_cliente", "")) != str(cliente_id):
            continue
        for assignment in _sql_document_catalog_by_id(fascicolo).values():
            meta = assignment.metadata or {}
            # Collegamento automatico solo con identità congiunta (nome + codice fiscale o data di nascita);
            # altrimenti serve la conferma dell'avvocato.
            if assignment.status not in {"confirmed", "manual_override"} and not meta.get("identity_binding_verified"):
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
