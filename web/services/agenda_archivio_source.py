"""Fonti dell'Agenda dal fatto canonico corrente, senza rettificare l'impegno."""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote

from pct.archivio_letture.deduplica import fatti_canonici


def fonte_da_fatto(event: dict[str, Any], fascicolo: Any, *, registro: Any, tenant: str) -> dict[str, Any]:
    marker = re.search(r"\bARCHIVIO_FATTO:([A-Za-z0-9_-]+)", str(event.get("technicalNotes") or event.get("notes") or ""))
    if not marker or fascicolo is None:
        return {}
    fid = str(fascicolo.id)
    facts = fatti_canonici(registro.fatti(tenant, fid, categoria="data", campo="udienza"))
    fact = next((f for f in facts if f.id == marker.group(1)), None)
    missing = {"sourceHref": "", "sourceKind": "documento", "sourceLabel": "Fonte documentale da verificare", "sourceVerified": False}
    if not fact or fact.verifica not in {"verificata", "corretta"} or fact.tipo != "documento":
        return missing
    # Non collegare una fonte che non sostiene giorno e orario dell'impegno.
    if len(fact.valore) < 16 or fact.valore[:16] != str(event.get("start") or "")[:16]:
        return missing
    doc = next((d for d in getattr(fascicolo, "documenti", []) if str(d.id) == fact.oggetto_id and not getattr(d, "eliminato_il", "")), None)
    obj = registro.oggetto(tenant, fid, "documento", fact.oggetto_id)
    if doc is None or obj is None or not obj.presente or not fact.sha256 or fact.sha256 != obj.impronta:
        return missing
    storage_hash = str(getattr(doc, "hash_sha256", "") or "")
    content_hash = str(getattr(doc, "hash_contenuto_sha256", "") or "")
    if not ((storage_hash and storage_hash == obj.sha256_archivio) or (content_hash and content_hash == fact.sha256)):
        return missing
    return {
        "sourceHref": f"/fascicoli/{quote(fid, safe='')}/documenti/{quote(fact.oggetto_id, safe='')}/visualizza",
        "sourceKind": "documento", "sourceLabel": str(getattr(doc, "nome", "") or obj.nome or "Documento del fascicolo"),
        "sourceVerified": True,
    }


def fonte_corrente(event: dict[str, Any], fascicolo: Any) -> dict[str, Any]:
    """Consulta SQL una volta per impegno nella richiesta, senza aprire PDF/OCR."""
    if "ARCHIVIO_FATTO:" not in str(event.get("technicalNotes") or event.get("notes") or ""):
        return {}
    from flask import g, has_app_context
    if not has_app_context():
        return {}
    from web.services.registro_letture_runtime import registro_corrente, tenant_corrente
    cache = getattr(g, "_agenda_archive_sources", {})
    key = (str(getattr(fascicolo, "id", "")), str(event.get("id", "")), str(event.get("start", "")))
    if key not in cache:
        registry = getattr(g, "_agenda_archive_registry", None)
        if registry is None:
            registry = registro_corrente()
            g._agenda_archive_registry = registry
        cache[key] = fonte_da_fatto(event, fascicolo, registro=registry, tenant=tenant_corrente())
        g._agenda_archive_sources = cache
    return cache[key]
