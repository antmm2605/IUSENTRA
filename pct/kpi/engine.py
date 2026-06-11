"""Motore KPI direzionali dello studio (cabina di controllo gestione).

Calcola gli indicatori operativi da collezioni di dominio già caricate (fascicoli,
scadenze, udienze, parcelle, timesheet). È puro e deterministico: il wiring ai
repository reali tenant-aware è un passo successivo. Tutte le soglie temporali
usano il fuso `Europe/Rome` (regola obbligatoria del progetto): mai confrontare
datetime naive con aware.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any, Iterable
from zoneinfo import ZoneInfo

ROME_TZ = ZoneInfo("Europe/Rome")

_DATE_FORMATS = ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y %H:%M", "%d/%m/%Y", "%d-%m-%Y")


def _rome_now(now: datetime | None) -> datetime:
    if now is None:
        return datetime.now(ROME_TZ)
    return now.replace(tzinfo=ROME_TZ) if now.tzinfo is None else now.astimezone(ROME_TZ)


def _parse_dt(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value.replace(tzinfo=ROME_TZ) if value.tzinfo is None else value.astimezone(ROME_TZ)
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, tzinfo=ROME_TZ)
    text = str(value or "").strip()
    if not text:
        return None
    iso = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(iso)
        return parsed.replace(tzinfo=ROME_TZ) if parsed.tzinfo is None else parsed.astimezone(ROME_TZ)
    except ValueError:
        pass
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=ROME_TZ)
        except ValueError:
            continue
    return None


def _to_float(value: Any) -> float:
    text = str(value if value is not None else "").strip().replace("€", "").replace(" ", "")
    if not text:
        return 0.0
    import re

    if re.search(r",\d{1,2}$", text):
        text = text.replace(".", "").replace(",", ".")
    else:
        text = text.replace(",", "")
    try:
        return float(text)
    except ValueError:
        return 0.0


def _is_closed(stato: Any) -> bool:
    return str(stato or "").strip().lower() in {"chiuso", "chiusa", "archiviato", "archiviata", "definito", "concluso"}


def compute_kpis(
    *,
    fascicoli: Iterable[dict[str, Any]] | None = None,
    scadenze: Iterable[dict[str, Any]] | None = None,
    udienze: Iterable[dict[str, Any]] | None = None,
    parcelle: Iterable[dict[str, Any]] | None = None,
    timesheet: Iterable[dict[str, Any]] | None = None,
    now: datetime | None = None,
    critical_days: int = 7,
) -> dict[str, Any]:
    """Calcola il cruscotto KPI. Vedi docstring del modulo per i contratti dati."""

    ref = _rome_now(now)
    today = ref.date()
    fascicoli = list(fascicoli or [])
    scadenze = list(scadenze or [])
    udienze = list(udienze or [])
    parcelle = list(parcelle or [])
    timesheet = list(timesheet or [])

    aperte = [f for f in fascicoli if not _is_closed(f.get("stato"))]
    chiuse = [f for f in fascicoli if _is_closed(f.get("stato"))]
    valore_pratiche = round(sum(_to_float(f.get("valore")) for f in fascicoli), 2)

    # Scadenze critiche: non completate, entro `critical_days` (incluse scadute).
    scadute = 0
    critiche = 0
    for s in scadenze:
        if str(s.get("completata")).lower() in {"true", "1", "yes"} or s.get("completata") is True:
            continue
        dt = _parse_dt(s.get("data") or s.get("data_scadenza"))
        if dt is None:
            continue
        delta_days = (dt.date() - today).days
        if delta_days < 0:
            scadute += 1
        if delta_days <= critical_days:
            critiche += 1

    def _udienze_entro(giorni: int) -> int:
        limite = ref + timedelta(days=giorni)
        count = 0
        for u in udienze:
            dt = _parse_dt(u.get("data_ora") or u.get("data"))
            if dt is not None and ref <= dt <= limite:
                count += 1
        return count

    # Economia / parcelle.
    parcelle_emesse = len(parcelle)
    incassato = 0.0
    insoluto = 0.0
    insoluto_scaduto = 0.0
    for p in parcelle:
        importo = _to_float(p.get("importo") or p.get("totale"))
        stato = str(p.get("stato") or "").strip().lower()
        if stato in {"pagata", "incassata", "saldata"}:
            incassato += importo
        elif stato in {"insoluta", "emessa", "scaduta", "da_incassare", "non_pagata"}:
            insoluto += importo
            scad_pag = _parse_dt(p.get("scadenza_pagamento") or p.get("scadenza"))
            if scad_pag is not None and scad_pag.date() < today:
                insoluto_scaduto += importo

    # Timesheet: tempo lavorato, non fatturato (WIP), produttività.
    minuti_per_fascicolo: dict[str, int] = defaultdict(int)
    minuti_per_utente: dict[str, int] = defaultdict(int)
    minuti_non_fatturati = 0
    wip_valore = 0.0
    for t in timesheet:
        minuti = int(_to_float(t.get("minuti") or t.get("durata_minuti")))
        fascicolo_id = str(t.get("fascicolo_id") or t.get("pratica_id") or "")
        utente_id = str(t.get("utente_id") or t.get("professionista_id") or "")
        if fascicolo_id:
            minuti_per_fascicolo[fascicolo_id] += minuti
        if utente_id:
            minuti_per_utente[utente_id] += minuti
        fatturabile = t.get("fatturabile", True)
        fatturato = str(t.get("fatturato")).lower() in {"true", "1", "yes"} or t.get("fatturato") is True
        if fatturabile and not fatturato:
            minuti_non_fatturati += minuti
            wip_valore += (minuti / 60.0) * _to_float(t.get("tariffa_oraria"))

    # Marginalità per cliente (ricavi da parcelle pagate per cliente).
    ricavi_cliente: dict[str, float] = defaultdict(float)
    for p in parcelle:
        if str(p.get("stato") or "").lower() in {"pagata", "incassata", "saldata"}:
            ricavi_cliente[str(p.get("cliente_id") or "")] += _to_float(p.get("importo") or p.get("totale"))

    # Rischio operativo per fascicolo: scadenze scadute + udienza imminente.
    rischio_fascicolo = _rischio_per_fascicolo(aperte, scadenze, udienze, ref, today)

    return {
        "generatedAt": ref.isoformat(),
        "pratiche": {
            "aperte": len(aperte),
            "chiuse": len(chiuse),
            "totale": len(fascicoli),
            "valoreTotale": valore_pratiche,
        },
        "scadenze": {"critiche": critiche, "scadute": scadute, "totaliAperte": sum(1 for s in scadenze if s.get("completata") is not True)},
        "udienze": {"prossimi30": _udienze_entro(30), "prossimi60": _udienze_entro(60), "prossimi90": _udienze_entro(90)},
        "economia": {
            "parcelleEmesse": parcelle_emesse,
            "incassato": round(incassato, 2),
            "insoluto": round(insoluto, 2),
            "insolutoScaduto": round(insoluto_scaduto, 2),
            "wip": round(wip_valore, 2),
        },
        "tempo": {
            "minutiTotali": sum(minuti_per_fascicolo.values()),
            "minutiNonFatturati": minuti_non_fatturati,
            "perFascicolo": dict(minuti_per_fascicolo),
            "perProfessionista": dict(minuti_per_utente),
        },
        "marginalitaPerCliente": {k: round(v, 2) for k, v in ricavi_cliente.items() if k},
        "rischioOperativo": rischio_fascicolo,
    }


def _rischio_per_fascicolo(
    aperte: list[dict[str, Any]],
    scadenze: list[dict[str, Any]],
    udienze: list[dict[str, Any]],
    ref: datetime,
    today: date,
) -> list[dict[str, Any]]:
    scadute_by_fasc: dict[str, int] = defaultdict(int)
    for s in scadenze:
        if s.get("completata") is True:
            continue
        dt = _parse_dt(s.get("data") or s.get("data_scadenza"))
        if dt is not None and dt.date() < today:
            scadute_by_fasc[str(s.get("fascicolo_id") or "")] += 1
    udienza_imminente: dict[str, bool] = {}
    limite = ref + timedelta(days=7)
    for u in udienze:
        dt = _parse_dt(u.get("data_ora") or u.get("data"))
        if dt is not None and ref <= dt <= limite:
            udienza_imminente[str(u.get("fascicolo_id") or "")] = True

    out: list[dict[str, Any]] = []
    for f in aperte:
        fid = str(f.get("id") or "")
        score = scadute_by_fasc.get(fid, 0) * 2 + (3 if udienza_imminente.get(fid) else 0)
        if score <= 0:
            continue
        livello = "alto" if score >= 5 else "medio" if score >= 2 else "basso"
        out.append({"fascicoloId": fid, "score": score, "livello": livello, "scadenzeScadute": scadute_by_fasc.get(fid, 0), "udienzaImminente": udienza_imminente.get(fid, False)})
    return sorted(out, key=lambda x: x["score"], reverse=True)


__all__ = ["compute_kpis", "ROME_TZ"]
