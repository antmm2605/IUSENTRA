"""Indicizzazione incrementale e completa della Ricerca Studio."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
from time import perf_counter
from typing import Any

from .adapters import BaseSearchAdapter, default_adapters
from .models import GlobalSearchDocument
from .repository import GlobalSearchRepository


@dataclass(slots=True)
class ReindexReport:
    tenant_id: str
    indexed: int = 0
    removed: int = 0
    took_ms: float = 0.0
    per_adapter: dict[str, int] = field(default_factory=dict)
    errors: list[dict[str, str]] = field(default_factory=list)
    started_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "indexed": self.indexed,
            "removed": self.removed,
            "took_ms": round(self.took_ms, 2),
            "per_adapter": self.per_adapter,
            "errors": self.errors,
            "started_at": self.started_at,
        }


class GlobalSearchIndexer:
    def __init__(
        self,
        repository: GlobalSearchRepository,
        adapters: list[BaseSearchAdapter] | None = None,
    ):
        self.repository = repository
        self.adapters = adapters or default_adapters()

    def collect_documents(self, context: dict[str, Any]) -> tuple[list[GlobalSearchDocument], dict[str, int], list[dict[str, str]]]:
        documents: list[GlobalSearchDocument] = []
        per_adapter: dict[str, int] = {}
        errors: list[dict[str, str]] = []
        for adapter in self.adapters:
            name = adapter.__class__.__name__
            try:
                items = adapter.collect(context)
                documents.extend(items)
                per_adapter[name] = len(items)
            except Exception as exc:
                per_adapter[name] = 0
                errors.append({"adapter": name, "error": str(exc)})
        documents = consolida_documenti(documents)
        return documents, per_adapter, errors

    def reindex_all(self, context: dict[str, Any]) -> ReindexReport:
        tenant_id = str(context.get("tenant_id") or "default")
        started = perf_counter()
        documents, per_adapter, errors = self.collect_documents(context)
        removed = self.repository.clear_tenant(tenant_id)
        indexed = self.repository.upsert_many(documents)
        report = ReindexReport(
            tenant_id=tenant_id,
            indexed=indexed,
            removed=removed,
            took_ms=(perf_counter() - started) * 1000,
            per_adapter=per_adapter,
            errors=errors,
        )
        self.repository.audit(tenant_id, "reindex_all", report.to_dict())
        return report

    def reindex_entity(self, context: dict[str, Any], entity_type: str, entity_id: str) -> dict[str, Any]:
        tenant_id = str(context.get("tenant_id") or "default")
        documents, _, errors = self.collect_documents(context)
        matched = [
            doc for doc in documents
            if doc.entity_type == entity_type and str(doc.entity_id) == str(entity_id)
        ]
        removed = self.repository.remove_entity(tenant_id, entity_type, str(entity_id))
        indexed = self.repository.upsert_many(matched)
        payload = {"tenant_id": tenant_id, "entity_type": entity_type, "entity_id": entity_id, "removed": removed, "indexed": indexed, "errors": errors}
        self.repository.audit(tenant_id, "reindex_entity", payload)
        return payload


#  Consolidamento delle voci che descrivono la stessa cosa
#  --------------------------------------------------------------------------
#  Una PEC puo' essere letta da due sorgenti diverse: il registro delle
#  comunicazioni dello studio e la casella vera. Finche' ciascuna produceva una
#  voce propria, l'avvocato vedeva lo stesso messaggio due volte, con due link
#  diversi e nessun modo di capire quale aprire. Qui le voci che parlano dello
#  stesso messaggio diventano una sola, che conserva tutte le provenienze.

#  Ordine di preferenza della voce principale: chi porta al messaggio vero
#  vince su chi porta al registro, perche' e' quella che l'avvocato vuole
#  aprire.
_PREFERENZA_SORGENTE = {"email": 0, "comunicazioni": 1}


def _identita_messaggio(doc: GlobalSearchDocument) -> str:
    """Identita' stabile di un messaggio, condivisa fra le sorgenti.

    Il ``Message-ID`` e' l'unico dato che le due sorgenti hanno in comune: gli
    identificativi interni sono diversi per costruzione. Senza di esso non si
    consolida nulla, per non accorpare messaggi diversi.
    """

    if doc.entity_type not in {"pec", "email"}:
        return ""
    grezzo = str((doc.metadata or {}).get("message_id") or "").strip()
    return grezzo.strip("<>").lower()


def _unisci(principale: GlobalSearchDocument, secondario: GlobalSearchDocument) -> GlobalSearchDocument:
    """Fonde due voci dello stesso messaggio senza perdere informazioni."""

    meta = dict(principale.metadata or {})
    meta_secondario = dict(secondario.metadata or {})

    #  Le etichette di entrambe le sorgenti, senza ripetizioni e in ordine.
    badge = list(meta.get("badges") or [])
    for etichetta in meta_secondario.get("badges") or []:
        if etichetta and etichetta not in badge:
            badge.append(etichetta)
    meta["badges"] = badge

    #  L'altra provenienza resta raggiungibile invece di sparire.
    altre = list(meta.get("altre_posizioni") or [])
    if secondario.source_url and secondario.source_url != principale.source_url:
        voce = {"url": secondario.source_url, "modulo": secondario.source_module}
        if voce not in altre:
            altre.append(voce)
    if altre:
        meta["altre_posizioni"] = altre
    meta["sorgenti"] = sorted({
        *(meta.get("sorgenti") or [principale.source_module]),
        secondario.source_module,
    })

    #  Il corpo piu' ricco vince; le parole chiave si sommano, cosi' la voce
    #  unica resta trovabile con i termini di entrambe le sorgenti.
    corpo = principale.body if len(principale.body) >= len(secondario.body) else secondario.body
    chiavi = " ".join(dict.fromkeys((f"{principale.keywords} {secondario.keywords}").split()))

    return replace(
        principale,
        body=corpo,
        keywords=chiavi,
        metadata=meta,
        client_id=principale.client_id or secondario.client_id,
        fascicolo_id=principale.fascicolo_id or secondario.fascicolo_id,
        pratica_id=principale.pratica_id or secondario.pratica_id,
    )


def consolida_documenti(documents: list[GlobalSearchDocument]) -> list[GlobalSearchDocument]:
    """Riduce a una sola voce i messaggi letti da piu' sorgenti."""

    per_identita: dict[tuple[str, str], int] = {}
    risultato: list[GlobalSearchDocument] = []
    for doc in documents:
        identita = _identita_messaggio(doc)
        if not identita:
            risultato.append(doc)
            continue
        chiave = (doc.tenant_id, identita)
        posizione = per_identita.get(chiave)
        if posizione is None:
            per_identita[chiave] = len(risultato)
            risultato.append(doc)
            continue
        esistente = risultato[posizione]
        preferisci_nuovo = _PREFERENZA_SORGENTE.get(doc.source_module, 9) < _PREFERENZA_SORGENTE.get(
            esistente.source_module, 9
        )
        risultato[posizione] = (
            _unisci(doc, esistente) if preferisci_nuovo else _unisci(esistente, doc)
        )
    return risultato
