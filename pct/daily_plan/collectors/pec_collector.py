"""Collettore dei segnali PEC dal presidio audit-grade.

Legge ESCLUSIVAMENTE gli esiti già materializzati da ``PecAuditRepository``
(pipeline D.M. 44/2011: classificazione, firma, collegamento fascicolo,
eventi legali, termini candidati, udienze, pagamenti). Nessun contenuto
grezzo del messaggio entra nei segnali: il testo PEC è input non affidabile
e non viene mai trattato come istruzione.

Il collettore NON invia PEC e NON calcola termini processuali: i termini
candidati non confermati diventano attività di verifica umana.
"""

from __future__ import annotations

from typing import Any

from ..models import OperationalSignal, SignalEvidence, SourceCoverage
from .base import CollectorContext, CollectorResult, unavailable_result

# sotto questa soglia il collegamento fascicolo proposto è "debole"
WEAK_LINK_SCORE = 0.75

_BAD_QUALITY = {"rosso"}
_WARN_QUALITY = {"giallo", "da_controllare"}
_BAD_SIGNATURE = {"non_valida", "invalida", "errore"}
_REMOTE_HEARING_MODES = {"remoto", "mista", "remota", "remote", "telematica", "videoudienza"}


def _fascicolo_of(row: dict[str, Any]) -> tuple[str, str]:
    """(fascicolo_id, match) dal collegamento materializzato sul messaggio."""
    fascicolo_id = str(row.get("linked_fascicolo_id") or "")
    try:
        score = float(row.get("linked_fascicolo_score") or 0.0)
    except Exception:
        score = 0.0
    if not fascicolo_id:
        return "", ""
    if score < WEAK_LINK_SCORE:
        return fascicolo_id, "weak"
    return fascicolo_id, "strong"


def _evidence(row: dict[str, Any], label: str) -> SignalEvidence:
    return SignalEvidence(
        source_type="pec",
        source_id=str(row.get("message_id") or row.get("id") or ""),
        label=label,
        timestamp=str(row.get("received_at") or row.get("created_at") or ""),
        confidence=float(row.get("event_confidence") or 0.0),
    )


