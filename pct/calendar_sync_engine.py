"""Motore bidirezionale server-side per Agenda e Scadenziario."""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Any

from pct.ora_italiana import giorno_italiano
from pct.agenda import Agenda, Appuntamento, StatoAppuntamento, TipoAppuntamento
from pct.calendar_bindings import CalendarSyncRepository, now_iso
from pct.calendar_conflicts import CalendarConflictRepository
from pct.calendar_credentials import CalendarCredentialVault
from pct.calendar_providers import build_default_providers, provider_for
from pct.calendar_providers.base import CalendarProvider, event_content_hash, normalise_provider_event, parse_datetime, stable_hash
from pct.scadenziario import GestioneScadenziario, Scadenza, StatoTermine, TipoTermine


RETRY_MAX_ATTEMPTS = 5
RETRY_BASE_DELAY = timedelta(minutes=5)
RETRY_MAX_DELAY = timedelta(hours=6)

PRIVACY_COMPLETE = "complete"
PRIVACY_REDUCED = "professional_reduced"
PRIVACY_BUSY = "busy_only"
ALLOWED_PRIVACY = {PRIVACY_COMPLETE, PRIVACY_REDUCED, PRIVACY_BUSY}
TECHNICAL_VISIBLE_RE = re.compile(
    r"\b(?:PEC_AUDIT|pipeline|audit|audit-grade|source_event|profile_id|payload|runtime|backend|frontend|legacy|json_api|external_uid|external_provider|worker|job|provider|webhook|endpoint)\b",
    re.IGNORECASE,
)
INTERNAL_NOTE_PREFIXES = (
    "tipo evento:",
    "decorrenza letta:",
    "fonte:",
    "scadenza:",
    "hash:",
    "id:",
)
OPERATIONAL_PREFIX_RE = re.compile(
    r"^\s*(?:Presidio\s+PEC|Presidio\s+anomalie\s+PEC|Verifica\s+comunicazione\s+di\s+cancelleria\s+PEC)\s*:?\s*-?\s*",
    re.IGNORECASE,
)


def _clean_prefix(title: str) -> str:
    value = str(title or "").strip()
    for prefix in ("[SCADENZA]", "[UDIENZA]"):
        if value.upper().startswith(prefix):
            return value[len(prefix) :].strip() or value
    return value


def _short_text(value: Any, limit: int = 220) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "..."


def _calendar_visible_text(value: Any, limit: int = 500) -> str:
    parts: list[str] = []
    for raw_line in str(value or "").splitlines():
        line = _short_text(raw_line, limit=max(limit, 220))
        if not line:
            continue
        line = re.sub(r"\bPEC_AUDIT:[A-Za-z0-9_.:-]+", "", line).strip()
        if not line:
            continue
        lowered = line.lower()
        if lowered.startswith("fonte link udienza:"):
            parts.append("Allegato udienza: " + _short_text(line.split(":", 1)[1], 120))
            continue
        if lowered.startswith("verifica link udienza:"):
            value_part = _short_text(line.split(":", 1)[1], 160).lower()
            if "identico" in value_part:
                parts.append("Link udienza verificato sull'allegato.")
            elif value_part:
                parts.append("Link udienza da controllare sull'allegato.")
            continue
        if lowered.startswith(INTERNAL_NOTE_PREFIXES):
            continue
        if TECHNICAL_VISIBLE_RE.search(line):
            continue
        line = OPERATIONAL_PREFIX_RE.sub("", line).strip(" -:")
        if line:
            parts.append(line)
    return _short_text(" ".join(parts), limit)


def _professional_prefixed_title(prefix: str, title: str) -> str:
    clean_prefix = str(prefix or "").strip().rstrip(":")
    clean_title = str(title or "").strip()
    if not clean_title:
        return clean_prefix
    if clean_title.lower().startswith(clean_prefix.lower()):
        return clean_title
    return f"{clean_prefix}: {clean_title}"


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


