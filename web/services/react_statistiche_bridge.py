"""Bridge read-only per la pagina React delle statistiche."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from typing import Any, Callable


MONTH_LABELS = ["Gen", "Feb", "Mar", "Apr", "Mag", "Giu", "Lug", "Ago", "Set", "Ott", "Nov", "Dic"]


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _enum_value(value: Any) -> str:
    return str(getattr(value, "value", value) or "").strip()


def _to_number(value: Any) -> float:
    try:
        return round(float(value or 0), 2)
    except (TypeError, ValueError):
        return 0.0


def _parse_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    raw = str(value or "").strip()
    if not raw:
        return None
    for sample in (raw[:10], raw.replace("Z", "+00:00")):
        try:
            return datetime.fromisoformat(sample).date()
        except ValueError:
            continue
    return None


def _safe(label: str, warnings: list[dict[str, str]], loader: Callable[[], Any], fallback: Any) -> Any:
    try:
        return loader()
    except Exception as exc:
        warnings.append({
            "code": f"{label}_non_disponibile",
            "message": f"Sorgente {label} non disponibile: {type(exc).__name__}.",
        })
        return fallback


def _stats_dict(manager: Any) -> dict[str, Any]:
    func = getattr(manager, "statistiche", None)
    if not callable(func):
        return {}
    value = func()
    return value if isinstance(value, dict) else {}


def _all(manager: Any, *, include_archived: bool = False, open_only: bool | None = None) -> list[Any]:
    if manager is None:
        return []
    if include_archived:
        try:
            return list(manager.tutti(archiviati=True))
        except TypeError:
            pass
    if open_only is not None:
        try:
            return list(manager.tutte(solo_aperte=open_only))
        except TypeError:
            pass
    for name in ("tutti", "tutte"):
        func = getattr(manager, name, None)
        if callable(func):
            try:
                return list(func())
            except TypeError:
                return list(func(False))
    return []


def _monthly_billing(parcelle: list[Any]) -> list[dict[str, Any]]:
    year = date.today().year
    fatturato: defaultdict[int, float] = defaultdict(float)
    incassato: defaultdict[int, float] = defaultdict(float)
    for parcella in parcelle:
        issued = str(getattr(parcella, "data_emissione", "") or "")
        if not issued.startswith(str(year)):
            continue
        try:
            month = int(issued[5:7])
        except (ValueError, IndexError):
            continue
        stato = _enum_value(getattr(parcella, "stato", "")).upper()
        total = _to_number(getattr(parcella, "totale", 0))
        if stato != "ANNULLATA":
            fatturato[month] += total
        if stato == "PAGATA":
            incassato[month] += total
    return [
        {
            "id": f"fatturato-{index + 1}",
            "label": label,
            "value": round(fatturato.get(index + 1, 0), 2),
            "secondaryValue": round(incassato.get(index + 1, 0), 2),
            "note": "Fatturato / incassato",
            "tone": "primary" if fatturato.get(index + 1, 0) else "neutral",
        }
        for index, label in enumerate(MONTH_LABELS)
    ]


def _counter_section(section_id: str, title: str, counter: Counter[str], empty_note: str) -> dict[str, Any]:
    items = [
        {
            "id": f"{section_id}-{index}",
            "label": label,
            "value": count,
            "note": "",
            "tone": "primary" if count else "neutral",
        }
        for index, (label, count) in enumerate(counter.most_common())
    ]
    return {
        "id": section_id,
        "title": title,
        "kind": "distribution",
        "items": items,
        "emptyMessage": empty_note,
    }


def _depositi_records(fascicoli: list[Any]) -> list[dict[str, Any]]:
    year = date.today().year
    records: defaultdict[int, dict[str, int]] = defaultdict(lambda: {"depositi": 0, "accettati": 0, "rifiutati": 0})
    for fascicolo in fascicoli:
        for attivita in getattr(fascicolo, "attivita", []) or []:
            data_attivita = attivita.get("data", "") if isinstance(attivita, dict) else getattr(attivita, "data", "")
            parsed = _parse_date(data_attivita)
            if not parsed or parsed.year != year:
                continue
            tipo = str(attivita.get("tipo", "") if isinstance(attivita, dict) else getattr(attivita, "tipo", "")).lower()
            if "deposito" in tipo or "deposita" in tipo:
                records[parsed.month]["depositi"] += 1
            if "accettat" in tipo:
                records[parsed.month]["accettati"] += 1
            if "rifiutat" in tipo:
                records[parsed.month]["rifiutati"] += 1
    return [
        {
            "id": f"depositi-{index + 1}",
            "label": label,
            "value": records[index + 1]["depositi"],
            "secondaryValue": records[index + 1]["accettati"],
            "note": f"Rifiutati: {records[index + 1]['rifiutati']}",
            "tone": "success" if records[index + 1]["accettati"] else "neutral",
        }
        for index, label in enumerate(MONTH_LABELS)
    ]


def _productivity(fascicoli: list[Any], scadenze: list[Any]) -> dict[str, Any]:
    today = date.today()
    chiusi = 0
    durate: list[int] = []
    for fascicolo in fascicoli:
        stato = _enum_value(getattr(fascicolo, "stato", "")).upper()
        if stato not in {"CHIUSO", "DEFINITO", "ARCHIVIATO"}:
            continue
        chiusi += 1
        opened = _parse_date(getattr(fascicolo, "data_apertura", "") or getattr(fascicolo, "creato_il", ""))
        closed = _parse_date(getattr(fascicolo, "data_chiusura", "") or getattr(fascicolo, "aggiornato_il", ""))
        if opened and closed:
            durate.append(max((closed - opened).days, 0))

    completed = 0
    respected = 0
    expired = 0
    for scadenza in scadenze:
        stato = _enum_value(getattr(scadenza, "stato", "")).upper()
        due = _parse_date(getattr(scadenza, "data_scadenza", ""))
        if stato == "COMPLETATO":
            completed += 1
            completed_at = _parse_date(getattr(scadenza, "completata_il", "") or getattr(scadenza, "data_completamento", ""))
            if not completed_at or not due or completed_at <= due:
                respected += 1
        elif due and due < today:
            expired += 1

    total_matters = len(fascicoli)
    return {
        "durata_media_gg": round(sum(durate) / len(durate)) if durate else 0,
        "tasso_chiusura_pct": round(chiusi / total_matters * 100) if total_matters else 0,
        "fascicoli_chiusi": chiusi,
        "fascicoli_totali": total_matters,
        "tasso_scadenze_rispettate_pct": round(respected / completed * 100) if completed else 0,
        "scadenze_completate": completed,
        "scadenze_totali": len(scadenze),
        "scadenze_scadute": expired,
    }


def build_react_statistiche_payload(
    *,
    get_agenda: Callable[[], Any],
    get_clienti: Callable[[], Any],
    get_fascicoli: Callable[[], Any],
    get_fatturazione: Callable[[], Any],
    get_scadenziario: Callable[[], Any],
) -> dict[str, Any]:
    warnings: list[dict[str, str]] = []
    today = date.today()

    agenda = _safe("agenda", warnings, get_agenda, None)
    clienti = _safe("clienti", warnings, get_clienti, None)
    fascicoli_manager = _safe("fascicoli", warnings, get_fascicoli, None)
    fatturazione = _safe("fatturazione", warnings, get_fatturazione, None)
    scadenziario = _safe("scadenziario", warnings, get_scadenziario, None)

    clienti_stats = _safe("clienti_statistiche", warnings, lambda: _stats_dict(clienti), {})
    fascicoli_stats = _safe("fascicoli_statistiche", warnings, lambda: _stats_dict(fascicoli_manager), {})
    scadenze_stats = _safe("scadenziario_statistiche", warnings, lambda: _stats_dict(scadenziario), {})
    fatturazione_stats = _safe("fatturazione_statistiche", warnings, lambda: _stats_dict(fatturazione), {})

    appuntamenti_oggi = _safe("agenda_oggi", warnings, lambda: len(agenda.per_giorno(today)) if agenda else 0, 0)
    scadenze = _safe("scadenze_lista", warnings, lambda: _all(scadenziario, open_only=False), [])
    fascicoli = _safe("fascicoli_lista", warnings, lambda: _all(fascicoli_manager, include_archived=True), [])
    parcelle = _safe("fatturazione_lista", warnings, lambda: _all(fatturazione), [])
    clienti_lista = _safe("clienti_lista", warnings, lambda: _all(clienti), [])
    agenda_lista = _safe("agenda_lista", warnings, lambda: _all(agenda), [])

    scadenze_oggi = sum(1 for item in scadenze if _parse_date(getattr(item, "data_scadenza", "")) == today)
    productivity = _productivity(fascicoli, scadenze)

    metrics = [
        {
            "id": "clienti",
            "label": "Clienti",
            "value": clienti_stats.get("totale", clienti_stats.get("totale_clienti", len(clienti_lista))),
            "note": "Anagrafiche reali in archivio",
            "tone": "primary",
        },
        {
            "id": "fascicoli",
            "label": "Fascicoli attivi",
            "value": fascicoli_stats.get("attivi", fascicoli_stats.get("aperti", len([f for f in fascicoli if _enum_value(getattr(f, "stato", "")).upper() not in {"CHIUSO", "DEFINITO", "ARCHIVIATO"}]))),
            "note": f"Totale fascicoli: {fascicoli_stats.get('totale', len(fascicoli))}",
            "tone": "success",
        },
        {
            "id": "scadenze",
            "label": "Scadenze aperte",
            "value": scadenze_stats.get("aperte", scadenze_stats.get("totale", len(scadenze))),
            "note": f"Oggi: {scadenze_oggi}",
            "tone": "warning" if scadenze_oggi else "neutral",
        },
        {
            "id": "agenda",
            "label": "Appuntamenti oggi",
            "value": appuntamenti_oggi,
            "note": today.strftime("%d/%m/%Y"),
            "tone": "info",
        },
        {
            "id": "incassi",
            "label": "Da incassare",
            "value": fatturazione_stats.get("da_incassare", 0),
            "note": "Valore da fatturazione reale",
            "tone": "primary",
        },
        {
            "id": "produttivita",
            "label": "Scadenze rispettate",
            "value": f"{productivity['tasso_scadenze_rispettate_pct']}%",
            "note": f"Completate: {productivity['scadenze_completate']}",
            "tone": "success",
        },
    ]

    tipo_counter = Counter(_enum_value(getattr(item, "tipo", "")) or "Non indicato" for item in fascicoli)
    stato_counter = Counter(_enum_value(getattr(item, "stato", "")) or "Non indicato" for item in fascicoli)
    priorita_counter = Counter(_enum_value(getattr(item, "priorita", "")) or "Non indicata" for item in scadenze)
    agenda_counter = Counter(_enum_value(getattr(item, "tipo", "")) or "Non indicato" for item in agenda_lista)

    sections = [
        _counter_section("fascicoli_tipo", "Fascicoli per tipo", tipo_counter, "Nessun fascicolo presente."),
        _counter_section("fascicoli_stato", "Fascicoli per stato", stato_counter, "Nessuno stato fascicolo disponibile."),
        _counter_section("scadenze_priorita", "Scadenze per priorita", priorita_counter, "Nessuna scadenza disponibile."),
        _counter_section("agenda_tipo", "Appuntamenti per tipo", agenda_counter, "Nessun appuntamento disponibile."),
        {
            "id": "fatturato_mensile",
            "title": "Fatturato mensile",
            "kind": "monthly",
            "items": _monthly_billing(parcelle),
            "emptyMessage": "Nessuna parcella emessa nell'anno corrente.",
        },
        {
            "id": "depositi_trend",
            "title": "Trend depositi",
            "kind": "monthly",
            "items": _depositi_records(fascicoli),
            "emptyMessage": "Nessuna attivita di deposito nell'anno corrente.",
        },
    ]

    records = [
        {"id": "clienti", "label": "Clienti registrati", "value": len(clienti_lista), "note": "Anagrafica clienti", "href": "/clienti"},
        {"id": "fascicoli", "label": "Fascicoli totali", "value": len(fascicoli), "note": "Archivio fascicoli", "href": "/fascicoli"},
        {"id": "parcelle", "label": "Parcelle", "value": len(parcelle), "note": "Fatturazione legacy", "href": "/fatturazione"},
        {"id": "scadenze", "label": "Scadenze", "value": len(scadenze), "note": "Scadenziario", "href": "/scadenziario"},
        {"id": "durata_media", "label": "Durata media fascicoli", "value": productivity["durata_media_gg"], "note": "Giorni", "href": "/fascicoli"},
        {"id": "tasso_chiusura", "label": "Tasso chiusura fascicoli", "value": f"{productivity['tasso_chiusura_pct']}%", "note": f"Chiusi: {productivity['fascicoli_chiusi']}", "href": "/fascicoli"},
    ]

    actions = [
        {"id": "refresh", "label": "Aggiorna dati", "href": "/statistiche", "method": "GET", "tone": "primary"},
        {"id": "clienti_csv", "label": "Esporta clienti", "href": "/export/clienti.csv", "method": "GET", "tone": "neutral"},
        {"id": "fascicoli_csv", "label": "Esporta fascicoli", "href": "/export/fascicoli.csv", "method": "GET", "tone": "neutral"},
        {"id": "agenda_ics", "label": "Esporta agenda", "href": "/agenda/export.ics", "method": "GET", "tone": "neutral"},
        {"id": "scadenziario_ics", "label": "Esporta scadenziario", "href": "/scadenziario/export.ics", "method": "GET", "tone": "neutral"},
    ]

    return {
        "source": "repository_reali",
        "generated_at": _iso_now(),
        "contracts": {
            "mock_fallback": False,
            "writes": "none",
            "route_owner": "react_shell",
            "legacy_contract": "artifacts/react-migration/legacy-contracts/statistiche.json",
        },
        "metrics": metrics,
        "sections": sections,
        "records": records,
        "actions": actions,
        "warnings": warnings,
    }


def build_react_statistiche_error_payload(message: str = "Statistiche non disponibili.") -> dict[str, Any]:
    return {
        "source": "errore_controllato",
        "generated_at": _iso_now(),
        "contracts": {
            "mock_fallback": False,
            "writes": "none",
            "route_owner": "react_shell",
            "legacy_contract": "artifacts/react-migration/legacy-contracts/statistiche.json",
        },
        "metrics": [],
        "sections": [],
        "records": [],
        "actions": [{"id": "retry", "label": "Riprova statistiche", "href": "/statistiche", "method": "GET", "tone": "primary"}],
        "warnings": [{"code": "statistiche_errore_controllato", "message": message}],
    }