class PecSignalCollector:
    source_type = "pec"

    def collect(self, ctx: CollectorContext) -> CollectorResult:
        repo = ctx.pec_repository
        if repo is None:
            return unavailable_result(self.source_type, "Presidio PEC non disponibile.")

        since = str((ctx.watermarks.get(self.source_type) or {}).get("watermark") or "")
        limit = ctx.budget.max_items_per_source
        signals: list[OperationalSignal] = []
        truncated = False
        try:
            deadlines = repo.list_legal_deadlines_since(since, limit=limit)
            hearings = repo.list_legal_hearings_since(since, limit=limit)
            payments = repo.list_legal_payments_since(since, limit=limit)
            messages = repo.list_messages_to_presidiate(since, limit=limit)
            watermark = repo.daily_plan_watermark()
        except Exception:
            return unavailable_result(
                self.source_type, "Errore in lettura del presidio PEC."
            )
        truncated = any(
            len(rows) >= limit for rows in (deadlines, hearings, payments, messages)
        )

        for row in deadlines:
            signals.append(self._deadline_signal(ctx, row))
        for row in hearings:
            sig = self._hearing_signal(ctx, row)
            if sig is not None:
                signals.append(sig)
            link_sig = self._remote_link_signal(ctx, row)
            if link_sig is not None:
                signals.append(link_sig)
        for row in payments:
            if str(row.get("workflow_status") or "") == "to_review":
                signals.append(self._payment_signal(ctx, row))
        for row in messages:
            signals.append(self._message_signal(ctx, row))

        return CollectorResult(
            source_type=self.source_type,
            signals=[s for s in signals if s is not None],
            coverage=SourceCoverage(
                source_type=self.source_type,
                status="complete" if not truncated else "stale",
                watermark=watermark,
                note="" if not truncated else "Arretrato PEC in smaltimento su più esecuzioni.",
            ),
            watermark=watermark,
            truncated=truncated,
        )

    # ------------------------------------------------------------- mapper

    def _deadline_signal(self, ctx: CollectorContext, row: dict[str, Any]) -> OperationalSignal:
        fascicolo_id, match = _fascicolo_of(row)
        scadenza_id = str(row.get("scadenziario_id") or "")
        confermata = bool(scadenza_id) and str(row.get("deterministic_status") or "") == "ok"
        review = bool(row.get("human_review_required")) or not confermata
        norm = str(row.get("norm_ref") or "").strip()
        peremptory_raw = row.get("peremptory")
        peremptory = bool(peremptory_raw) if peremptory_raw is not None else False
        metadata: dict[str, Any] = {
            "canonical_event": f"pec_deadline:{row.get('id')}",
            "esito_deterministico": str(row.get("deterministic_status") or ""),
        }
        if scadenza_id:
            metadata["scadenziario_id"] = scadenza_id
        if match == "weak":
            metadata["fascicolo_match"] = "weak"
        if review:
            metadata["needs_review"] = True
        titolo = "Conferma il termine ricevuto via PEC"
        motivo = (
            "La comunicazione contiene un termine che potrebbe decorrere dalla "
            "comunicazione stessa: confermare associazione e data di decorrenza."
        )
        if norm:
            motivo += f" Riferimento: {norm}."
        return OperationalSignal(
            id=f"sig_pecd_{row.get('id')}",
            tenant_id=ctx.tenant_id,
            source_type=self.source_type,
            source_id=str(row.get("id") or ""),
            kind="pec_deadline",
            title=titolo,
            dedupe_key="",
            fascicolo_id=fascicolo_id,
            reason=motivo,
            event_at=str(row.get("received_at") or ""),
            due_at=str(row.get("dies_a_quo_date") or ""),
            peremptory=peremptory,
            legal_risk="high" if peremptory else "medium",
            confidence=float(row.get("event_confidence") or 0.0),
            href=f"/email/messaggio/{row.get('message_id')}" if row.get("message_id") else "",
            metadata=metadata,
            evidence=[_evidence(row, "Termine candidato da PEC")],
        )

    def _hearing_signal(self, ctx: CollectorContext, row: dict[str, Any]) -> OperationalSignal | None:
        hearing_date = str(row.get("hearing_date") or "")
        if not hearing_date:
            return None
        fascicolo_id, match = _fascicolo_of(row)
        metadata: dict[str, Any] = {"canonical_event": f"pec_hearing:{row.get('id')}"}
        agenda_id = str(row.get("agenda_id") or "")
        if agenda_id:
            metadata["agenda_id"] = agenda_id
        if match == "weak":
            metadata["fascicolo_match"] = "weak"
        if bool(row.get("human_review_required")):
            metadata["needs_review"] = True
        return OperationalSignal(
            id=f"sig_pech_{row.get('id')}",
            tenant_id=ctx.tenant_id,
            source_type=self.source_type,
            source_id=str(row.get("id") or ""),
            kind="hearing_attend",
            title="Udienza comunicata via PEC",
            dedupe_key="",
            fascicolo_id=fascicolo_id,
            reason="La comunicazione fissa o conferma un'udienza.",
            event_at=str(row.get("received_at") or ""),
            due_at=hearing_date,
            confidence=float(row.get("event_confidence") or 0.0),
            href=f"/email/messaggio/{row.get('message_id')}" if row.get("message_id") else "",
            metadata=metadata,
            evidence=[_evidence(row, "Udienza da PEC")],
        )

    def _remote_link_signal(self, ctx: CollectorContext, row: dict[str, Any]) -> OperationalSignal | None:
        mode = str(row.get("mode") or "").strip().lower()
        link = str(row.get("link") or "").strip()
        verified = row.get("link_verified")
        has_trusted_link = bool(link) and (verified is True or verified == 1)
        if mode not in _REMOTE_HEARING_MODES or has_trusted_link:
            return None
        fascicolo_id, _ = _fascicolo_of(row)
        link_is_present = bool(link)
        return OperationalSignal(
            id=f"sig_pecl_{row.get('id')}",
            tenant_id=ctx.tenant_id,
            source_type=self.source_type,
            source_id=f"{row.get('id')}:link",
            kind="hearing_link_missing",
            title=(
                "Collegamento per udienza da remoto non verificato"
                if link_is_present
                else "Collegamento per udienza da remoto mancante"
            ),
            dedupe_key="",
            fascicolo_id=fascicolo_id,
            reason=(
                "L'udienza si terrà da remoto ma il collegamento acquisito non risulta verificato."
                if link_is_present
                else "L'udienza si terrà da remoto ma il collegamento non risulta acquisito."
            ),
            due_at=str(row.get("hearing_date") or ""),
            priority_hint="P1",
            confidence=float(row.get("event_confidence") or 0.0),
            metadata={"canonical_event": f"pec_hearing_link:{row.get('id')}"},
            evidence=[
                _evidence(
                    row,
                    "Udienza da remoto con collegamento non verificato"
                    if link_is_present
                    else "Udienza da remoto senza collegamento",
                )
            ],
        )

    def _payment_signal(self, ctx: CollectorContext, row: dict[str, Any]) -> OperationalSignal:
        fascicolo_id, match = _fascicolo_of(row)
        metadata: dict[str, Any] = {"canonical_event": f"pec_payment:{row.get('id')}"}
        if match == "weak":
            metadata["fascicolo_match"] = "weak"
        return OperationalSignal(
            id=f"sig_pecp_{row.get('id')}",
            tenant_id=ctx.tenant_id,
            source_type=self.source_type,
            source_id=str(row.get("id") or ""),
            kind="payment_review",
            title="Importi da verificare in una comunicazione",
            dedupe_key="",
            fascicolo_id=fascicolo_id,
            reason="La comunicazione contiene importi o liquidazioni da verificare.",
            event_at=str(row.get("received_at") or ""),
            confidence=float(row.get("event_confidence") or 0.0),
            href=f"/email/messaggio/{row.get('message_id')}" if row.get("message_id") else "",
            metadata=metadata,
            evidence=[_evidence(row, "Evento economico da PEC")],
        )

    def _message_signal(self, ctx: CollectorContext, row: dict[str, Any]) -> OperationalSignal:
        message_id = str(row.get("id") or "")
        quality = str(row.get("quality_status") or "")
        signature = str(row.get("signature_status") or "")
        fascicolo_id = str(row.get("linked_fascicolo_id") or "")
        metadata: dict[str, Any] = {"canonical_event": f"pec_message:{message_id}"}
        blocking = quality in _BAD_QUALITY or signature in _BAD_SIGNATURE
        review = False
        if not fascicolo_id:
            titolo = "PEC non associata a un fascicolo"
            motivo = "La comunicazione non risulta collegata ad alcun fascicolo: assegnarla."
            review = True
        elif signature in _BAD_SIGNATURE:
            titolo = "PEC con anomalia di firma"
            motivo = "La verifica della firma digitale ha rilevato un problema."
        elif quality in _BAD_QUALITY:
            titolo = "PEC con controlli in errore"
            motivo = "I controlli automatici sulla comunicazione sono in stato rosso."
        else:
            titolo = "PEC da visionare"
            motivo = "La comunicazione è in attesa di controllo da parte dello studio."
            review = bool(row.get("event_review_required"))
        if review:
            metadata["needs_review"] = True
        return OperationalSignal(
            id=f"sig_pecm_{message_id}",
            tenant_id=ctx.tenant_id,
            source_type=self.source_type,
            source_id=message_id,
            kind="pec_review",
            title=titolo,
            dedupe_key="",
            fascicolo_id=fascicolo_id,
            reason=motivo,
            event_at=str(row.get("received_at") or ""),
            blocking=blocking,
            legal_risk="high" if blocking else "low",
            priority_hint="P1" if (blocking or not fascicolo_id) else "P2",
            confidence=0.85 if blocking else 0.7,
            href=f"/email/messaggio/{message_id}" if message_id else "",
            metadata=metadata,
            evidence=[
                SignalEvidence(
                    source_type="pec",
                    source_id=message_id,
                    label=titolo,
                    timestamp=str(row.get("received_at") or ""),
                    confidence=0.85,
                )
            ],
        )


__all__ = ["PecSignalCollector", "WEAK_LINK_SCORE"]
