"""Collettore del presidio operativo dei fascicoli.

Riusa le azioni P0–P3 GIÀ prodotte da ``build_fascicolo_operational_presidio``
(presidio documentale, PEC, relata, economico, doppioni) senza duplicarne le
regole. Il provider viene costruito dal runtime web (che ha accesso ai testi
già estratti e al riepilogo pagamenti veloce): questo collettore non esegue
mai OCR o estrazioni.

Un evento, una attività: le azioni dello stesso fascicolo con lo stesso
settore, lo stesso adempimento e la stessa data (per esempio il deposito
delle note scritte ex art. 127-ter c.p.c. letto da tre copie del decreto)
diventano UN segnale con un'evidenza per ogni documento che lo prova.
"""

from __future__ import annotations

import hashlib
from typing import Any

from ..correlation import event_text_key
from ..models import OperationalSignal, SignalEvidence, SourceCoverage
from .base import CollectorContext, CollectorResult, unavailable_result

# settore presidio → tipo azione canonico del piano
SECTOR_ACTION_KINDS = {
    "pec": "pec_review",
    "documenti": "document_review",
    "relata": "relata_completion",
    "economico": "economic_entry",
    "doppioni": "duplicate_reconciliation",
}

_PRIORITY_ORDER = ("P0", "P1", "P2", "P3")


def action_event_key(action: dict[str, Any]) -> tuple[str, str, str]:
    """Chiave dell'evento: settore, adempimento normalizzato, data."""
    return (
        str(action.get("sector") or ""),
        event_text_key(str(action.get("title") or action.get("label") or "")),
        str(action.get("dateIso") or "")[:10],
    )


