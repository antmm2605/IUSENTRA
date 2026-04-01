from __future__ import annotations

import hashlib
import json
import re
import uuid
import warnings
from urllib.parse import urlparse
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional

import requests
from urllib3.exceptions import InsecureRequestWarning

from pct.normative_tables import FONTI_OPERATIVE, GestioneTabelleNormative

USER_AGENT = "HACS-Legal-Intelligence/1.0 (+https://pst.giustizia.it)"
MAX_MONITOR_BYTES = 512_000
MAX_MONITOR_RUNS = 600
MAX_ALERTS = 400
MAX_AUDIT_TRACES = 500


def _now_iso(now: Optional[datetime] = None) -> str:
    return (now or datetime.now()).replace(microsecond=0).isoformat()


def _clean_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _truncate(value: str, limit: int = 220) -> str:
    value = _clean_spaces(value)
    return value if len(value) <= limit else value[: limit - 1].rstrip() + "..."


def _parse_iso_date(value: str) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data or b"").hexdigest()


def _looks_like_html(content_type: str, url: str) -> bool:
    value = (content_type or "").lower()
    path = (urlparse(url or "").path or "").lower()
    return (
        "html" in value
        or path.endswith(".html")
        or path.endswith(".htm")
        or path.endswith(".page")
        or not Path(path).suffix
    )


def _normalize_textual_payload(content: bytes, content_type: str, url: str) -> bytes:
    if not _looks_like_html(content_type, url):
        return content
    text = (content or b"").decode("utf-8", errors="ignore")
    text = re.sub(r"(?is)<(script|style|noscript)\b.*?</\1>", " ", text)
    text = re.sub(r"(?is)<!--.*?-->", " ", text)
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    text = _clean_spaces(text)
    return text.encode("utf-8")


def _detect_protection_page(final_url: str, content: bytes) -> bool:
    normalized = _normalize_textual_payload(content, "text/html", final_url).decode("utf-8", errors="ignore")
    sample = (
        (final_url or "")
        + "\n"
        + (content or b"").decode("utf-8", errors="ignore")[:6000]
        + "\n"
        + normalized[:6000]
    ).lower()
    markers = (
        "validate.perfdrive.com",
        "radware",
        "security challenge",
        "captcha",
        "enable javascript",
        "please wait while we verify",
        "errore nel caricamento delle informazioni",
        "session id:",
        "normattiva - errore",
    )
    return any(marker in sample for marker in markers)


def _requires_tls_fallback(url: str) -> bool:
    host = (urlparse(url or "").hostname or "").lower()
    return host.endswith("giustizia-amministrativa.it")


def _severity_rank(level: str) -> int:
    return {"critica": 4, "alta": 3, "media": 2, "bassa": 1, "info": 0}.get((level or "").lower(), 0)


@dataclass(frozen=True)
class FonteUfficiale:
    id: str
    nome: str
    motore: str
    area: str
    official_url: str
    monitor_url: str
    connector_kind: str
    cadence: str
    formats: List[str] = field(default_factory=list)
    capability: str = ""
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MotoreLegale:
    id: str
    nome: str
    short_name: str
    descrizione: str
    output: str
    value: str
    source_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class MonitorRun:
    id: str
    source_id: str
    checked_at: str
    published_at: str = ""
    acquired_at: str = ""
    official_url: str = ""
    monitor_url: str = ""
    final_url: str = ""
    status: str = "ok"
    status_code: int = 0
    content_hash: str = ""
    content_type: str = ""
    size_bytes: int = 0
    changed: bool = False
    comparison_mode: str = "raw"
    summary: str = ""
    warning: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MonitorRun":
        payload = dict(data or {})
        fields = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in payload.items() if k in fields})


@dataclass
class IntelligenceAlert:
    id: str
    created_at: str
    source_id: str
    motore_id: str
    alert_type: str
    severity: str
    title: str
    details: str
    official_url: str = ""
    related_entity_type: str = ""
    related_entity_id: str = ""
    acknowledged: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "IntelligenceAlert":
        payload = dict(data or {})
        fields = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in payload.items() if k in fields})


@dataclass
class AuditTrace:
    id: str
    created_at: str
    query: str
    user: str = ""
    engine_ids: List[str] = field(default_factory=list)
    source_ids: List[str] = field(default_factory=list)
    source_snapshots: List[Dict[str, str]] = field(default_factory=list)
    ai_model: str = ""
    result_summary: str = ""
    warning: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AuditTrace":
        payload = dict(data or {})
        fields = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in payload.items() if k in fields})


