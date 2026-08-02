"""Collettori agenda e scadenziario.

Leggono gli store di dominio già esistenti (``pct.agenda.Agenda`` e
``pct.scadenziario.GestioneScadenziario``) senza duplicarne le regole.
Le scadenze arretrate ancora aperte NON vengono mai escluse.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from pct.formatting import parse_datetime_rome

from ..models import OperationalSignal, SignalEvidence, SourceCoverage
from .base import CollectorContext, CollectorResult, unavailable_result

FUTURE_WINDOW_DAYS = 14
HEARING_PREP_WINDOW_DAYS = 2

_CLOSED_DEADLINE_STATES = {"completata", "chiusa", "annullata"}
_CANCELLED_APPOINTMENT_STATES = {"annullato", "cancellato"}


def _to_date(value: Any) -> date | None:
    parsed = parse_datetime_rome(value)
    return parsed.date() if parsed is not None else None


def _enum_val(obj: Any) -> str:
    return str(getattr(obj, "value", obj or "") or "")


class ScadenzarioCollector:
    source_type = "scadenziario"

    def collect(self, ctx: CollectorContext) -> CollectorResult:
        store = ctx.scadenziario_store
        if store is None:
            return unavailable_result(self.source_type, "Scadenziario non disponibile.")
        try:
            tutte = list(store.tutte(solo_aperte=True))
        except TypeError:
            try:
                tutte = list(store.tutte())
            except Exception:
                return unavailable_result(self.source_type, "Errore in lettura scadenziario.")
        except Exception:
            return unavailable_result(self.source_type, "Errore in lettura scadenziario.")

        planning_day = ctx.planning_date or ctx.clock.today()
        horizon = planning_day + timedelta(days=FUTURE_WINDOW_DAYS)
        signals: list[OperationalSignal] = []
        truncated = False
        max_watermark = ""
        for sc in tutte:
            stato = _enum_val(getattr(sc, "stato", "")).lower()
            if stato in _CLOSED_DEADLINE_STATES:
                continue
            due = _to_date(
                getattr(sc, "operational_due_at", "") or getattr(sc, "data_scadenza", "")
            )
            # gli arretrati aperti restano SEMPRE nel piano; il futuro oltre
            # l'orizzonte dei 14 giorni non entra nel giorno selezionato
            if due is not None and due > horizon:
                continue
            if len(signals) >= ctx.budget.max_items_per_source:
                truncated = True
                break
            scadenza_id = str(getattr(sc, "id", "") or "")
            fascicolo_id = str(getattr(sc, "id_fascicolo", "") or "")
            responsabile = str(getattr(sc, "id_utente_responsabile", "") or "")
            perentorio = bool(getattr(sc, "perentorio", False))
            creata = str(getattr(sc, "creata_il", "") or getattr(sc, "created_at", "") or "")
            max_watermark = max(max_watermark, creata)
            titolo = str(getattr(sc, "titolo", "") or "Scadenza")
            due_iso = due.isoformat() if due else ""
            signals.append(
                OperationalSignal(
                    id=f"sig_sc_{scadenza_id}",
                    tenant_id=ctx.tenant_id,
                    source_type=self.source_type,
                    source_id=scadenza_id,
                    kind="deadline_fulfill",
                    title=titolo,
                    dedupe_key="",
                    fascicolo_id=fascicolo_id,
                    responsible_user_id=responsabile,
                    reason=(
                        "Termine perentorio dello scadenziario."
                        if perentorio
                        else "Scadenza aperta dello scadenziario."
                    ),
                    due_at=due_iso,
                    peremptory=perentorio,
                    blocking=perentorio,
                    legal_risk="high" if perentorio else "medium",
                    confidence=0.95,
                    href=f"/scadenziario?scadenza={scadenza_id}" if scadenza_id else "/scadenziario",
                    metadata={"scadenziario_id": scadenza_id},
                    evidence=[
                        SignalEvidence(
                            source_type=self.source_type,
                            source_id=scadenza_id,
                            label=titolo,
                            timestamp=due_iso,
                            confidence=0.95,
                        )
                    ],
                )
            )
        return CollectorResult(
            source_type=self.source_type,
            signals=signals,
            coverage=SourceCoverage(
                source_type=self.source_type,
                status="complete" if not truncated else "stale",
                watermark=max_watermark,
                note="" if not truncated else "Risultato limitato dal budget di lavorazione.",
            ),
            watermark=max_watermark,
            truncated=truncated,
        )


class AgendaCollector:
    source_type = "agenda"

    def collect(self, ctx: CollectorContext) -> CollectorResult:
        store = ctx.agenda_store
        if store is None:
            return unavailable_result(self.source_type, "Agenda non disponibile.")
        try:
            tutti = list(store.tutti())
        except Exception:
            return unavailable_result(self.source_type, "Errore in lettura agenda.")

        planning_day = ctx.planning_date or ctx.clock.today()
        prep_horizon = planning_day + timedelta(days=HEARING_PREP_WINDOW_DAYS)
        signals: list[OperationalSignal] = []
        fixed_agenda: list[dict[str, Any]] = []
        day_slots: list[tuple[datetime, datetime, str]] = []
        truncated = False

        for ap in tutti:
            stato = _enum_val(getattr(ap, "stato", "")).lower()
            if stato in _CANCELLED_APPOINTMENT_STATES:
                continue
            raw_start = str(getattr(ap, "data_ora", "") or "")
            start_date = _to_date(raw_start)
            if start_date is None:
                continue
            tipo = _enum_val(getattr(ap, "tipo", "")).upper()
            is_hearing = "UDIENZA" in tipo
            app_id = str(getattr(ap, "id", "") or "")
            titolo = str(getattr(ap, "titolo", "") or "Appuntamento")
            avvocato = str(getattr(ap, "avvocato", "") or "")
            durata = int(getattr(ap, "durata_minuti", 0) or 0) or 60

            if start_date == planning_day:
                entry = {
                    "id": app_id,
                    "titolo": titolo,
                    "tipo": tipo or ("UDIENZA" if is_hearing else "APPUNTAMENTO"),
                    "data_ora": raw_start,
                    "durata_minuti": durata,
                    "avvocato": avvocato,
                    "luogo": str(getattr(ap, "luogo", "") or ""),
                    "procedimento": str(getattr(ap, "procedimento", "") or ""),
                    "id_cliente": str(getattr(ap, "id_cliente", "") or ""),
                    "stato": _enum_val(getattr(ap, "stato", "")),
                }
                fixed_agenda.append(entry)
                try:
                    start_dt = parse_datetime_rome(raw_start)
                    if start_dt is None:
                        raise ValueError("data agenda non leggibile")
                    day_slots.append(
                        (start_dt, start_dt + timedelta(minutes=durata), app_id)
                    )
                except Exception:
                    pass

            if is_hearing and planning_day <= start_date <= prep_horizon:
                if len(signals) >= ctx.budget.max_items_per_source:
                    truncated = True
                    break
                signals.append(
                    OperationalSignal(
                        id=f"sig_ag_{app_id}",
                        tenant_id=ctx.tenant_id,
                        source_type=self.source_type,
                        source_id=app_id,
                        kind="hearing_attend",
                        title=f"Udienza: {titolo}",
                        dedupe_key="",
                        lawyer_hint=avvocato,
                        reason=(
                            "Udienza fissata nel giorno selezionato in agenda."
                            if start_date == planning_day
                            else "Udienza imminente da preparare."
                        ),
                        due_at=raw_start or start_date.isoformat(),
                        blocking=start_date == planning_day,
                        legal_risk="high" if start_date == planning_day else "medium",
                        confidence=0.9,
                        href=f"/agenda?appuntamento={app_id}" if app_id else "/agenda",
                        metadata={
                            "agenda_id": app_id,
                            "agenda_avvocato": avvocato,
                            "procedimento_rg": str(getattr(ap, "procedimento", "") or ""),
                        },
                        evidence=[
                            SignalEvidence(
                                source_type=self.source_type,
                                source_id=app_id,
                                label=titolo,
                                timestamp=raw_start,
                                confidence=0.9,
                            )
                        ],
                    )
                )

        # conflitti di calendario: sovrapposizioni tra impegni del giorno
        day_slots.sort()
        for prev, cur in zip(day_slots, day_slots[1:], strict=False):
            if cur[0] < prev[1]:
                signals.append(
                    OperationalSignal(
                        id=f"sig_conf_{prev[2]}_{cur[2]}",
                        tenant_id=ctx.tenant_id,
                        source_type=self.source_type,
                        source_id=f"{prev[2]}+{cur[2]}",
                        kind="calendar_conflict",
                        title="Sovrapposizione di impegni in agenda",
                        dedupe_key="",
                        reason=(
                            "Due impegni del giorno selezionato si sovrappongono: "
                            "verificare orari o delegare."
                        ),
                        due_at=planning_day.isoformat(),
                        priority_hint="P1",
                        confidence=0.9,
                        href="/agenda",
                        metadata={"canonical_event": f"conflict:{prev[2]}:{cur[2]}"},
                    )
                )

        return CollectorResult(
            source_type=self.source_type,
            signals=signals,
            coverage=SourceCoverage(
                source_type=self.source_type,
                status="complete" if not truncated else "stale",
                note="" if not truncated else "Risultato limitato dal budget di lavorazione.",
            ),
            fixed_agenda=fixed_agenda,
            truncated=truncated,
        )


__all__ = ["AgendaCollector", "ScadenzarioCollector"]
