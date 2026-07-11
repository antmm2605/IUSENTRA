"""Collettore del presidio operativo dei fascicoli.

Riusa le azioni P0–P3 GIÀ prodotte da ``build_fascicolo_operational_presidio``
(presidio documentale, PEC, relata, economico, doppioni) senza duplicarne le
regole: ogni azione diventa un ``OperationalSignal`` con il presidio come
fonte. Il provider viene costruito dal runtime web (che ha accesso ai testi
già estratti e al riepilogo pagamenti veloce): questo collettore non esegue
mai OCR o estrazioni.
"""

from __future__ import annotations

from typing import Any

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


class CasePresidioCollector:
    source_type = "case_presidio"

    def collect(self, ctx: CollectorContext) -> CollectorResult:
        provider = ctx.presidio_provider
        if provider is None:
            return unavailable_result(
                self.source_type, "Presidio fascicoli non disponibile."
            )
        signals: list[OperationalSignal] = []
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
                for action in entry.get("actions") or []:
                    sig = self._signal_from_action(ctx, fascicolo, dict(action))
                    if sig is not None:
                        signals.append(sig)
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
        )

    def _signal_from_action(
        self, ctx: CollectorContext, fascicolo: dict[str, Any], action: dict[str, Any]
    ) -> OperationalSignal | None:
        action_id = str(action.get("id") or "")
        if not action_id:
            return None
        fascicolo_id = str(fascicolo.get("id") or "")
        sector = str(action.get("sector") or "")
        kind = SECTOR_ACTION_KINDS.get(sector, "document_review")
        priority = str(action.get("priority") or "")
        evidence_rows = action.get("evidence") or []
        evidence = [
            SignalEvidence(
                source_type=self.source_type,
                source_id=f"{fascicolo_id}:{action_id}",
                label=str(ev if not isinstance(ev, dict) else ev.get("label") or ev.get("title") or ""),
                confidence=0.8,
            )
            for ev in evidence_rows[:3]
        ] or [
            SignalEvidence(
                source_type=self.source_type,
                source_id=f"{fascicolo_id}:{action_id}",
                label=str(action.get("title") or ""),
                confidence=0.8,
            )
        ]
        metadata: dict[str, Any] = {
            "canonical_event": f"presidio:{fascicolo_id}:{action_id}",
            "sector": sector,
            "fascicolo_referente": str(fascicolo.get("avvocato_referente") or ""),
            "fascicolo_dominus": str(fascicolo.get("avvocato_dominus") or ""),
            "fascicolo_label": str(fascicolo.get("numero") or fascicolo.get("titolo") or ""),
        }
        base_normativa = str(action.get("legalBasis") or "")
        if base_normativa:
            metadata["base_normativa"] = base_normativa
        if bool(action.get("requiresCommunicationDate")):
            metadata["needs_review"] = True
        return OperationalSignal(
            id=f"sig_case_{fascicolo_id}_{action_id}",
            tenant_id=ctx.tenant_id,
            source_type=self.source_type,
            source_id=f"{fascicolo_id}:{action_id}",
            kind=kind,
            title=str(action.get("title") or action.get("label") or "Azione di presidio"),
            dedupe_key="",
            fascicolo_id=fascicolo_id,
            cliente_id=str(fascicolo.get("id_cliente") or ""),
            lawyer_hint=str(fascicolo.get("avvocato_referente") or ""),
            reason=str(action.get("reason") or ""),
            due_at=str(action.get("dateIso") or ""),
            priority_hint=priority if priority in ("P0", "P1", "P2", "P3") else "",
            blocking=bool(action.get("blocking")),
            peremptory=bool(action.get("peremptory")),
            legal_risk="high" if action.get("blocking") else "medium",
            confidence=0.8,
            href=str(action.get("href") or (f"/fascicoli/{fascicolo_id}" if fascicolo_id else "")),
            metadata=metadata,
            evidence=evidence,
        )


__all__ = ["CasePresidioCollector", "SECTOR_ACTION_KINDS"]
