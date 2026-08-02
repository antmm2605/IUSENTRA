from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional
from zoneinfo import ZoneInfo

from pct import cache as _cache
from pct.agenda import Agenda, Appuntamento, StatoAppuntamento
from pct.calendar_sync import GestioneCalendarSync
from pct.fascicoli import Fascicolo, GestioneFascicoli, StatoFascicolo, TipoDocumento, TipoFascicolo
from pct.fascicolo_document_presidio import duplicate_practice_groups
from pct.giurisprudenza import GestioneGiurisprudenza
from pct.postgres_runtime_support import resolve_runtime_postgres_dsn
from pct.scadenziario import GestioneScadenziario, RegolaCalendario, Scadenza
from pct.workspace_intelligence_repository import (
    WorkspaceIntelligenceRepository,
    derive_workspace_intelligence_repository_db_path,
)


ROME_TZ = ZoneInfo("Europe/Rome")


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


def _local_now() -> datetime:
    return datetime.now(ROME_TZ).replace(tzinfo=None)


def _local_naive_datetime(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value or "").strip()
        if not text:
            return None
        parsed = None
        for sample in (text.replace("Z", "+00:00"), text[:19], text[:10]):
            try:
                parsed = datetime.fromisoformat(sample)
                break
            except ValueError:
                continue
        if parsed is None:
            return None
    if parsed.tzinfo is not None:
        return parsed.astimezone(ROME_TZ).replace(tzinfo=None)
    return parsed


def _parse_datetime(value: str) -> Optional[datetime]:
    text = str(value or "").strip()
    if not text:
        return None
    return _local_naive_datetime(text)


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


def _enum_value(value: Any) -> Any:
    return getattr(value, "value", value)


def _snapshot_appuntamento(item: Appuntamento) -> Dict[str, Any]:
    return {
        "id": item.id,
        "titolo": _truncate(item.titolo, 180),
        "tipo": _enum_value(item.tipo),
        "stato": _enum_value(item.stato),
        "data_ora": item.data_ora,
        "fine": item.fine_dt.isoformat(timespec="seconds"),
        "durata_minuti": item.durata_minuti,
        "luogo": _truncate(item.luogo, 140),
        "cliente": _truncate(item.cliente, 140),
        "procedimento": _truncate(item.procedimento, 120),
        "tribunale": _truncate(item.tribunale, 120),
        "hearing_mode": _truncate(item.hearing_mode, 80),
        "remote_hearing_detected": bool(item.remote_hearing_detected),
        "remote_hearing_mode": _truncate(item.remote_hearing_mode, 80),
        "remote_hearing_verified": bool(item.remote_hearing_verified),
        "remote_hearing_platform": _truncate(item.remote_hearing_platform, 80),
    }


def _snapshot_scadenza(item: Scadenza) -> Dict[str, Any]:
    return {
        "id": item.id,
        "id_fascicolo": item.id_fascicolo,
        "titolo": _truncate(item.titolo, 180),
        "tipo": _enum_value(item.tipo),
        "priorita": _enum_value(item.priorita),
        "stato": _enum_value(item.stato),
        "data_scadenza": item.data_scadenza,
        "legal_due_at": item.legal_due_at,
        "operational_due_at": item.operational_due_at,
        "giorni_alla_scadenza": item.giorni_alla_scadenza,
        "perentorio": bool(item.perentorio),
        "deadline_profile_code": item.deadline_profile_code,
        "judicial_office_name": _truncate(item.judicial_office_name, 140),
        "judicial_office_type": _truncate(item.judicial_office_type, 80),
        "judicial_office_city": _truncate(item.judicial_office_city, 80),
        "office_mode_on_legal_due_date": item.office_mode_on_legal_due_date,
        "source_event_type": item.source_event_type,
        "source_event_type_label": item.source_event_type_label,
    }


