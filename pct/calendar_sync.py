"""
pct/calendar_sync.py - Profili di sincronizzazione calendario esterno.

Gestisce integrazioni professionali basate su standard aperti:
  - URL ICS / WebCal
  - preview remota del calendario
  - sincronizzazione uno-a-uno verso l'agenda interna
  - profili persistenti per studio / tenant

Scelta architetturale:
  - niente OAuth obbligatorio
  - massima compatibilita con Google, Outlook, Apple e calendari generici
  - aggiornamenti idempotenti via UID RFC 5545
"""
from __future__ import annotations

import json
import hashlib
import ipaddress
import socket
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import urljoin, urlparse

import requests

from pct.agenda import Agenda, TipoAppuntamento
from pct.ical_import import EventoImportato, parse_ics

USER_AGENT = "IUSENTRA-Calendar-Sync/1.0 (+https://pst.giustizia.it)"
MAX_ICS_BYTES = 5 * 1024 * 1024
_REMOTE_CALENDAR_SCHEMES = {"http", "https"}


def _now_iso(now: Optional[datetime] = None) -> str:
    return (now or datetime.now()).replace(microsecond=0).isoformat()


def _decode_ics_bytes(raw: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-16", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _normalize_calendar_url(url: str) -> str:
    value = (url or "").strip()
    if value.lower().startswith("webcal://"):
        return "https://" + value[len("webcal://") :]
    return value


def _host_is_public_calendar_target(host: str, *, resolve_dns: bool) -> bool:
    value = (host or "").strip().lower().rstrip(".")
    if not value or value in {"localhost", "localhost.localdomain"} or value.endswith(".local"):
        return False
    addresses: list[str] = []
    try:
        addresses.append(str(ipaddress.ip_address(value)))
    except ValueError:
        if not resolve_dns:
            return True
        try:
            for family, _, _, _, sockaddr in socket.getaddrinfo(value, None):
                if family in {socket.AF_INET, socket.AF_INET6} and sockaddr:
                    addresses.append(str(sockaddr[0]))
        except socket.gaierror:
            return False
    for address in addresses:
        ip = ipaddress.ip_address(address)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_unspecified or ip.is_reserved:
            return False
    return bool(addresses)


def _validate_remote_calendar_url(url: str, *, resolve_dns: bool) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in _REMOTE_CALENDAR_SCHEMES or not parsed.hostname:
        raise ValueError("URL calendario non valido.")
    if parsed.username or parsed.password:
        raise ValueError("L'URL calendario non deve contenere credenziali.")
    if not _host_is_public_calendar_target(parsed.hostname, resolve_dns=resolve_dns):
        raise ValueError("URL calendario non ammesso.")
    return parsed.geturl()


def _content_hash(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


@dataclass
class ProfiloSyncCalendario:
    id: str
    nome: str
    provider: str
    source_url: str
    enabled: bool = True
    import_mode: str = "uid_upsert"
    default_tipo: str = TipoAppuntamento.ALTRO.value
    default_reminder_minuti: int = 60
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)
    last_sync_at: str = ""
    last_status: str = "mai_eseguito"
    last_message: str = ""
    last_created: int = 0
    last_updated: int = 0
    last_skipped: int = 0
    last_conflicts: int = 0
    last_source_hash: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProfiloSyncCalendario":
        payload = dict(data or {})
        fields = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in payload.items() if k in fields})