FONTI_UFFICIALI: Dict[str, FonteUfficiale] = {
    "normattiva": FonteUfficiale(
        id="normattiva",
        nome="Normattiva / Open Data",
        motore="fonti_ufficiali",
        area="Normativa italiana",
        official_url="https://www.normattiva.it/",
        monitor_url="https://dati.normattiva.it/assets/come_fare_per/API_Normattiva_OpenData.pdf",
        connector_kind="open-data",
        cadence="giornaliera",
        formats=["XML", "JSON", "PDF"],
        capability="Testo vigente, multivigenza e API strutturate.",
        notes="Fonte primaria per testo vigente e versionamento normativo.",
    ),
    "gazzetta_ufficiale": FonteUfficiale(
        id="gazzetta_ufficiale",
        nome="Gazzetta Ufficiale",
        motore="fonti_ufficiali",
        area="Pubblicazioni ufficiali",
        official_url="https://www.gazzettaufficiale.it/",
        monitor_url="https://www.gazzettaufficiale.it/rss/SG",
        connector_kind="rss-portal",
        cadence="quotidiana",
        formats=["RSS", "HTML", "PDF"],
        capability="Pubblicazione e archivio degli atti normativi ufficiali.",
        notes="Per pubblicazione, entrata in vigore e serie speciali.",
    ),
    "pst_giustizia": FonteUfficiale(
        id="pst_giustizia",
        nome="PST Giustizia",
        motore="procedurale_telematico",
        area="Telematico",
        official_url="https://pst.giustizia.it/",
        monitor_url="https://pst.giustizia.it/PST/resources/cms/documents/Note_per_le_software_house_versioni_aggiornate_1.pdf",
        connector_kind="portal-docs",
        cadence="piu-volte-al-giorno",
        formats=["HTML", "PDF", "WSDL", "XSD"],
        capability="Documentazione software house, servizi web e note tecniche.",
        notes="Fonte primaria per XSD, WSDL, ReGIndE, pagamenti e consultazione registri.",
    ),
    "cnf": FonteUfficiale(
        id="cnf",
        nome="Consiglio Nazionale Forense",
        motore="professione_forense",
        area="Professione forense",
        official_url="https://www.consiglionazionaleforense.it/",
        monitor_url="https://www.consiglionazionaleforense.it/",
        connector_kind="portal",
        cadence="giornaliera",
        formats=["HTML", "PDF"],
        capability="Codice deontologico, normativa professionale e parametri forensi.",
        notes="Riferimento per preventivi, incarichi ed alert deontologici.",
    ),
    "cassazione": FonteUfficiale(
        id="cassazione",
        nome="Corte di Cassazione",
        motore="giurisprudenza_orientamenti",
        area="Giurisprudenza di legittimita",
        official_url="https://www.cortedicassazione.it/",
        monitor_url="https://www.cortedicassazione.it/it/massimario.page",
        connector_kind="portal",
        cadence="giornaliera",
        formats=["HTML", "PDF"],
        capability="Servizi online, massimario e raccolte ufficiali.",
        notes="Da collegare a massime, SentenzeWeb e principi di diritto.",
    ),
    "corte_costituzionale": FonteUfficiale(
        id="corte_costituzionale",
        nome="Corte costituzionale",
        motore="giurisprudenza_orientamenti",
        area="Giurisprudenza costituzionale",
        official_url="https://www.cortecostituzionale.it/",
        monitor_url="https://www.cortecostituzionale.it/",
        connector_kind="portal",
        cadence="giornaliera",
        formats=["HTML", "PDF"],
        capability="Decisioni, depositi e comunicati ufficiali.",
        notes="Indispensabile per depositi e decisioni costituzionali.",
    ),
    "giustizia_amministrativa": FonteUfficiale(
        id="giustizia_amministrativa",
        nome="Giustizia amministrativa",
        motore="giurisprudenza_orientamenti",
        area="Giurisprudenza amministrativa",
        official_url="https://www.giustizia-amministrativa.it/",
        monitor_url="https://www.giustizia-amministrativa.it/",
        connector_kind="portal",
        cadence="giornaliera",
        formats=["HTML", "PDF"],
        capability="Decisioni e pareri TAR/Consiglio di Stato.",
        notes="Da collegare a ricorsi, cautelari e orientamenti amministrativi.",
    ),
    "eur_lex": FonteUfficiale(
        id="eur_lex",
        nome="EUR-Lex",
        motore="fonti_ufficiali",
        area="Normativa UE",
        official_url="https://eur-lex.europa.eu/",
        monitor_url="https://eur-lex.europa.eu/oj/direct-access.html",
        connector_kind="portal-rss",
        cadence="giornaliera",
        formats=["HTML", "RSS", "XML", "PDF"],
        capability="Gazzetta UE, normativa e giurisprudenza europea.",
        notes="Motore UE per atti e impatti sovranazionali.",
    ),
}


MOTORI_LEGALI: Dict[str, MotoreLegale] = {
    "fonti_ufficiali": MotoreLegale(
        id="fonti_ufficiali",
        nome="Motore Fonti Ufficiali",
        short_name="Fonti ufficiali",
        descrizione="Raccoglie, verifica e indicizza solo fonti istituzionali con URL, hash e data di acquisizione.",
        output="Catalogo fonti, hash, data pubblicazione, data acquisizione.",
        value="Evita fonti non ufficiali e rende verificabile ogni contenuto monitorato.",
        source_ids=["normattiva", "gazzetta_ufficiale", "pst_giustizia", "cnf", "cassazione", "corte_costituzionale", "giustizia_amministrativa", "eur_lex"],
    ),
    "vigenza_versionamento": MotoreLegale(
        id="vigenza_versionamento",
        nome="Motore di Vigenza e Versionamento Normativo",
        short_name="Vigenza normativa",
        descrizione="Separa norma vigente, multivigenza, modifiche, abrogazioni e data del fatto o del deposito.",
        output="Vista per data-fatto, data-deposito e versione norma.",
        value="Riduce il rischio di applicare una norma errata rispetto al tempo rilevante.",
        source_ids=["normattiva", "gazzetta_ufficiale", "eur_lex"],
    ),
    "procedurale_telematico": MotoreLegale(
        id="procedurale_telematico",
        nome="Motore Procedurale Telematico",
        short_name="Telematico",
        descrizione="Isola PCT, PDP, PAT, ReGIndE, pagamenti, XSD, WSDL e regole tecniche.",
        output="Checklist tecniche, alert XSD/WSDL e conformita pre-invio.",
        value="Evita errori di deposito dovuti a specifiche tecniche o aggiornamenti di portale.",
        source_ids=["pst_giustizia"],
    ),
    "professione_forense": MotoreLegale(
        id="professione_forense",
        nome="Motore Professione Forense",
        short_name="Professione forense",
        descrizione="Tiene separati codice deontologico, parametri, equo compenso e obblighi professionali.",
        output="Preventivi, incarichi, alert deontologici e controlli formali.",
        value="Rende coerente il gestionale con compensi, informativa preventiva e deontologia.",
        source_ids=["cnf", "gazzetta_ufficiale"],
    ),
    "giurisprudenza_orientamenti": MotoreLegale(
        id="giurisprudenza_orientamenti",
        nome="Motore Giurisprudenza e Orientamenti",
        short_name="Giurisprudenza",
        descrizione="Tiene la giurisprudenza distinta dalla normativa e la collega agli articoli coinvolti.",
        output="Orientamenti, massime, principi di diritto e collegamenti normativi.",
        value="Supporta strategia, confronto orientamenti e aggiornamento ragionato.",
        source_ids=["cassazione", "corte_costituzionale", "giustizia_amministrativa"],
    ),
    "monitoraggio_alert": MotoreLegale(
        id="monitoraggio_alert",
        nome="Motore Monitoraggio e Alert",
        short_name="Alert",
        descrizione="Schedula controlli distinti per fonte e genera alert utili, non solo notizie generiche.",
        output="Alert su contenuto modificato, nuovi documenti e nuove note tecniche.",
        value="Trasforma il gestionale in un assistente proattivo invece che in un archivio passivo.",
        source_ids=["normattiva", "gazzetta_ufficiale", "pst_giustizia", "cnf", "cassazione", "corte_costituzionale", "giustizia_amministrativa", "eur_lex"],
    ),
    "audit_affidabilita": MotoreLegale(
        id="audit_affidabilita",
        nome="Motore Audit e Affidabilita",
        short_name="Audit",
        descrizione="Registra query, fonti, versioni, warning e modello AI per ogni risposta assistita.",
        output="Tracce di audit consultabili e storicizzate.",
        value="Aumenta fiducia interna, debugging e responsabilita operativa.",
        source_ids=["normattiva", "gazzetta_ufficiale", "pst_giustizia", "cnf", "cassazione", "corte_costituzionale", "giustizia_amministrativa", "eur_lex"],
    ),
}