def _utc_iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_utc(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text[:-1] + "+00:00" if text.endswith("Z") else text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def retry_delay(attempts: int) -> timedelta:
    """Backoff esponenziale limitato: 5, 10, 20, 40 minuti... fino a 6 ore."""

    exponent = max(int(attempts or 1) - 1, 0)
    return min(RETRY_BASE_DELAY * (2 ** min(exponent, 16)), RETRY_MAX_DELAY)


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
        start = app.data_ora_utc.astimezone(ZoneInfo("Europe/Rome")).isoformat(timespec="seconds")
        end = app.fine_utc.astimezone(ZoneInfo("Europe/Rome")).isoformat(timespec="seconds")
        all_day = False
        categories = ["IUSENTRA-AGENDA", f"IUSENTRA-{app.tipo.value}"]
        clean_title = _calendar_visible_text(app.titolo, 140) or "Impegno di studio"
        if privacy == PRIVACY_COMPLETE:
            title = clean_title
            description_parts = [
                _calendar_visible_text(app.note, 700),
                app.cliente,
                app.procedimento,
                app.tribunale,
            ]
            description = "\n".join(part for part in description_parts if str(part or "").strip())
            location = app.luogo
        elif privacy == PRIVACY_BUSY:
            title = "Occupato"
            description = ""
            location = ""
        else:
            title = "Udienza: impegno di studio" if app.tipo == TipoAppuntamento.UDIENZA else "Impegno di studio"
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
        clean_title = _calendar_visible_text(scadenza.titolo, 140) or "Scadenza"
        if privacy == PRIVACY_COMPLETE:
            title = f"Termine perentorio: {clean_title}" if scadenza.perentorio else f"Scadenza: {clean_title}"
            description_parts = [
                _calendar_visible_text(scadenza.descrizione, 700),
                _calendar_visible_text(scadenza.note, 700),
                f"Fascicolo: {scadenza.id_fascicolo}" if str(scadenza.id_fascicolo or "").strip() else "",
            ]
            description = "\n".join(part for part in description_parts if str(part or "").strip())
            location = scadenza.judicial_office_name
        elif privacy == PRIVACY_BUSY:
            title = "Occupato"
            description = ""
            location = ""
        else:
            title = (
                _professional_prefixed_title("Termine perentorio", clean_title)
                if scadenza.perentorio
                else _professional_prefixed_title("Scadenza", clean_title)
            )
            description = "Dettagli riservati in IUSENTRA."
            location = ""
        if scadenza.stato == StatoTermine.ANNULLATO:
            status = "cancelled"
        elif scadenza.stato == StatoTermine.BOZZA:
            # Difesa in profondita': una proposta non confermata non e' mai
            # "confirmed" (push_local_event comunque non la pubblica).
            status = "tentative"
        else:
            status = "confirmed"
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

    def _snapshot_remote(self, event: dict[str, Any]) -> dict[str, Any]:
        normalised = normalise_provider_event(event)
        snapshot_keys = (
            "id",
            "uid",
            "title",
            "description",
            "location",
            "start",
            "end",
            "all_day",
            "status",
            "deleted",
            "etag",
            "change_key",
            "sequence",
            "updated_at",
        )
        snapshot = {key: normalised.get(key) for key in snapshot_keys if normalised.get(key) not in (None, "")}
        snapshot["content_hash"] = self._remote_hash(normalised)
        return snapshot

    def _remote_hash(self, event: dict[str, Any]) -> str:
        return event_content_hash(normalise_provider_event(event))

    # -- job di sincronizzazione e retry -------------------------------------

    @staticmethod
    def _job_target(job: dict[str, Any]) -> tuple[str, str, str, str, str]:
        action = str(job.get("action") or "")
        group = "local" if action in {"push", "delete"} else action
        return (
            group,
            str(job.get("account_id") or ""),
            str(job.get("calendar_id") or ""),
            str(job.get("local_type") or ""),
            str(job.get("local_id") or ""),
        )

    def _open_failed_job(self, target: tuple[str, str, str, str, str]) -> dict[str, Any] | None:
        for job in self.repository.list_jobs(self.tenant_id, status="failed"):
            if str(job.get("retry_state") or "") in {"resolved", "superseded"}:
                continue
            if self._job_target(job) == target:
                return job
        return None

    def _start_job(
        self,
        *,
        action: str,
        account_id: str,
        calendar_id: str,
        local_type: str = "",
        local_id: str = "",
        retry_job: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Apre (o riprende) il job tracciato per un singolo elemento/calendario.

        Un elemento che continua a fallire riusa sempre lo stesso job, cosi' i
        tentativi si accumulano fino al limite e non nascono job duplicati.
        """

        context = {"calendar_id": calendar_id, "local_type": local_type, "local_id": local_id}
        existing = retry_job
        if existing is None:
            probe = {"action": action, "account_id": account_id, **context}
            existing = self._open_failed_job(self._job_target(probe))
        if existing is not None:
            return self.repository.update_job(existing["id"], action=action, status="running", **context)
        job = self.repository.create_job(tenant_id=self.tenant_id, account_id=account_id, action=action, status="running")
        return self.repository.update_job(job["id"], **context)

    def _job_succeeded(self, job: dict[str, Any]) -> dict[str, Any]:
        return self.repository.update_job(
            job["id"],
            status="success",
            attempts=int(job.get("attempts") or 0) + 1,
            error="",
            retry_state="",
            next_retry_at="",
        )

    def _job_noop(self, job: dict[str, Any] | None, reason: str) -> None:
        """Chiude un job di retry che non ha piu' nulla da fare."""

        if job is not None:
            self.repository.update_job(job["id"], status="success", error="", retry_state="resolved", resolution=reason, next_retry_at="")

    def _job_failed(self, job: dict[str, Any], exc: Exception, *, now: datetime | None = None) -> dict[str, Any]:
        attempts = int(job.get("attempts") or 0) + 1
        exhausted = attempts >= RETRY_MAX_ATTEMPTS
        current = now or datetime.now(timezone.utc)
        return self.repository.update_job(
            job["id"],
            status="failed",
            attempts=attempts,
            error=_short_text(str(exc) or type(exc).__name__, 300),
            retry_state="exhausted" if exhausted else "pending",
            next_retry_at="" if exhausted else _utc_iso(current + retry_delay(attempts)),
        )

    def _record_binding_error(self, binding: dict[str, Any] | None, exc: Exception | None) -> None:
        if not binding or not binding.get("id"):
            return
        fields = dict(binding)
        fields["last_error"] = "" if exc is None else _short_text(str(exc) or type(exc).__name__, 300)
        fields["last_error_at"] = "" if exc is None else now_iso()
        self.repository.upsert_binding(fields)

    def _delete_with_job(
        self,
        account: dict[str, Any],
        calendar: dict[str, Any],
        binding: dict[str, Any],
        *,
        local_type: str,
        local_id: str,
        retry_job: dict[str, Any] | None,
        reason: str = "",
    ) -> dict[str, Any]:
        job = self._start_job(
            action="delete",
            account_id=str(account.get("id") or ""),
            calendar_id=str(calendar.get("id") or ""),
            local_type=local_type,
            local_id=local_id,
            retry_job=retry_job,
        )
        try:
            result = self.delete_remote_for_binding(account, calendar, binding, deleted_local=True)
        except Exception as exc:
            self._job_failed(job, exc)
            self._record_binding_error(binding, exc)
            calendar["last_error"] = "Sincronizzazione non riuscita."
            self.repository.upsert_calendar(calendar)
            raise
        self._job_succeeded(job)
        if reason:
            result = {**result, "reason": reason}
        return result

    def push_local_event(
        self,
        local_type: str,
        local_id: str,
        account_id: str,
        calendar_id: str,
        *,
        _retry_job: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        account = self.repository.get_account(account_id, self.tenant_id)
        calendar = self.repository.get_calendar(calendar_id, self.tenant_id)
        if not account or not calendar:
            self._job_noop(_retry_job, "account_o_calendario_rimosso")
            raise KeyError("Account o calendario non trovato.")
        if str(calendar.get("direction") or "bidirectional") == "inbound":
            self._job_noop(_retry_job, "solo_importazione")
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
                return self._delete_with_job(account, calendar, binding, local_type=local_type, local_id=local_id, retry_job=_retry_job)
            self._job_noop(_retry_job, "elemento_locale_rimosso")
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
                return self._delete_with_job(account, calendar, binding, local_type=local_type, local_id=local_id, retry_job=_retry_job)
            self._job_noop(_retry_job, "annullato_senza_binding")
            return {"ok": True, "skipped": True, "reason": "annullato_senza_binding"}

        if local_type == "scadenza" and local.stato == StatoTermine.BOZZA:
            # Proposta non confermata: mai pubblicata sui calendari esterni.
            # Se era gia' stata pubblicata (termine riportato in bozza), il
            # relativo evento remoto viene rimosso una sola volta.
            if binding and binding.get("external_event_id") and not binding.get("deleted_local_at"):
                return self._delete_with_job(
                    account,
                    calendar,
                    binding,
                    local_type=local_type,
                    local_id=local_id,
                    retry_job=_retry_job,
                    reason="bozza_non_confermata",
                )
            self._job_noop(_retry_job, "bozza_non_confermata")
            return {"ok": True, "skipped": True, "reason": "bozza_non_confermata"}

        event = privacy_export_event(local_type, local, str(calendar.get("privacy_level") or PRIVACY_REDUCED))
        if binding:
            event["binding"] = binding
        provider = self._provider(account)
        job = self._start_job(
            action="push",
            account_id=account_id,
            calendar_id=calendar_id,
            local_type=local_type,
            local_id=local_id,
            retry_job=_retry_job,
        )
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
                    "last_error": "",
                    "last_error_at": "",
                }
            )
            calendar["last_sync_at"] = now_iso()
            calendar["last_error"] = ""
            self.repository.upsert_calendar(calendar)
            self._job_succeeded(job)
            return {"ok": True, "binding": updated_binding, "event": remote}
        except Exception as exc:
            self._job_failed(job, exc)
            self._record_binding_error(binding, exc)
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
        title_upper = title.upper()
        if role == "scadenze" or "IUSENTRA-SCADENZA" in categories or title_upper.startswith(("[SCADENZA]", "SCADENZA:", "TERMINE PERENTORIO:")):
            return "scadenza", TipoTermine.TERMINE_PERENTORIO if "IUSENTRA-PERENTORIA" in categories else TipoTermine.ALTRO
        if title_upper.startswith(("[UDIENZA]", "UDIENZA:")):
            return "agenda", TipoAppuntamento.UDIENZA
        if role == "agenda":
            return "agenda", TipoAppuntamento.ALTRO
        if event.get("all_day") and role in {"completo", "import_only"} and ("SCADENZA" in title_upper):
            return "scadenza", TipoTermine.ALTRO
        return "agenda", TipoAppuntamento.ALTRO

    def _create_local_from_remote(self, calendar: dict[str, Any], event: dict[str, Any]) -> tuple[str, Appuntamento | Scadenza]:
        local_type, kind = self._classify_remote(calendar, event)
        title = _clean_prefix(str(event.get("title") or "Evento calendario"))
        if local_type == "scadenza":
            scadenza = self.scadenziario.nuova(
                titolo=title or "Scadenza calendario",
                tipo=kind if isinstance(kind, TipoTermine) else TipoTermine.ALTRO,
                data_scadenza=giorno_italiano(event.get("start")),
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
            new_date = giorno_italiano(event.get("start"))
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
                remote_snapshot=self._snapshot_remote(event),
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

    def pull_remote_changes(
        self,
        account_id: str,
        calendar_id: str,
        *,
        _retry_job: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        account = self.repository.get_account(account_id, self.tenant_id)
        calendar = self.repository.get_calendar(calendar_id, self.tenant_id)
        if not account or not calendar:
            self._job_noop(_retry_job, "account_o_calendario_rimosso")
            raise KeyError("Account o calendario non trovato.")
        if str(calendar.get("direction") or "bidirectional") == "outbound":
            self._job_noop(_retry_job, "solo_esportazione")
            return {"ok": True, "skipped": True, "reason": "solo_esportazione"}
        provider = self._provider(account)
        cursor = str(calendar.get("sync_cursor") or account.get("sync_cursor") or "")
        job = self._start_job(action="pull", account_id=account_id, calendar_id=calendar_id, retry_job=_retry_job)
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
                    new_date = giorno_italiano(event.get("start"))
                    if new_date and local.data_scadenza and new_date != local.data_scadenza:
                        self.conflicts.create_conflict(
                            tenant_id=self.tenant_id,
                            local_type=local_type,
                            local_id=local_id,
                            provider=str(account.get("provider") or ""),
                            conflict_type="scadenza_perentoria_spostata",
                            local_snapshot=self._snapshot_local(local_type, local),
                            remote_snapshot=self._snapshot_remote(event),
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
                        remote_snapshot=self._snapshot_remote(event),
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
            self._job_succeeded(job)
            return {"ok": True, "created": created, "updated": updated, "deleted": deleted, "conflicts": conflicts, "cursor": cursor_out}
        except Exception as exc:
            self._job_failed(job, exc)
            calendar["last_error"] = "Sincronizzazione non riuscita."
            self.repository.upsert_calendar(calendar)
            raise

    def sync_account(self, account_id: str) -> dict[str, Any]:
        """Allinea un account: un errore su un elemento non blocca gli altri.

        Ogni fallimento resta registrato sul job (con retry e backoff) e, se
        esiste, sul binding; il report finale riporta ``ok=False`` e gli errori.
        """

        account = self.repository.get_account(account_id, self.tenant_id)
        if not account:
            raise KeyError("Account calendario non trovato.")
        reports = []
        pulled = 0
        pushed = 0
        skipped = 0
        failed = 0
        conflicts = 0

        def _push(calendar_id: str, local_type: str, local_id: str) -> None:
            nonlocal pushed, skipped, failed
            base = {"calendar_id": calendar_id, "phase": "push", "local_type": local_type, "local_id": local_id}
            try:
                outcome = self.push_local_event(local_type, local_id, account_id, calendar_id)
            except Exception as exc:
                failed += 1
                reports.append({**base, "ok": False, "error": _short_text(str(exc) or type(exc).__name__, 300)})
                return
            if outcome.get("skipped"):
                skipped += 1
            else:
                pushed += 1
            reports.append({**base, **outcome})

        for calendar in self.repository.list_calendars(self.tenant_id, account_id=account_id):
            if not calendar.get("enabled", True):
                continue
            direction = str(calendar.get("direction") or "bidirectional")
            role = str(calendar.get("role") or "completo")
            if direction in {"inbound", "bidirectional"}:
                try:
                    report = self.pull_remote_changes(account_id, calendar["id"])
                except Exception as exc:
                    failed += 1
                    reports.append(
                        {
                            "calendar_id": calendar["id"],
                            "phase": "pull",
                            "ok": False,
                            "error": _short_text(str(exc) or type(exc).__name__, 300),
                        }
                    )
                else:
                    pulled += int(report.get("created") or 0) + int(report.get("updated") or 0)
                    conflicts += int(report.get("conflicts") or 0)
                    reports.append(
                        {
                            "calendar_id": calendar["id"],
                            "phase": "pull",
                            **report,
                        }
                    )
            if direction in {"outbound", "bidirectional"}:
                known_roles = {"agenda", "scadenze", "completo", "import_only", "export_only"}
                include_agenda = role in {"agenda", "completo", "export_only"} or role not in known_roles
                include_scadenze = role in {"scadenze", "completo", "export_only"} or role not in known_roles
                if include_agenda:
                    for app in self.agenda.tutti():
                        _push(calendar["id"], "agenda", app.id)
                if include_scadenze:
                    # Tutti gli stati passano da push_local_event: le BOZZE non
                    # vengono pubblicate (ed eventuali eventi gia' pubblicati
                    # vengono rimossi), gli annullati cancellano il remoto.
                    for scadenza in self.scadenziario.tutte(solo_aperte=False):
                        _push(calendar["id"], "scadenza", scadenza.id)
        return {
            "ok": failed == 0,
            "account_id": account_id,
            "pulled": pulled,
            "pushed": pushed,
            "skipped": skipped,
            "failed": failed,
            "conflicts": conflicts,
            "reports": reports,
        }

    def push_local_to_linked_calendars(self, local_type: str, local_id: str) -> dict[str, Any]:
        """Pubblica subito un elemento locale sui calendari esterni abilitati."""

        if local_type not in {"agenda", "scadenza"}:
            raise ValueError("Tipo locale calendario non supportato.")
        reports: list[dict[str, Any]] = []
        pushed = 0
        skipped = 0
        for account in self.repository.list_accounts(self.tenant_id):
            if str(account.get("provider") or "") in {"webcal", "ics"}:
                skipped += 1
                continue
            account_id = str(account.get("id") or "")
            for calendar in self.repository.list_calendars(self.tenant_id, account_id=account_id):
                if not calendar.get("enabled", True):
                    skipped += 1
                    continue
                direction = str(calendar.get("direction") or "bidirectional")
                if direction not in {"outbound", "bidirectional"}:
                    skipped += 1
                    continue
                role = str(calendar.get("role") or "completo")
                known_roles = {"agenda", "scadenze", "completo", "import_only", "export_only"}
                allows_agenda = role in {"agenda", "completo", "export_only"} or role not in known_roles
                allows_deadline = role in {"scadenze", "completo", "export_only"} or role not in known_roles
                if (local_type == "agenda" and not allows_agenda) or (local_type == "scadenza" and not allows_deadline):
                    skipped += 1
                    continue
                try:
                    reports.append(
                        {
                            "calendar_id": calendar["id"],
                            "account_id": account_id,
                            "local_type": local_type,
                            "local_id": local_id,
                            **self.push_local_event(local_type, local_id, account_id, calendar["id"]),
                        }
                    )
                    pushed += 1
                except Exception as exc:
                    reports.append(
                        {
                            "ok": False,
                            "calendar_id": calendar.get("id", ""),
                            "account_id": account_id,
                            "local_type": local_type,
                            "local_id": local_id,
                            "error": str(exc),
                        }
                    )
        failed = sum(1 for item in reports if item.get("ok") is False)
        return {
            "ok": failed == 0,
            "local_type": local_type,
            "local_id": local_id,
            "pushed": pushed,
            "skipped": skipped,
            "failed": failed,
            "reports": reports,
        }

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

    def sync_due_jobs(self, *, now: datetime | None = None) -> dict[str, Any]:
        """Riprova calendari: riesegue i job falliti scaduti (backoff) o in coda.

        - push/delete con contesto: ripubblica l'elemento (idempotente: il
          binding esistente aggiorna l'evento remoto, non ne crea un altro);
        - pull con contesto: rilegge il calendario;
        - job senza contesto (storici o in coda): un solo ``sync_account`` per
          account, poi il job viene chiuso (i fallimenti residui hanno ora un
          job con contesto proprio);
        - oltre ``RETRY_MAX_ATTEMPTS`` il job resta ``failed`` con
          ``retry_state='exhausted'`` e non viene piu' ripreso in automatico.
        """

        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        processed = 0
        failed = 0
        succeeded = 0
        exhausted = 0
        legacy_accounts: dict[str, list[dict[str, Any]]] = {}
        due: list[dict[str, Any]] = []
        for job in self.repository.list_jobs(self.tenant_id):
            status = str(job.get("status") or "")
            if status not in {"queued", "failed"}:
                continue
            retry_state = str(job.get("retry_state") or "")
            if retry_state in {"resolved", "superseded", "exhausted"}:
                continue
            if status == "failed" and int(job.get("attempts") or 0) >= RETRY_MAX_ATTEMPTS:
                self.repository.update_job(job["id"], retry_state="exhausted", next_retry_at="")
                exhausted += 1
                continue
            next_retry = _parse_utc(job.get("next_retry_at"))
            if next_retry is not None and next_retry > current:
                continue
            action = str(job.get("action") or "")
            has_local = bool(job.get("calendar_id") and job.get("local_type") and job.get("local_id"))
            if action in {"push", "delete"} and has_local:
                due.append(job)
            elif action == "pull" and job.get("calendar_id"):
                due.append(job)
            elif action in {"pull", "push", "delete", "renew_webhook"} and job.get("account_id"):
                legacy_accounts.setdefault(str(job.get("account_id")), []).append(job)

        for job in due:
            processed += 1
            try:
                if str(job.get("action")) == "pull":
                    self.pull_remote_changes(str(job.get("account_id") or ""), str(job.get("calendar_id") or ""), _retry_job=job)
                else:
                    self.push_local_event(
                        str(job.get("local_type") or ""),
                        str(job.get("local_id") or ""),
                        str(job.get("account_id") or ""),
                        str(job.get("calendar_id") or ""),
                        _retry_job=job,
                    )
                succeeded += 1
            except Exception:
                failed += 1

        for account_id, jobs in legacy_accounts.items():
            processed += 1
            try:
                report = self.sync_account(account_id)
                ok = bool(report.get("ok"))
            except Exception as exc:
                ok = False
                for job in jobs:
                    self._job_failed(job, exc, now=current)
            else:
                for job in jobs:
                    self.repository.update_job(
                        job["id"],
                        status="success" if ok else "failed",
                        retry_state="resolved" if ok else "superseded",
                        next_retry_at="",
                    )
            if ok:
                succeeded += 1
            else:
                failed += 1
        return {"ok": failed == 0, "processed": processed, "succeeded": succeeded, "failed": failed, "exhausted": exhausted}