class GestioneCalendarSync:
    def __init__(self, db_path: str = "./agenda/calendar_sync.json", timeout: int = 20):
        self.db_path = Path(db_path)
        self.timeout = timeout
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._data: Dict[str, Any] = {"profiles": []}
        self._load()

    def _load(self) -> None:
        if not self.db_path.exists():
            return
        try:
            with self.db_path.open(encoding="utf-8") as fh:
                raw = json.load(fh)
            self._data["profiles"] = [
                ProfiloSyncCalendario.from_dict(item).to_dict() for item in (raw.get("profiles") or [])
            ]
        except Exception:
            self._data = {"profiles": []}

    def _save(self) -> None:
        with self.db_path.open("w", encoding="utf-8") as fh:
            json.dump(self._data, fh, ensure_ascii=False, indent=2)

    def list_profiles(self) -> List[Dict[str, Any]]:
        profiles = [dict(item) for item in self._data.get("profiles", [])]
        profiles.sort(key=lambda item: ((not bool(item.get("enabled"))), item.get("nome", "").lower()))
        return profiles

    def get_profile(self, profile_id: str) -> Optional[Dict[str, Any]]:
        return next((dict(item) for item in self._data.get("profiles", []) if item.get("id") == profile_id), None)

    def create_profile(
        self,
        *,
        nome: str,
        provider: str,
        source_url: str,
        default_tipo: str = TipoAppuntamento.ALTRO.value,
        default_reminder_minuti: int = 60,
        enabled: bool = True,
    ) -> Dict[str, Any]:
        normalized_url = _normalize_calendar_url(source_url)
        existing = next(
            (
                dict(item) for item in self._data.get("profiles", [])
                if (item.get("provider") or "").strip() == (provider or "generico").strip()
                and (item.get("source_url") or "").strip() == normalized_url
            ),
            None,
        )
        if existing:
            raise ValueError("Esiste gia un profilo calendario con la stessa sorgente.")
        profile = ProfiloSyncCalendario(
            id=uuid.uuid4().hex[:12],
            nome=(nome or "").strip() or "Calendario esterno",
            provider=(provider or "generico").strip() or "generico",
            source_url=normalized_url,
            default_tipo=(default_tipo or TipoAppuntamento.ALTRO.value),
            default_reminder_minuti=max(int(default_reminder_minuti or 60), 0),
            enabled=bool(enabled),
        )
        self._data.setdefault("profiles", []).append(profile.to_dict())
        self._save()
        return profile.to_dict()

    def update_profile(self, profile_id: str, **fields: Any) -> Dict[str, Any]:
        for item in self._data.get("profiles", []):
            if item.get("id") != profile_id:
                continue
            for key, value in fields.items():
                if key == "source_url":
                    value = _normalize_calendar_url(str(value or ""))
                if key == "default_reminder_minuti":
                    value = max(int(value or 0), 0)
                if key in item:
                    item[key] = value
            item["updated_at"] = _now_iso()
            self._save()
            return dict(item)
        raise KeyError(f"Profilo calendario '{profile_id}' non trovato.")

    def delete_profile(self, profile_id: str) -> None:
        before = len(self._data.get("profiles", []))
        self._data["profiles"] = [item for item in self._data.get("profiles", []) if item.get("id") != profile_id]
        if len(self._data["profiles"]) == before:
            raise KeyError(f"Profilo calendario '{profile_id}' non trovato.")
        self._save()

    def _fetch_remote_ics(
        self,
        source_url: str,
        *,
        request_get: Optional[Callable[..., Any]] = None,
    ) -> Dict[str, Any]:
        url = _validate_remote_calendar_url(
            _normalize_calendar_url(source_url),
            resolve_dns=request_get is None,
        )
        if not url:
            raise ValueError("URL calendario mancante.")
        fetch = request_get or requests.get
        response = None
        for _ in range(4):
            response = fetch(
                url,
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept": "text/calendar,text/plain,application/octet-stream,*/*;q=0.5",
                },
                timeout=self.timeout,
                allow_redirects=False,
            )
            status_code = int(getattr(response, "status_code", 0) or 0)
            if status_code not in {301, 302, 303, 307, 308}:
                break
            location = str((getattr(response, "headers", {}) or {}).get("location", "") or "").strip()
            if not location:
                break
            url = _validate_remote_calendar_url(urljoin(url, location), resolve_dns=request_get is None)
        if response is None:
            raise RuntimeError("Calendario remoto non raggiungibile.")
        status_code = int(getattr(response, "status_code", 0) or 0)
        if status_code >= 400:
            raise RuntimeError(f"HTTP {status_code}")
        raw = bytes(getattr(response, "content", b"") or b"")
        if len(raw) > MAX_ICS_BYTES:
            raise ValueError("Il calendario remoto supera il limite di 5 MB.")
        text = _decode_ics_bytes(raw)
        return {
            "url": str(getattr(response, "url", url) or url),
            "raw": raw,
            "text": text,
            "content_type": str((getattr(response, "headers", {}) or {}).get("content-type", "") or ""),
        }

    def preview_remote_calendar(
        self,
        source_url: str,
        *,
        request_get: Optional[Callable[..., Any]] = None,
    ) -> Dict[str, Any]:
        payload = self._fetch_remote_ics(source_url, request_get=request_get)
        events = parse_ics(payload["text"])
        return {
            "events": events,
            "source_url": payload["url"],
            "source_hash": _content_hash(payload["text"]),
            "content_type": payload["content_type"],
        }

    def sync_profile(
        self,
        profile_id: str,
        *,
        agenda: Agenda,
        request_get: Optional[Callable[..., Any]] = None,
        now: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        profile = self.get_profile(profile_id)
        if not profile:
            raise KeyError(f"Profilo calendario '{profile_id}' non trovato.")
        if not profile.get("enabled", True):
            raise ValueError("Il profilo calendario e disattivato.")

        current_time = now or datetime.now()
        payload = self.preview_remote_calendar(profile["source_url"], request_get=request_get)
        created = 0
        updated = 0
        skipped = 0
        conflicts = 0

        for event in payload["events"]:
            result = agenda.upsert_da_evento_importato(
                event,
                provider=profile.get("provider", "generico"),
                source_url=payload["source_url"],
                profile_id=profile["id"],
                default_tipo=TipoAppuntamento(profile.get("default_tipo", TipoAppuntamento.ALTRO.value)),
                reminder_minuti=int(profile.get("default_reminder_minuti", 60) or 60),
            )
            outcome = result.get("outcome")
            if outcome == "created":
                created += 1
            elif outcome == "updated":
                updated += 1
            elif outcome == "conflict":
                conflicts += 1
            else:
                skipped += 1

        last_message = (
            f"Creati {created}, aggiornati {updated}, saltati {skipped}, conflitti {conflicts}."
        )
        updated_profile = self.update_profile(
            profile_id,
            last_sync_at=_now_iso(current_time),
            last_status="ok",
            last_message=last_message,
            last_created=created,
            last_updated=updated,
            last_skipped=skipped,
            last_conflicts=conflicts,
            last_source_hash=payload["source_hash"],
        )
        return {
            "ok": True,
            "profile": updated_profile,
            "events_total": len(payload["events"]),
            "created": created,
            "updated": updated,
            "skipped": skipped,
            "conflicts": conflicts,
            "source_url": payload["source_url"],
        }

    def mark_sync_error(self, profile_id: str, message: str) -> Dict[str, Any]:
        return self.update_profile(
            profile_id,
            last_sync_at=_now_iso(),
            last_status="errore",
            last_message=str(message or ""),
        )

    def sync_enabled_profiles(
        self,
        *,
        agenda: Agenda,
        request_get: Optional[Callable[..., Any]] = None,
        now: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        results: List[Dict[str, Any]] = []
        ok = 0
        failed = 0
        for profile in self.list_profiles():
            if not profile.get("enabled", True):
                continue
            try:
                report = self.sync_profile(
                    profile["id"],
                    agenda=agenda,
                    request_get=request_get,
                    now=now,
                )
                results.append(report)
                ok += 1
            except Exception as exc:
                self.mark_sync_error(profile["id"], str(exc))
                results.append(
                    {
                        "ok": False,
                        "profile": self.get_profile(profile["id"]),
                        "error": str(exc),
                    }
                )
                failed += 1
        return {
            "ok": failed == 0,
            "processed": ok + failed,
            "successful": ok,
            "failed": failed,
            "results": results,
        }