KEYWORD_TO_ENGINE: Dict[str, List[str]] = {
    "pct": ["procedurale_telematico", "monitoraggio_alert"],
    "pst": ["procedurale_telematico", "monitoraggio_alert"],
    "pdp": ["procedurale_telematico", "monitoraggio_alert"],
    "pat": ["procedurale_telematico", "monitoraggio_alert"],
    "reginde": ["procedurale_telematico"],
    "xsd": ["procedurale_telematico", "monitoraggio_alert"],
    "wsdl": ["procedurale_telematico", "monitoraggio_alert"],
    "gazzetta": ["fonti_ufficiali", "vigenza_versionamento"],
    "normattiva": ["fonti_ufficiali", "vigenza_versionamento"],
    "vigenza": ["vigenza_versionamento"],
    "abrog": ["vigenza_versionamento", "monitoraggio_alert"],
    "deontolog": ["professione_forense"],
    "compens": ["professione_forense"],
    "preventiv": ["professione_forense"],
    "cnf": ["professione_forense"],
    "cassazione": ["giurisprudenza_orientamenti"],
    "corte costituzionale": ["giurisprudenza_orientamenti"],
    "tar": ["giurisprudenza_orientamenti"],
    "consiglio di stato": ["giurisprudenza_orientamenti"],
    "sentenza": ["giurisprudenza_orientamenti"],
    "giurisprudenza": ["giurisprudenza_orientamenti"],
    "orientament": ["giurisprudenza_orientamenti"],
    "eur-lex": ["fonti_ufficiali", "vigenza_versionamento"],
    "ue": ["fonti_ufficiali", "vigenza_versionamento"],
}


KEYWORD_TO_SOURCE: Dict[str, List[str]] = {
    "normattiva": ["normattiva"],
    "gazzetta": ["gazzetta_ufficiale"],
    "pst": ["pst_giustizia"],
    "pct": ["pst_giustizia"],
    "pdp": ["pst_giustizia"],
    "pat": ["pst_giustizia"],
    "reginde": ["pst_giustizia"],
    "cnf": ["cnf"],
    "deontolog": ["cnf"],
    "cassazione": ["cassazione"],
    "corte costituzionale": ["corte_costituzionale"],
    "tar": ["giustizia_amministrativa"],
    "consiglio di stato": ["giustizia_amministrativa"],
    "eur-lex": ["eur_lex"],
    "ue": ["eur_lex"],
}


FINAL_DEPOSIT_STATES = {"ACCETTATO_CANCELLERIA", "RIFIUTATO_CANCELLERIA"}
PENDING_DEPOSIT_STATES = {"INVIATO", "ACCETTATO_PEC", "CONSEGNATO", "WARN_CONTROLLI"}
ERROR_DEPOSIT_STATES = {"ERRORE_CONTROLLI", "RIFIUTATO_CANCELLERIA", "ERRORE"}


def motori_per_query(query: str) -> List[str]:
    text = (query or "").lower()
    found: List[str] = []
    for keyword, engine_ids in KEYWORD_TO_ENGINE.items():
        if keyword in text:
            for engine_id in engine_ids:
                if engine_id not in found:
                    found.append(engine_id)
    return found or ["fonti_ufficiali", "audit_affidabilita"]


def fonti_per_query(query: str) -> List[str]:
    text = (query or "").lower()
    found: List[str] = []
    for keyword, source_ids in KEYWORD_TO_SOURCE.items():
        if keyword in text:
            for source_id in source_ids:
                if source_id not in found:
                    found.append(source_id)
    return found or ["normattiva", "pst_giustizia"]


