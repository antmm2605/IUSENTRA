"""Collettore del presidio economico.

Legge preventivi/conferimenti (``pct.preventivi``) e parcelle
(``pct.fatturazione``) già persistiti. Non emette MAI fatture definitive:
produce solo attività di verifica e proposte di predisposizione bozze.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from ..models import OperationalSignal, SignalEvidence, SourceCoverage
from .base import CollectorContext, CollectorResult, unavailable_result

QUOTE_FOLLOWUP_AFTER_DAYS = 7
_OPEN_QUOTE_STATES = {"INVIATO", "APERTO"}


def _enum_val(obj: Any) -> str:
    return str(getattr(obj, "value", obj or "") or "")


def _parse_date(value: Any):
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return datetime.strptime(raw[:10], "%Y-%m-%d").date()
    except Exception:
        return None


class EconomicSignalCollector:
    source_type = "economic"

    def collect(self, ctx: CollectorContext) -> CollectorResult:
        if ctx.preventivi_store is None and ctx.fatturazione_store is None:
            return unavailable_result(
                self.source_type, "Presidio economico non disponibile."
            )
        signals: list[OperationalSignal] = []
        note = ""
        try:
            signals.extend(self._quote_signals(ctx))
        except Exception:
            note = "Preventivi non leggibili."
        try:
            signals.extend(self._invoice_signals(ctx))
        except Exception:
            note = (note + " Parcelle non leggibili.").strip()
        truncated = len(signals) > ctx.budget.max_items_per_source
        if truncated:
            signals = signals[: ctx.budget.max_items_per_source]
        status = "complete"
        if note:
            status = "stale"
        elif truncated:
            status = "stale"
            note = "Risultato limitato dal budget di lavorazione."
        return CollectorResult(
            source_type=self.source_type,
            signals=signals,
            coverage=SourceCoverage(source_type=self.source_type, status=status, note=note),
            truncated=truncated,
        )

    def _quote_signals(self, ctx: CollectorContext) -> list[OperationalSignal]:
        store = ctx.preventivi_store
        if store is None:
            return []
        today = ctx.planning_date or ctx.clock.today()
        out: list[OperationalSignal] = []
        for p in store.tutti_preventivi():
            stato = _enum_val(getattr(p, "stato", "")).upper()
            if stato not in _OPEN_QUOTE_STATES:
                continue
            inviato = _parse_date(getattr(p, "inviato_cliente_il", "") or getattr(p, "data_emissione", ""))
            if inviato is None or (today - inviato).days < QUOTE_FOLLOWUP_AFTER_DAYS:
                continue
            pid = str(getattr(p, "id", "") or "")
            numero = str(getattr(p, "numero", "") or "")
            out.append(
                OperationalSignal(
                    id=f"sig_prev_{pid}",
                    tenant_id=ctx.tenant_id,
                    source_type=self.source_type,
                    source_id=pid,
                    kind="quote_followup",
                    title=f"Preventivo {numero} senza riscontro dal cliente",
                    dedupe_key="",
                    fascicolo_id=str(getattr(p, "id_fascicolo", "") or ""),
                    cliente_id=str(getattr(p, "id_cliente", "") or ""),
                    reason=(
                        "Il preventivo è stato inviato da oltre una settimana senza "
                        "accettazione: valutare un sollecito."
                    ),
                    due_at="",
                    priority_hint="P3",
                    confidence=0.9,
                    href=f"/preventivi?preventivo={pid}" if pid else "/preventivi",
                    metadata={"canonical_event": f"preventivo:{pid}"},
                    evidence=[
                        SignalEvidence(
                            source_type=self.source_type,
                            source_id=pid,
                            label=f"Preventivo {numero}",
                            timestamp=str(getattr(p, "inviato_cliente_il", "") or ""),
                            confidence=0.9,
                        )
                    ],
                )
            )
        return out

    def _invoice_signals(self, ctx: CollectorContext) -> list[OperationalSignal]:
        store = ctx.fatturazione_store
        if store is None:
            return []
        today = ctx.planning_date or ctx.clock.today()
        out: list[OperationalSignal] = []
        for parcella in store.tutte():
            stato = _enum_val(getattr(parcella, "stato", "")).upper()
            pid = str(getattr(parcella, "id", "") or "")
            numero = str(getattr(parcella, "numero", "") or "")
            fascicolo_id = str(getattr(parcella, "id_fascicolo", "") or "")
            cliente_id = str(getattr(parcella, "id_cliente", "") or "")
            scadenza = _parse_date(getattr(parcella, "data_scadenza", ""))
            if stato == "BOZZA":
                out.append(
                    OperationalSignal(
                        id=f"sig_parc_{pid}",
                        tenant_id=ctx.tenant_id,
                        source_type=self.source_type,
                        source_id=pid,
                        kind="invoice_draft_needed",
                        title=f"Parcella {numero} ferma in bozza",
                        dedupe_key="",
                        fascicolo_id=fascicolo_id,
                        cliente_id=cliente_id,
                        reason="La parcella è in bozza: completarla o programmarne l'emissione.",
                        priority_hint="P2",
                        confidence=0.9,
                        href=f"/fatturazione?parcella={pid}" if pid else "/fatturazione",
                        metadata={"canonical_event": f"parcella:{pid}"},
                        evidence=[
                            SignalEvidence(
                                source_type=self.source_type,
                                source_id=pid,
                                label=f"Parcella {numero} (bozza)",
                                confidence=0.9,
                            )
                        ],
                    )
                )
            elif stato in {"EMESSA", "SCADUTA"} and scadenza is not None and scadenza < today:
                giorni = (today - scadenza).days
                out.append(
                    OperationalSignal(
                        id=f"sig_insoluto_{pid}",
                        tenant_id=ctx.tenant_id,
                        source_type=self.source_type,
                        source_id=pid,
                        kind="payment_review",
                        title=f"Parcella {numero} non incassata",
                        dedupe_key="",
                        fascicolo_id=fascicolo_id,
                        cliente_id=cliente_id,
                        reason=f"Il pagamento risulta scaduto da {giorni} giorni: valutare sollecito.",
                        due_at=(today + timedelta(days=7)).isoformat(),
                        priority_hint="P2",
                        confidence=0.9,
                        href=f"/fatturazione?parcella={pid}" if pid else "/fatturazione",
                        metadata={"canonical_event": f"insoluto:{pid}"},
                        evidence=[
                            SignalEvidence(
                                source_type=self.source_type,
                                source_id=pid,
                                label=f"Parcella {numero} scaduta",
                                timestamp=str(getattr(parcella, "data_scadenza", "") or ""),
                                confidence=0.9,
                            )
                        ],
                    )
                )
        return out


__all__ = ["EconomicSignalCollector", "QUOTE_FOLLOWUP_AFTER_DAYS"]
