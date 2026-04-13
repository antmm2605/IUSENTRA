"""Motore scadenziario con calcolo legale e operativo."""

from __future__ import annotations

import calendar
import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, time, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class TipoTermine(str, Enum):
    UDIENZA = "UDIENZA"
    DEPOSITO_MEMORIA = "DEPOSITO_MEMORIA"
    DEPOSITO_ATTO = "DEPOSITO_ATTO"
    NOTIFICA = "NOTIFICA"
    IMPUGNAZIONE = "IMPUGNAZIONE"
    RISPOSTA_ECCEZIONE = "RISPOSTA_ECCEZIONE"
    PAGAMENTO = "PAGAMENTO"
    PRESCRIZIONE = "PRESCRIZIONE"
    DECADENZA = "DECADENZA"
    ADEMPIMENTO = "ADEMPIMENTO"
    TERMINE_PERENTORIO = "TERMINE_PERENTORIO"
    TERMINE_ORDINATORIO = "TERMINE_ORDINATORIO"
    ALTRO = "ALTRO"


class PrioritaTermine(str, Enum):
    CRITICA = "CRITICA"
    ALTA = "ALTA"
    MEDIA = "MEDIA"
    BASSA = "BASSA"


class StatoTermine(str, Enum):
    APERTO = "APERTO"
    COMPLETATO = "COMPLETATO"
    ANNULLATO = "ANNULLATO"
    SCADUTO = "SCADUTO"


class UnitaTermine(str, Enum):
    ORE = "hours"
    GIORNI = "days"
    MESI = "months"
    ANNI = "years"


class ModalitaOperativa(str, Enum):
    APERTO = "open"
    CHIUSO = "closed"
    SOLO_URGENTI = "urgent_only"
    ORARI_LIMITATI = "limited_hours"


class AmbitoCalendario(str, Enum):
    NAZIONALE = "national"
    UFFICIO = "judicial_office"
    STUDIO = "studio"
    PROCEDURALE = "procedural"


class TipoRegolaCalendario(str, Enum):
    FESTIVITA_FISSA = "fixed_holiday"
    FESTIVITA_MOBILE = "movable_holiday"
    PATRONO = "patron_holiday"
    CHIUSURA_RANGE = "range_closure"
    SOSPENSIONE_PROCEDURALE = "procedural_suspension"
    OSSERVANZA = "observance"


def _calcola_pasqua(anno: int) -> date:
    a = anno % 19
    b = anno // 100
    c = anno % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mese = (h + l - 7 * m + 114) // 31
    giorno = ((h + l - 7 * m + 114) % 31) + 1
    return date(anno, mese, giorno)


def festività_italiane(anno: int) -> List[date]:
    pasqua = _calcola_pasqua(anno)
    return [
        date(anno, 1, 1),
        date(anno, 1, 6),
        pasqua,
        pasqua + timedelta(days=1),
        date(anno, 4, 25),
        date(anno, 5, 1),
        date(anno, 6, 2),
        date(anno, 8, 15),
        date(anno, 11, 1),
        date(anno, 12, 8),
        date(anno, 12, 25),
        date(anno, 12, 26),
    ]


def _festività_cache(anni: range) -> set[date]:
    feste: set[date] = set()
    for anno in anni:
        feste.update(festività_italiane(anno))
    return feste


def è_giorno_lavorativo(d: date, sospensione_feriale: bool = True) -> bool:
    if d.weekday() >= 5:
        return False
    if d in _festività_cache(range(d.year - 1, d.year + 2)):
        return False
    if sospensione_feriale and d.month == 8:
        return False
    return True


def prossimo_giorno_lavorativo(d: date, sospensione_feriale: bool = True) -> date:
    while not è_giorno_lavorativo(d, sospensione_feriale):
        d += timedelta(days=1)
    return d


