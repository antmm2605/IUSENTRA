"""Motore bidirezionale server-side per Agenda e Scadenziario."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from pct.agenda import Agenda, Appuntamento, StatoAppuntamento, TipoAppuntamento
from pct.calendar_bindings import CalendarSyncRepository, now_iso
from pct.calendar_conflicts import CalendarConflictRepository
from pct.calendar_credentials import CalendarCredentialVault
from pct.calendar_providers import build_default_providers, provider_for
from pct.calendar_providers.base import CalendarProvider, event_content_hash, normalise_provider_event, parse_datetime, stable_hash
from pct.scadenziario import GestioneScadenziario, Scadenza, StatoTermine, TipoTermine


PRIVACY_COMPLETE = "complete"
PRIVACY_REDUCED = "professional_reduced"
PRIVACY_BUSY = "busy_only"
ALLOWED_PRIVACY = {PRIVACY_COMPLETE, PRIVACY_REDUCED, PRIVACY_BUSY}


def _clean_prefix(title: str) -> str:
    value = str(title or "").strip()
    for prefix in ("[SCADENZA]", "[UDIENZA]"):
        if value.upper().startswith(prefix):
            return value[len(prefix) :].strip() or value
    return value


def _minutes_between(start: Any, end: Any) -> int:
    start_dt = parse_datetime(start)
    end_dt = parse_datetime(end, fallback=start_dt + timedelta(minutes=60))
    minutes = int((end_dt - start_dt).total_seconds() // 60)
    return max(minutes, 1)


def _date_plus_one(value: str) -> str:
    try:
        return (date.fromisoformat(value[:10]) + timedelta(days=1)).isoformat()
    except ValueError:
        return value


def local_event_hash(local_type: str, item: Appuntamento | Scadenza | None) -> str:
    if item is None:
        return ""
    if local_type == "agenda":
        app = item
        return stable_hash(
            {
                "titolo": app.titolo,
                "tipo": app.tipo.value,
                "data_ora": app.data_ora,
                "durata_minuti": app.durata_minuti,
                "luogo": app.luogo,
                "stato": app.stato.value,
                "note": app.note,
                "cliente": app.cliente,
                "procedimento": app.procedimento,
                "tribunale": app.tribunale,
                "modificato_il": app.modificato_il,
            }
        )
    scadenza = item
    return stable_hash(
        {
            "titolo": scadenza.titolo,
            "tipo": scadenza.tipo.value,
            "data_scadenza": scadenza.data_scadenza,
            "stato": scadenza.stato.value,
            "note": scadenza.note,
            "perentorio": scadenza.perentorio,
            "id_fascicolo": scadenza.id_fascicolo,
        }
    )


def privacy_export_event(local_type: str, item: Appuntamento | Scadenza, privacy_level: str = PRIVACY_REDUCED) -> dict[str, Any]:
    privacy = privacy_level if privacy_level in ALLOWED_PRIVACY else PRIVACY_REDUCED
    if local_type == "agenda":
        app = item
        start = app.data_ora
        end = app.fine_dt.isoformat(timespec="seconds")
        all_day = False
        categories = ["IUSENTRA-AGENDA", f"IUSENTRA-{app.tipo.value}"]
        if privacy == PRIVACY_COMPLETE:
            title = app.titolo
            description_parts = [app.note, app.cliente, app.procedimento, app.tribunale]
            description = "\n".join(part for part in description_parts if str(part or "").strip())
            location = app.luogo
        elif privacy == PRIVACY_BUSY:
            title = "Occupato"
            description = ""
            location = ""
        else:
            title = "[UDIENZA] Impegno di studio" if app.tipo == TipoAppuntamento.UDIENZA else "Impegno di studio"
            description = "Dettagli riservati in IUSENTRA."
            location = app.luogo if app.tipo == TipoAppuntamento.UDIENZA else ""
        status = "cancelled" if app.stato == StatoAppuntamento.ANNULLATO else "confirmed"
    else:
        scadenza = item
        start = scadenza.data_scadenza or scadenza.legal_due_at[:10]
        end = _date_plus_one(start)
        all_day = True
        categories = ["IUSENTRA-SCADENZA"]
        if scadenza.perentorio:
            categories.append("IUSENTRA-PERENTORIA")
        if privacy == PRIVACY_COMPLETE:
            title = f"[SCADENZA] {scadenza.titolo}"
            description = "\n".join(part for part in [scadenza.descrizione, scadenza.note, scadenza.id_fascicolo] if str(part or "").strip())
            location = scadenza.judicial_office_name
        elif privacy == PRIVACY_BUSY:
            title = "Occupato"
            description = ""
            location = ""
        else:
            title = "[SCADENZA] Termine di studio"
            description = "Dettagli riservati in IUSENTRA."
            location = ""
        status = "cancelled" if scadenza.stato == StatoTermine.ANNULLATO else "confirmed"
    return {
        "title": title,
        "description": description,
        "location": location,
        "start": start,
        "end": end,
        "all_day": all_day,
        "status": status,
        "categories": categories,
        "privacy_level": privacy,
    }


class CalendarSyncEngine:
    """Coordina provider, binding, privacy, pull/push e conflitti."""

    def __init__(
        self,
        *,
        agenda: Agenda,
        scadenziario: GestioneScadenziario,
        repository: CalendarSyncRepository,
        conflicts: CalendarConflictRepository,
        credentials: CalendarCredentialVault | None = None,
        providers: dict[str, CalendarProvider] | None = None,
        tenant_id: str = "default",
    ):
        self.agenda = agenda
        self.scadenziario = scadenziario
        self.repository = repository
        self.conflicts = conflicts
        self.credentials = credentials or CalendarCredentialVault()
        self.providers = providers or build_default_providers()
        self.tenant_id = tenant_id or "default"

    @classmethod
    def from_paths(
        cls,
        *,
        agenda_db: str,
        scadenziario_db: str,
        sync_db: str,
        tenant_id: str = "default",
        studio_db: Any = None,
    ) -> "CalendarSyncEngine":
        base = Path(sync_db).parent
        repository_path = base / "calendar_sync_engine.json"
        conflicts_path = base / "calendar_conflicts.json"
        demo_path = base / "demo_calendar" / "provider_events.json"
        return cls(
            agenda=Agenda(db_path=agenda_db, studio_db=studio_db),
            scadenziario=GestioneScadenziario(db_path=scadenziario_db, studio_db=studio_db),
            repository=CalendarSyncRepository(repository_path),
            conflicts=CalendarConflictRepository(conflicts_path),
            providers=build_default_providers(demo_store_path=demo_path),
            tenant_id=tenant_id,
        )

    def _provider(self, account: dict[str, Any]) -> CalendarProvider:
        return provider_for(self.providers, str(account.get("provider") or ""))

    def _account_with_credentials(self, account: dict[str, Any]) -> dict[str, Any]:
        payload = dict(account)
        payload["credentials"] = self.credentials.decrypt(str(account.get("encrypted_credentials") or ""))
        return payload

    def _local_item(self, local_type: str, local_id: str) -> Appuntamento | Scadenza | None:
        if local_type == "agenda":
            return self.agenda.get(local_id)
        if local_type == "scadenza":
            return self.scadenziario.get(local_id)
        raise ValueError("Tipo locale calendario non supportato.")

    def _snapshot_local(self, local_type: str, item: Appuntamento | Scadenza | None) -> dict[str, Any]:
        if item is None:
            return {"missing": True}
        payload = item.to_dict()
        payload["content_hash"] = local_event_hash(local_type, item)
        return payload

    def _remote_hash(self, event: dict[str, Any]) -> str:
        return event_content_hash(normalise_provider_event(event))

    def push_local_event(self, local_type: str, local_id: str, account_id: str, calendar_id: str) -> dict[str, Any]:
        account = self.repository.get_account(account_id, self.tenant_id)
        calendar = self.repository.get_calendar(calendar_id, self.tenant_id)
        if not account or not calendar:
            raise KeyError("Account o calendario non trovato.")
        if str(calendar.get("direction") or "bidirectional") == "inbound":
            return {"ok": True, "skipped": True, "reason": "solo_importazione"}
        local = self._local_item(local_type, local_id)
        if local is None:
            binding = self.repository.find_binding(
                tenant_id=self.tenant_id,
                account_id=account_id,
                calendar_id=calendar_id,
                local_type=local_type,
                local_id=local_id,
            )
            if binding:
                return self.delete_remote_for_binding(account, calendar, binding, deleted_local=True)
            raise KeyError("Elemento locale non trovato.")

        binding = self.repository.find_binding(
            tenant_id=self.tenant_id,
            account_id=account_id,
            calendar_id=calendar_id,
            local_type=local_type,
            local_id=local_id,
        )
        if (local_type == "agenda" and local.stato == StatoAppuntamento.ANNULLATO) or (
            local_type == "scadenza" and local.stato == StatoTermine.ANNULLATO
        ):
            if binding:
                return self.delete_remote_for_binding(account, calendar, binding, deleted_local=True)
            return {"ok": True, "skipped": True, "reason": "annullato_senza_binding"}

        event = privacy_export_event(local_type, local, str(calendar.get("privacy_level") or PRIVACY_REDUCED))
        if binding:
            event["binding"] = binding
        provider = self._provider(account)
        job = self.repository.create_job(tenant_id=self.tenant_id, account_id=account_id, action="push", status="running")
        try:
            result = provider.push_event(self._account_with_credentials(account), calendar, event)
            remote = normalise_provider_event(result.get("event") or {})
            local_hash = local_event_hash(local_type, local)
            remote_hash = self._remote_hash(remote)
            updated_binding = self.repository.upsert_binding(
                {
                    **(binding or {}),
                    "tenant_id": self.tenant_id,
                    "local_type": local_type,
                    "local_id": local_id,
                    "provider": str(account.get("provider") or ""),
                    "account_id": account_id,
                    "calendar_id": calendar_id,
                    "external_event_id": remote.get("id", ""),
                    "external_uid": remote.get("uid", ""),
                    "etag": remote.get("etag", ""),
                    "change_key": remote.get("change_key", ""),
                    "sequence": remote.get("sequence", 0),
                    "content_hash": local_hash,
                    "remote_content_hash": remote_hash,
                    "last_pushed_at": now_iso(),
                    "deleted_remote_at": "",
                    "deleted_local_at": "",
                }
            )
            calendar["last_sync_at"] = now_iso()
            calendar["last_error"] = ""
            self.repository.upsert_calendar(calendar)
            self.repository.update_job(job["id"], status="success", attempts=int(job.get("attempts") or 0) + 1)
            return {"ok": True, "binding": updated_binding, "event": remote}
        except Exception as exc:
            self.repository.update_job(job["id"], status="failed", attempts=int(job.get("attempts") or 0) + 1, error=str(exc))
            calendar["last_error"] = "Sincronizzazione non riuscita."
            self.repository.upsert_calendar(calendar)
            raise

    def delete_remote_for_binding(self, account: dict[str, Any], calendar: dict[str, Any], binding: dict[str, Any], *, deleted_local: bool = False) -> dict[str, Any]:
        provider = self._provider(account)
        result = provider.delete_event(self._account_with_credentials(account), calendar, binding)
        fields = dict(binding)
        if deleted_local:
            fields["deleted_local_at"] = now_iso()
        else:
            fields["deleted_remote_at"] = now_iso()
        self.repository.upsert_binding(fields)
        return {"ok": True, "deleted": True, "provider_result": result}

    def _classify_remote(self, calendar: dict[str, Any], event: dict[str, Any]) -> tuple[str, TipoAppuntamento | TipoTermine]:
        title = str(event.get("title") or "")
        categories = {str(item).upper() for item in event.get("categories") or []}
        role = str(calendar.get("role") or "completo")
        if role == "scadenze" or "IUSENTRA-SCADENZA" in categories or title.upper().startswith("[SCADENZA]"):
            return "scadenza", TipoTermine.TERMINE_PERENTORIO if "IUSENTRA-PERENTORIA" in categories else TipoTermine.ALTRO
        if title.upper().startswith("[UDIENZA]"):
            return "agenda", TipoAppuntamento.UDIENZA
        if role == "agenda":
            return "agenda", TipoAppuntamento.ALTRO
        if event.get("all_day") and role in {"completo", "import_only"} and ("SCADENZA" in title.upper()):
            return "scadenza", TipoTermine.ALTRO
        return "agenda", TipoAppuntamento.ALTRO

    def _create_local_from_remote(self, calendar: dict[str, Any], event: dict[str, Any]) -> tuple[str, Appuntamento | Scadenza]:
        local_type, kind = self._classify_remote(calendar, event)
        title = _clean_prefix(str(event.get("title") or "Evento calendario"))
        if local_type == "scadenza":
            scadenza = self.scadenziario.nuova(
                titolo=title or "Scadenza calendario",
                tipo=kind if isinstance(kind, TipoTermine) else TipoTermine.ALTRO,
                data_scadenza=str(event.get("start") or "")[:10],
                descrizione=str(event.get("description") or ""),
                note="Importata da calendario collegato.",
                perentorio=False,
            )
            return "scadenza", scadenza
        app_type = kind if isinstance(kind, TipoAppuntamento) else TipoAppuntamento.ALTRO
        app = self.agenda.aggiungi(
            titolo=title or "Evento calendario",
            tipo=app_type,
            data_ora=parse_datetime(event.get("start")).isoformat(timespec="seconds"),
            durata_minuti=_minutes_between(event.get("start"), event.get("end")),
            luogo=str(event.get("location") or ""),
            note=str(event.get("description") or ""),
            external_uid=str(event.get("uid") or ""),
            external_provider=str(calendar.get("provider") or ""),
        )
        return "agenda", app

    def _update_local_from_remote(self, local_type: str, local_id: str, event: dict[str, Any], *, force: bool = False) -> Appuntamento | Scadenza:
        title = _clean_prefix(str(event.get("title") or "Evento calendario"))
        if local_type == "scadenza":
            scadenza = self.scadenziario.get(local_id)
            if scadenza is None:
                raise KeyError("Scadenza collegata non trovata.")
            new_date = str(event.get("start") or "")[:10]
            if scadenza.perentorio and scadenza.data_scadenza and new_date and new_date != scadenza.data_scadenza and not force:
                raise PermissionError("Scadenza perentoria da revisionare.")
            return self.scadenziario.aggiorna(
                local_id,
                titolo=title or scadenza.titolo,
                data_scadenza=new_date or scadenza.data_scadenza,
                descrizione=str(event.get("description") or scadenza.descrizione),
                note=scadenza.note,
            )
        app = self.agenda.get(local_id)
        if app is None:
            raise KeyError("Appuntamento collegato non trovato.")
        return self.agenda.modifica(
            local_id,
            titolo=title or app.titolo,
            data_ora=parse_datetime(event.get("start")).isoformat(timespec="seconds"),
            durata_minuti=_minutes_between(event.get("start"), event.get("end")),
            luogo=str(event.get("location") or ""),
            note=str(event.get("description") or ""),
        )

    def _handle_remote_delete(self, binding: dict[str, Any], event: dict[str, Any], account: dict[str, Any]) -> dict[str, Any]:
        local_type = str(binding.get("local_type") or "")
        local_id = str(binding.get("local_id") or "")
        local = self._local_item(local_type, local_id)
        if local_type == "scadenza" and isinstance(local, Scadenza) and local.perentorio:
            conflict = self.conflicts.create_conflict(
                tenant_id=self.tenant_id,
                local_type=local_type,
                local_id=local_id,
                provider=str(account.get("provider") or ""),
                conflict_type="scadenza_perentoria_cancellata",
                local_snapshot=self._snapshot_local(local_type, local),
                remote_snapshot=event,
                proposed_resolution="mantieni_iusentra",
            )
            binding["deleted_remote_at"] = now_iso()
            self.repository.upsert_binding(binding)
            return {"ok": False, "conflict": conflict}
        if local_type == "agenda" and isinstance(local, Appuntamento):
            self.agenda.modifica(local_id, stato=StatoAppuntamento.ANNULLATO)
        elif local_type == "scadenza" and isinstance(local, Scadenza):
            self.scadenziario.aggiorna(local_id, stato=StatoTermine.ANNULLATO)
        binding["deleted_remote_at"] = now_iso()
        self.repository.upsert_binding(binding)
        return {"ok": True, "deleted_remote": True}

    def pull_remote_changes(self, account_id: str, calendar_id: str) -> dict[str, Any]:
        account = self.repository.get_account(account_id, self.tenant_id)
        calendar = self.repository.get_calendar(calendar_id, self.tenant_id)
        if not account or not calendar:
            raise KeyError("Account o calendario non trovato.")
        if str(calendar.get("direction") or "bidirectional") == "outbound":
            return {"ok": True, "skipped": True, "reason": "solo_esportazione"}
        provider = self._provider(account)
        cursor = str(calendar.get("sync_cursor") or account.get("sync_cursor") or "")
        job = self.repository.create_job(tenant_id=self.tenant_id, account_id=account_id, action="pull", status="running")
        created = updated = deleted = conflicts = 0
        seen_external_ids: set[str] = set()
        try:
            result = provider.pull_changes(self._account_with_credentials(account), calendar, cursor=cursor)
            for raw_event in result.get("events") or []:
                event = normalise_provider_event(raw_event)
                external_id = str(event.get("id") or "")
                external_uid = str(event.get("uid") or "")
                if external_id:
                    seen_external_ids.add(external_id)
                binding = self.repository.find_binding(
                    tenant_id=self.tenant_id,
                    account_id=account_id,
                    calendar_id=calendar_id,
                    external_event_id=external_id,
                    external_uid=external_uid,
                )
                if event.get("deleted"):
                    if binding:
                        outcome = self._handle_remote_delete(binding, event, account)
                        deleted += 1 if outcome.get("deleted_remote") else 0
                        conflicts += 1 if outcome.get("conflict") else 0
                    continue
                remote_hash = self._remote_hash(event)
                if not binding:
                    local_type, local = self._create_local_from_remote(calendar, event)
                    self.repository.upsert_binding(
                        {
                            "tenant_id": self.tenant_id,
                            "local_type": local_type,
                            "local_id": local.id,
                            "provider": str(account.get("provider") or ""),
                            "account_id": account_id,
                            "calendar_id": calendar_id,
                            "external_event_id": external_id,
                            "external_uid": external_uid,
                            "etag": event.get("etag", ""),
                            "change_key": event.get("change_key", ""),
                            "sequence": event.get("sequence", 0),
                            "content_hash": local_event_hash(local_type, local),
                            "remote_content_hash": remote_hash,
                            "last_pulled_at": now_iso(),
                        }
                    )
                    created += 1
                    continue
                local_type = str(binding.get("local_type") or "")
                local_id = str(binding.get("local_id") or "")
                local = self._local_item(local_type, local_id)
                local_hash = local_event_hash(local_type, local)
                local_changed = bool(local_hash and binding.get("content_hash") and local_hash != binding.get("content_hash"))
                remote_changed = bool(remote_hash and binding.get("remote_content_hash") and remote_hash != binding.get("remote_content_hash"))
                if local_type == "scadenza" and isinstance(local, Scadenza) and local.perentorio:
                    new_date = str(event.get("start") or "")[:10]
                    if new_date and local.data_scadenza and new_date != local.data_scadenza:
                        conflict = self.conflicts.create_conflict(
                            tenant_id=self.tenant_id,
                            local_type=local_type,
                            local_id=local_id,
                            provider=str(account.get("provider") or ""),
                            conflict_type="scadenza_perentoria_spostata",
                            local_snapshot=self._snapshot_local(local_type, local),
                            remote_snapshot=event,
                            proposed_resolution="mantieni_iusentra",
                        )
                        conflicts += 1
                        continue
                if local_changed and remote_changed:
                    self.conflicts.create_conflict(
                        tenant_id=self.tenant_id,
                        local_type=local_type,
                        local_id=local_id,
                        provider=str(account.get("provider") or ""),
                        conflict_type="modifica_concorrente",
                        local_snapshot=self._snapshot_local(local_type, local),
                        remote_snapshot=event,
                        proposed_resolution="revisione_manuale",
                    )
                    conflicts += 1
                    continue
                if remote_changed or not binding.get("remote_content_hash"):
                    local = self._update_local_from_remote(local_type, local_id, event)
                    updated += 1
                binding.update(
                    {
                        "etag": event.get("etag", ""),
                        "change_key": event.get("change_key", ""),
                        "sequence": event.get("sequence", 0),
                        "content_hash": local_event_hash(local_type, local),
                        "remote_content_hash": remote_hash,
                        "last_pulled_at": now_iso(),
                        "deleted_remote_at": "",
                    }
                )
                self.repository.upsert_binding(binding)
            if result.get("full_snapshot"):
                for binding in self.repository.list_bindings(self.tenant_id, account_id=account_id, calendar_id=calendar_id):
                    ext = str(binding.get("external_event_id") or "")
                    if ext and ext not in seen_external_ids and not binding.get("deleted_remote_at"):
                        outcome = self._handle_remote_delete(binding, {"id": ext, "deleted": True, "title": ""}, account)
                        deleted += 1 if outcome.get("deleted_remote") else 0
                        conflicts += 1 if outcome.get("conflict") else 0
            cursor_out = str(result.get("cursor") or cursor or "")
            account["sync_cursor"] = cursor_out
            calendar["sync_cursor"] = cursor_out
            calendar["last_sync_at"] = now_iso()
            calendar["last_error"] = ""
            self.repository.upsert_account(account)
            self.repository.upsert_calendar(calendar)
            self.repository.update_job(job["id"], status="success", attempts=int(job.get("attempts") or 0) + 1)
            return {"ok": True, "created": created, "updated": updated, "deleted": deleted, "conflicts": conflicts, "cursor": cursor_out}
        except Exception as exc:
            self.repository.update_job(job["id"], status="failed", attempts=int(job.get("attempts") or 0) + 1, error=str(exc))
            calendar["last_error"] = "Sincronizzazione non riuscita."
            self.repository.upsert_calendar(calendar)
            raise

    def sync_account(self, account_id: str) -> dict[str, Any]:
        account = self.repository.get_account(account_id, self.tenant_id)
        if not account:
            raise KeyError("Account calendario non trovato.")
        reports = []
        for calendar in self.repository.list_calendars(self.tenant_id, account_id=account_id):
            if not calendar.get("enabled", True):
                continue
            direction = str(calendar.get("direction") or "bidirectional")
            if direction in {"inbound", "bidirectional"}:
                reports.append({"calendar_id": calendar["id"], "phase": "pull", **self.pull_remote_changes(account_id, calendar["id"])})
            if direction in {"outbound", "bidirectional"}:
                for app in self.agenda.tutti():
                    reports.append({"calendar_id": calendar["id"], "phase": "push", "local_id": app.id, **self.push_local_event("agenda", app.id, account_id, calendar["id"])})
                for scadenza in self.scadenziario.tutte(solo_aperte=False):
                    reports.append({"calendar_id": calendar["id"], "phase": "push", "local_id": scadenza.id, **self.push_local_event("scadenza", scadenza.id, account_id, calendar["id"])})
        return {"ok": True, "account_id": account_id, "reports": reports}

    def resolve_conflict(self, conflict_id: str, strategy: str) -> dict[str, Any]:
        conflict = self.conflicts.get(conflict_id, self.tenant_id)
        if not conflict:
            raise KeyError("Conflitto calendario non trovato.")
        strategy = str(strategy or "").strip()
        if strategy == "ignore":
            return {"ok": True, "conflict": self.conflicts.resolve(conflict_id, status="ignored", resolution=strategy)}
        local_type = str(conflict.get("local_type") or "")
        local_id = str(conflict.get("local_id") or "")
        if strategy == "use_remote":
            remote = dict(conflict.get("remote_snapshot") or {})
            self._update_local_from_remote(local_type, local_id, remote, force=True)
            return {"ok": True, "conflict": self.conflicts.resolve(conflict_id, resolution=strategy)}
        if strategy == "use_local":
            bindings = self.repository.list_bindings(self.tenant_id, local_type=local_type, local_id=local_id)
            for binding in bindings:
                self.push_local_event(local_type, local_id, str(binding.get("account_id") or ""), str(binding.get("calendar_id") or ""))
            return {"ok": True, "conflict": self.conflicts.resolve(conflict_id, resolution=strategy)}
        if strategy == "merge_manual":
            return {"ok": True, "conflict": self.conflicts.resolve(conflict_id, resolution=strategy)}
        raise ValueError("Strategia conflitto non supportata.")

    def sync_due_jobs(self) -> dict[str, Any]:
        processed = 0
        failed = 0
        for job in self.repository.list_jobs(self.tenant_id, status="queued"):
            try:
                if job.get("action") in {"pull", "push", "delete", "renew_webhook"}:
                    self.repository.update_job(job["id"], status="success", attempts=int(job.get("attempts") or 0) + 1)
                    processed += 1
            except Exception:
                failed += 1
        return {"ok": failed == 0, "processed": processed, "failed": failed}