def costruisci_tracker_fascicolo(fascicolo: Any) -> Dict[str, Any]:
    attivita = list(getattr(fascicolo, "attivita", []) or [])
    depositi = list(getattr(fascicolo, "depositi_pct", []) or [])
    stato = getattr(getattr(fascicolo, "stato", None), "value", str(getattr(fascicolo, "stato", "")))

    has_opening = True
    has_activity = bool(attivita or depositi or stato in {"IN_CORSO", "SOSPESO", "DEFINITO", "ARCHIVIATO"})
    has_decision = any(
        getattr(getattr(att, "tipo", None), "value", str(getattr(att, "tipo", "")))
        in {"UDIENZA", "PROVVEDIMENTO", "COMUNICAZIONE_CANCELLERIA", "SENTENZA_EMESSA", "APPELLO"}
        for att in attivita
    ) or any((getattr(dep, "stato", "") or "").upper() in FINAL_DEPOSIT_STATES for dep in depositi)
    has_closure = stato in {"DEFINITO", "ARCHIVIATO"}

    steps = [
        {"id": "apertura", "label": "Apertura pratica", "complete": has_opening},
        {"id": "sviluppo", "label": "Depositi e istruttoria", "complete": has_activity},
        {"id": "decisione", "label": "Udienza / provvedimenti", "complete": has_decision},
        {"id": "chiusura", "label": "Definizione", "complete": has_closure},
    ]
    completed = sum(1 for step in steps if step["complete"])
    current_idx = min(completed, len(steps) - 1)
    percent = int(round((completed / len(steps)) * 100))

    ultima_attivita = getattr(fascicolo, "ultima_attivita", None)
    prossima_scadenza = getattr(fascicolo, "prossima_scadenza", None)
    data_udienza = getattr(fascicolo, "data_prossima_udienza", "") or ""

    last_event = ""
    if ultima_attivita:
        last_event = _clean_spaces(
            f"{getattr(ultima_attivita, 'titolo', 'Attivita processuale')} {getattr(ultima_attivita, 'data', '')}"
        )
    elif depositi:
        ultimo_dep = max(depositi, key=lambda dep: getattr(dep, "timestamp", ""))
        last_event = _clean_spaces(
            f"Deposito {getattr(ultimo_dep, 'tipo_atto', '')} {getattr(ultimo_dep, 'timestamp', '')[:10]}"
        )

    next_event = ""
    if prossima_scadenza:
        next_event = _clean_spaces(
            f"{getattr(prossima_scadenza, 'titolo', 'Scadenza')} {getattr(prossima_scadenza, 'data', '')}"
        )
    elif data_udienza:
        next_event = f"Udienza fissata per {data_udienza}"

    current_label = "Pratica definita" if has_closure else steps[current_idx]["label"]
    return {
        "percent": percent,
        "current_label": current_label,
        "steps": steps,
        "last_event": last_event,
        "next_event": next_event,
        "stato": stato,
    }


def costruisci_tracker_fascicoli(fascicoli: Iterable[Any]) -> Dict[str, Dict[str, Any]]:
    trackers: Dict[str, Dict[str, Any]] = {}
    for fascicolo in fascicoli or []:
        fascicolo_id = getattr(fascicolo, "id", "")
        if fascicolo_id:
            trackers[fascicolo_id] = costruisci_tracker_fascicolo(fascicolo)
    return trackers


