"""Backfill del catalogo documentale ufficiale sul fascicolo locale."""

from __future__ import annotations

from typing import Any


_SERVICE_SOURCE_LABEL = {
    "polisweb_consultazione": "PST",
    "pdp_penale": "PDP",
    "pat_siga": "PAT",
    "ptt_sigit": "PTT",
}

_SERVICE_DOCUMENT_LABEL = {
    "polisweb_consultazione": "DocumentiFascicolo",
    "pdp_penale": "DocumentiFascicolo",
    "pat_siga": "DocumentiFascicolo",
    "ptt_sigit": "DocumentiFascicolo",
}


def _source_label(service_code: str) -> str:
    return _SERVICE_SOURCE_LABEL.get(str(service_code or "").strip(), "PST")


def _service_label(service_code: str) -> str:
    return _SERVICE_DOCUMENT_LABEL.get(str(service_code or "").strip(), str(service_code or "").strip() or "DocumentiFascicolo")


def _group_portal_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    for row in rows:
        service_code = str(row.get("service_code") or "").strip()
        title = str(row.get("title") or row.get("original_filename") or "").strip()
        if not service_code or not title:
            continue
        data_deposito = str(row.get("data_deposito") or row.get("portal_document_date") or "").strip()
        mittente = str(row.get("mittente") or "").strip()
        id_deposito = str(row.get("id_deposito") or "").strip()
        fallback_key = f"__{data_deposito}__{mittente}" if data_deposito or mittente else f"__{title}"
        group_key = f"{service_code}::{id_deposito or fallback_key}"
        group = groups.setdefault(
            group_key,
            {
                "service_code": service_code,
                "source_label": _source_label(service_code),
                "service_label": _service_label(service_code),
                "id_deposito": id_deposito or fallback_key,
                "tipo_atto": str(row.get("tipo_atto") or "").strip(),
                "data_deposito": data_deposito,
                "mittente": mittente,
                "documenti": [],
            },
        )
        if not group["tipo_atto"] and str(row.get("tipo_atto") or "").strip():
            group["tipo_atto"] = str(row.get("tipo_atto") or "").strip()
        if not group["data_deposito"] and data_deposito:
            group["data_deposito"] = data_deposito
        if not group["mittente"] and mittente:
            group["mittente"] = mittente
        portal_ref = str(row.get("portal_document_ref") or "").strip()
        group["documenti"].append(
            {
                "id_documento": portal_ref,
                "id_cat": portal_ref,
                "id_repeatto": "",
                "msg_id": "",
                "nome": title,
                "tipo": str(row.get("document_category") or "").strip(),
                "data_deposito": data_deposito,
                "mittente": mittente,
                "dimensione_bytes": int(row.get("file_size_bytes") or 0),
                "disponibile": True,
                "id_deposito": id_deposito or fallback_key,
                "tipo_atto": str(row.get("tipo_atto") or "").strip(),
            }
        )
    return sorted(
        groups.values(),
        key=lambda item: (
            item.get("data_deposito") or "",
            item.get("id_deposito") or "",
        ),
        reverse=True,
    )


def sync_official_catalog_on_fascicolo(
    *,
    gestore_fascicoli: Any,
    repo_telematico: Any,
    id_fasc: str,
) -> dict[str, int]:
    rows = list(repo_telematico.list_documents_for_practice(id_fasc, source_type="portal") or [])
    groups = _group_portal_rows(rows)
    synced = 0
    documents = 0
    for group in groups:
        if not list(group.get("documenti") or []):
            continue
        gestore_fascicoli.sincronizza_deposito_portale(
            id_fasc,
            fonte=str(group.get("source_label") or "PST"),
            id_deposito_esterno=str(group.get("id_deposito") or "").strip(),
            tipo_atto=str(group.get("tipo_atto") or "").strip(),
            data_deposito=str(group.get("data_deposito") or "").strip(),
            mittente=str(group.get("mittente") or "").strip(),
            documenti_portale=list(group.get("documenti") or []),
            note=f"Catalogo ufficiale riallineato dal core telematico ({group.get('service_label') or 'DocumentiFascicolo'}).",
            stato="IMPORTATO_DA_PORTALE",
            servizio_portale=str(group.get("service_label") or "DocumentiFascicolo"),
        )
        synced += 1
        documents += len(list(group.get("documenti") or []))
    return {
        "depositi_allineati": synced,
        "documenti_catalogati": documents,
    }
