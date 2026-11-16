"""Collettori agenda e scadenziario.

Leggono gli store di dominio già esistenti (``pct.agenda.Agenda`` e
``pct.scadenziario.GestioneScadenziario``) senza duplicarne le regole.
Le scadenze arretrate ancora aperte restano consultabili con la loro fonte.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Any

from pct.formatting import parse_datetime_rome
from pct.scadenze_stato import (
    ANNULLATA, BOZZA, COMPLETATA, ESITO_UDIENZA, STORICA, data_termine_corrente, stato_operativo,
    termine_note_in_sostituzione, termine_perentorio,
)

from ..models import OperationalSignal, SignalEvidence, SourceCoverage
from .base import CollectorContext, CollectorResult, unavailable_result

FUTURE_WINDOW_DAYS = 14
HEARING_PREP_WINDOW_DAYS = 2

_CLOSED_DEADLINE_STATES = {"completata", "chiusa", "annullata"}
_ESITO_UDIENZA_REASON = (
    "Udienza già tenuta: registrare rinvio, riserva o decisione dal verbale o dal provvedimento "
    "(artt. 126 e 127-ter c.p.c.)."
)
_CANCELLED_APPOINTMENT_STATES = {"annullato", "cancellato"}


def _to_date(value: Any) -> date | None:
    parsed = parse_datetime_rome(value)
    return parsed.date() if parsed is not None else None


def _enum_val(obj: Any) -> str:
    return str(getattr(obj, "value", obj or "") or "")


_PEC_AUDIT_REF = re.compile(r"\bPEC_AUDIT:([A-Za-z0-9][A-Za-z0-9_.:-]{1,179})", re.IGNORECASE)
_PEC_AUDIT_SUFFIX = re.compile(r":(?:deadline|hearing(?::[A-Za-z0-9_.-]+)?)$", re.IGNORECASE)


def origin_event_metadata(sc: Any) -> dict[str, str]:
    """Evento d'origine della scadenza (tipo, giorno Europe/Rome, PEC audit).

    Serve alla correlazione per riconoscere la stessa comunicazione registrata
    più volte nello scadenziario; nessun dato viene dedotto se manca.
    """
    out: dict[str, str] = {}
    event_day = _to_date(getattr(sc, "source_event_at", "") or "")
    if event_day is not None:
        out["evento_origine_giorno"] = event_day.isoformat()
    event_type = str(getattr(sc, "source_event_type", "") or "").strip()
    if event_type:
        out["evento_origine_tipo"] = event_type
    context = "\n".join(
        str(getattr(sc, attr, "") or "") for attr in ("note", "descrizione", "external_uid", "dedupe_key")
    )
    match = _PEC_AUDIT_REF.search(context)
    if match:
        pec_id = _PEC_AUDIT_SUFFIX.sub("", match.group(1).rstrip(".,;:"))
        if pec_id and not pec_id.casefold().startswith("docpresidio:"):
            out["pec_audit_id"] = pec_id
    return out


_REVOCA_UDIENZA = re.compile(r"^revoca\s+(?:(?:dell[’']|della)\s*)?udienza\b", re.I)


def registra_revoca_udienza(ctx: CollectorContext, scadenza: Any, fase: str) -> None:
    """Usa la revoca della cancelleria già recepita nello Scadenziario."""
    if fase in {ANNULLATA, BOZZA}:
        return
    if (_enum_val(getattr(scadenza, "source_event_type", "")) != "comunicazione_cancelleria"
            or _enum_val(getattr(scadenza, "hearing_mode", "")) != "note_scritte"
            or not _REVOCA_UDIENZA.match(_enum_val(getattr(scadenza, "titolo", "")))
            or not origin_event_metadata(scadenza).get("pec_audit_id")):
        return
    giorno_udienza = _to_date(getattr(scadenza, "source_event_at", ""))
    fascicolo_id = _enum_val(getattr(scadenza, "id_fascicolo", ""))
    if fascicolo_id and giorno_udienza:
        ctx.udienze_revocate_da_cancelleria.add((fascicolo_id, giorno_udienza))


def _scadenza_reason(ctx: CollectorContext, sc: Any, perentorio: bool) -> str:
    base = "Termine perentorio dello scadenziario." if perentorio else "Scadenza aperta dello scadenziario."
    resolver = ctx.scadenza_reason_resolver
    if resolver is None:
        return base
    try:
        detail = " ".join(str(resolver(sc) or "").split())
    except Exception:
        detail = ""
    return f"{base} {detail}".strip() if detail else base


class ScadenzarioCollector:
    source_type = "scadenziario"

    def collect(self, ctx: CollectorContext) -> CollectorResult:
        store = ctx.scadenziario_store
        if store is None:
            return unavailable_result(self.source_type, "Scadenziario non disponibile.")
        try:
            tutte = list(store.tutte(solo_aperte=False))
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
            fase = stato_operativo(sc, planning_day)
            registra_revoca_udienza(ctx, sc, fase)
            if fase in {ANNULLATA, BOZZA, COMPLETATA} or stato in _CLOSED_DEADLINE_STATES:
                continue
            if fase == STORICA:
                id_appuntamento = str(getattr(sc, "id_appuntamento", "") or "")
                if id_appuntamento and termine_note_in_sostituzione(sc):
                    ctx.appuntamenti_sostituiti_da_note.add(id_appuntamento)
                continue
            due = _to_date(data_termine_corrente(sc))
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
            perentorio = termine_perentorio(sc)
            creata = str(getattr(sc, "creata_il", "") or getattr(sc, "created_at", "") or "")
            max_watermark = max(max_watermark, creata)
            titolo = str(getattr(sc, "titolo", "") or "Scadenza")
            due_iso = due.isoformat() if due else ""
            # Regola V28 (pct.scadenze_stato): un'udienza passata e ancora aperta non e'
            # un termine scaduto ma un esito da registrare dal verbale o dal provvedimento
            # (artt. 126 e 127-ter c.p.c.); nessun termine perentorio ne dipende.
            esito_udienza = fase == ESITO_UDIENZA
            motivo = _ESITO_UDIENZA_REASON if esito_udienza else _scadenza_reason(ctx, sc, perentorio)
            href = f"/scadenziario?scadenza={scadenza_id}" if scadenza_id else "/scadenziario"
            if termine_note_in_sostituzione(sc):
                motivo = "Deposito di note in sostituzione dell’udienza (art. 127-ter c.p.c.). Fonte nello scadenziario."
                id_appuntamento = str(getattr(sc, "id_appuntamento", "") or "")
                if id_appuntamento:
                    ctx.appuntamenti_sostituiti_da_note.add(id_appuntamento)
            signals.append(
                OperationalSignal(
                    id=f"sig_sc_{scadenza_id}",
                    tenant_id=ctx.tenant_id,
                    source_type=self.source_type,
                    source_id=scadenza_id,
                    kind="hearing_outcome" if esito_udienza else "deadline_fulfill",
                    title=f"Registrare l'esito dell'udienza: {titolo}" if esito_udienza else titolo,
                    dedupe_key="",
                    fascicolo_id=fascicolo_id,
                    responsible_user_id=responsabile,
                    reason=motivo,
                    due_at=due_iso,
                    peremptory=perentorio and not esito_udienza,
                    blocking=perentorio and not esito_udienza,
                    legal_risk="high" if perentorio and not esito_udienza else "medium",
                    confidence=0.95,
                    href=href,
                    metadata={"scadenziario_id": scadenza_id, **origin_event_metadata(sc)},
                    evidence=[
                        SignalEvidence(
                            source_type=self.source_type,
                            source_id=scadenza_id,
                            label=titolo,
                            timestamp=due_iso,
                            href=f"/scadenziario?scadenza={scadenza_id}" if scadenza_id else "/scadenziario",
                            confidence=0.95,
                        ),
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
            if app_id in ctx.appuntamenti_sostituiti_da_note:
                continue
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


__all__ = ["AgendaCollector", "ScadenzarioCollector", "origin_event_metadata"]