def _snapshot_safe_value(value: Any) -> Any:
    if isinstance(value, Appuntamento):
        return _snapshot_appuntamento(value)
    if isinstance(value, Scadenza):
        return _snapshot_scadenza(value)
    if isinstance(value, dict):
        return {str(key): _snapshot_safe_value(child) for key, child in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_snapshot_safe_value(child) for child in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if hasattr(value, "value"):
        return value.value
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "id") and hasattr(value, "titolo"):
        return {
            "id": str(getattr(value, "id", "") or ""),
            "titolo": _truncate(str(getattr(value, "titolo", "") or ""), 180),
        }
    return _truncate(str(value), 240)


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


def _documento_tipo_value(documento: Any) -> str:
    return str(getattr(getattr(documento, "tipo", ""), "value", getattr(documento, "tipo", "")) or "").strip().upper()


def _documento_classificazione_ufficiale(documento: Any) -> str:
    return str(
        getattr(documento, "classificazione_portale", "")
        or getattr(documento, "tipo_atto_portale", "")
        or getattr(documento, "nome_portale", "")
        or _documento_tipo_value(documento).replace("_", " ")
    ).strip()


def _documento_e_provvedimento(documento: Any) -> bool:
    return _documento_tipo_value(documento) in {
        TipoDocumento.SENTENZA.value,
        TipoDocumento.ORDINANZA.value,
        TipoDocumento.DECRETO.value,
        TipoDocumento.VERBALE.value,
    }


def _documento_e_provvedimento_finale(documento: Any) -> bool:
    tipo = _documento_tipo_value(documento)
    testo = " ".join(
        [
            tipo,
            str(getattr(documento, "classificazione_portale", "") or ""),
            str(getattr(documento, "tipo_atto_portale", "") or ""),
            str(getattr(documento, "nome_portale", "") or ""),
            str(getattr(documento, "nome", "") or ""),
        ]
    ).lower()
    if tipo == TipoDocumento.SENTENZA.value:
        return True
    return tipo in {TipoDocumento.ORDINANZA.value, TipoDocumento.DECRETO.value} and any(
        token in testo for token in ("definitiv", "estin", "chius", "provvedimento finale")
    )


def _documento_sort_date(documento: Any) -> str:
    return str(
        getattr(documento, "data_deposito_portale", "")
        or getattr(documento, "data_documento", "")
        or getattr(documento, "data_caricamento", "")
        or ""
    )[:10]


