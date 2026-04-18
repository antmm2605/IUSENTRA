from __future__ import annotations

import json
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from pct import cache as _cache
from pct.agenda import Agenda, StatoAppuntamento
from pct.calendar_sync import GestioneCalendarSync
from pct.fascicoli import Fascicolo, GestioneFascicoli, StatoFascicolo, TipoFascicolo
from pct.giurisprudenza import GestioneGiurisprudenza
from pct.postgres_runtime_support import resolve_runtime_postgres_dsn
from pct.scadenziario import GestioneScadenziario, RegolaCalendario, Scadenza
from pct.workspace_intelligence_repository import (
    WorkspaceIntelligenceRepository,
    derive_workspace_intelligence_repository_db_path,
)


FONTI_CALCOLO_PROCESSUALE: List[Dict[str, str]] = [
    {
        "id": "cpc_155",
        "label": "Art. 155 c.p.c.",
        "url": "https://www.normattiva.it/eli/id/1940/10/28/040U1443/CONSOLIDATED/",
        "note": "Computo dei termini, esclusione del dies a quo e proroga del giorno finale non utile.",
    },
    {
        "id": "feriale_742_1969",
        "label": "Legge n. 742/1969",
        "url": "https://www.normattiva.it/eli/id/1969/11/06/069U0742/CONSOLIDATED/20241015",
        "note": "Sospensione feriale dei termini processuali, applicata solo ai profili che la prevedono.",
    },
    {
        "id": "uffici_giustizia_map",
        "label": "Giustizia Map e avvisi uffici",
        "url": "https://www.giustizia.it/resources/cms/documents/sito_giustizia2.pdf",
        "note": "Base ufficiale per presidiare uffici giudiziari, festivita locali e avvisi di operativita.",
    },
]


def _parse_date(value: str) -> Optional[date]:
    text = str(value or "").strip()
    if not text:
        return None
    for sample in (text[:10], text[:19], text):
        try:
            return datetime.fromisoformat(sample).date()
        except ValueError:
            continue
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _parse_datetime(value: str) -> Optional[datetime]:
    text = str(value or "").strip()
    if not text:
        return None
    for sample in (text[:19], text):
        try:
            return datetime.fromisoformat(sample)
        except ValueError:
            continue
    return None


def _unique_strings(values: Iterable[str]) -> List[str]:
    out: List[str] = []
    seen: set[str] = set()
    for value in values:
        item = str(value or "").strip()
        if not item:
            continue
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def _truncate(text: str, limit: int = 180) -> str:
    raw = " ".join(str(text or "").split())
    if len(raw) <= limit:
        return raw
    return raw[: limit - 1].rstrip() + "…"


def _provider_label(provider: str) -> str:
    mapping = {
        "google": "Google Calendar",
        "google_calendar": "Google Calendar",
        "outlook": "Microsoft Outlook",
        "apple": "Apple Calendar",
        "icloud": "Apple Calendar",
        "webcal": "Calendario WebCal",
        "generico": "Calendario esterno",
    }
    key = str(provider or "").strip().lower()
    return mapping.get(key, str(provider or "Calendario esterno").replace("_", " ").title())


def _fascicolo_area_hint(fascicolo: Fascicolo) -> str:
    mapping = {
        TipoFascicolo.CIVILE.value: "Civile",
        TipoFascicolo.PENALE.value: "Penale",
        TipoFascicolo.AMMINISTRATIVO.value: "Amministrativo",
        TipoFascicolo.TRIBUTARIO.value: "Tributario",
        TipoFascicolo.LAVORO.value: "Lavoro e previdenza",
        TipoFascicolo.FAMIGLIA.value: "Civile",
        TipoFascicolo.SUCCESSIONI.value: "Civile",
    }
    return mapping.get(getattr(fascicolo.tipo, "value", ""), "")


def _extract_keywords(fascicolo: Fascicolo) -> List[str]:
    bag = " ".join(
        [
            fascicolo.titolo,
            fascicolo.oggetto,
            fascicolo.controparte,
            fascicolo.numero_rg,
            fascicolo.tribunale,
        ]
    ).lower()
    seeds = [
        "decreto ingiuntivo",
        "opposizione",
        "locazione",
        "sfratto",
        "appalto",
        "responsabilita medica",
        "responsabilita civile",
        "licenziamento",
        "lavoro",
        "cassazione",
        "appello",
        "pignoramento",
        "precetto",
        "separazione",
        "divorzio",
        "tributario",
        "cartella",
        "accesso agli atti",
        "appalti",
        "urbanistica",
        "cautelare",
        "esecuzione",
        "societario",
    ]
    return [seed for seed in seeds if seed in bag]