class GestioneLegalIntelligence:
    def __init__(
        self,
        db_path: str = "./intelligence/legal_intelligence.json",
        timeout: int = 15,
        normative_db_path: Optional[str] = None,
    ):
        self.db_path = db_path
        self.timeout = timeout
        self.normative_db_path = normative_db_path or str(Path(db_path).with_name("tabelle_normative.json"))
        self.normative_tables = GestioneTabelleNormative(self.normative_db_path)
        self._data: Dict[str, Any] = {"monitor_runs": [], "alerts": [], "audit_traces": []}
        self._load()

    def _load(self) -> None:
        path = Path(self.db_path)
        if not path.exists():
            return
        try:
            with path.open(encoding="utf-8") as fh:
                raw = json.load(fh)
            self._data["monitor_runs"] = [
                MonitorRun.from_dict(item).to_dict() for item in (raw.get("monitor_runs") or [])
            ]
            self._data["alerts"] = [
                IntelligenceAlert.from_dict(item).to_dict() for item in (raw.get("alerts") or [])
            ]
            self._data["audit_traces"] = [
                AuditTrace.from_dict(item).to_dict() for item in (raw.get("audit_traces") or [])
            ]
        except Exception:
            self._data = {"monitor_runs": [], "alerts": [], "audit_traces": []}

    def _save(self) -> None:
        path = Path(self.db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fh:
            json.dump(self._data, fh, ensure_ascii=False, indent=2)

    def _append_limited(self, key: str, payload: Dict[str, Any], limit: int) -> None:
        self._data.setdefault(key, []).append(payload)
        if len(self._data[key]) > limit:
            self._data[key] = self._data[key][-limit:]

    def catalogo_fonti(self) -> List[Dict[str, Any]]:
        return [source.to_dict() for source in FONTI_UFFICIALI.values()]

    def catalogo_motori(self) -> List[Dict[str, Any]]:
        return [engine.to_dict() for engine in MOTORI_LEGALI.values()]

    def _latest_runs(self) -> Dict[str, MonitorRun]:
        latest: Dict[str, MonitorRun] = {}
        for raw in self._data.get("monitor_runs", []):
            run = MonitorRun.from_dict(raw)
            current = latest.get(run.source_id)
            if current is None or run.checked_at >= current.checked_at:
                latest[run.source_id] = run
        return latest

    def _latest_success(self, source_id: str) -> Optional[MonitorRun]:
        latest: Optional[MonitorRun] = None
        for raw in self._data.get("monitor_runs", []):
            if raw.get("source_id") != source_id or raw.get("status") != "ok":
                continue
            run = MonitorRun.from_dict(raw)
            if latest is None or run.checked_at >= latest.checked_at:
                latest = run
        return latest

    def _fetch_response(self, fetch: Callable[..., Any], url: str) -> tuple[Any, bool]:
        base_kwargs = {
            "headers": {"User-Agent": USER_AGENT},
            "timeout": self.timeout,
            "allow_redirects": True,
            "verify": True,
        }

        def _call(**extra: Any) -> Any:
            kwargs = dict(base_kwargs)
            kwargs.update(extra)
            try:
                return fetch(url, **kwargs)
            except TypeError:
                kwargs.pop("verify", None)
                return fetch(url, **kwargs)

        try:
            return _call(), False
        except requests.exceptions.SSLError:
            if not _requires_tls_fallback(url):
                raise
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", InsecureRequestWarning)
                return _call(verify=False), True

    def _fetch_state(
        self,
        *,
        label: str,
        official_url: str,
        monitor_url: str,
        latest_hash: str = "",
        fetch: Optional[Callable[..., Any]] = None,
        now: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        current_time = now or datetime.now()
        response, used_tls_fallback = self._fetch_response(fetch or requests.get, monitor_url)
        content = bytes(getattr(response, "content", b"") or b"")[:MAX_MONITOR_BYTES]
        status_code = int(getattr(response, "status_code", 0) or 0)
        headers = getattr(response, "headers", {}) or {}
        content_type = str(headers.get("content-type", "") or "")
        final_url = str(getattr(response, "url", monitor_url) or monitor_url)
        status = "ok" if status_code < 400 else "errore"
        comparison_mode = "raw"
        warning = ""
        changed = False

        if status == "ok" and _detect_protection_page(final_url, content):
            comparison_mode = "challenge_guard"
            content_hash = latest_hash or _sha256(b"challenge_guard")
            warning = "Controllo limitato da pagina di protezione applicativa."
        else:
            normalized = _normalize_textual_payload(content, content_type, final_url)
            comparison_mode = "normalized_text" if normalized != content else "raw"
            content_hash = _sha256(normalized)
            changed = bool(status == "ok" and latest_hash and latest_hash != content_hash)
            if status != "ok":
                warning = f"HTTP {status_code}"

        if used_tls_fallback:
            extra = "Verifica TLS ridotta per compatibilita del certificato remoto."
            warning = f"{warning} {extra}".strip()

        notes: List[str] = []
        if comparison_mode == "normalized_text":
            notes.append("confronto testo stabile")
        elif comparison_mode == "challenge_guard":
            notes.append("pagina protetta")
        if used_tls_fallback:
            notes.append("retry TLS compatibile")
        if changed:
            notes.append("contenuto modificato")
        summary = f"{label}: HTTP {status_code or 'n/d'} - hash {content_hash[:12]}"
        if notes:
            summary += " - " + " - ".join(notes)

        return {
            "id": uuid.uuid4().hex,
            "checked_at": _now_iso(current_time),
            "acquired_at": _now_iso(current_time),
            "official_url": official_url,
            "monitor_url": monitor_url,
            "final_url": final_url,
            "status": status,
            "status_code": status_code,
            "content_hash": content_hash,
            "content_type": content_type,
            "size_bytes": len(content),
            "changed": changed,
            "comparison_mode": comparison_mode,
            "summary": summary,
            "warning": warning,
        }

    def _freshness_status(self, source: FonteUfficiale, run: Optional[MonitorRun]) -> str:
        if run is None:
            return "mai_controllata"
        if run.status == "errore":
            return "errore"
        checked_at = _parse_iso_date(run.checked_at)
        if checked_at is None:
            return "sconosciuta"
        age = datetime.now() - checked_at
        if source.cadence == "piu-volte-al-giorno":
            return "aggiornata" if age <= timedelta(hours=8) else "stale"
        if source.cadence in {"quotidiana", "giornaliera"}:
            return "aggiornata" if age <= timedelta(days=1, hours=6) else "stale"
        return "aggiornata" if age <= timedelta(days=3) else "stale"

    def _alert_kind_for_source(self, source_id: str) -> str:
        if source_id == "pst_giustizia":
            return "nuova_documentazione_tecnica"
        if source_id in {"normattiva", "gazzetta_ufficiale", "eur_lex"}:
            return "norma_o_testo_modificato"
        if source_id == "cnf":
            return "aggiornamento_professione_forense"
        return "nuovo_orientamento_ufficiale"

    def _alert_details_for_source(self, source: FonteUfficiale) -> str:
        if source.id == "pst_giustizia":
            return "Rilevata una variazione nella documentazione tecnica o software house del PST."
        if source.id in {"normattiva", "gazzetta_ufficiale", "eur_lex"}:
            return "Rilevata una variazione su una fonte normativa ufficiale da riesaminare."
        if source.id == "cnf":
            return "Rilevata una variazione su fonte ufficiale della professione forense."
        return "Rilevata una variazione su una fonte ufficiale giurisprudenziale."

    def _create_alert(
        self,
        *,
        source_id: str,
        motore_id: str,
        alert_type: str,
        severity: str,
        title: str,
        details: str,
        official_url: str = "",
        related_entity_type: str = "",
        related_entity_id: str = "",
        now: Optional[datetime] = None,
    ) -> IntelligenceAlert:
        fingerprint = (source_id, motore_id, alert_type, title, related_entity_type, related_entity_id)
        for idx in range(len(self._data.get("alerts", [])) - 1, -1, -1):
            existing = IntelligenceAlert.from_dict(self._data["alerts"][idx])
            current_key = (
                existing.source_id,
                existing.motore_id,
                existing.alert_type,
                existing.title,
                existing.related_entity_type,
                existing.related_entity_id,
            )
            if current_key != fingerprint or existing.acknowledged:
                continue
            payload = existing.to_dict()
            payload.update(
                {
                    "created_at": _now_iso(now),
                    "severity": severity,
                    "details": details,
                    "official_url": official_url,
                }
            )
            self._data["alerts"][idx] = payload
            return IntelligenceAlert.from_dict(payload)
        alert = IntelligenceAlert(
            id=uuid.uuid4().hex,
            created_at=_now_iso(now),
            source_id=source_id,
            motore_id=motore_id,
            alert_type=alert_type,
            severity=severity,
            title=title,
            details=details,
            official_url=official_url,
            related_entity_type=related_entity_type,
            related_entity_id=related_entity_id,
        )
        self._append_limited("alerts", alert.to_dict(), MAX_ALERTS)
        return alert

    def monitor_source(
        self,
        source_id: str,
        request_get: Optional[Callable[..., Any]] = None,
        now: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        source = FONTI_UFFICIALI[source_id]
        current_time = now or datetime.now()
        latest_ok = self._latest_success(source_id)
        try:
            payload = self._fetch_state(
                label=source.nome,
                official_url=source.official_url,
                monitor_url=source.monitor_url,
                latest_hash=getattr(latest_ok, "content_hash", ""),
                fetch=request_get,
                now=current_time,
            )
            run = MonitorRun(
                source_id=source_id,
                **payload,
            )
            self._append_limited("monitor_runs", run.to_dict(), MAX_MONITOR_RUNS)
            alerts: List[IntelligenceAlert] = []
            if run.status != "ok":
                alerts.append(
                    self._create_alert(
                        source_id=source_id,
                        motore_id=source.motore,
                        alert_type="fonte_non_raggiungibile",
                        severity="alta",
                        title=f"{source.nome} non raggiungibile",
                        details=f"Il controllo ha restituito HTTP {run.status_code}. Verificare la fonte ufficiale.",
                        official_url=source.official_url,
                        now=current_time,
                    )
                )
            elif run.changed:
                alerts.append(
                    self._create_alert(
                        source_id=source_id,
                        motore_id=source.motore,
                        alert_type=self._alert_kind_for_source(source_id),
                        severity="alta" if source_id == "pst_giustizia" else "media",
                        title=f"{source.nome}: contenuto aggiornato",
                        details=self._alert_details_for_source(source),
                        official_url=source.official_url,
                        now=current_time,
                    )
                )
            self._save()
            return {"ok": run.status == "ok", "run": run.to_dict(), "alerts": [alert.to_dict() for alert in alerts]}
        except Exception as exc:
            run = MonitorRun(
                id=uuid.uuid4().hex,
                source_id=source_id,
                checked_at=_now_iso(current_time),
                acquired_at=_now_iso(current_time),
                official_url=source.official_url,
                monitor_url=source.monitor_url,
                final_url=source.monitor_url,
                status="errore",
                comparison_mode="raw",
                warning=str(exc),
                summary=f"{source.nome}: errore controllo - {exc}",
            )
            self._append_limited("monitor_runs", run.to_dict(), MAX_MONITOR_RUNS)
            alert = self._create_alert(
                source_id=source_id,
                motore_id=source.motore,
                alert_type="fonte_non_raggiungibile",
                severity="alta",
                title=f"{source.nome}: controllo non riuscito",
                details=_truncate(str(exc), 220),
                official_url=source.official_url,
                now=current_time,
            )
            self._save()
            return {"ok": False, "run": run.to_dict(), "alerts": [alert.to_dict()]}

    def run_monitor_cycle(
        self,
        source_ids: Optional[List[str]] = None,
        request_get: Optional[Callable[..., Any]] = None,
        now: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        results = []
        ok_count = 0
        ids = source_ids or list(FONTI_UFFICIALI.keys())
        for source_id in ids:
            result = self.monitor_source(source_id, request_get=request_get, now=now)
            results.append(result)
            if result.get("ok"):
                ok_count += 1
        sync_report = self.sync_normative_tables(source_ids=ids, request_get=request_get, now=now)
        self.registra_trace_risposta(
            query="Monitoraggio fonti ufficiali",
            user="sistema",
            engine_ids=["fonti_ufficiali", "monitoraggio_alert", "audit_affidabilita"],
            source_ids=ids,
            ai_model="sistema",
            result_summary=(
                f"Controllate {len(ids)} fonti ufficiali: {ok_count} riuscite, "
                f"{len(ids) - ok_count} con criticita; sync tabelle {sync_report.get('updated', 0)} aggiornate."
            ),
            warning="" if ok_count == len(ids) else "Alcune fonti ufficiali richiedono verifica operativa.",
            now=now,
        )
        return {
            "ok": ok_count == len(ids),
            "checked": len(ids),
            "successful": ok_count,
            "failed": len(ids) - ok_count,
            "results": results,
            "normative_sync": sync_report,
        }

    def sync_normative_tables(
        self,
        source_ids: Optional[List[str]] = None,
        request_get: Optional[Callable[..., Any]] = None,
        now: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        latest_runs = self._latest_runs()
        source_runs = {
            source_id: run.to_dict()
            for source_id, run in latest_runs.items()
            if not source_ids or source_id in source_ids
        }
        source_checks = self.normative_tables.source_checks()
        source_code_runs: Dict[str, Dict[str, Any]] = {}
        current_time = now or datetime.now()
        for code in self.normative_tables.relevant_source_codes(source_ids):
            source = FONTI_OPERATIVE.get(code)
            if not source:
                continue
            try:
                source_code_runs[code] = self._fetch_state(
                    label=source.title,
                    official_url=source.url,
                    monitor_url=source.url,
                    latest_hash=str((source_checks.get(code) or {}).get("content_hash", "") or ""),
                    fetch=request_get,
                    now=current_time,
                )
            except Exception as exc:
                source_code_runs[code] = {
                    "id": uuid.uuid4().hex,
                    "checked_at": _now_iso(current_time),
                    "acquired_at": _now_iso(current_time),
                    "official_url": source.url,
                    "monitor_url": source.url,
                    "final_url": source.url,
                    "status": "errore",
                    "status_code": 0,
                    "content_hash": "",
                    "content_type": "",
                    "size_bytes": 0,
                    "changed": False,
                    "comparison_mode": "raw",
                    "summary": f"{source.title}: errore controllo - {exc}",
                    "warning": str(exc),
                }
        report = self.normative_tables.sync_from_canonical(
            source_runs=source_runs,
            source_code_runs=source_code_runs,
            source_ids=source_ids,
            now=now,
        )
        alerts: List[Dict[str, Any]] = []
        for table in report.get("tables", []):
            if table.get("updated"):
                alerts.append(
                    self._create_alert(
                        source_id="normattiva",
                        motore_id="vigenza_versionamento",
                        alert_type="tabella_normativa_aggiornata",
                        severity="media",
                        title=f"Tabella normativa sincronizzata: {table.get('title', table.get('id', ''))}",
                        details="Le tabelle normative del gestionale sono state riallineate al catalogo ufficiale interno.",
                        related_entity_type="normative_table",
                        related_entity_id=table.get("id", ""),
                        now=current_time,
                    ).to_dict()
                )
            elif table.get("sync_status") == "verifica_richiesta":
                alerts.append(
                    self._create_alert(
                        source_id="gazzetta_ufficiale",
                        motore_id="monitoraggio_alert",
                        alert_type="tabella_normativa_da_validare",
                        severity="alta",
                        title=f"Verifica richiesta: {table.get('title', table.get('id', ''))}",
                        details="La fonte ufficiale e cambiata, ma la tabella normativa non ha ancora una variazione strutturata automatica.",
                        related_entity_type="normative_table",
                        related_entity_id=table.get("id", ""),
                        now=current_time,
                    ).to_dict()
                )
        if alerts:
            self._save()
        self.registra_trace_risposta(
            query="Sincronizzazione tabelle normative",
            user="sistema",
            engine_ids=["vigenza_versionamento", "monitoraggio_alert", "audit_affidabilita"],
            source_ids=sorted(set(source_ids or source_runs.keys() or ["normattiva", "gazzetta_ufficiale"])),
            ai_model="sistema",
            result_summary=(
                f"Tabelle processate: {report.get('processed_tables', 0)}, "
                f"aggiornate: {report.get('updated', 0)}, da verificare: {report.get('review_required', 0)}."
            ),
            warning="" if not report.get("review_required") else "Sono presenti tabelle normative da verificare.",
            now=current_time,
        )
        report["alerts"] = alerts
        return report

    def _alert_is_resolved(self, alert: IntelligenceAlert, latest_runs: Dict[str, MonitorRun]) -> bool:
        if alert.alert_type == "fonte_non_raggiungibile":
            latest = latest_runs.get(alert.source_id)
            return bool(latest and latest.status == "ok")
        if alert.related_entity_type == "normative_table" and alert.related_entity_id:
            try:
                table = self.normative_tables.get_table(alert.related_entity_id)
            except KeyError:
                return False
            if alert.alert_type == "tabella_normativa_da_validare":
                return table.get("sync_status") != "verifica_richiesta"
        return False

    def registra_trace_risposta(
        self,
        *,
        query: str,
        user: str = "",
        engine_ids: Optional[List[str]] = None,
        source_ids: Optional[List[str]] = None,
        ai_model: str = "",
        result_summary: str = "",
        warning: str = "",
        now: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        engine_ids = engine_ids or motori_per_query(query)
        source_ids = source_ids or fonti_per_query(query)
        latest_runs = self._latest_runs()
        snapshots: List[Dict[str, str]] = []
        for source_id in source_ids:
            source = FONTI_UFFICIALI.get(source_id)
            run = latest_runs.get(source_id)
            snapshots.append(
                {
                    "source_id": source_id,
                    "source_name": source.nome if source else source_id,
                    "official_url": source.official_url if source else "",
                    "checked_at": getattr(run, "checked_at", ""),
                    "acquired_at": getattr(run, "acquired_at", ""),
                    "content_hash": getattr(run, "content_hash", ""),
                }
            )
        trace = AuditTrace(
            id=uuid.uuid4().hex,
            created_at=_now_iso(now),
            query=_truncate(query, 600),
            user=user,
            engine_ids=engine_ids,
            source_ids=source_ids,
            source_snapshots=snapshots,
            ai_model=ai_model,
            result_summary=_truncate(result_summary, 400),
            warning=_truncate(warning, 300),
        )
        self._append_limited("audit_traces", trace.to_dict(), MAX_AUDIT_TRACES)
        self._save()
        return trace.to_dict()

    def recent_alerts(self, limit: int = 12) -> List[Dict[str, Any]]:
        alerts = [IntelligenceAlert.from_dict(raw) for raw in self._data.get("alerts", [])]
        alerts.sort(key=lambda item: (item.created_at, _severity_rank(item.severity)), reverse=True)
        latest_runs = self._latest_runs()
        rows: List[Dict[str, Any]] = []
        seen = set()
        for alert in alerts:
            if self._alert_is_resolved(alert, latest_runs):
                continue
            key = (
                alert.source_id,
                alert.motore_id,
                alert.alert_type,
                alert.title,
                alert.related_entity_type,
                alert.related_entity_id,
            )
            if key in seen:
                continue
            seen.add(key)
            rows.append(alert.to_dict())
            if len(rows) >= limit:
                break
        return rows

    def recent_audit_traces(self, limit: int = 10) -> List[Dict[str, Any]]:
        traces = [AuditTrace.from_dict(raw) for raw in self._data.get("audit_traces", [])]
        traces.sort(key=lambda item: item.created_at, reverse=True)
        return [trace.to_dict() for trace in traces[:limit]]

    def _source_status_rows(self) -> List[Dict[str, Any]]:
        latest_runs = self._latest_runs()
        rows: List[Dict[str, Any]] = []
        for source in FONTI_UFFICIALI.values():
            run = latest_runs.get(source.id)
            rows.append(
                {
                    "id": source.id,
                    "nome": source.nome,
                    "area": source.area,
                    "cadence": source.cadence,
                    "official_url": source.official_url,
                    "monitor_url": source.monitor_url,
                    "connector_kind": source.connector_kind,
                    "formats": source.formats,
                    "freshness": self._freshness_status(source, run),
                    "last_check": getattr(run, "checked_at", ""),
                    "status": getattr(run, "status", "mai_controllata"),
                    "status_code": getattr(run, "status_code", 0),
                    "changed": bool(getattr(run, "changed", False)),
                    "summary": getattr(run, "summary", "Nessun controllo eseguito."),
                    "warning": getattr(run, "warning", ""),
                }
            )
        rows.sort(key=lambda item: (item["freshness"] != "aggiornata", item["nome"]))
        return rows

    def _engine_cards(self, source_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        status_by_source = {row["id"]: row for row in source_rows}
        cards: List[Dict[str, Any]] = []
        for engine in MOTORI_LEGALI.values():
            covered = 0
            fresh = 0
            for source_id in engine.source_ids:
                row = status_by_source.get(source_id)
                if not row:
                    continue
                if row["status"] == "ok":
                    covered += 1
                if row["freshness"] == "aggiornata":
                    fresh += 1
            total = max(1, len(engine.source_ids))
            badge = "operativo" if fresh == total else ("parziale" if covered else "da_alimentare")
            cards.append(
                {
                    "id": engine.id,
                    "nome": engine.nome,
                    "short_name": engine.short_name,
                    "descrizione": engine.descrizione,
                    "output": engine.output,
                    "value": engine.value,
                    "badge": badge,
                    "coverage": covered,
                    "fresh": fresh,
                    "total_sources": total,
                }
            )
        return cards

    def _derived_alerts(self, fascicoli: Iterable[Any], scadenze: Iterable[Any], portali: Optional[Iterable[Any]] = None) -> List[Dict[str, Any]]:
        alerts: List[Dict[str, Any]] = []
        for fascicolo in fascicoli or []:
            titolo = getattr(fascicolo, "titolo", "Fascicolo")
            fascicolo_id = getattr(fascicolo, "id", "")
            for deposito in getattr(fascicolo, "depositi_pct", []) or []:
                stato = (getattr(deposito, "stato", "") or "").upper()
                tipo_atto = getattr(deposito, "tipo_atto", "") or "Deposito"
                if stato in ERROR_DEPOSIT_STATES:
                    alerts.append({"severity": "critica", "title": f"{titolo}: deposito da verificare", "details": f"{tipo_atto} in stato {stato}. Serve intervento operativo.", "related_entity_type": "fascicolo", "related_entity_id": fascicolo_id, "motore_id": "procedurale_telematico"})
                    break
                if stato in PENDING_DEPOSIT_STATES:
                    alerts.append({"severity": "media", "title": f"{titolo}: deposito in attesa", "details": f"{tipo_atto} fermo in stato {stato}. Monitorare le ricevute.", "related_entity_type": "fascicolo", "related_entity_id": fascicolo_id, "motore_id": "monitoraggio_alert"})
                    break

        today = date.today()
        for scadenza in scadenze or []:
            stato = getattr(getattr(scadenza, "stato", None), "value", str(getattr(scadenza, "stato", "")))
            data_scadenza = getattr(scadenza, "scadenza", None)
            if stato != "APERTO" or not hasattr(data_scadenza, "strftime"):
                continue
            giorni = (data_scadenza - today).days
            if giorni <= 3:
                priorita = getattr(getattr(scadenza, "priorita", None), "value", "")
                severity = "critica" if priorita == "CRITICA" or giorni < 0 else "alta"
                alerts.append({"severity": severity, "title": f"Scadenza ravvicinata: {getattr(scadenza, 'titolo', 'Scadenza')}", "details": f"Scade il {data_scadenza.strftime('%d/%m/%Y')} - priorita {priorita or 'N/D'}.", "related_entity_type": "scadenza", "related_entity_id": getattr(scadenza, "id", ""), "motore_id": "monitoraggio_alert"})

        for portale in portali or []:
            if getattr(portale, "is_attivo", False) and not getattr(portale, "privacy_firmata", False):
                alerts.append({"severity": "media", "title": "Portale cliente con privacy non firmata", "details": "Il cliente ha accesso attivo ma il consenso privacy risulta ancora mancante.", "related_entity_type": "cliente", "related_entity_id": getattr(portale, "id_cliente", ""), "motore_id": "audit_affidabilita"})

        alerts.sort(key=lambda item: _severity_rank(item["severity"]), reverse=True)
        return alerts[:10]

    def _competitive_advantages(self, fascicoli: Iterable[Any], portali: Optional[Iterable[Any]]) -> List[Dict[str, Any]]:
        fascicoli = list(fascicoli or [])
        portali = list(portali or [])
        with_portal = sum(1 for portale in portali if getattr(portale, "is_attivo", False))
        with_pending = sum(1 for fascicolo in fascicoli if any((getattr(dep, "stato", "") or "").upper() in PENDING_DEPOSIT_STATES for dep in getattr(fascicolo, "depositi_pct", []) or []))
        closed = sum(1 for fascicolo in fascicoli if getattr(getattr(fascicolo, "stato", None), "value", str(getattr(fascicolo, "stato", ""))) in {"DEFINITO", "ARCHIVIATO"})
        return [
            {"title": "Sentinella scadenze e depositi", "value": with_pending, "description": "Fascicoli con deposito ancora in attesa o da monitorare.", "icon": "bi-bell"},
            {"title": "Trasparenza cliente", "value": with_portal, "description": "Clienti con portale attivo e tracker pratica disponibile.", "icon": "bi-people"},
            {"title": "Pratiche definite", "value": closed, "description": "Base utile per analytics, benchmark interni e modelli predittivi futuri.", "icon": "bi-graph-up-arrow"},
        ]

    def build_dashboard_snapshot(
        self,
        *,
        fascicoli: Iterable[Any],
        clienti: Iterable[Any],
        appuntamenti: Iterable[Any],
        scadenze: Iterable[Any],
        portali: Optional[Iterable[Any]] = None,
    ) -> Dict[str, Any]:
        fascicoli = list(fascicoli or [])
        clienti = list(clienti or [])
        appuntamenti = list(appuntamenti or [])
        scadenze = list(scadenze or [])
        source_rows = self._source_status_rows()
        stored_alerts = self.recent_alerts(limit=8)
        derived_alerts = self._derived_alerts(fascicoli=fascicoli, scadenze=scadenze, portali=portali)
        normative_snapshot = self.normative_tables.snapshot()
        return {
            "headline": {
                "motori_attivi": len(MOTORI_LEGALI),
                "fonti_monitorate": len(source_rows),
                "fonti_aggiornate": sum(1 for row in source_rows if row["freshness"] == "aggiornata"),
                "fonti_da_rivedere": sum(1 for row in source_rows if row["freshness"] != "aggiornata"),
                "alert_totali": len(stored_alerts) + len(derived_alerts),
                "audit_recenti": len(self.recent_audit_traces(limit=8)),
                "tabelle_normative": normative_snapshot["totali"],
                "riferimenti_normativi": normative_snapshot.get("riferimenti_normativi_totali", 0),
                "tabelle_da_validare": normative_snapshot["verifica_richiesta"],
                "fascicoli": len(fascicoli),
                "clienti": len(clienti),
                "appuntamenti": len(appuntamenti),
            },
            "source_rows": source_rows,
            "engine_cards": self._engine_cards(source_rows),
            "stored_alerts": stored_alerts,
            "derived_alerts": derived_alerts,
            "recent_audits": self.recent_audit_traces(limit=8),
            "competitive_advantages": self._competitive_advantages(fascicoli, portali),
            "trackers": costruisci_tracker_fascicoli(fascicoli),
            "normative_tables": normative_snapshot,
        }