def _aggiungi_mesi_calendario(d: date, mesi: int) -> date:
    totale = (d.month - 1) + mesi
    anno = d.year + (totale // 12)
    mese = (totale % 12) + 1
    giorno = min(d.day, calendar.monthrange(anno, mese)[1])
    return date(anno, mese, giorno)


def _aggiungi_anni_calendario(d: date, anni: int) -> date:
    anno = d.year + anni
    giorno = min(d.day, calendar.monthrange(anno, d.month)[1])
    return date(anno, d.month, giorno)


def _aggiungi_giorni_processuali(data_inizio: date, giorni: int, sospensione_feriale: bool = True, escludi_inizio: bool = True) -> date:
    if giorni <= 0:
        return data_inizio
    corrente = data_inizio + timedelta(days=1) if escludi_inizio else data_inizio
    contati = 0
    while True:
        if not (sospensione_feriale and corrente.month == 8):
            contati += 1
            if contati == giorni:
                return corrente
        corrente += timedelta(days=1)


def _aggiungi_giorni_lavorativi(data_inizio: date, giorni: int, sospensione_feriale: bool = True, escludi_inizio: bool = True) -> date:
    if giorni <= 0:
        return data_inizio
    corrente = data_inizio + timedelta(days=1) if escludi_inizio else data_inizio
    contati = 0
    while True:
        if è_giorno_lavorativo(corrente, sospensione_feriale):
            contati += 1
            if contati == giorni:
                return corrente
        corrente += timedelta(days=1)


def calcola_termine(data_inizio: date, giorni: int = 0, tipo: str = "liberi", sospensione_feriale: bool = True, escludi_inizio: bool = True, mesi: int = 0, anni: int = 0) -> date:
    d = data_inizio
    tipo_norm = (tipo or "liberi").lower()
    if anni:
        d = _aggiungi_anni_calendario(d, anni)
    if mesi:
        d = _aggiungi_mesi_calendario(d, mesi)
    if giorni:
        if tipo_norm == "lavorativi":
            d = _aggiungi_giorni_lavorativi(d, giorni, sospensione_feriale=sospensione_feriale, escludi_inizio=escludi_inizio)
        else:
            d = _aggiungi_giorni_processuali(d, giorni, sospensione_feriale=sospensione_feriale, escludi_inizio=escludi_inizio)
    return prossimo_giorno_lavorativo(d, sospensione_feriale)


@dataclass
class RegolaCalendario:
    scope: str
    kind: str
    label: str
    entity_id: str | None = None
    code: str | None = None
    month_num: int | None = None
    day_num: int | None = None
    start_date: str | None = None
    end_date: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    applies_to_legal_deadlines: bool = False
    applies_to_operational_deadlines: bool = False
    operating_mode: str = ModalitaOperativa.CHIUSO.value
    is_recurring: bool = True
    is_enabled: bool = True
    priority: int = 100
    source_url: str = ""
    verified_at: str = ""
    notes: str = ""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "RegolaCalendario":
        payload = dict(data or {})
        return RegolaCalendario(**{k: v for k, v in payload.items() if k in RegolaCalendario.__dataclass_fields__})


@dataclass
class ProfiloTermine:
    code: str
    label: str
    unit: str
    quantity: int
    exclude_initial_day: bool = True
    extend_if_final_holiday: bool = True
    extend_if_final_saturday: bool = True
    apply_ferial_suspension: bool = True
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "ProfiloTermine":
        payload = dict(data or {})
        return ProfiloTermine(**{k: v for k, v in payload.items() if k in ProfiloTermine.__dataclass_fields__})


@dataclass
class EsitoCalcoloScadenza:
    raw_due_at: str
    legal_due_at: str
    operational_due_at: str | None
    office_mode_on_legal_due_date: str
    trace: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


PROFILI_TERMINE_BUILTIN: Dict[str, ProfiloTermine] = {
    "TERM_10_DAYS": ProfiloTermine("TERM_10_DAYS", "Termine 10 giorni", UnitaTermine.GIORNI.value, 10),
    "TERM_15_DAYS": ProfiloTermine("TERM_15_DAYS", "Termine 15 giorni", UnitaTermine.GIORNI.value, 15),
    "TERM_20_DAYS": ProfiloTermine("TERM_20_DAYS", "Termine 20 giorni", UnitaTermine.GIORNI.value, 20),
    "TERM_30_DAYS": ProfiloTermine("TERM_30_DAYS", "Termine 30 giorni", UnitaTermine.GIORNI.value, 30),
    "TERM_40_DAYS": ProfiloTermine("TERM_40_DAYS", "Termine 40 giorni", UnitaTermine.GIORNI.value, 40),
    "TERM_60_DAYS": ProfiloTermine("TERM_60_DAYS", "Termine 60 giorni", UnitaTermine.GIORNI.value, 60),
    "TERM_3_HOURS": ProfiloTermine("TERM_3_HOURS", "Termine 3 ore", UnitaTermine.ORE.value, 3, extend_if_final_saturday=False, apply_ferial_suspension=False),
    "TERM_1_MONTH": ProfiloTermine("TERM_1_MONTH", "Termine 1 mese", UnitaTermine.MESI.value, 1, exclude_initial_day=False),
    "TERM_6_MONTHS": ProfiloTermine("TERM_6_MONTHS", "Termine 6 mesi", UnitaTermine.MESI.value, 6, exclude_initial_day=False, apply_ferial_suspension=False),
    "TERM_1_YEAR": ProfiloTermine("TERM_1_YEAR", "Termine 1 anno", UnitaTermine.ANNI.value, 1, exclude_initial_day=False, apply_ferial_suspension=False),
    "TERM_10_YEARS": ProfiloTermine("TERM_10_YEARS", "Termine 10 anni", UnitaTermine.ANNI.value, 10, exclude_initial_day=False, apply_ferial_suspension=False),
    "TERM_30_DAYS_NO_FERIAL": ProfiloTermine("TERM_30_DAYS_NO_FERIAL", "Termine 30 giorni senza sospensione feriale", UnitaTermine.GIORNI.value, 30, apply_ferial_suspension=False),
}


def profili_termine_builtin() -> Dict[str, Dict[str, Any]]:
    return {code: profilo.to_dict() for code, profilo in PROFILI_TERMINE_BUILTIN.items()}


def _profilo_custom(code: str, label: str, *, giorni: int = 0, mesi: int = 0, anni: int = 0, ore: int = 0, tipo: str = "liberi", sospensione_feriale: bool = True) -> ProfiloTermine:
    if ore:
        return ProfiloTermine(code, label, UnitaTermine.ORE.value, ore, extend_if_final_saturday=False, apply_ferial_suspension=False)
    if mesi:
        return ProfiloTermine(code, label, UnitaTermine.MESI.value, mesi, exclude_initial_day=False, apply_ferial_suspension=sospensione_feriale)
    if anni:
        return ProfiloTermine(code, label, UnitaTermine.ANNI.value, anni, exclude_initial_day=False, apply_ferial_suspension=sospensione_feriale)
    return ProfiloTermine(code, label, UnitaTermine.GIORNI.value, max(giorni, 0), exclude_initial_day=tipo != "continui", apply_ferial_suspension=sospensione_feriale)


def _same_month_day(d: date, month: int, day: int) -> bool:
    return d.month == month and d.day == day


def _to_datetime(value: str | datetime | date) -> datetime:
    if isinstance(value, datetime):
        return value.replace(microsecond=0)
    if isinstance(value, date):
        return datetime.combine(value, time.min)
    text = str(value or "").strip()
    if not text:
        raise ValueError("Data/ora iniziale obbligatoria")
    if len(text) == 10:
        return datetime.combine(date.fromisoformat(text), time.min)
    return datetime.fromisoformat(text)


def _iso_dt(value: datetime) -> str:
    return value.replace(microsecond=0).isoformat()


def _matches_rule(rule: RegolaCalendario, when: datetime, channel: str) -> bool:
    if not rule.is_enabled:
        return False
    if channel == "legal" and not rule.applies_to_legal_deadlines:
        return False
    if channel == "operational" and not rule.applies_to_operational_deadlines:
        return False
    if rule.kind in {TipoRegolaCalendario.FESTIVITA_FISSA.value, TipoRegolaCalendario.PATRONO.value, TipoRegolaCalendario.OSSERVANZA.value}:
        return bool(rule.month_num and rule.day_num and _same_month_day(when.date(), rule.month_num, rule.day_num))
    if rule.kind == TipoRegolaCalendario.FESTIVITA_MOBILE.value:
        return rule.code == "EASTER_MONDAY" and (_calcola_pasqua(when.year) + timedelta(days=1)) == when.date()
    if rule.kind == TipoRegolaCalendario.CHIUSURA_RANGE.value:
        return bool(rule.start_date and rule.end_date and date.fromisoformat(rule.start_date) <= when.date() <= date.fromisoformat(rule.end_date))
    if rule.kind == TipoRegolaCalendario.SOSPENSIONE_PROCEDURALE.value:
        return rule.code == "FERRIAL_AUGUST" and when.month == 8 and 1 <= when.day <= 31
    return False


def _matching_rules(when: datetime, rules: List[RegolaCalendario], channel: str) -> List[RegolaCalendario]:
    return [rule for rule in rules if _matches_rule(rule, when, channel)]


def _dominant_operating_mode(when: datetime, rules: List[RegolaCalendario], channel: str) -> str:
    matches = sorted([rule for rule in _matching_rules(when, rules, channel) if rule.operating_mode != ModalitaOperativa.APERTO.value], key=lambda rule: rule.priority)
    return matches[0].operating_mode if matches else ModalitaOperativa.APERTO.value


def _is_procedural_suspension_day(when: datetime, rules: List[RegolaCalendario]) -> bool:
    return any(rule.kind == TipoRegolaCalendario.SOSPENSIONE_PROCEDURALE.value and _matches_rule(rule, when, "legal") for rule in rules)


def _has_blocking_rule(when: datetime, rules: List[RegolaCalendario], channel: str) -> bool:
    for rule in rules:
        if rule.kind == TipoRegolaCalendario.SOSPENSIONE_PROCEDURALE.value:
            continue
        if _matches_rule(rule, when, channel) and rule.operating_mode != ModalitaOperativa.APERTO.value:
            return True
    return False


def _count_suspension_days_between(start_at: datetime, end_at: datetime, procedural_rules: List[RegolaCalendario]) -> int:
    cursor = start_at
    count = 0
    while cursor.date() <= end_at.date():
        if _is_procedural_suspension_day(cursor, procedural_rules):
            count += 1
        cursor += timedelta(days=1)
    return count


def _compute_raw_due(start_at: datetime, profile: ProfiloTermine, procedural_rules: List[RegolaCalendario], trace: List[str]) -> datetime:
    if profile.unit == UnitaTermine.ORE.value:
        cursor = start_at + timedelta(hours=1) if profile.exclude_initial_day else start_at
        if profile.exclude_initial_day:
            trace.append(f"Esclusa l'ora iniziale -> {_iso_dt(cursor)}")
        counted = 0
        while counted < profile.quantity:
            if not (profile.apply_ferial_suspension and _is_procedural_suspension_day(cursor, procedural_rules)):
                counted += 1
                if counted == profile.quantity:
                    trace.append(f"Ora utile n.{counted} -> {_iso_dt(cursor)}")
                    return cursor
            else:
                trace.append(f"Ora sospesa per periodo feriale -> {_iso_dt(cursor)}")
            cursor += timedelta(hours=1)
        return cursor
    if profile.unit == UnitaTermine.GIORNI.value:
        cursor = start_at + timedelta(days=1) if profile.exclude_initial_day else start_at
        if profile.exclude_initial_day:
            trace.append(f"Escluso il giorno iniziale -> {_iso_dt(cursor)}")
        counted = 0
        while counted < profile.quantity:
            if not (profile.apply_ferial_suspension and _is_procedural_suspension_day(cursor, procedural_rules)):
                counted += 1
                if counted == profile.quantity:
                    trace.append(f"Giorno utile n.{counted} -> {_iso_dt(cursor)}")
                    return cursor
            else:
                trace.append(f"Giorno sospeso per periodo feriale -> {cursor.date().isoformat()}")
            cursor += timedelta(days=1)
        return cursor
    base_due = datetime.combine(_aggiungi_mesi_calendario(start_at.date(), profile.quantity), start_at.time()) if profile.unit == UnitaTermine.MESI.value else datetime.combine(_aggiungi_anni_calendario(start_at.date(), profile.quantity), start_at.time())
    trace.append(f"Scadenza base a calendario comune -> {_iso_dt(base_due)}")
    if not profile.apply_ferial_suspension:
        return base_due
    due = base_due
    suspension_count_start = start_at + timedelta(days=1) if profile.exclude_initial_day else start_at
    while True:
        extra_days = _count_suspension_days_between(suspension_count_start, due, procedural_rules)
        shifted = base_due + timedelta(days=extra_days)
        if shifted == due:
            if extra_days > 0:
                trace.append(f"Aggiunti {extra_days} giorni di sospensione feriale -> {_iso_dt(due)}")
            return due
        due = shifted


def _roll_forward_legal_due(raw_due: datetime, profile: ProfiloTermine, legal_rules: List[RegolaCalendario], trace: List[str]) -> datetime:
    due = raw_due
    while True:
        sunday = due.weekday() == 6
        saturday = due.weekday() == 5
        holiday = _has_blocking_rule(due, legal_rules, "legal")
        must_extend = (profile.extend_if_final_holiday and (sunday or holiday)) or (profile.extend_if_final_saturday and saturday)
        if not must_extend:
            return due
        trace.append(f"Proroga dal {due.date().isoformat()} al primo giorno successivo utile")
        due += timedelta(days=1)


def _is_operational_business_day(when: datetime, rules: List[RegolaCalendario]) -> bool:
    if when.weekday() >= 5:
        return False
    return not _has_blocking_rule(when, rules, "operational")


def _subtract_operational_business_days(from_date: datetime, business_days: int, operational_rules: List[RegolaCalendario], trace: List[str]) -> Optional[datetime]:
    if business_days <= 0:
        return None
    cursor = from_date
    remaining = business_days
    while remaining > 0:
        cursor -= timedelta(days=1)
        if _is_operational_business_day(cursor, operational_rules):
            remaining -= 1
            trace.append(f"Anticipo operativo: trovato giorno utile {cursor.date().isoformat()} ({remaining} residui)")
        else:
            trace.append(f"Anticipo operativo: saltato giorno non utile {cursor.date().isoformat()}")
    return cursor


def regole_calendario_nazionali(include_october_observance_blocking: bool = False) -> List[RegolaCalendario]:
    now_iso = datetime.now().isoformat(timespec="seconds")
    return [
        RegolaCalendario(id="nat_0101", scope=AmbitoCalendario.NAZIONALE.value, kind=TipoRegolaCalendario.FESTIVITA_FISSA.value, code="NEW_YEAR", label="Capodanno", month_num=1, day_num=1, applies_to_legal_deadlines=True, applies_to_operational_deadlines=True, operating_mode=ModalitaOperativa.CHIUSO.value, priority=10, verified_at=now_iso),
        RegolaCalendario(id="nat_0106", scope=AmbitoCalendario.NAZIONALE.value, kind=TipoRegolaCalendario.FESTIVITA_FISSA.value, code="EPIPHANY", label="Epifania", month_num=1, day_num=6, applies_to_legal_deadlines=True, applies_to_operational_deadlines=True, operating_mode=ModalitaOperativa.CHIUSO.value, priority=10, verified_at=now_iso),
        RegolaCalendario(id="nat_easter_monday", scope=AmbitoCalendario.NAZIONALE.value, kind=TipoRegolaCalendario.FESTIVITA_MOBILE.value, code="EASTER_MONDAY", label="Lunedi dell'Angelo", applies_to_legal_deadlines=True, applies_to_operational_deadlines=True, operating_mode=ModalitaOperativa.CHIUSO.value, priority=10, verified_at=now_iso),
        RegolaCalendario(id="nat_0425", scope=AmbitoCalendario.NAZIONALE.value, kind=TipoRegolaCalendario.FESTIVITA_FISSA.value, code="LIBERATION_DAY", label="Anniversario della Liberazione", month_num=4, day_num=25, applies_to_legal_deadlines=True, applies_to_operational_deadlines=True, operating_mode=ModalitaOperativa.CHIUSO.value, priority=10, verified_at=now_iso),
        RegolaCalendario(id="nat_0501", scope=AmbitoCalendario.NAZIONALE.value, kind=TipoRegolaCalendario.FESTIVITA_FISSA.value, code="LABOUR_DAY", label="Festa del Lavoro", month_num=5, day_num=1, applies_to_legal_deadlines=True, applies_to_operational_deadlines=True, operating_mode=ModalitaOperativa.CHIUSO.value, priority=10, verified_at=now_iso),
        RegolaCalendario(id="nat_0602", scope=AmbitoCalendario.NAZIONALE.value, kind=TipoRegolaCalendario.FESTIVITA_FISSA.value, code="REPUBLIC_DAY", label="Festa della Repubblica", month_num=6, day_num=2, applies_to_legal_deadlines=True, applies_to_operational_deadlines=True, operating_mode=ModalitaOperativa.CHIUSO.value, priority=10, verified_at=now_iso),
        RegolaCalendario(id="nat_0815", scope=AmbitoCalendario.NAZIONALE.value, kind=TipoRegolaCalendario.FESTIVITA_FISSA.value, code="FERRAGOSTO", label="Ferragosto", month_num=8, day_num=15, applies_to_legal_deadlines=True, applies_to_operational_deadlines=True, operating_mode=ModalitaOperativa.CHIUSO.value, priority=10, verified_at=now_iso),
        RegolaCalendario(id="nat_1101", scope=AmbitoCalendario.NAZIONALE.value, kind=TipoRegolaCalendario.FESTIVITA_FISSA.value, code="ALL_SAINTS", label="Ognissanti", month_num=11, day_num=1, applies_to_legal_deadlines=True, applies_to_operational_deadlines=True, operating_mode=ModalitaOperativa.CHIUSO.value, priority=10, verified_at=now_iso),
        RegolaCalendario(id="nat_1208", scope=AmbitoCalendario.NAZIONALE.value, kind=TipoRegolaCalendario.FESTIVITA_FISSA.value, code="IMMACULATE_CONCEPTION", label="Immacolata Concezione", month_num=12, day_num=8, applies_to_legal_deadlines=True, applies_to_operational_deadlines=True, operating_mode=ModalitaOperativa.CHIUSO.value, priority=10, verified_at=now_iso),
        RegolaCalendario(id="nat_1225", scope=AmbitoCalendario.NAZIONALE.value, kind=TipoRegolaCalendario.FESTIVITA_FISSA.value, code="CHRISTMAS", label="Natale", month_num=12, day_num=25, applies_to_legal_deadlines=True, applies_to_operational_deadlines=True, operating_mode=ModalitaOperativa.CHIUSO.value, priority=10, verified_at=now_iso),
        RegolaCalendario(id="nat_1226", scope=AmbitoCalendario.NAZIONALE.value, kind=TipoRegolaCalendario.FESTIVITA_FISSA.value, code="ST_STEPHEN", label="Santo Stefano", month_num=12, day_num=26, applies_to_legal_deadlines=True, applies_to_operational_deadlines=True, operating_mode=ModalitaOperativa.CHIUSO.value, priority=10, verified_at=now_iso),
        RegolaCalendario(id="proc_ferrial_august", scope=AmbitoCalendario.PROCEDURALE.value, kind=TipoRegolaCalendario.SOSPENSIONE_PROCEDURALE.value, code="FERRIAL_AUGUST", label="Sospensione feriale 1-31 agosto", applies_to_legal_deadlines=True, applies_to_operational_deadlines=False, operating_mode=ModalitaOperativa.CHIUSO.value, priority=5, verified_at=now_iso, notes="Sospensione del decorso dei termini ove applicabile."),
        RegolaCalendario(id="nat_1004_observance", scope=AmbitoCalendario.NAZIONALE.value, kind=TipoRegolaCalendario.OSSERVANZA.value, code="OCT_4_OBSERVANCE", label="4 ottobre - osservanza configurabile", month_num=10, day_num=4, applies_to_legal_deadlines=include_october_observance_blocking, applies_to_operational_deadlines=include_october_observance_blocking, operating_mode=ModalitaOperativa.CHIUSO.value if include_october_observance_blocking else ModalitaOperativa.APERTO.value, priority=50, verified_at=now_iso, notes="Osservanza civile non bloccante di default."),
    ]


def regola_patrono_studio(studio_id: str, patron_name: str, patron_day: int, patron_month: int, source_url: str = "", verified_at: str = "") -> RegolaCalendario | None:
    if not patron_day or not patron_month:
        return None
    return RegolaCalendario(id=f"studio_patron_{studio_id}", scope=AmbitoCalendario.STUDIO.value, entity_id=studio_id, kind=TipoRegolaCalendario.PATRONO.value, code="STUDIO_PATRON", label=f"Santo patrono studio{f' - {patron_name}' if patron_name else ''}", month_num=patron_month, day_num=patron_day, applies_to_legal_deadlines=False, applies_to_operational_deadlines=True, operating_mode=ModalitaOperativa.CHIUSO.value, priority=20, source_url=source_url, verified_at=verified_at)


def regola_patrono_ufficio(office_id: str, patron_name: str, patron_day: int, patron_month: int, operating_mode: str = ModalitaOperativa.CHIUSO.value, source_url: str = "", verified_at: str = "") -> RegolaCalendario | None:
    if not patron_day or not patron_month:
        return None
    entity_id = str(office_id or "").strip() or "__manual_office__"
    return RegolaCalendario(id=f"office_patron_{entity_id}", scope=AmbitoCalendario.UFFICIO.value, entity_id=entity_id, kind=TipoRegolaCalendario.PATRONO.value, code="OFFICE_PATRON", label=f"Santo patrono ufficio{f' - {patron_name}' if patron_name else ''}", month_num=patron_month, day_num=patron_day, applies_to_legal_deadlines=operating_mode != ModalitaOperativa.APERTO.value, applies_to_operational_deadlines=True, operating_mode=operating_mode, priority=20, source_url=source_url, verified_at=verified_at)


def calcola_scadenza_avanzata(start_at: str | datetime | date, profile: ProfiloTermine, national_rules: Optional[List[RegolaCalendario]] = None, office_rules: Optional[List[RegolaCalendario]] = None, studio_rules: Optional[List[RegolaCalendario]] = None, procedural_rules: Optional[List[RegolaCalendario]] = None, operational_lead_business_days: int = 0) -> EsitoCalcoloScadenza:
    trace: List[str] = []
    start_dt = _to_datetime(start_at)
    national_rules = list(national_rules or [])
    office_rules = list(office_rules or [])
    studio_rules = list(studio_rules or [])
    procedural_rules = list(procedural_rules or [])
    raw_due = _compute_raw_due(start_dt, profile, procedural_rules, trace)
    legal_due = _roll_forward_legal_due(raw_due, profile, national_rules + office_rules, trace)
    operational_due = _subtract_operational_business_days(legal_due, operational_lead_business_days, national_rules + studio_rules, trace)
    return EsitoCalcoloScadenza(raw_due_at=_iso_dt(raw_due), legal_due_at=_iso_dt(legal_due), operational_due_at=_iso_dt(operational_due) if operational_due else None, office_mode_on_legal_due_date=_dominant_operating_mode(legal_due, office_rules, "legal"), trace=trace)


PRESET_TERMINI: Dict[str, Dict[str, Any]] = {
    "impugnazione_sentenza_civile": {"label": "Impugnazione sentenza civile", "giorni": 30, "tipo": "liberi", "sospensione_feriale": True, "descrizione": "Art. 325 c.p.c. - 30 giorni dalla notifica della sentenza, con sospensione feriale se applicabile.", "profile_code": "TERM_30_DAYS", "source_event_type": "notifica", "operational_lead_business_days": 2},
    "appello_breve": {"label": "Appello (termine breve)", "giorni": 30, "tipo": "liberi", "sospensione_feriale": True, "descrizione": "Art. 325 c.p.c. - 30 giorni dalla notifica della sentenza.", "profile_code": "TERM_30_DAYS", "source_event_type": "notifica", "operational_lead_business_days": 2},
    "appello_lungo": {"label": "Appello (termine lungo)", "mesi": 6, "tipo": "continui", "sospensione_feriale": False, "descrizione": "Art. 327 c.p.c. - 6 mesi dal deposito della sentenza, computati a mesi di calendario comune.", "profile_code": "TERM_6_MONTHS", "source_event_type": "deposito_sentenza", "operational_lead_business_days": 5},
    "cassazione_breve": {"label": "Ricorso in Cassazione (breve)", "giorni": 60, "tipo": "liberi", "sospensione_feriale": True, "descrizione": "Art. 325 c.p.c. - 60 giorni dalla notifica.", "profile_code": "TERM_60_DAYS", "source_event_type": "notifica", "operational_lead_business_days": 3},
    "cassazione_lungo": {"label": "Ricorso in Cassazione (lungo)", "mesi": 6, "tipo": "continui", "sospensione_feriale": False, "descrizione": "Art. 327 c.p.c. - 6 mesi dal deposito, computati a mesi di calendario comune.", "profile_code": "TERM_6_MONTHS", "source_event_type": "deposito_sentenza", "operational_lead_business_days": 5},
    "opposizione_decreto_ingiuntivo": {"label": "Opposizione decreto ingiuntivo", "giorni": 40, "tipo": "liberi", "sospensione_feriale": True, "descrizione": "Art. 641 c.p.c. - 40 giorni dalla notifica.", "profile_code": "TERM_40_DAYS", "source_event_type": "notifica", "operational_lead_business_days": 2},
    "memoria_ex_171_ter_n1": {"label": "Memoria art. 171-ter n. 1", "giorni": 40, "tipo": "liberi", "sospensione_feriale": True, "descrizione": "Prima memoria del rito ordinario post-Cartabia: 40 giorni prima dell'udienza.", "profile_code": "TERM_40_DAYS", "source_event_type": "udienza", "operational_lead_business_days": 2},
    "memoria_ex_171_ter_n2": {"label": "Memoria art. 171-ter n. 2", "giorni": 20, "tipo": "liberi", "sospensione_feriale": True, "descrizione": "Seconda memoria del rito ordinario post-Cartabia: 20 giorni prima dell'udienza.", "profile_code": "TERM_20_DAYS", "source_event_type": "udienza", "operational_lead_business_days": 2},
    "memoria_ex_171_ter_n3": {"label": "Memoria art. 171-ter n. 3", "giorni": 10, "tipo": "liberi", "sospensione_feriale": True, "descrizione": "Terza memoria del rito ordinario post-Cartabia: 10 giorni prima dell'udienza.", "profile_code": "TERM_10_DAYS", "source_event_type": "udienza", "operational_lead_business_days": 1},
    "memoria_ex_183_co6_n1": {"label": "Memoria art. 183 co. 6 n. 1 (rito previgente)", "giorni": 30, "tipo": "liberi", "sospensione_feriale": True, "descrizione": "Preset legacy per fascicoli con rito previgente: 30 giorni.", "profile_code": "TERM_30_DAYS", "source_event_type": "udienza", "operational_lead_business_days": 2},
    "memoria_ex_183_co6_n2": {"label": "Memoria art. 183 co. 6 n. 2 (rito previgente)", "giorni": 30, "tipo": "liberi", "sospensione_feriale": True, "descrizione": "Preset legacy per fascicoli con rito previgente: 30 giorni.", "profile_code": "TERM_30_DAYS", "source_event_type": "udienza", "operational_lead_business_days": 2},
    "memoria_ex_183_co6_n3": {"label": "Memoria art. 183 co. 6 n. 3 (rito previgente)", "giorni": 20, "tipo": "liberi", "sospensione_feriale": True, "descrizione": "Preset legacy per fascicoli con rito previgente: 20 giorni.", "profile_code": "TERM_20_DAYS", "source_event_type": "udienza", "operational_lead_business_days": 2},
    "comparsa_conclusionale": {"label": "Comparsa conclusionale", "giorni": 60, "tipo": "liberi", "sospensione_feriale": True, "descrizione": "Art. 190 c.p.c. - 60 giorni.", "profile_code": "TERM_60_DAYS", "source_event_type": "udienza", "operational_lead_business_days": 3},
    "memoria_replica": {"label": "Memoria di replica", "giorni": 20, "tipo": "liberi", "sospensione_feriale": True, "descrizione": "Art. 190 c.p.c. - 20 giorni dopo la comparsa conclusionale.", "profile_code": "TERM_20_DAYS", "source_event_type": "deposito", "operational_lead_business_days": 1},
    "prescrizione_ordinaria": {"label": "Prescrizione ordinaria", "anni": 10, "tipo": "continui", "sospensione_feriale": False, "descrizione": "Art. 2946 c.c. - 10 anni, computati secondo il calendario comune.", "profile_code": "TERM_10_YEARS", "source_event_type": "evento", "operational_lead_business_days": 30},
    "prescrizione_breve_5anni": {"label": "Prescrizione breve (5 anni)", "anni": 5, "tipo": "continui", "sospensione_feriale": False, "descrizione": "Art. 2948 c.c. - 5 anni, computati secondo il calendario comune.", "profile_code": "TERM_1_YEAR", "source_event_type": "evento", "operational_lead_business_days": 30},
}


def profilo_da_preset(preset_key: str) -> ProfiloTermine:
    preset = PRESET_TERMINI.get(preset_key)
    if not preset:
        raise ValueError(f"Preset '{preset_key}' non trovato")
    code = preset.get("profile_code") or f"PRESET_{preset_key.upper()}"
    if code in PROFILI_TERMINE_BUILTIN:
        return PROFILI_TERMINE_BUILTIN[code]
    return _profilo_custom(code=code, label=preset.get("label", preset_key), giorni=int(preset.get("giorni", 0) or 0), mesi=int(preset.get("mesi", 0) or 0), anni=int(preset.get("anni", 0) or 0), ore=int(preset.get("ore", 0) or 0), tipo=str(preset.get("tipo", "liberi")), sospensione_feriale=bool(preset.get("sospensione_feriale", True)))


@dataclass
class Scadenza:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    id_fascicolo: str = ""
    id_appuntamento: str = ""
    tipo: TipoTermine = TipoTermine.ALTRO
    priorita: PrioritaTermine = PrioritaTermine.MEDIA
    stato: StatoTermine = StatoTermine.APERTO
    titolo: str = ""
    descrizione: str = ""
    data_decorrenza: str = ""
    data_scadenza: str = ""
    giorni_preavviso: List[int] = field(default_factory=lambda: [7, 3, 1])
    avvisi_inviati: List[int] = field(default_factory=list)
    id_utente_responsabile: str = ""
    note: str = ""
    creata_il: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    completata_il: str = ""
    perentorio: bool = False
    source_event_type: str = ""
    source_event_at: str = ""
    deadline_profile_code: str = ""
    studio_id: str = "default-studio"
    judicial_office_id: str = ""
    judicial_office_name: str = ""
    judicial_office_type: str = ""
    judicial_office_city: str = ""
    judicial_office_patron_name: str = ""
    judicial_office_patron_day: int = 0
    judicial_office_patron_month: int = 0
    judicial_office_operating_mode: str = ModalitaOperativa.APERTO.value
    judicial_office_source_url: str = ""
    judicial_office_verified_at: str = ""
    raw_due_at: str = ""
    legal_due_at: str = ""
    operational_due_at: str = ""
    office_mode_on_legal_due_date: str = ModalitaOperativa.APERTO.value
    trace_json: str = "[]"
    operational_lead_business_days: int = 0
    october_observance_blocks: bool = False

    @property
    def data_scadenza_obj(self) -> Optional[date]:
        if self.data_scadenza:
            return date.fromisoformat(self.data_scadenza[:10])
        if self.legal_due_at:
            return date.fromisoformat(self.legal_due_at[:10])
        return None

    @property
    def giorni_alla_scadenza(self) -> Optional[int]:
        ds = self.data_scadenza_obj
        return (ds - date.today()).days if ds else None

    @property
    def raw_due_at_obj(self) -> Optional[datetime]:
        try:
            return _to_datetime(self.raw_due_at) if self.raw_due_at else None
        except Exception:
            return None

    @property
    def legal_due_at_obj(self) -> Optional[datetime]:
        try:
            return _to_datetime(self.legal_due_at) if self.legal_due_at else None
        except Exception:
            return None

    @property
    def operational_due_at_obj(self) -> Optional[datetime]:
        try:
            return _to_datetime(self.operational_due_at) if self.operational_due_at else None
        except Exception:
            return None

    @property
    def è_scaduta(self) -> bool:
        giorni = self.giorni_alla_scadenza
        return giorni is not None and giorni < 0 and self.stato == StatoTermine.APERTO

    @property
    def è_imminente(self, soglia: int = 7) -> bool:
        giorni = self.giorni_alla_scadenza
        return giorni is not None and 0 <= giorni <= soglia

    @property
    def trace(self) -> List[str]:
        try:
            payload = json.loads(self.trace_json or "[]")
            return payload if isinstance(payload, list) else []
        except Exception:
            return []

    @property
    def ha_calcolo_avanzato(self) -> bool:
        return bool(self.legal_due_at or self.deadline_profile_code or self.trace)

    def _calcola_priorita(self) -> PrioritaTermine:
        giorni = self.giorni_alla_scadenza
        if giorni is None:
            return PrioritaTermine.BASSA
        if giorni <= 3 or (self.perentorio and giorni <= 7):
            return PrioritaTermine.CRITICA
        if giorni <= 7:
            return PrioritaTermine.ALTA
        if giorni <= 30:
            return PrioritaTermine.MEDIA
        return PrioritaTermine.BASSA

    def aggiorna_priorita(self) -> None:
        self.priorita = self._calcola_priorita()

    def sync_date_fields(self) -> None:
        if self.legal_due_at and not self.data_scadenza:
            self.data_scadenza = self.legal_due_at[:10]
        if self.source_event_at and not self.data_decorrenza:
            self.data_decorrenza = self.source_event_at[:10]

    def to_dict(self) -> Dict[str, Any]:
        self.sync_date_fields()
        payload = asdict(self)
        payload["tipo"] = self.tipo.value
        payload["priorita"] = self.priorita.value
        payload["stato"] = self.stato.value
        return payload

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "Scadenza":
        payload = dict(data or {})
        payload["tipo"] = TipoTermine(payload.get("tipo", TipoTermine.ALTRO.value) if payload.get("tipo") in {e.value for e in TipoTermine} else TipoTermine.ALTRO.value)
        payload["priorita"] = PrioritaTermine(payload.get("priorita", PrioritaTermine.MEDIA.value) if payload.get("priorita") in {e.value for e in PrioritaTermine} else PrioritaTermine.MEDIA.value)
        payload["stato"] = StatoTermine(payload.get("stato", StatoTermine.APERTO.value) if payload.get("stato") in {e.value for e in StatoTermine} else StatoTermine.APERTO.value)
        allowed = set(Scadenza.__dataclass_fields__.keys())
        scadenza = Scadenza(**{k: v for k, v in payload.items() if k in allowed})
        scadenza.sync_date_fields()
        return scadenza


class GestioneScadenziario:
    def __init__(self, db_path: str = "./scadenziario/scadenze.json", studio_db=None):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._studio_db = studio_db
        self._scadenze: Dict[str, Scadenza] = {}
        self._carica()

    def _carica(self) -> None:
        if self._studio_db is not None:
            try:
                rows = self._studio_db.conn.execute("SELECT * FROM scadenze").fetchall()
                self._scadenze = {}
                for row in rows:
                    payload = dict(row)
                    dati = payload.get("dati_json")
                    try:
                        data = json.loads(dati) if dati else payload
                        if not dati:
                            data["giorni_preavviso"] = json.loads(payload.get("giorni_preavviso") or "[]")
                            data["avvisi_inviati"] = json.loads(payload.get("avvisi_inviati") or "[]")
                        scadenza = Scadenza.from_dict(data)
                        self._scadenze[scadenza.id] = scadenza
                    except Exception:
                        continue
            except Exception:
                self._scadenze = {}
            return
        from pct import cache as _cache
        try:
            raw = _cache.load(self.db_path)
            self._scadenze = {k: Scadenza.from_dict(v) for k, v in raw.items()}
        except Exception:
            self._scadenze = {}

    def _salva(self) -> None:
        if self._studio_db is not None:
            def _insert(conn, scadenza: Scadenza) -> None:
                conn.execute(
                    """
                    INSERT INTO scadenze
                    (id, tipo, stato, titolo, data_scadenza, priorita, perentorio, note, id_fascicolo, id_appuntamento, id_utente, giorni_preavviso, avvisi_inviati, completata_il, creato_il, dati_json)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        scadenza.id, scadenza.tipo.value, scadenza.stato.value, scadenza.titolo, scadenza.data_scadenza, scadenza.priorita.value, 1 if scadenza.perentorio else 0, scadenza.note, scadenza.id_fascicolo or None, scadenza.id_appuntamento or None, scadenza.id_utente_responsabile, json.dumps(scadenza.giorni_preavviso, ensure_ascii=False), json.dumps(scadenza.avvisi_inviati, ensure_ascii=False), scadenza.completata_il, scadenza.creata_il, json.dumps(scadenza.to_dict(), ensure_ascii=False),
                    ),
                )
            self._studio_db.salva_tabella("scadenze", list(self._scadenze.values()), _insert)
            return
        from pct import cache as _cache
        _cache.save(self.db_path, {k: v.to_dict() for k, v in self._scadenze.items()})

    @staticmethod
    def profili_termine() -> Dict[str, Dict[str, Any]]:
        return profili_termine_builtin()

    @staticmethod
    def regole_nazionali(include_october_observance_blocking: bool = False) -> List[Dict[str, Any]]:
        return [rule.to_dict() for rule in regole_calendario_nazionali(include_october_observance_blocking)]

    @staticmethod
    def calcola_avanzata(*, start_at: str | datetime | date, profile: ProfiloTermine, studio_rule: RegolaCalendario | None = None, office_rule: RegolaCalendario | None = None, include_october_observance_blocking: bool = False, operational_lead_business_days: int = 0) -> EsitoCalcoloScadenza:
        national_rules = regole_calendario_nazionali(include_october_observance_blocking)
        procedural_rules = [rule for rule in national_rules if rule.kind == TipoRegolaCalendario.SOSPENSIONE_PROCEDURALE.value]
        return calcola_scadenza_avanzata(start_at=start_at, profile=profile, national_rules=national_rules, office_rules=[office_rule] if office_rule else [], studio_rules=[studio_rule] if studio_rule else [], procedural_rules=procedural_rules, operational_lead_business_days=operational_lead_business_days)

    def nuova(self, titolo: str, tipo: TipoTermine, data_scadenza: str, id_fascicolo: str = "", descrizione: str = "", data_decorrenza: str = "", giorni_preavviso: Optional[List[int]] = None, id_utente_responsabile: str = "", note: str = "", perentorio: bool = False, **extra: Any) -> Scadenza:
        if not titolo.strip():
            raise ValueError("Titolo obbligatorio")
        scadenza = Scadenza(tipo=tipo, titolo=titolo.strip(), descrizione=descrizione.strip(), data_decorrenza=data_decorrenza, data_scadenza=data_scadenza, id_fascicolo=id_fascicolo, giorni_preavviso=giorni_preavviso if giorni_preavviso is not None else [7, 3, 1], id_utente_responsabile=id_utente_responsabile, note=note, perentorio=perentorio)
        for key, value in extra.items():
            if key in Scadenza.__dataclass_fields__:
                setattr(scadenza, key, value)
        scadenza.sync_date_fields()
        scadenza.aggiorna_priorita()
        self._scadenze[scadenza.id] = scadenza
        self._salva()
        return scadenza

    def nuova_da_preset(self, preset_key: str, titolo: str, data_decorrenza: str, id_fascicolo: str = "", **kwargs: Any) -> Scadenza:
        preset = PRESET_TERMINI.get(preset_key)
        if not preset:
            raise ValueError(f"Preset '{preset_key}' non trovato")
        if not data_decorrenza or not data_decorrenza.strip():
            raise ValueError("Data decorrenza obbligatoria per il calcolo del termine")
        d_scadenza = calcola_termine(date.fromisoformat(data_decorrenza), giorni=preset.get("giorni", 0), tipo=preset.get("tipo", "liberi"), sospensione_feriale=preset.get("sospensione_feriale", True), mesi=preset.get("mesi", 0), anni=preset.get("anni", 0))
        return self.nuova(titolo=titolo, tipo=TipoTermine.TERMINE_PERENTORIO, data_scadenza=d_scadenza.isoformat(), id_fascicolo=id_fascicolo, descrizione=preset.get("descrizione", ""), data_decorrenza=data_decorrenza, deadline_profile_code=preset.get("profile_code", ""), source_event_type=preset.get("source_event_type", ""), source_event_at=data_decorrenza, **kwargs)

    def aggiorna(self, id_sc: str, **kwargs: Any) -> Scadenza:
        scadenza = self._get_or_raise(id_sc)
        campi_ok = set(Scadenza.__dataclass_fields__.keys()) - {"id", "creata_il"}
        for key, value in kwargs.items():
            if key not in campi_ok:
                raise ValueError(f"Campo non modificabile: {key}")
            if key == "tipo":
                value = TipoTermine(value)
            if key == "priorita":
                value = PrioritaTermine(value)
            if key == "stato":
                value = StatoTermine(value)
            setattr(scadenza, key, value)
        scadenza.sync_date_fields()
        scadenza.aggiorna_priorita()
        self._salva()
        return scadenza

    def completa(self, id_sc: str, note: str = "") -> Scadenza:
        scadenza = self._get_or_raise(id_sc)
        scadenza.stato = StatoTermine.COMPLETATO
        scadenza.completata_il = datetime.now().isoformat(timespec="seconds")
        if note:
            scadenza.note = (scadenza.note + "\n" + note).strip()
        self._salva()
        return scadenza

    def elimina(self, id_sc: str) -> None:
        if id_sc not in self._scadenze:
            raise ValueError(f"Scadenza {id_sc!r} non trovata")
        del self._scadenze[id_sc]
        self._salva()

    def get(self, id_sc: str) -> Optional[Scadenza]:
        return self._scadenze.get(id_sc)

    def tutte(self, stato: Optional[StatoTermine] = None, tipo: Optional[TipoTermine] = None, priorita: Optional[PrioritaTermine] = None, id_fascicolo: str = "", id_utente: str = "", solo_aperte: bool = True) -> List[Scadenza]:
        risultati = list(self._scadenze.values())
        if solo_aperte:
            risultati = [s for s in risultati if s.stato == StatoTermine.APERTO]
        if stato:
            risultati = [s for s in risultati if s.stato == stato]
        if tipo:
            risultati = [s for s in risultati if s.tipo == tipo]
        if priorita:
            risultati = [s for s in risultati if s.priorita == priorita]
        if id_fascicolo:
            risultati = [s for s in risultati if s.id_fascicolo == id_fascicolo]
        if id_utente:
            risultati = [s for s in risultati if s.id_utente_responsabile == id_utente]
        for s in risultati:
            s.aggiorna_priorita()
        return sorted(risultati, key=lambda s: s.data_scadenza or "9999-12-31")

    def imminenti(self, entro_giorni: int = 7) -> List[Scadenza]:
        limite = (date.today() + timedelta(days=entro_giorni)).isoformat()
        result = [s for s in self._scadenze.values() if s.stato == StatoTermine.APERTO and s.data_scadenza and s.data_scadenza <= limite]
        for s in result:
            s.aggiorna_priorita()
        return sorted(result, key=lambda s: s.data_scadenza)

    def scadute(self) -> List[Scadenza]:
        oggi = date.today().isoformat()
        result = [s for s in self._scadenze.values() if s.stato == StatoTermine.APERTO and s.data_scadenza < oggi]
        for s in result:
            s.stato = StatoTermine.SCADUTO
        if result:
            self._salva()
        return sorted(result, key=lambda s: s.data_scadenza)

    def per_mese(self, anno: int, mese: int) -> List[Scadenza]:
        prefisso = f"{anno:04d}-{mese:02d}"
        return [s for s in self._scadenze.values() if s.data_scadenza.startswith(prefisso)]

    def scadenze_da_notificare(self) -> List[Tuple[Scadenza, int]]:
        oggi = date.today()
        result: List[Tuple[Scadenza, int]] = []
        for s in self._scadenze.values():
            if s.stato != StatoTermine.APERTO or not s.data_scadenza:
                continue
            giorni = (date.fromisoformat(s.data_scadenza) - oggi).days
            for soglia in s.giorni_preavviso:
                if giorni == soglia and soglia not in s.avvisi_inviati:
                    result.append((s, giorni))
                    break
        return result

    def segna_avviso_inviato(self, id_sc: str, giorni: int) -> None:
        scadenza = self._get_or_raise(id_sc)
        if giorni not in scadenza.avvisi_inviati:
            scadenza.avvisi_inviati.append(giorni)
        self._salva()

    def invia_avvisi(self, gm=None, avvocati_email: Optional[Dict[str, str]] = None) -> List[Dict[str, Any]]:
        inviati: List[Dict[str, Any]] = []
        for scadenza, giorni in self.scadenze_da_notificare():
            avviso = {"id_scadenza": scadenza.id, "titolo": scadenza.titolo, "data_scadenza": scadenza.data_scadenza, "giorni": giorni, "priorita": scadenza.priorita.value}
            if gm and avvocati_email:
                email = avvocati_email.get(scadenza.id_utente_responsabile, "")
                if email:
                    try:
                        from .messaggi import CanaleMsggio, TipoAutomazione
                        gm.invia_da_template(tipo=TipoAutomazione.AVVISO_SCADENZA, canali=[CanaleMsggio.EMAIL], destinatario_email=email, variabili={"nome": scadenza.id_utente_responsabile, "scadenza": scadenza.data_scadenza, "tipo_atto": scadenza.titolo, "numero_fascicolo": scadenza.id_fascicolo or "-", "giorni": str(giorni), "priorita": scadenza.priorita.value}, id_fascicolo=scadenza.id_fascicolo)
                        avviso["email_inviata"] = email
                    except Exception as exc:
                        avviso["errore_email"] = str(exc)
            self.segna_avviso_inviato(scadenza.id, giorni)
            inviati.append(avviso)
        return inviati

    def calendario_mese(self, anno: int, mese: int) -> Dict[str, List[Scadenza]]:
        calendario_mese: Dict[str, List[Scadenza]] = {}
        for scadenza in self.per_mese(anno, mese):
            calendario_mese.setdefault(scadenza.data_scadenza, []).append(scadenza)
        return calendario_mese

    def statistiche(self) -> Dict[str, Any]:
        tutte = list(self._scadenze.values())
        aperte = [s for s in tutte if s.stato == StatoTermine.APERTO]
        return {"totale": len(tutte), "aperte": len(aperte), "completate": sum(1 for s in tutte if s.stato == StatoTermine.COMPLETATO), "scadute": sum(1 for s in tutte if s.stato == StatoTermine.SCADUTO), "critiche": sum(1 for s in aperte if s.priorita == PrioritaTermine.CRITICA), "alte": sum(1 for s in aperte if s.priorita == PrioritaTermine.ALTA), "imminenti_7gg": len(self.imminenti(7)), "avanzate": sum(1 for s in tutte if s.ha_calcolo_avanzato), "con_anticipo_operativo": sum(1 for s in tutte if bool(s.operational_due_at)), "per_tipo": {t.value: sum(1 for s in aperte if s.tipo == t) for t in TipoTermine}, "per_priorita": {p.value: sum(1 for s in aperte if s.priorita == p) for p in PrioritaTermine}}

    def _get_or_raise(self, id_sc: str) -> Scadenza:
        scadenza = self._scadenze.get(id_sc)
        if not scadenza:
            raise ValueError(f"Scadenza {id_sc!r} non trovata")
        return scadenza