class WorkspaceIntelligenteService:
    def __init__(
        self,
        *,
        agenda: Agenda,
        scadenziario: GestioneScadenziario,
        fascicoli: GestioneFascicoli,
        calendar_sync: Optional[GestioneCalendarSync] = None,
        giurisprudenza: Optional[GestioneGiurisprudenza] = None,
        studio_patron_rule: Optional[RegolaCalendario] = None,
        snapshot_path: str = "",
        postgres_dsn: str = "",
    ) -> None:
        self.agenda = agenda
        self.scadenziario = scadenziario
        self.fascicoli = fascicoli
        self.calendar_sync = calendar_sync
        self.giurisprudenza = giurisprudenza
        self.studio_patron_rule = studio_patron_rule
        self.snapshot_path = str(snapshot_path or "").strip()
        self.postgres_dsn = resolve_runtime_postgres_dsn(postgres_dsn)
        self._snapshot_repository = (
            WorkspaceIntelligenceRepository(
                derive_workspace_intelligence_repository_db_path(self.snapshot_path),
                postgres_dsn=self.postgres_dsn,
            )
            if self.snapshot_path
            else None
        )

    def _appointments_upcoming(self, horizon_days: int = 7, limit: int = 10) -> List[Any]:
        now = datetime.now()
        until = now + timedelta(days=max(int(horizon_days or 7), 1))
        rows = [
            item
            for item in self.agenda.tutti()
            if item.stato not in (StatoAppuntamento.ANNULLATO, StatoAppuntamento.COMPLETATO)
            and now <= item.data_ora_dt <= until
        ]
        rows.sort(key=lambda item: item.data_ora_dt)
        return rows[:limit]

    def _sync_profiles_status(self) -> List[Dict[str, Any]]:
        if not self.calendar_sync:
            return []
        profiles = self.calendar_sync.list_profiles()
        now = datetime.now()
        out: List[Dict[str, Any]] = []
        for profile in profiles:
            last_sync_at = _parse_datetime(profile.get("last_sync_at", ""))
            hours_since = None
            if last_sync_at:
                hours_since = max(int((now - last_sync_at).total_seconds() // 3600), 0)
            status = profile.get("last_status") or "mai_eseguito"
            tone = "secondary"
            label = "Mai sincronizzato"
            if not profile.get("enabled", True):
                tone = "secondary"
                label = "Disattivato"
            elif status == "ok" and last_sync_at and (now - last_sync_at) <= timedelta(hours=2):
                tone = "success"
                label = "Allineato"
            elif status == "ok":
                tone = "warning"
                label = "Da aggiornare"
            else:
                tone = "danger"
                label = "Da verificare"
            out.append(
                {
                    **profile,
                    "provider_label": _provider_label(profile.get("provider", "")),
                    "status_label": label,
                    "status_tone": tone,
                    "hours_since": hours_since,
                    "is_stale": bool(profile.get("enabled", True) and tone != "success"),
                }
            )
        out.sort(
            key=lambda row: (
                not bool(row.get("enabled", True)),
                row.get("status_tone") == "success",
                row.get("nome", "").lower(),
            )
        )
        return out

    def _giurisprudenza_per_fascicolo(self, fascicolo: Fascicolo, limit: int = 5) -> List[Dict[str, Any]]:
        if not self.giurisprudenza:
            return []

        direct: List[Dict[str, Any]] = []
        direct_keys = {
            fascicolo.id.lower(),
            str(fascicolo.numero or "").lower(),
            str(getattr(fascicolo, "rg_completo", "") or "").lower(),
        }
        for row in self.giurisprudenza.cerca():
            linked = {str(item or "").strip().lower() for item in (row.get("fascicoli_collegati") or [])}
            if direct_keys & linked:
                direct.append(row)
        if direct:
            direct.sort(key=lambda row: row.get("data_deposito", ""), reverse=True)
            return direct[:limit]

        area_hint = _fascicolo_area_hint(fascicolo)
        keywords = _extract_keywords(fascicolo)
        queries = keywords or [token for token in [fascicolo.oggetto, fascicolo.titolo] if token]

        seen: set[str] = set()
        suggestions: List[Dict[str, Any]] = []
        for query in queries[:3]:
            matches = self.giurisprudenza.cerca(
                q=str(query or "").strip(),
                area=area_hint,
            )
            for row in matches:
                row_id = str(row.get("id", ""))
                if not row_id or row_id in seen:
                    continue
                seen.add(row_id)
                suggestions.append(row)
                if len(suggestions) >= limit:
                    return suggestions
        return suggestions[:limit]

    def _next_actions_for_fascicolo(
        self,
        fascicolo: Fascicolo,
        deadlines: List[Scadenza],
        appointments: List[Any],
        judgments: List[Dict[str, Any]],
    ) -> List[str]:
        actions: List[str] = []
        if deadlines:
            first = deadlines[0]
            days = first.giorni_alla_scadenza
            if days is not None and days <= 3:
                actions.append(f"Preparare subito l'adempimento '{first.titolo}' e verificare firma o allegati.")
            elif days is not None and days <= 7:
                actions.append(f"Pianificare entro oggi la lavorazione di '{first.titolo}'.")
        else:
            actions.append("Valutare se manca una scadenza processuale da presidiare nel fascicolo.")

        if appointments:
            first_app = appointments[0]
            actions.append(f"Confermare agenda e note operative per '{first_app.titolo}'.")
        elif fascicolo.stato in (StatoFascicolo.APERTO, StatoFascicolo.IN_CORSO):
            actions.append("Valutare un appuntamento cliente o una riunione di preparazione.")

        if not judgments:
            actions.append("Avviare una ricerca giurisprudenziale mirata collegata all'oggetto della pratica.")
        else:
            actions.append("Selezionare le sentenze piu forti e collegarle all'atto o all'udienza.")

        return actions[:3]

    def _fascicoli_hot(self, horizon_days: int = 14, limit: int = 8) -> List[Dict[str, Any]]:
        fascicoli = self.fascicoli.tutti()
        deadlines = self.scadenziario.tutte(solo_aperte=True)
        deadlines_by_fascicolo: Dict[str, List[Scadenza]] = defaultdict(list)
        for deadline in deadlines:
            if deadline.id_fascicolo:
                deadlines_by_fascicolo[deadline.id_fascicolo].append(deadline)
        for items in deadlines_by_fascicolo.values():
            items.sort(key=lambda row: row.data_scadenza or "9999-12-31")

        appointments = self._appointments_upcoming(horizon_days=horizon_days, limit=200)
        appointments_by_fascicolo: Dict[str, List[Any]] = defaultdict(list)
        for item in appointments:
            procedimento = str(getattr(item, "procedimento", "") or "").strip().lower()
            for fascicolo in fascicoli:
                if item.id_cliente and fascicolo.id_cliente and item.id_cliente == fascicolo.id_cliente:
                    appointments_by_fascicolo[fascicolo.id].append(item)
                    continue
                if procedimento and (
                    procedimento == str(fascicolo.numero).strip().lower()
                    or procedimento == str(getattr(fascicolo, "rg_completo", "") or "").strip().lower()
                    or procedimento in str(fascicolo.titolo or "").strip().lower()
                ):
                    appointments_by_fascicolo[fascicolo.id].append(item)
        hot: List[Dict[str, Any]] = []
        for fascicolo in fascicoli:
            fasc_deadlines = deadlines_by_fascicolo.get(fascicolo.id, [])
            fasc_apps = appointments_by_fascicolo.get(fascicolo.id, [])
            judgments = self._giurisprudenza_per_fascicolo(fascicolo, limit=3)
            score = 0
            if fasc_deadlines:
                first_deadline = fasc_deadlines[0]
                days = first_deadline.giorni_alla_scadenza
                if days is not None:
                    if days <= 3:
                        score += 60
                    elif days <= 7:
                        score += 40
                    elif days <= horizon_days:
                        score += 20
            if fasc_apps:
                first_app = fasc_apps[0]
                days_to_app = (first_app.data_ora_dt.date() - date.today()).days
                if days_to_app <= 2:
                    score += 30
                elif days_to_app <= 7:
                    score += 15
            if fascicolo.stato == StatoFascicolo.IN_CORSO:
                score += 10
            if not fasc_deadlines and fascicolo.stato in (StatoFascicolo.APERTO, StatoFascicolo.IN_CORSO):
                score += 5
            if not judgments:
                score += 4
            if not score:
                continue
            hot.append(
                {
                    "id": fascicolo.id,
                    "numero": fascicolo.numero,
                    "rg_completo": getattr(fascicolo, "rg_completo", "") or "",
                    "titolo": fascicolo.titolo,
                    "tipo": getattr(fascicolo.tipo, "value", ""),
                    "stato": getattr(fascicolo.stato, "value", ""),
                    "tribunale": fascicolo.tribunale,
                    "score": score,
                    "scadenze": fasc_deadlines[:3],
                    "appuntamenti": fasc_apps[:2],
                    "giurisprudenza": judgments,
                    "azioni": self._next_actions_for_fascicolo(fascicolo, fasc_deadlines[:3], fasc_apps[:2], judgments),
                }
            )
        hot.sort(
            key=lambda row: (
                -int(row.get("score", 0)),
                (row.get("scadenze") or [{}])[0].data_scadenza if row.get("scadenze") else "9999-12-31",
            )
        )
        return hot[:limit]

    def panoramica(self, *, horizon_days: int = 14, hot_limit: int = 8) -> Dict[str, Any]:
        urgent_deadlines = self.scadenziario.imminenti(entro_giorni=3)
        horizon_deadlines = self.scadenziario.imminenti(entro_giorni=horizon_days)
        appointments = self._appointments_upcoming(horizon_days=horizon_days, limit=12)
        sync_profiles = self._sync_profiles_status()
        fascicoli_hot = self._fascicoli_hot(horizon_days=horizon_days, limit=hot_limit)
        due_notifications = self.scadenziario.scadenze_da_notificare()
        reminders = self.agenda.prossimi_reminder(entro_minuti=180)

        office_sources = []
        seen_sources: set[str] = set()
        for deadline in horizon_deadlines:
            key = f"{deadline.judicial_office_name}|{deadline.judicial_office_source_url}|{deadline.judicial_office_patron_day}|{deadline.judicial_office_patron_month}"
            if not deadline.judicial_office_name or key in seen_sources:
                continue
            seen_sources.add(key)
            office_sources.append(
                {
                    "office_name": deadline.judicial_office_name,
                    "office_type": deadline.judicial_office_type,
                    "city": deadline.judicial_office_city,
                    "patron_name": deadline.judicial_office_patron_name,
                    "patron_day": deadline.judicial_office_patron_day,
                    "patron_month": deadline.judicial_office_patron_month,
                    "operating_mode": deadline.office_mode_on_legal_due_date or deadline.judicial_office_operating_mode,
                    "source_url": deadline.judicial_office_source_url,
                    "verified_at": deadline.judicial_office_verified_at,
                }
            )

        studio_patron = None
        if self.studio_patron_rule:
            studio_patron = {
                "label": self.studio_patron_rule.label,
                "patron_name": self.studio_patron_rule.label.replace("Santo patrono studio - ", ""),
                "day": self.studio_patron_rule.day_num,
                "month": self.studio_patron_rule.month_num,
                "source_url": self.studio_patron_rule.source_url,
                "verified_at": self.studio_patron_rule.verified_at,
            }

        actions: List[Dict[str, str]] = []
        if urgent_deadlines:
            actions.append(
                {
                    "tone": "danger",
                    "title": "Presidiare le scadenze urgenti",
                    "description": f"{len(urgent_deadlines)} termini entro 3 giorni da verificare o depositare.",
                    "href": "/scadenziario",
                }
            )
        if reminders:
            actions.append(
                {
                    "tone": "warning",
                    "title": "Confermare promemoria imminenti",
                    "description": f"{len(reminders)} appuntamenti hanno un reminder nelle prossime 3 ore.",
                    "href": "/agenda",
                }
            )
        if any(profile.get("is_stale") for profile in sync_profiles):
            actions.append(
                {
                    "tone": "primary",
                    "title": "Allineare i calendari esterni",
                    "description": "Almeno un profilo Google, Outlook o WebCal richiede verifica o refresh.",
                    "href": "/impostazioni/calendario",
                }
            )
        if fascicoli_hot:
            actions.append(
                {
                    "tone": "secondary",
                    "title": "Lavorare sui fascicoli attenzionati",
                    "description": f"{len(fascicoli_hot)} pratiche hanno scadenze, udienze o ricerche da presidiare.",
                    "href": f"/fascicoli/{fascicoli_hot[0]['id']}",
                }
            )

        return {
            "generated_at": datetime.now().replace(microsecond=0).isoformat(),
            "summary": {
                "scadenze_urgenti": len(urgent_deadlines),
                "scadenze_orizzonte": len(horizon_deadlines),
                "appuntamenti_orizzonte": len(appointments),
                "profili_sync_attivi": len([profile for profile in sync_profiles if profile.get("enabled", True)]),
                "profili_sync_da_verificare": len([profile for profile in sync_profiles if profile.get("is_stale")]),
                "fascicoli_attenzionati": len(fascicoli_hot),
                "promemoria_imminenti": len(reminders),
                "notifiche_scadenze": len(due_notifications),
            },
            "actions": actions[:4],
            "urgent_deadlines": urgent_deadlines[:6],
            "upcoming_deadlines": horizon_deadlines[:8],
            "upcoming_appointments": appointments[:8],
            "sync_profiles": sync_profiles,
            "fascicoli_hot": fascicoli_hot,
            "fonti_calcolo": list(FONTI_CALCOLO_PROCESSUALE),
            "uffici_monitorati": office_sources[:8],
            "studio_patron": studio_patron,
        }

    def per_fascicolo(
        self,
        fascicolo: Fascicolo,
        *,
        apps: Optional[List[Any]] = None,
        scadenze: Optional[List[Scadenza]] = None,
        judgments_limit: int = 5,
    ) -> Dict[str, Any]:
        fasc_deadlines = list(scadenze or [])
        if not fasc_deadlines:
            fasc_deadlines = self.scadenziario.tutte(id_fascicolo=fascicolo.id, solo_aperte=True)
        fasc_deadlines.sort(key=lambda row: row.data_scadenza or "9999-12-31")

        fasc_apps = list(apps or [])
        if not fasc_apps:
            fasc_apps = [
                item
                for item in self._appointments_upcoming(horizon_days=30, limit=200)
                if item.id_cliente and fascicolo.id_cliente and item.id_cliente == fascicolo.id_cliente
            ]
        fasc_apps.sort(key=lambda row: row.data_ora)

        judgments = self._giurisprudenza_per_fascicolo(fascicolo, limit=judgments_limit)
        office_sources = _unique_strings(
            deadline.judicial_office_source_url
            for deadline in fasc_deadlines
            if deadline.judicial_office_source_url
        )
        return {
            "next_actions": self._next_actions_for_fascicolo(fascicolo, fasc_deadlines[:3], fasc_apps[:2], judgments),
            "scadenze": fasc_deadlines[:4],
            "appuntamenti": fasc_apps[:3],
            "giurisprudenza": judgments,
            "area_hint": _fascicolo_area_hint(fascicolo),
            "keywords": _extract_keywords(fascicolo),
            "office_sources": office_sources,
            "has_items": bool(fasc_deadlines or fasc_apps or judgments),
        }

    def save_snapshot(self, path: str, overview: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        payload = {
            "generated_at": datetime.now().replace(microsecond=0).isoformat(),
            "overview": overview or self.panoramica(),
        }
        if self._snapshot_repository is not None:
            self._snapshot_repository.save_snapshot(payload)
        _cache.save(path, payload, indent=2)
        return payload

    @staticmethod
    def load_snapshot(path: str, *, postgres_dsn: str = "") -> Dict[str, Any]:
        resolved_dsn = resolve_runtime_postgres_dsn(postgres_dsn)
        if resolved_dsn:
            repository = WorkspaceIntelligenceRepository(
                derive_workspace_intelligence_repository_db_path(path),
                postgres_dsn=resolved_dsn,
            )
            snapshot = repository.load_snapshot()
            if snapshot.get("generated_at") or snapshot.get("overview"):
                return snapshot
        return _cache.load(path, default={"generated_at": "", "overview": {}}) or {
            "generated_at": "",
            "overview": {},
        }