def _normalizza_chiave_presidio(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _stato_fascicolo_chiuso(fascicolo: Fascicolo) -> bool:
    stato = getattr(fascicolo, "stato", "")
    if stato in {StatoFascicolo.DEFINITO, StatoFascicolo.ARCHIVIATO}:
        return True
    stato_value = str(getattr(stato, "value", stato) or "").strip().upper()
    return stato_value in {"DEFINITO", "ARCHIVIATO", "STATOFASCICOLO.DEFINITO", "STATOFASCICOLO.ARCHIVIATO"}


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
        now = _local_now()
        until = now + timedelta(days=max(int(horizon_days or 7), 1))
        rows: List[tuple[datetime, Any]] = []
        for item in self.agenda.tutti():
            if item.stato in (StatoAppuntamento.ANNULLATO, StatoAppuntamento.COMPLETATO):
                continue
            starts_at = _local_naive_datetime(getattr(item, "data_ora", ""))
            if starts_at and now <= starts_at <= until:
                rows.append((starts_at, item))
        rows.sort(key=lambda row: row[0])
        return [item for _, item in rows[:limit]]

    def _sync_profiles_status(self) -> List[Dict[str, Any]]:
        if not self.calendar_sync:
            return []
        profiles = self.calendar_sync.list_profiles()
        now = _local_now()
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

    def _giurisprudenza_diretta_per_fascicoli(
        self,
        fascicoli: Iterable[Fascicolo],
        *,
        limit_per_fascicolo: int = 3,
    ) -> Dict[str, List[Dict[str, Any]]]:
        if not self.giurisprudenza:
            return {}

        lookup: Dict[str, set[str]] = defaultdict(set)
        for fascicolo in fascicoli:
            for raw_key in (
                getattr(fascicolo, "id", ""),
                getattr(fascicolo, "numero", ""),
                getattr(fascicolo, "rg_completo", ""),
            ):
                key = str(raw_key or "").strip().lower()
                if key:
                    lookup[key].add(fascicolo.id)
        if not lookup:
            return {}

        try:
            rows = self.giurisprudenza.cerca()
        except Exception:
            return {}

        out: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        seen: Dict[str, set[str]] = defaultdict(set)
        for row in rows:
            row_id = str(row.get("id", "") or "").strip()
            if not row_id:
                continue
            linked_keys = {
                str(item or "").strip().lower()
                for item in (row.get("fascicoli_collegati") or [])
                if str(item or "").strip()
            }
            if not linked_keys:
                continue
            for key in linked_keys:
                for fascicolo_id in lookup.get(key, set()):
                    if len(out[fascicolo_id]) >= limit_per_fascicolo or row_id in seen[fascicolo_id]:
                        continue
                    out[fascicolo_id].append(row)
                    seen[fascicolo_id].add(row_id)
        return dict(out)

    @staticmethod
    def _scadenze_operative_fascicolo(scadenze: List[Scadenza]) -> dict[str, List[Scadenza]]:
        aperte = [
            row
            for row in (scadenze or [])
            if getattr(getattr(row, "stato", ""), "value", getattr(row, "stato", "")) not in {"COMPLETATO", "ANNULLATO"}
        ]
        aperte.sort(key=lambda row: row.data_scadenza or "9999-12-31")
        future = [row for row in aperte if (row.giorni_alla_scadenza or 0) >= 0]
        overdue = [row for row in aperte if row.giorni_alla_scadenza is not None and row.giorni_alla_scadenza < 0]
        return {
            "aperte": aperte,
            "future": future,
            "scadute": overdue,
        }

    @staticmethod
    def _date_udienza_fascicolo(fascicolo: Fascicolo, apps: List[Any]) -> dict[str, Any]:
        candidati: list[date] = []
        for raw_value in (
            getattr(fascicolo, "data_prossima_udienza", ""),
            getattr(fascicolo, "data_prima_udienza", ""),
        ):
            parsed = _parse_date(str(raw_value or ""))
            if parsed:
                candidati.append(parsed)
        for item in apps or []:
            titolo = str(getattr(item, "titolo", "") or "").lower()
            if "udienza" not in titolo:
                continue
            parsed = _parse_date(str(getattr(item, "data_ora", "") or getattr(item, "data_ora_dt", "") or ""))
            if parsed:
                candidati.append(parsed)
        unique_dates = sorted({giorno.isoformat(): giorno for giorno in candidati}.values())
        today = date.today()
        future = [giorno for giorno in unique_dates if giorno >= today]
        past = [giorno for giorno in unique_dates if giorno < today]
        return {
            "future": future[0] if future else None,
            "last_past": past[-1] if past else None,
            "all": unique_dates,
        }

    @staticmethod
    def _provvedimenti_fascicolo(fascicolo: Fascicolo, limit: int = 5) -> List[Dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[tuple[str, str, str]] = set()
        for doc in getattr(fascicolo, "documenti", []) or []:
            if not _documento_e_provvedimento(doc):
                continue
            row = {
                "id_doc": getattr(doc, "id", ""),
                "titolo": str(getattr(doc, "nome_portale", "") or getattr(doc, "nome", "")).strip(),
                "classificazione": _documento_classificazione_ufficiale(doc),
                "data": _documento_sort_date(doc),
                "finale": _documento_e_provvedimento_finale(doc),
                "fonte": str(
                    getattr(doc, "servizio_portale", "")
                    or getattr(doc, "fonte_documento", "")
                    or "fascicolo"
                ).strip(),
            }
            dedup_key = (
                _normalizza_chiave_presidio(row["titolo"]),
                _normalizza_chiave_presidio(row["classificazione"]),
                _normalizza_chiave_presidio(row["data"]),
            )
            if dedup_key in seen:
                continue
            seen.add(dedup_key)
            rows.append(row)
        rows.sort(key=lambda row: (row.get("data", ""), row.get("titolo", "")), reverse=True)
        return rows[:limit]

    def _presidio_documentale_fascicolo(self, fascicolo: Fascicolo) -> dict[str, Any]:
        documenti = list(getattr(fascicolo, "documenti", []) or [])
        portale_docs = [
            doc
            for doc in documenti
            if getattr(doc, "id_deposito_pct", "") or getattr(doc, "fonte_documento", "") == "PORTALE_TELEMATICO"
        ]
        metadati_mancanti = [
            doc
            for doc in portale_docs
            if not any(
                str(getattr(doc, field_name, "") or "").strip()
                for field_name in ("classificazione_portale", "tipo_atto_portale", "id_documento_portale")
            )
        ]
        return {
            "documenti_totali": len(documenti),
            "documenti_portale": len(portale_docs),
            "documenti_portale_allineati": len(portale_docs) - len(metadati_mancanti),
            "documenti_portale_mancanti": len(metadati_mancanti),
            "metadati_mancanti": metadati_mancanti[:5],
            "provvedimenti": self._provvedimenti_fascicolo(fascicolo),
            "ha_provvedimento_finale": any(_documento_e_provvedimento_finale(doc) for doc in documenti),
        }

    def _presidio_fascicolo(
        self,
        fascicolo: Fascicolo,
        deadlines: List[Scadenza],
        appointments: List[Any],
        judgments: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        scadenze = self._scadenze_operative_fascicolo(deadlines)
        udienze = self._date_udienza_fascicolo(fascicolo, appointments)
        documenti = self._presidio_documentale_fascicolo(fascicolo)
        stato_chiusura = _stato_fascicolo_chiuso(fascicolo)
        anagrafica_ok = bool(
            (getattr(fascicolo, "id_cliente", "") or getattr(fascicolo, "nome_cliente", ""))
            and getattr(fascicolo, "tribunale", "")
            and getattr(fascicolo, "numero_rg", "")
            and getattr(fascicolo, "anno_rg", 0)
        )
        documenti_ok = documenti["documenti_totali"] > 0
        portale_ok = documenti["documenti_portale"] == 0 or documenti["documenti_portale_mancanti"] == 0
        udienza_passata_non_allineata = bool(
            udienze["last_past"]
            and not udienze["future"]
            and not documenti["ha_provvedimento_finale"]
            and not stato_chiusura
        )
        calendario_ok = not scadenze["scadute"] and not udienza_passata_non_allineata
        stato_pratica_ok = not (documenti["ha_provvedimento_finale"] and not stato_chiusura)
        checks = [
            {
                "label": "Anagrafica pratica completa",
                "ok": anagrafica_ok,
                "note": "Cliente, RG e tribunale presenti." if anagrafica_ok else "Completare cliente, RG o tribunale.",
            },
            {
                "label": "Documenti fascicolo disponibili",
                "ok": documenti_ok,
                "note": (
                    f"{documenti['documenti_totali']} documenti presenti."
                    if documenti_ok
                    else "Manca almeno un documento operativo."
                ),
            },
            {
                "label": "Metadati ufficiali del portale",
                "ok": portale_ok,
                "note": (
                    "Classificazioni ufficiali allineate."
                    if portale_ok
                    else f"{documenti['documenti_portale_mancanti']} documenti da riallineare."
                ),
            },
            {
                "label": "Scadenze e udienze coerenti con oggi",
                "ok": calendario_ok,
                "note": (
                    "Nessuna scadenza aperta scaduta."
                    if calendario_ok
                    else "Sono presenti scadenze scadute o udienze storiche ancora aperte."
                ),
            },
            {
                "label": "Stato pratica coerente con gli atti",
                "ok": stato_pratica_ok,
                "note": (
                    "Lo stato e' coerente con i provvedimenti presenti."
                    if stato_pratica_ok
                    else "E' presente un provvedimento finale ma la pratica non risulta definita."
                ),
            },
        ]
        completed = sum(1 for item in checks if item["ok"])
        progress = int(round((completed / len(checks)) * 100)) if checks else 0

        tone = "secondary"
        summary = "Pratica da riallineare"
        hero_note = "Controlli reali eseguiti su documenti, scadenze, udienze e stato della pratica."
        if scadenze["scadute"]:
            tone = "danger"
            first = scadenze["scadute"][0]
            summary = "Presidio urgente richiesto"
            hero_note = f"La scadenza '{first.titolo}' risulta scaduta e va chiusa o riallineata."
        elif udienza_passata_non_allineata:
            tone = "warning"
            summary = "Udienza storica da storicizzare"
            hero_note = "E' presente un'udienza gia' trascorsa ma la pratica non risulta ancora riallineata."
        elif not portale_ok:
            tone = "warning"
            summary = "Metadati ufficiali da completare"
            hero_note = "I documenti scaricati dal portale devono riportare classificazione e identificativi ufficiali."
        elif not stato_pratica_ok:
            tone = "primary"
            summary = "Provvedimento finale presente"
            hero_note = "Gli atti mostrano una chiusura sostanziale: aggiorna definizione, incasso e archivio."
        elif stato_chiusura and progress == 100:
            tone = "success"
            summary = "Pratica chiusa e coerente"
            hero_note = "Il fascicolo e' definito e non emergono disallineamenti operativi residui."
        elif progress >= 80:
            tone = "success"
            summary = "Pratica presidiata"
            hero_note = "Il fascicolo e' allineato sulle evidenze operative correnti."

        return {
            "progress_percent": progress,
            "tone": tone,
            "summary": summary,
            "hero_note": hero_note,
            "checks": checks,
            "scadenze_future": scadenze["future"][:4],
            "scadenze_scadute": scadenze["scadute"][:4],
            "udienza_futura": udienze["future"].isoformat() if udienze["future"] else "",
            "udienza_passata": udienze["last_past"].isoformat() if udienze["last_past"] else "",
            "documentale": documenti,
            "stato_chiusura": stato_chiusura,
            "ha_giurisprudenza": bool(judgments),
            "udienza_passata_non_allineata": udienza_passata_non_allineata,
            "provvedimenti": documenti["provvedimenti"],
        }

    def _next_actions_for_fascicolo(
        self,
        fascicolo: Fascicolo,
        deadlines: List[Scadenza],
        appointments: List[Any],
        judgments: List[Dict[str, Any]],
        *,
        presidio: Optional[Dict[str, Any]] = None,
    ) -> List[str]:
        actions: List[str] = []
        presidio = dict(presidio or {})
        scadenze_future = list(presidio.get("scadenze_future") or deadlines or [])
        scadenze_scadute = list(presidio.get("scadenze_scadute") or [])
        documentale = dict(presidio.get("documentale") or {})
        ha_provvedimento_finale_aperto = bool(
            documentale.get("ha_provvedimento_finale") and not presidio.get("stato_chiusura")
        )

        if ha_provvedimento_finale_aperto:
            actions.append(
                "E' presente un provvedimento finale: aggiorna definizione, incasso e archiviazione della pratica."
            )
        elif scadenze_scadute:
            first = scadenze_scadute[0]
            actions.append(
                f"Chiudere o riallineare subito la scadenza '{first.titolo}' perche' risulta gia' scaduta."
            )
        elif scadenze_future:
            first = scadenze_future[0]
            days = first.giorni_alla_scadenza
            if days is not None and days <= 3:
                actions.append(f"Preparare subito l'adempimento '{first.titolo}' e verificare firma o allegati.")
            elif days is not None and days <= 7:
                actions.append(f"Pianificare entro oggi la lavorazione di '{first.titolo}'.")
        elif fascicolo.stato in (StatoFascicolo.APERTO, StatoFascicolo.IN_CORSO):
            actions.append("Verificare se manca una scadenza processuale o un esito udienza da presidiare nel fascicolo.")

        if documentale.get("documenti_portale_mancanti"):
            actions.append(
                f"Allineare {documentale['documenti_portale_mancanti']} documenti del portale con classificazione ufficiale e identificativi del deposito."
            )
        elif presidio.get("udienza_passata_non_allineata"):
            actions.append("Storicizzare l'udienza gia' trascorsa o aggiornare il fascicolo con il relativo provvedimento.")
        elif appointments and not ha_provvedimento_finale_aperto:
            first_app = appointments[0]
            actions.append(f"Confermare agenda e note operative per '{first_app.titolo}'.")
        elif presidio.get("udienza_futura") and not ha_provvedimento_finale_aperto:
            actions.append("Confermare note operative, presenze e allegati per la prossima udienza.")
        elif fascicolo.stato in (StatoFascicolo.APERTO, StatoFascicolo.IN_CORSO) and not ha_provvedimento_finale_aperto:
            actions.append("Valutare un appuntamento cliente o una riunione di preparazione.")

        if not judgments and not presidio.get("provvedimenti"):
            actions.append("Avviare una ricerca giurisprudenziale mirata collegata all'oggetto della pratica.")
        else:
            actions.append("Selezionare i provvedimenti o le sentenze piu rilevanti e collegarli all'atto o all'esito della pratica.")

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
        fascicoli_by_cliente: Dict[str, List[Fascicolo]] = defaultdict(list)
        fascicoli_by_procedimento: Dict[str, List[Fascicolo]] = defaultdict(list)
        for fascicolo in fascicoli:
            cliente_key = str(getattr(fascicolo, "id_cliente", "") or "").strip()
            if cliente_key:
                fascicoli_by_cliente[cliente_key].append(fascicolo)
            for raw_key in (
                getattr(fascicolo, "numero", ""),
                getattr(fascicolo, "rg_completo", ""),
                getattr(fascicolo, "titolo", ""),
            ):
                key = str(raw_key or "").strip().lower()
                if key:
                    fascicoli_by_procedimento[key].append(fascicolo)
        for item in appointments:
            procedimento = str(getattr(item, "procedimento", "") or "").strip().lower()
            matched_ids: set[str] = set()
            for fascicolo in fascicoli_by_cliente.get(str(getattr(item, "id_cliente", "") or "").strip(), []):
                appointments_by_fascicolo[fascicolo.id].append(item)
                matched_ids.add(fascicolo.id)
            if procedimento:
                candidates = list(fascicoli_by_procedimento.get(procedimento, []))
                if not candidates and len(procedimento) >= 4:
                    for fascicolo in fascicoli:
                        if procedimento in str(fascicolo.titolo or "").strip().lower():
                            candidates.append(fascicolo)
                for fascicolo in candidates:
                    if fascicolo.id in matched_ids:
                        continue
                    appointments_by_fascicolo[fascicolo.id].append(item)
                    matched_ids.add(fascicolo.id)
        direct_judgments_by_fascicolo = self._giurisprudenza_diretta_per_fascicoli(
            fascicoli,
            limit_per_fascicolo=3,
        )
        hot: List[Dict[str, Any]] = []
        for fascicolo in fascicoli:
            fasc_deadlines = deadlines_by_fascicolo.get(fascicolo.id, [])
            fasc_apps = appointments_by_fascicolo.get(fascicolo.id, [])
            judgments = direct_judgments_by_fascicolo.get(fascicolo.id, [])
            presidio = self._presidio_fascicolo(fascicolo, fasc_deadlines[:6], fasc_apps[:4], judgments)
            score = 0
            if presidio["scadenze_scadute"]:
                score += 70
            elif presidio["scadenze_future"]:
                first_deadline = presidio["scadenze_future"][0]
                days = first_deadline.giorni_alla_scadenza
                if days is not None:
                    if days <= 3:
                        score += 60
                    elif days <= 7:
                        score += 40
                    elif days <= horizon_days:
                        score += 20
            if presidio.get("udienza_futura"):
                score += 20
            if presidio.get("documentale", {}).get("documenti_portale_mancanti"):
                score += 18
            if presidio.get("udienza_passata_non_allineata"):
                score += 16
            if presidio.get("documentale", {}).get("ha_provvedimento_finale") and not presidio.get("stato_chiusura"):
                score += 14
            if fascicolo.stato == StatoFascicolo.IN_CORSO:
                score += 10
            if not judgments and not presidio.get("provvedimenti"):
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
                    "scadenze": presidio["scadenze_future"][:3],
                    "scadenze_scadute": presidio["scadenze_scadute"][:2],
                    "appuntamenti": fasc_apps[:2],
                    "giurisprudenza": judgments,
                    "provvedimenti": presidio["provvedimenti"],
                    "presidio": presidio,
                    "azioni": self._next_actions_for_fascicolo(
                        fascicolo,
                        presidio["scadenze_future"][:3],
                        fasc_apps[:2],
                        judgments,
                        presidio=presidio,
                    ),
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
        try:
            duplicate_groups = duplicate_practice_groups(
                item for item in self.fascicoli.tutti() if not _stato_fascicolo_chiuso(item)
            )
        except Exception:
            duplicate_groups = []
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
        if duplicate_groups:
            first_group = duplicate_groups[0]
            actions.append(
                {
                    "tone": "warning",
                    "title": "Verificare pratiche doppie",
                    "description": f"{len(duplicate_groups)} gruppi hanno stesso cliente e numero RG: controlla prima scadenze, documenti e valori economici.",
                    "href": f"/fascicoli?rg={str(first_group.get('rg') or '').replace('RG ', '')}",
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
            "generated_at": _local_now().replace(microsecond=0).isoformat(),
            "summary": {
                "scadenze_urgenti": len(urgent_deadlines),
                "scadenze_orizzonte": len(horizon_deadlines),
                "appuntamenti_orizzonte": len(appointments),
                "profili_sync_attivi": len([profile for profile in sync_profiles if profile.get("enabled", True)]),
                "profili_sync_da_verificare": len([profile for profile in sync_profiles if profile.get("is_stale")]),
                "fascicoli_attenzionati": len(fascicoli_hot),
                "pratiche_doppie": len(duplicate_groups),
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
        presidio = self._presidio_fascicolo(fascicolo, fasc_deadlines[:8], fasc_apps[:4], judgments)
        office_sources = _unique_strings(
            deadline.judicial_office_source_url
            for deadline in fasc_deadlines
            if deadline.judicial_office_source_url
        )
        return {
            "next_actions": self._next_actions_for_fascicolo(
                fascicolo,
                presidio["scadenze_future"][:3],
                fasc_apps[:2],
                judgments,
                presidio=presidio,
            ),
            "scadenze": presidio["scadenze_future"][:4],
            "scadenze_scadute": presidio["scadenze_scadute"][:4],
            "appuntamenti": fasc_apps[:3],
            "giurisprudenza": judgments,
            "provvedimenti": presidio["provvedimenti"],
            "presidio": presidio,
            "area_hint": _fascicolo_area_hint(fascicolo),
            "keywords": _extract_keywords(fascicolo),
            "office_sources": office_sources,
            "has_items": bool(fasc_deadlines or fasc_apps or judgments or presidio["provvedimenti"]),
        }

    def save_snapshot(self, path: str, overview: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        safe_overview = _snapshot_safe_value(overview or self.panoramica())
        payload = {
            "generated_at": _local_now().replace(microsecond=0).isoformat(),
            "overview": safe_overview,
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