class CasePresidioCollector:
    source_type = "case_presidio"

    def collect(self, ctx: CollectorContext) -> CollectorResult:
        provider = ctx.presidio_provider
        if provider is None:
            return unavailable_result(
                self.source_type, "Presidio fascicoli non disponibile."
            )
        signals: list[OperationalSignal] = []
        scanned: set[str] = set()
        processed = 0
        truncated = False
        try:
            for entry in provider(ctx):
                fascicolo = dict(entry.get("fascicolo") or {})
                fascicolo_id = str(fascicolo.get("id") or "")
                if ctx.dirty_fascicoli is not None and fascicolo_id not in ctx.dirty_fascicoli:
                    continue
                if processed >= ctx.budget.max_fascicoli:
                    truncated = True
                    break
                processed += 1
                groups: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
                for action in entry.get("actions") or []:
                    row = dict(action)
                    if str(row.get("id") or ""):
                        groups.setdefault(action_event_key(row), []).append(row)
                for actions in groups.values():
                    signals.append(self._signal_from_actions(ctx, fascicolo, actions))
                # lettura completa del fascicolo: i segnali non riemessi sono superati
                if fascicolo_id and entry.get("complete", True):
                    scanned.add(fascicolo_id)
        except Exception:
            return unavailable_result(
                self.source_type, "Errore durante la lettura del presidio fascicoli."
            )
        return CollectorResult(
            source_type=self.source_type,
            signals=signals,
            coverage=SourceCoverage(
                source_type=self.source_type,
                status="complete" if not truncated else "stale",
                note=(
                    ""
                    if not truncated
                    else f"Analizzati {processed} fascicoli su budget: il resto al prossimo giro."
                ),
            ),
            truncated=truncated,
            scanned_scopes=scanned,
        )

    def _evidence_for(self, fascicolo_id: str, action: dict[str, Any]) -> list[SignalEvidence]:
        action_id = str(action.get("id") or "")
        source_href = str(action.get("sourceHref") or "")
        source_label = str(action.get("source") or "")
        rows = action.get("evidence") or []
        # Il presidio espone ``evidence`` come testo unico: iterarlo come lista
        # produrrebbe un'evidenza per ogni carattere (etichetta di una lettera).
        if isinstance(rows, str):
            rows = [rows]
        elif not isinstance(rows, (list, tuple)):
            rows = []
        labels = [
            str(ev if not isinstance(ev, dict) else ev.get("label") or ev.get("title") or "").strip()
            for ev in rows[:3]
        ]
        labels = [label for label in labels if label] or [source_label or str(action.get("title") or "")]
        return [
            SignalEvidence(
                source_type=self.source_type,
                source_id=f"{fascicolo_id}:{action_id}",
                label=label,
                href=source_href,
                confidence=0.8,
            )
            for label in labels[:1]
        ]

    def _signal_from_actions(
        self, ctx: CollectorContext, fascicolo: dict[str, Any], actions: list[dict[str, Any]]
    ) -> OperationalSignal:
        fascicolo_id = str(fascicolo.get("id") or "")
        actions = sorted(
            actions,
            key=lambda a: (
                _PRIORITY_ORDER.index(a.get("priority")) if a.get("priority") in _PRIORITY_ORDER else 9,
                str(a.get("id") or ""),
            ),
        )
        primary = actions[0]
        sector, title_key, due = action_event_key(primary)
        event_hash = hashlib.sha256(f"{sector}|{title_key}|{due}".encode()).hexdigest()[:16]
        source_id = f"{fascicolo_id}:evento-{event_hash}"
        kind = SECTOR_ACTION_KINDS.get(sector, "document_review")

        evidence: list[SignalEvidence] = []
        seen: set[tuple[str, str]] = set()
        document_ids: list[str] = []
        for action in actions:
            doc_id = str(action.get("documentId") or "")
            if doc_id and doc_id not in document_ids:
                document_ids.append(doc_id)
            for ev in self._evidence_for(fascicolo_id, action):
                ref = (ev.href or ev.source_id, ev.label)
                if ref in seen:
                    continue
                seen.add(ref)
                evidence.append(ev)

        metadata: dict[str, Any] = {
            "canonical_event": f"presidio:{fascicolo_id}:{sector}:{title_key}",
            "sector": sector,
            "fascicolo_referente": str(fascicolo.get("avvocato_referente") or ""),
            "fascicolo_dominus": str(fascicolo.get("avvocato_dominus") or ""),
            "fascicolo_label": str(fascicolo.get("numero") or fascicolo.get("titolo") or ""),
            "presidio_action_ids": [str(a.get("id") or "") for a in actions][:20],
            # segnali delle versioni precedenti (uno per azione): servono a
            # conservare le decisioni già prese quando le copie si fondono
            "legacy_signal_ids": [f"sig_case_{fascicolo_id}_{a.get('id')}" for a in actions][:20],
        }
        if document_ids:
            metadata["document_id"] = document_ids[0]
            metadata["document_ids"] = document_ids[:20]
        base_normativa = next((str(a.get("legalBasis") or "") for a in actions if a.get("legalBasis")), "")
        if base_normativa:
            metadata["base_normativa"] = base_normativa
        if any(bool(a.get("requiresCommunicationDate")) for a in actions):
            metadata["needs_review"] = True

        reason = str(primary.get("reason") or "")
        if len(document_ids) > 1:
            reason = f"{reason} Stesso adempimento letto in {len(document_ids)} documenti del fascicolo.".strip()
        priority = str(primary.get("priority") or "")
        blocking = any(bool(a.get("blocking")) for a in actions)
        return OperationalSignal(
            id=f"sig_case_{fascicolo_id}_{event_hash}",
            tenant_id=ctx.tenant_id,
            source_type=self.source_type,
            source_id=source_id,
            kind=kind,
            title=str(primary.get("title") or primary.get("label") or "Azione di presidio"),
            dedupe_key="",
            fascicolo_id=fascicolo_id,
            cliente_id=str(fascicolo.get("id_cliente") or ""),
            lawyer_hint=str(fascicolo.get("avvocato_referente") or ""),
            reason=reason,
            due_at=due,
            priority_hint=priority if priority in _PRIORITY_ORDER else "",
            blocking=blocking,
            peremptory=any(bool(a.get("peremptory")) for a in actions),
            legal_risk="high" if blocking else "medium",
            confidence=0.8,
            href=str(primary.get("href") or (f"/fascicoli/{fascicolo_id}" if fascicolo_id else "")),
            metadata=metadata,
            evidence=evidence[:10],
        )


__all__ = ["CasePresidioCollector", "SECTOR_ACTION_KINDS", "action_event_key"]
