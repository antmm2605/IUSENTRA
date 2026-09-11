"""Audit e bonifica dei presidi automatici duplicati PEC/documenti.

Dry-run predefinito: legge Agenda e Scadenziario senza modificare dati.
Con ``--apply`` annulla solo duplicati automatici non ambigui, conservando note e
marker sulla voce canonica. Non cancella fisicamente record.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pct.agenda import StatoAppuntamento  # noqa: E402
from pct.pec_pipeline import PecAuditRepository, _operational_presidio_family  # noqa: E402
from pct.scadenziario import StatoTermine  # noqa: E402
from pct.tenant import GestioneTenant  # noqa: E402


TERMINAL_DEADLINE_STATUSES = {"ANNULLATO", "COMPLETATO"}
TERMINAL_AGENDA_STATUSES = {"ANNULLATO", "COMPLETATO", "RINVIATO"}
REPAIRABLE_SOURCES = {"pec", "document"}


@dataclass(frozen=True)
class PresidioRecord:
    tenant: str
    surface: str
    record_id: str
    linked_id: str
    title: str
    date: str
    time: str
    status: str
    case_key: str
    family: str
    source: str
    note: str
    created: str
    active: bool
    rg_values: tuple[str, ...]

    @property
    def group_key(self) -> tuple[str, str, str, str, str]:
        return (self.tenant, self.case_key, self.date, self.time, self.family)


def _registry_path(value: str = "") -> Path:
    raw = (
        value
        or os.environ.get("TENANTS_REGISTRY")
        or os.environ.get("IUSENTRA_TENANTS_REGISTRY")
        or os.environ.get("PCT_TENANTS_REGISTRY")
        or "data/tenants.json"
    )
    return Path(raw)


def _matches(slug: str, wanted: str) -> bool:
    return not wanted or slug == wanted or slug.lower() == wanted.lower()


def _load_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def _json_rows(path: Path) -> list[dict[str, Any]]:
    raw = _load_json(path, {})
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]
    if isinstance(raw, dict):
        for key in ("items", "records", "data", "scadenze", "appuntamenti"):
            value = raw.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        return [item for item in raw.values() if isinstance(item, dict)]
    return []


def _sqlite_rows(studio_db: Path, table: str) -> list[dict[str, Any]]:
    if not studio_db.exists():
        return []
    try:
        conn = sqlite3.connect(studio_db)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(f"SELECT * FROM {table}").fetchall()
        finally:
            conn.close()
    except sqlite3.Error:
        return []
    values: list[dict[str, Any]] = []
    for row in rows:
        payload = dict(row)
        dati = payload.get("dati_json")
        if dati:
            try:
                parsed = json.loads(dati)
                if isinstance(parsed, dict):
                    values.append(parsed)
                    continue
            except Exception:
                pass
        values.append(payload)
    return values


def _rows(paths: dict[str, Any], *, table: str, json_key: str) -> tuple[str, list[dict[str, Any]]]:
    studio_db = Path(str(paths.get("STUDIO_DB") or ""))
    rows = _sqlite_rows(studio_db, table)
    if rows:
        return ("sqlite", rows)
    return ("json", _json_rows(Path(str(paths[json_key]))))


def _pec_audit_db_for_paths(paths: dict[str, Any]) -> Path:
    configured = _text(paths.get("PEC_AUDIT_DB"))
    if configured:
        return Path(configured)
    email_config = _text(paths.get("EMAIL_CASELLA_DB"))
    if email_config:
        return Path(email_config).parent / "pec_audit.sqlite"
    return Path(_text(paths["SCADENZIARIO_DB"])).parent.parent / "email" / "pec_audit.sqlite"


def _repository_for_paths(tenant: str, paths: dict[str, Any]) -> PecAuditRepository:
    return PecAuditRepository(
        _pec_audit_db_for_paths(paths),
        tenant_id=tenant,
        fascicoli_db_path=paths.get("FASCICOLI_DB"),
        scadenziario_db_path=paths["SCADENZIARIO_DB"],
        agenda_db_path=paths["AGENDA_DB"],
    )


def _text(value: Any, limit: int = 0) -> str:
    text = " ".join(str(value or "").replace("\x00", " ").split())
    return text[:limit] if limit else text


def _enum_value(value: Any) -> str:
    if isinstance(value, dict):
        value = value.get("value")
    return _text(getattr(value, "value", value), 80).upper()


def _date_key(value: Any) -> str:
    return _text(value, 40)[:10]


def _time_key(*values: Any) -> str:
    for value in values:
        match = re.search(r"(?:T|\b)([01]?\d|2[0-3])[:.]([0-5]\d)\b", str(value or ""))
        if match:
            return f"{int(match.group(1)):02d}:{match.group(2)}"
    return ""


def _normal_rg(value: str) -> str:
    match = re.search(r"\b(\d{1,7})\s*/\s*(\d{2,4})(?:/[A-Z]{2,5})?\b", str(value or ""), flags=re.I)
    if not match:
        return ""
    year = match.group(2)
    if len(year) == 2:
        year = f"20{year}"
    return f"{int(match.group(1))}/{year}"


def _extract_rgs(*texts: Any) -> tuple[str, ...]:
    values: set[str] = set()
    for text in texts:
        for match in re.finditer(r"\b(\d{1,7})\s*/\s*(\d{2,4})(?:/[A-Z]{2,5})?\b", str(text or ""), flags=re.I):
            year = match.group(2)
            if len(year) == 2:
                year = f"20{year}"
            values.add(f"{int(match.group(1))}/{year}")
    return tuple(sorted(values))


def _case_key(*values: Any) -> str:
    for value in values:
        clean = _text(value, 120)
        if clean:
            return clean
    for value in values:
        rg = _normal_rg(str(value or ""))
        if rg:
            return rg
    return ""


def _source_kind(*, note: str, source_event_type: str = "", external_uid: str = "") -> str:
    haystack = "\n".join((_text(note), _text(source_event_type), _text(external_uid)))
    if "PEC_RICEZIONE:" in haystack:
        return "pec_received"
    if "IUSENTRA_LEGAL_NOTIFICATION:" in haystack:
        return "notification"
    if "docpresidio:" in haystack or source_event_type == "fascicolo_documenti_audit":
        return "document"
    if "PEC_AUDIT:" in haystack:
        return "pec"
    return "manual"


def _deadline_records(tenant: str, rows: list[dict[str, Any]]) -> list[PresidioRecord]:
    records: list[PresidioRecord] = []
    for row in rows:
        note = _text(row.get("note") or row.get("descrizione") or "", 5000)
        title = _text(row.get("titolo") or "", 240)
        source_event_type = _text(row.get("source_event_type") or "", 120)
        source = _source_kind(note=note, source_event_type=source_event_type)
        family = _operational_presidio_family(title, row.get("descrizione"), note, source_event_type)
        case_key = _case_key(row.get("id_fascicolo"), title, note)
        status = _enum_value(row.get("stato") or "APERTO")
        date_key = _date_key(row.get("operational_due_at") or row.get("data_scadenza"))
        if not date_key or not case_key or family == "generico":
            continue
        kind = "udienza" if _enum_value(row.get("tipo")) == "UDIENZA" or "udienza" in title.lower() else "termine"
        records.append(
            PresidioRecord(
                tenant=tenant,
                surface="scadenziario",
                record_id=_text(row.get("id"), 120),
                linked_id=_text(row.get("id_appuntamento"), 120),
                title=title,
                date=date_key,
                time=_time_key(row.get("remote_hearing_time"), row.get("hearing_time"), row.get("operational_due_at")) if kind == "udienza" else "",
                status=status,
                case_key=case_key,
                family=family,
                source=source,
                note=note,
                created=_text(row.get("creata_il") or row.get("creato_il") or "", 60),
                active=status not in TERMINAL_DEADLINE_STATUSES,
                rg_values=_extract_rgs(title, row.get("descrizione"), note),
            )
        )
    return records


def _agenda_records(tenant: str, rows: list[dict[str, Any]]) -> list[PresidioRecord]:
    records: list[PresidioRecord] = []
    for row in rows:
        note = _text(row.get("note") or "", 5000)
        title = _text(row.get("titolo") or "", 240)
        external_uid = _text(row.get("external_uid") or "", 240)
        source = _source_kind(note=note, external_uid=external_uid)
        family = _operational_presidio_family(title, note)
        case_key = _case_key(row.get("id_fascicolo"), row.get("procedimento"), note, title)
        status = _enum_value(row.get("stato") or "PROGRAMMATO")
        date_key = _date_key(row.get("data_ora"))
        if not date_key or not case_key or family == "generico":
            continue
        records.append(
            PresidioRecord(
                tenant=tenant,
                surface="agenda",
                record_id=_text(row.get("id"), 120),
                linked_id="",
                title=title,
                date=date_key,
                time=_time_key(row.get("data_ora"), note),
                status=status,
                case_key=case_key,
                family=family,
                source=source,
                note=note,
                created=_text(row.get("creato_il") or row.get("creata_il") or "", 60),
                active=status not in TERMINAL_AGENDA_STATUSES,
                rg_values=_extract_rgs(title, row.get("procedimento"), note),
            )
        )
    return records


def _merge_note(*notes: str) -> str:
    lines: list[str] = []
    seen: set[str] = set()
    for note in notes:
        for line in str(note or "").splitlines():
            clean = line.strip()
            key = clean.casefold()
            if clean and key not in seen:
                seen.add(key)
                lines.append(clean)
    return "\n".join(lines)


def _group_payload(records: list[PresidioRecord]) -> dict[str, Any]:
    active = [row for row in records if row.active]
    by_surface = {
        surface: [row for row in active if row.surface == surface]
        for surface in ("agenda", "scadenziario")
    }
    sources = sorted({row.source for row in active})
    rg_values = sorted({rg for row in active for rg in row.rg_values})
    case_rg = _normal_rg(records[0].case_key)
    ambiguous = bool(len(rg_values) > 1 and (not case_rg or any(rg != case_rg for rg in rg_values)))
    repairable = (
        not ambiguous
        and bool(active)
        and set(sources).issubset(REPAIRABLE_SOURCES)
        and (len(by_surface["agenda"]) > 1 or len(by_surface["scadenziario"]) > 1)
    )
    return {
        "tenant": records[0].tenant,
        "case": records[0].case_key,
        "date": records[0].date,
        "time": records[0].time,
        "family": records[0].family,
        "sources": sources,
        "rg_values": rg_values,
        "active": len(active),
        "agenda_active": len(by_surface["agenda"]),
        "deadline_active": len(by_surface["scadenziario"]),
        "repairable": repairable,
        "ambiguous": ambiguous,
        "records": [
            {
                "surface": row.surface,
                "id": row.record_id,
                "linked_id": row.linked_id,
                "status": row.status,
                "source": row.source,
                "title": row.title,
                "active": row.active,
            }
            for row in sorted(records, key=lambda item: (item.surface, item.created, item.record_id))
        ],
    }


def audit_paths(tenant: str, paths: dict[str, Any]) -> dict[str, Any]:
    deadline_source, deadline_rows = _rows(paths, table="scadenze", json_key="SCADENZIARIO_DB")
    agenda_source, agenda_rows = _rows(paths, table="appuntamenti", json_key="AGENDA_DB")
    records = _deadline_records(tenant, deadline_rows) + _agenda_records(tenant, agenda_rows)
    grouped: dict[tuple[str, str, str, str, str], list[PresidioRecord]] = {}
    for record in records:
        if record.source not in REPAIRABLE_SOURCES:
            continue
        grouped.setdefault(record.group_key, []).append(record)
    groups = [
        _group_payload(rows)
        for rows in grouped.values()
        if sum(1 for row in rows if row.active and row.surface == "agenda") > 1
        or sum(1 for row in rows if row.active and row.surface == "scadenziario") > 1
    ]
    groups.sort(key=lambda item: (not item["repairable"], item["tenant"], item["date"], item["case"], item["family"]))
    return {
        "tenant": tenant,
        "source_of_truth": {"agenda": agenda_source, "scadenziario": deadline_source},
        "records_read": {"agenda": len(agenda_rows), "scadenziario": len(deadline_rows), "operational": len(records)},
        "groups": groups,
        "summary": {
            "suspect_groups": len(groups),
            "repairable_groups": sum(1 for item in groups if item["repairable"]),
            "review_groups": sum(1 for item in groups if not item["repairable"]),
        },
    }


def _cancel_note(canonical_id: str) -> str:
    timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
    return f"Doppione automatico annullato il {timestamp}: confluito nel presidio {canonical_id}."


def apply_paths(tenant: str, paths: dict[str, Any]) -> dict[str, Any]:
    audit = audit_paths(tenant, paths)
    repairable = [group for group in audit["groups"] if group["repairable"]]
    repository = _repository_for_paths(tenant, paths)
    scadenziario = repository._scadenziario_manager()
    agenda = repository._agenda_manager()
    changed_deadlines = 0
    changed_agenda = 0
    enriched_deadlines = 0
    cancelled_deadline_ids: set[str] = set()
    cancelled_agenda_ids: set[str] = set()
    enriched_deadline_ids: set[str] = set()
    protected_agenda_ids: set[str] = set()
    errors: list[str] = []
    for group in repairable:
        records = group["records"]
        deadline_ids = [row["id"] for row in records if row["surface"] == "scadenziario" and row["active"]]
        agenda_ids = [row["id"] for row in records if row["surface"] == "agenda" and row["active"]]
        canonical_deadline_id = deadline_ids[0] if deadline_ids else ""
        canonical_agenda_id = ""
        if canonical_deadline_id:
            try:
                canonical_deadline = scadenziario.get(canonical_deadline_id)
                canonical_agenda_id = _text(getattr(canonical_deadline, "id_appuntamento", "") or "", 120)
                if canonical_agenda_id:
                    protected_agenda_ids.add(canonical_agenda_id)
            except Exception:
                canonical_deadline = None
        else:
            canonical_deadline = None
        if not canonical_agenda_id and agenda_ids:
            canonical_agenda_id = next((item for item in agenda_ids if item in protected_agenda_ids), "") or agenda_ids[0]
        duplicate_deadline_ids = [
            item for item in deadline_ids if item != canonical_deadline_id and item not in cancelled_deadline_ids
        ]
        duplicate_agenda_ids = [
            item
            for item in agenda_ids
            if item != canonical_agenda_id and item not in cancelled_agenda_ids and item not in protected_agenda_ids
        ]

        if canonical_deadline is not None and canonical_deadline_id not in enriched_deadline_ids:
            duplicate_notes = []
            for duplicate_id in duplicate_deadline_ids:
                duplicate = scadenziario.get(duplicate_id)
                if duplicate is not None:
                    duplicate_notes.append(str(getattr(duplicate, "note", "") or ""))
            merged = _merge_note(
                str(getattr(canonical_deadline, "note", "") or ""),
                *duplicate_notes,
                f"Presidio canonico: fonti automatiche duplicate confluite ({', '.join(duplicate_deadline_ids) or 'nessuna scadenza duplicata'}).",
            )
            if merged != str(getattr(canonical_deadline, "note", "") or ""):
                try:
                    scadenziario.aggiorna(canonical_deadline_id, note=merged)
                    enriched_deadlines += 1
                    enriched_deadline_ids.add(canonical_deadline_id)
                except Exception as exc:
                    errors.append(f"{tenant}: scadenza canonica {canonical_deadline_id}: {exc}")
        for duplicate_id in duplicate_deadline_ids:
            if duplicate_id in cancelled_deadline_ids:
                continue
            duplicate = scadenziario.get(duplicate_id)
            if duplicate is None:
                continue
            try:
                scadenziario.aggiorna(
                    duplicate_id,
                    stato=StatoTermine.ANNULLATO,
                    completata_il=datetime.now().isoformat(timespec="seconds"),
                    note=_merge_note(str(getattr(duplicate, "note", "") or ""), _cancel_note(canonical_deadline_id or canonical_agenda_id)),
                )
                changed_deadlines += 1
                cancelled_deadline_ids.add(duplicate_id)
                linked_agenda = _text(getattr(duplicate, "id_appuntamento", "") or "", 120)
                if (
                    linked_agenda
                    and linked_agenda != canonical_agenda_id
                    and linked_agenda not in duplicate_agenda_ids
                    and linked_agenda not in cancelled_agenda_ids
                ):
                    duplicate_agenda_ids.append(linked_agenda)
            except Exception as exc:
                errors.append(f"{tenant}: scadenza duplicata {duplicate_id}: {exc}")
        for duplicate_id in duplicate_agenda_ids:
            if duplicate_id in cancelled_agenda_ids:
                continue
            appointment = agenda.get(duplicate_id)
            if appointment is None:
                continue
            try:
                agenda.modifica(
                    duplicate_id,
                    stato=StatoAppuntamento.ANNULLATO,
                    note=_merge_note(str(getattr(appointment, "note", "") or ""), _cancel_note(canonical_deadline_id or canonical_agenda_id)),
                )
                changed_agenda += 1
                cancelled_agenda_ids.add(duplicate_id)
            except Exception as exc:
                errors.append(f"{tenant}: appuntamento duplicato {duplicate_id}: {exc}")
    after = audit_paths(tenant, paths)
    return {
        "tenant": tenant,
        "repairable_groups": len(repairable),
        "deadlines_cancelled": changed_deadlines,
        "agenda_cancelled": changed_agenda,
        "deadlines_enriched": enriched_deadlines,
        "errors": errors,
        "before": audit["summary"],
        "after": after["summary"],
    }


def run(*, registry: Path, tenant: str = "", apply: bool = False) -> dict[str, Any]:
    manager = GestioneTenant(str(registry))
    studios = [studio for studio in manager.lista() if _matches(studio.slug, tenant)]
    result: dict[str, Any] = {
        "ok": True,
        "apply": apply,
        "registry": str(registry),
        "studios": {},
        "total": {
            "suspect_groups": 0,
            "repairable_groups": 0,
            "review_groups": 0,
            "deadlines_cancelled": 0,
            "agenda_cancelled": 0,
            "deadlines_enriched": 0,
            "errors": 0,
        },
    }
    for studio in studios:
        paths = manager.percorsi_dati(studio.slug, reconcile_aliases=False)
        payload = apply_paths(studio.slug, paths) if apply else audit_paths(studio.slug, paths)
        result["studios"][studio.slug] = payload
        summary = payload.get("summary") or payload.get("before") or {}
        result["total"]["suspect_groups"] += int(summary.get("suspect_groups") or 0)
        result["total"]["repairable_groups"] += int(summary.get("repairable_groups") or payload.get("repairable_groups") or 0)
        result["total"]["review_groups"] += int(summary.get("review_groups") or 0)
        result["total"]["deadlines_cancelled"] += int(payload.get("deadlines_cancelled") or 0)
        result["total"]["agenda_cancelled"] += int(payload.get("agenda_cancelled") or 0)
        result["total"]["deadlines_enriched"] += int(payload.get("deadlines_enriched") or 0)
        result["total"]["errors"] += len(payload.get("errors") or [])
    if tenant and not studios:
        result["ok"] = False
        result["errors"] = [f"Studio non trovato: {tenant}"]
    if result["total"]["errors"]:
        result["ok"] = False
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit e bonifica dei presidi duplicati PEC/documenti.")
    parser.add_argument("--registry", default="", help="Percorso tenants.json; default da ambiente o data/tenants.json.")
    parser.add_argument("--tenant", default="", help="Slug studio; vuoto = tutti.")
    parser.add_argument("--apply", action="store_true", help="Applica la bonifica idempotente sui gruppi riparabili.")
    args = parser.parse_args()
    payload = run(registry=_registry_path(args.registry), tenant=args.tenant, apply=bool(args.apply))
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
