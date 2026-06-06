"""Auto-fetch governato per fonti legali pubbliche.

Il modulo coordina fonti, cursori e coda job senza fare scraping diretto:
la pipeline esistente resta proprietaria del fetch, mentre questo layer decide
quali fonti sono dovute, le accoda con deduplica e produce un monitor operativo.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from pct.legal_update_batch_runner import (
    LegalUpdateJobConfig,
    run_legal_update_batch_with_timeouts,
)
from pct.legal_update_job_queue import (
    LEGAL_UPDATE_JOB_QUEUE_SCHEMA,
    LegalUpdateJobQueue,
)
from pct.legal_update_pipeline import LegalUpdatePipeline, build_legal_update_pipeline


LEGAL_UPDATE_AUTOFETCH_SCHEMA = "iusentra.legal_update_autofetch.v1"
LEGAL_UPDATE_PROGRESSIVE_STEP = "fase9_fonti_verdi"
LEGAL_UPDATE_PROGRESSIVE_SOURCE_BUDGET = 3
LEGAL_UPDATE_PROGRESSIVE_PUBLISH_MAX_ITEMS = 5
LEGAL_UPDATE_PROGRESSIVE_ITEM_TIMEOUT_SECONDS = 120
LEGAL_UPDATE_PROGRESSIVE_CASSAZIONE_MAX_ITEMS = 5
LEGAL_UPDATE_PROGRESSIVE_STEP1_SOURCE_CODES: tuple[str, ...] = (
    "cassazione_ultime_sent_ord_questioni",
    "corte_conti",
    "curia_cgue_rss",
    "inps_circolari",
    "inps_messaggi",
    "agcom_provvedimenti",
    "anac_documenti",
    "garante_privacy",
    "gazzetta_ufficiale",
)
LEGAL_UPDATE_PROGRESSIVE_RAG_ONLY_SOURCE_CODES: tuple[str, ...] = (
    "dati_normattiva",
    "eur_lex",
    "istat_prezzi",
    "openga_giustizia_amministrativa",
    "openga_calendario_udienze",
    "openga_sentenze",
    "openga_ordinanze",
    "openga_decreti",
    "openga_pareri",
    "openga_provvedimenti_pubblicati",
    "openga_ricorsi_definiti",
    "openga_ricorsi_pendenti",
    "openga_ricorsi_pervenuti",
    "pst_giustizia_download",
)
LEGAL_UPDATE_PROGRESSIVE_OBSERVATION_SOURCE_CODES: tuple[str, ...] = (
    "cassazione_massimario",
    "cassazione_citazioni_verificate",
    "corte_costituzionale",
    "giustizia_amministrativa",
    "giustizia_amministrativa_decisioni_pareri",
    "inps_sentenze",
    "agenzia_entrate",
    "ministero_lavoro",
    "ministero_lavoro_interpelli",
    "agcm_bollettino",
    "banca_italia_normativa",
    "inail_istruzioni_operative",
    "mimit_incentivi",
)
LEGAL_UPDATE_PROGRESSIVE_ARCHIVE_SOURCE_CODES: tuple[str, ...] = (
    "normattiva",
    "codice_civile",
    "codice_procedura_civile",
    "codice_penale",
    "codice_procedura_penale",
    "codice_processo_amministrativo",
    "codice_strada",
)
LEGAL_UPDATE_PROGRESSIVE_EXCLUDED_PUBLICATION_SOURCE_CODES: tuple[str, ...] = (
    LEGAL_UPDATE_PROGRESSIVE_RAG_ONLY_SOURCE_CODES
    + LEGAL_UPDATE_PROGRESSIVE_OBSERVATION_SOURCE_CODES
    + LEGAL_UPDATE_PROGRESSIVE_ARCHIVE_SOURCE_CODES
)
LEGAL_UPDATE_PROGRESSIVE_LOTS: dict[str, tuple[str, ...]] = {
    "giurisprudenza": (
        "cassazione_ultime_sent_ord_questioni",
        "cassazione_citazioni_verificate",
        "corte_costituzionale",
        "corte_conti",
        "curia_cgue_rss",
        "openga_sentenze",
        "openga_ordinanze",
        "openga_decreti",
        "openga_pareri",
    ),
    "prassi_autorita": (
        "inps_circolari",
        "inps_messaggi",
        "inps_sentenze",
        "agenzia_entrate",
        "ministero_lavoro",
        "ministero_lavoro_interpelli",
        "garante_privacy",
        "anac_documenti",
        "agcom_provvedimenti",
        "agcm_bollettino",
        "banca_italia_normativa",
        "inail_istruzioni_operative",
        "mimit_incentivi",
        "istat_prezzi",
    ),
    "telematico": ("pst_giustizia_download",),
    "normativa_ue": (
        "gazzetta_ufficiale",
        "normattiva",
        "dati_normattiva",
        "eur_lex",
        "codice_civile",
        "codice_procedura_civile",
        "codice_penale",
        "codice_procedura_penale",
        "codice_processo_amministrativo",
        "codice_strada",
    ),
}
LEGAL_UPDATE_PROGRESSIVE_SOURCE_CLASSIFICATION: dict[str, str] = {
    **{code: "verde_abilitata" for code in LEGAL_UPDATE_PROGRESSIVE_STEP1_SOURCE_CODES},
    **{code: "rag_only" for code in LEGAL_UPDATE_PROGRESSIVE_RAG_ONLY_SOURCE_CODES},
    **{code: "osservazione" for code in LEGAL_UPDATE_PROGRESSIVE_OBSERVATION_SOURCE_CODES},
    **{code: "archivio_locale" for code in LEGAL_UPDATE_PROGRESSIVE_ARCHIVE_SOURCE_CODES},
}
LEGAL_UPDATE_PROGRESSIVE_PUBLICATION_POLICY: dict[str, str] = {
    **{code: "guarded" for code in LEGAL_UPDATE_PROGRESSIVE_STEP1_SOURCE_CODES},
    **{code: "no_publish" for code in LEGAL_UPDATE_PROGRESSIVE_RAG_ONLY_SOURCE_CODES},
    **{code: "no_publish" for code in LEGAL_UPDATE_PROGRESSIVE_ARCHIVE_SOURCE_CODES},
    **{code: "blocked" for code in LEGAL_UPDATE_PROGRESSIVE_OBSERVATION_SOURCE_CODES},
}
LEGAL_UPDATE_PROGRESSIVE_CLASSIFICATION_REASONS: dict[str, str] = {
    "cassazione_ultime_sent_ord_questioni": "Fonte verde con schede Cassazione, PDF/OCR, riferimenti e domande gia' collaudati.",
    "corte_conti": "Fonte verde dopo fix parser e download PDF ufficiali, con pubblicazione guarded.",
    "curia_cgue_rss": "Fonte verde parziale: pubblica solo cause UE con riferimenti ritrovabili.",
    "inps_circolari": "Fonte verde per prassi previdenziale con testo/PDF e riferimenti.",
    "inps_messaggi": "Fonte verde parziale: solo messaggi operativi, scarti guarded sui testi tecnici.",
    "agcom_provvedimenti": "Fonte verde con filtro su delibere/provvedimenti e allegati ufficiali.",
    "anac_documenti": "Fonte verde dopo fix allegati fittizi; pubblicazione ancora guarded e sorvegliata.",
    "garante_privacy": "Fonte verde dopo fix allegati normativi fittizi; pubblicazione guarded su testi docweb leggibili.",
    "gazzetta_ufficiale": "Fonte verde dopo lettura PDF fascicolo; resta con limite basso e pubblicazione guarded.",
    "dati_normattiva": "Catalogo tecnico Normattiva: evidenza RAG, non news.",
    "eur_lex": "Fonte UE ufficiale: RAG-only finche' il parser CELEX dedicato non e' stabilizzato.",
    "istat_prezzi": "Fonte dati per rivalutazioni e calcoli: RAG/calcoli, non news generica.",
    "openga_giustizia_amministrativa": "Catalogo OpenGA generale: RAG-only, non pubblicazione news.",
    "openga_calendario_udienze": "OpenGA calendario udienze: dato di stato RAG-only, non news.",
    "openga_sentenze": "OpenGA tabellare: RAG-only salvo risorsa documentale concreta.",
    "openga_ordinanze": "OpenGA tabellare: RAG-only salvo risorsa documentale concreta.",
    "openga_decreti": "OpenGA tabellare: RAG-only salvo risorsa documentale concreta.",
    "openga_pareri": "OpenGA tabellare: RAG-only salvo risorsa documentale concreta.",
    "openga_provvedimenti_pubblicati": "OpenGA provvedimenti: RAG-only salvo documento concreto con chiavi minime.",
    "openga_ricorsi_definiti": "OpenGA ricorsi definiti: dato di stato RAG-only, non news.",
    "openga_ricorsi_pendenti": "OpenGA ricorsi pendenti: dato di stato RAG-only, non news.",
    "openga_ricorsi_pervenuti": "OpenGA ricorsi pervenuti: dato di stato RAG-only, non news.",
    "pst_giustizia_download": "Fonte tecnica PST: evidenza RAG telematica, non pubblicazione news.",
    "normattiva": "Archivio ufficiale locale: interrogazione RAG normativa, non batch fonte web.",
    "codice_civile": "Codice governato da archivio Normattiva locale.",
    "codice_procedura_civile": "Codice governato da archivio Normattiva locale.",
    "codice_penale": "Codice governato da archivio Normattiva locale.",
    "codice_procedura_penale": "Codice governato da archivio Normattiva locale.",
    "codice_processo_amministrativo": "Codice governato da archivio Normattiva locale.",
    "codice_strada": "Codice governato da archivio Normattiva locale.",
    "cassazione_massimario": "In osservazione: fonte Cassazione derivata dal massimario, da schedulare solo con canary verde dedicato.",
    "cassazione_citazioni_verificate": "In osservazione: fonte derivata, non schedulata finche' il dettaglio citazione non ha canary verde dedicato.",
    "corte_costituzionale": "In osservazione: la fonte diretta deve restituire schede pronuncia verificabili senza fallback.",
    "giustizia_amministrativa": "In osservazione: fonte HTML diretta disabilitata finche' canale, paginazione e allegati non sono stabili.",
    "giustizia_amministrativa_decisioni_pareri": "In osservazione: decisioni/pareri HTML richiedono canary dedicato prima della pubblicazione.",
    "inps_sentenze": "In osservazione: feed giurisprudenziale non ancora collaudato in publish guarded.",
    "agenzia_entrate": "In osservazione: richiede canary dedicato su documenti prassi tributaria.",
    "ministero_lavoro": "In osservazione: richiede filtro documentale stabile.",
    "ministero_lavoro_interpelli": "In osservazione: richiede canary dedicato sugli interpelli con allegati.",
    "agcm_bollettino": "In osservazione: richiede filtro stabile su bollettini e provvedimenti.",
    "banca_italia_normativa": "In osservazione: richiede canary dedicato su provvedimenti vigilanza.",
    "inail_istruzioni_operative": "In osservazione: fonte disabilitata finche' il canale non e' stabile.",
    "mimit_incentivi": "In osservazione/RAG: pubblicare solo documenti operativi utili, non news generiche.",
}
LEGAL_UPDATE_PROGRESSIVE_EXCLUDED_SOURCE_REASONS: dict[str, str] = {
    "anac_documenti": (
        "Esclusa dalla fase 9 progressiva: in fase 5 e nel canary alcune schede richiedono "
        "conferme ulteriori prima della pubblicazione governata."
    ),
    "garante_privacy": (
        "Esclusa dalla fase 9 progressiva: fonte utile ma ancora da osservare per allegati, "
        "riferimenti ritrovabili e qualità costante delle schede."
    ),
    "gazzetta_ufficiale": (
        "Gestita dagli archivi ufficiali locali della fase 6; non entra nel "
        "primo scheduler progressivo degli aggiornamenti fonte."
    ),
    "normattiva": (
        "Gestita dagli archivi ufficiali locali della fase 6; nessun import "
        "massivo notturno nella fase 9."
    ),
    "dati_normattiva": (
        "Canale tecnico Normattiva: resta fuori dal primo scheduler progressivo."
    ),
    "corte_costituzionale": (
        "Esclusa finché la fonte diretta non restituisce schede pronuncia "
        "verificabili senza fallback di navigazione."
    ),
    "openga_sentenze": (
        "Open data tabellare: resta RAG-only o in osservazione finché non "
        "vengono promossi solo documenti concreti."
    ),
    "pst_giustizia_download": (
        "Fonte tecnica: non pubblicabile come aggiornamento legale automatico."
    ),
}
LEGAL_UPDATE_PROGRESSIVE_EXCLUDED_SOURCE_REASONS = {
    code: LEGAL_UPDATE_PROGRESSIVE_CLASSIFICATION_REASONS.get(
        code,
        "Non pubblicabile nella fase 9: serve canary verde dedicato o resta solo RAG.",
    )
    for code in LEGAL_UPDATE_PROGRESSIVE_EXCLUDED_PUBLICATION_SOURCE_CODES
}

LEGAL_SOURCE_QUALITY_QUESTIONS: tuple[str, ...] = (
    "La fonte risulta censita nel database?",
    "La pagina ufficiale o pubblica e' raggiungibile?",
    "Sono presenti allegati, PDF o documenti collegati?",
    "Gli allegati sono stati scaricati e hashati?",
    "Il testo e' stato estratto oppure passato da OCR?",
    "Il testo OCR e' pulito o marcato come sporco?",
    "Sono state estratte norme, R.G., date e riferimenti utili?",
    "Ci sono discrepanze tra scheda, PDF, R.G., date o titolo?",
    "Il documento e' pronto per Memory Tree e RAG?",
    "Lex puo' rispondere con sintesi vera, link cliccabile e limiti chiari?",
)


def is_legal_update_progressive_step1_source(source_code: Any) -> bool:
    return _source_code(source_code) in LEGAL_UPDATE_PROGRESSIVE_STEP1_SOURCE_CODES


def legal_update_progressive_source_classification(source_code: Any) -> str:
    code = _source_code(source_code)
    return LEGAL_UPDATE_PROGRESSIVE_SOURCE_CLASSIFICATION.get(code, "fuori_perimetro")


def legal_update_progressive_publication_policy(source_code: Any) -> str:
    code = _source_code(source_code)
    return LEGAL_UPDATE_PROGRESSIVE_PUBLICATION_POLICY.get(code, "blocked")


def legal_update_progressive_step1_source_codes(
    sources: Sequence[Mapping[str, Any]] | None = None,
) -> tuple[str, ...]:
    if sources is None:
        return LEGAL_UPDATE_PROGRESSIVE_STEP1_SOURCE_CODES
    by_code = {_source_code(source.get("code")): dict(source or {}) for source in sources}
    selected: list[str] = []
    for code in LEGAL_UPDATE_PROGRESSIVE_STEP1_SOURCE_CODES:
        source = by_code.get(code)
        if source is None:
            continue
        if bool(source.get("enabled", True)):
            selected.append(code)
    return tuple(selected)


def legal_update_progressive_exclusion_reason(source_code: Any) -> str:
    code = _source_code(source_code)
    if not code or code in LEGAL_UPDATE_PROGRESSIVE_STEP1_SOURCE_CODES:
        return ""
    return LEGAL_UPDATE_PROGRESSIVE_EXCLUDED_SOURCE_REASONS.get(
        code,
        "Non incluso nella fase 9 progressiva: resta fuori scheduler finché non passa un canary/report verde dedicato.",
    )


def legal_update_progressive_scheduler_payload(
    sources: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    enabled_codes = legal_update_progressive_step1_source_codes(sources)
    excluded: list[dict[str, str]] = []
    for source in sources or ():
        code = _source_code(source.get("code"))
        reason = legal_update_progressive_exclusion_reason(code)
        if reason:
            excluded.append(
                {
                    "source_code": code,
                    "source_name": str(source.get("name") or code),
                    "reason": reason,
                }
            )
    return {
        "step": LEGAL_UPDATE_PROGRESSIVE_STEP,
        "enabled_source_codes": list(enabled_codes),
        "green_enabled_source_codes": list(LEGAL_UPDATE_PROGRESSIVE_STEP1_SOURCE_CODES),
        "rag_only_source_codes": list(LEGAL_UPDATE_PROGRESSIVE_RAG_ONLY_SOURCE_CODES),
        "observation_source_codes": list(LEGAL_UPDATE_PROGRESSIVE_OBSERVATION_SOURCE_CODES),
        "archive_source_codes": list(LEGAL_UPDATE_PROGRESSIVE_ARCHIVE_SOURCE_CODES),
        "excluded_publication_source_codes": list(LEGAL_UPDATE_PROGRESSIVE_EXCLUDED_PUBLICATION_SOURCE_CODES),
        "source_classification": dict(LEGAL_UPDATE_PROGRESSIVE_SOURCE_CLASSIFICATION),
        "publication_policy": dict(LEGAL_UPDATE_PROGRESSIVE_PUBLICATION_POLICY),
        "lot_source_codes": {key: list(value) for key, value in LEGAL_UPDATE_PROGRESSIVE_LOTS.items()},
        "excluded_sources": excluded,
        "source_budget": LEGAL_UPDATE_PROGRESSIVE_SOURCE_BUDGET,
        "publish_max_items": LEGAL_UPDATE_PROGRESSIVE_PUBLISH_MAX_ITEMS,
        "item_timeout_seconds": LEGAL_UPDATE_PROGRESSIVE_ITEM_TIMEOUT_SECONDS,
        "cassazione_latest_max_items": LEGAL_UPDATE_PROGRESSIVE_CASSAZIONE_MAX_ITEMS,
        "publication_mode": "guarded",
    }


@dataclass(frozen=True)
class LegalAutoFetchConfig:
    intelligence_db: str
    giurisprudenza_db: str = ""
    ai_base_url: str = ""
    ai_model: str = "mistral"
    queue_db_path: str = ""
    cursor_path: str = ""
    source_budget: int = LEGAL_UPDATE_PROGRESSIVE_SOURCE_BUDGET
    publish_max_items: int = LEGAL_UPDATE_PROGRESSIVE_PUBLISH_MAX_ITEMS
    item_timeout_seconds: int = LEGAL_UPDATE_PROGRESSIVE_ITEM_TIMEOUT_SECONDS
    max_attempts: int = 3
    execute_due_sources: bool = True
    export_json_enabled: bool = False
    mirror_giurisprudenza_json_enabled: bool = False

    @classmethod
    def from_job_config(
        cls,
        config: LegalUpdateJobConfig,
        *,
        queue_db_path: str = "",
        cursor_path: str = "",
        source_budget: int = LEGAL_UPDATE_PROGRESSIVE_SOURCE_BUDGET,
        publish_max_items: int = LEGAL_UPDATE_PROGRESSIVE_PUBLISH_MAX_ITEMS,
        item_timeout_seconds: int = LEGAL_UPDATE_PROGRESSIVE_ITEM_TIMEOUT_SECONDS,
        max_attempts: int = 3,
        execute_due_sources: bool = True,
    ) -> "LegalAutoFetchConfig":
        return cls(
            intelligence_db=config.intelligence_db,
            giurisprudenza_db=config.giurisprudenza_db,
            ai_base_url=config.ai_base_url,
            ai_model=config.ai_model,
            queue_db_path=queue_db_path,
            cursor_path=cursor_path,
            source_budget=source_budget,
            publish_max_items=publish_max_items,
            item_timeout_seconds=item_timeout_seconds,
            max_attempts=max_attempts,
            execute_due_sources=execute_due_sources,
            export_json_enabled=config.export_json_enabled,
            mirror_giurisprudenza_json_enabled=config.mirror_giurisprudenza_json_enabled,
        )

    def to_job_config(self) -> LegalUpdateJobConfig:
        return LegalUpdateJobConfig(
            intelligence_db=self.intelligence_db,
            giurisprudenza_db=self.giurisprudenza_db,
            ai_base_url=self.ai_base_url,
            ai_model=self.ai_model,
            export_json_enabled=self.export_json_enabled,
            mirror_giurisprudenza_json_enabled=self.mirror_giurisprudenza_json_enabled,
        )


class LegalAutoFetchCursorStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> dict[str, Any]:
        if not self.path.is_file():
            return {"schema": LEGAL_UPDATE_AUTOFETCH_SCHEMA, "sources": {}}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return {"schema": LEGAL_UPDATE_AUTOFETCH_SCHEMA, "sources": {}}
        if not isinstance(payload, dict):
            return {"schema": LEGAL_UPDATE_AUTOFETCH_SCHEMA, "sources": {}}
        payload.setdefault("schema", LEGAL_UPDATE_AUTOFETCH_SCHEMA)
        payload.setdefault("sources", {})
        return payload

    def save(self, payload: Mapping[str, Any]) -> None:
        data = dict(payload or {})
        data["schema"] = LEGAL_UPDATE_AUTOFETCH_SCHEMA
        data.setdefault("sources", {})
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")

    def mark_enqueued(self, source_code: str, *, enqueued_at: str, job_id: str, due_reason: str) -> None:
        payload = self.load()
        sources = dict(payload.get("sources") or {})
        row = dict(sources.get(_source_code(source_code)) or {})
        row.update(
            {
                "source_code": _source_code(source_code),
                "last_enqueued_at": enqueued_at,
                "last_job_id": job_id,
                "last_due_reason": due_reason,
            }
        )
        sources[_source_code(source_code)] = row
        payload["sources"] = sources
        payload["updated_at"] = enqueued_at
        self.save(payload)

    def mark_result(self, source_code: str, *, status: str, finished_at: str, error: str = "") -> None:
        payload = self.load()
        sources = dict(payload.get("sources") or {})
        row = dict(sources.get(_source_code(source_code)) or {})
        failures = int(row.get("consecutive_failures") or 0)
        if status == "completed":
            failures = 0
        elif status in {"failed", "timeout"}:
            failures += 1
        row.update(
            {
                "source_code": _source_code(source_code),
                "last_status": status,
                "last_finished_at": finished_at,
                "last_error": error,
                "consecutive_failures": failures,
            }
        )
        sources[_source_code(source_code)] = row
        payload["sources"] = sources
        payload["updated_at"] = finished_at
        self.save(payload)


def build_legal_autofetch_plan(
    sources: Sequence[Mapping[str, Any]],
    *,
    cursor_payload: Mapping[str, Any] | None = None,
    now: datetime | None = None,
    source_budget: int = 8,
    only_source_codes: Iterable[str] = (),
) -> dict[str, Any]:
    now_dt = now or datetime.now(tz=UTC)
    cursors = dict((cursor_payload or {}).get("sources") or {})
    allowed = {_source_code(code) for code in only_source_codes if _source_code(code)}
    candidates: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    for raw_source in sources:
        source = dict(raw_source or {})
        code = _source_code(source.get("code"))
        if not code:
            continue
        if allowed and code not in allowed:
            skipped.append({"source_code": code, "reason": "fuori_selezione"})
            continue
        if not bool(source.get("enabled", True)):
            skipped.append({"source_code": code, "reason": "fonte_disattivata"})
            continue
        cursor = dict(cursors.get(code) or {})
        interval_minutes = _positive_int(source.get("polling_minutes"), 1440)
        last_enqueued = _parse_dt(cursor.get("last_enqueued_at"))
        due_at = (last_enqueued + timedelta(minutes=interval_minutes)) if last_enqueued else now_dt
        due = last_enqueued is None or now_dt >= due_at
        if not due:
            skipped.append(
                {
                    "source_code": code,
                    "reason": "non_ancora_dovuta",
                    "due_at": _iso(due_at),
                }
            )
            continue
        failures = int(cursor.get("consecutive_failures") or 0)
        priority = _source_priority(source) + min(failures, 5)
        candidates.append(
            {
                "schema": LEGAL_UPDATE_AUTOFETCH_SCHEMA,
                "source_code": code,
                "source_name": str(source.get("name") or code),
                "source_id": int(source.get("id") or 0),
                "base_url": str(source.get("base_url") or ""),
                "category": str(source.get("category") or ""),
                "is_official": bool(source.get("is_official")),
                "polling_minutes": interval_minutes,
                "last_enqueued_at": str(cursor.get("last_enqueued_at") or ""),
                "due_at": _iso(due_at),
                "due_reason": "mai_eseguita" if last_enqueued is None else "intervallo_scaduto",
                "priority": priority,
                "quality_questions": list(LEGAL_SOURCE_QUALITY_QUESTIONS),
            }
        )

    budget = max(1, int(source_budget or 1))
    selected = sorted(candidates, key=lambda row: (-int(row["priority"]), row["due_at"], row["source_code"]))[:budget]
    overflow = [row | {"reason": "oltre_budget"} for row in candidates if row not in selected]
    return {
        "schema": LEGAL_UPDATE_AUTOFETCH_SCHEMA,
        "generated_at": _iso(now_dt),
        "source_budget": budget,
        "selected": selected,
        "skipped": skipped + overflow,
        "selected_count": len(selected),
        "skipped_count": len(skipped) + len(overflow),
        "quality_questions": list(LEGAL_SOURCE_QUALITY_QUESTIONS),
    }


def build_legal_update_progressive_run_plan(
    config: LegalAutoFetchConfig,
    *,
    pipeline: LegalUpdatePipeline | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Piano del ciclo progressivo controllato, senza enqueue o pubblicazione."""

    runtime_pipeline = pipeline or build_legal_update_pipeline(
        config.intelligence_db,
        giurisprudenza_db_path=config.giurisprudenza_db,
        ai_base_url=config.ai_base_url,
        ai_model=config.ai_model,
        export_json_enabled=config.export_json_enabled,
        mirror_giurisprudenza_json_enabled=config.mirror_giurisprudenza_json_enabled,
    )
    sources = list(runtime_pipeline.repository.list_sources(enabled_only=False))
    green_source_codes = legal_update_progressive_step1_source_codes(sources)
    cursor_payload = LegalAutoFetchCursorStore(_cursor_path(config)).load()
    plan = build_legal_autofetch_plan(
        sources,
        cursor_payload=cursor_payload,
        now=now,
        source_budget=config.source_budget,
        only_source_codes=green_source_codes,
    )
    excluded_sources: list[dict[str, Any]] = []
    for source in sources:
        code = _source_code(source.get("code"))
        if not code or code in green_source_codes:
            continue
        excluded_sources.append(
            {
                "source_code": code,
                "source_name": str(source.get("name") or code),
                "classification": legal_update_progressive_source_classification(code),
                "publication_policy": legal_update_progressive_publication_policy(code),
                "reason": legal_update_progressive_exclusion_reason(code),
            }
        )
    return {
        "ok": True,
        "schema": LEGAL_UPDATE_AUTOFETCH_SCHEMA,
        "mode": "progressive_controlled_cycle_plan",
        "publication_mode": "guarded",
        "guarded_only": True,
        "will_execute": False,
        "green_source_codes": list(green_source_codes),
        "rag_only_source_codes": list(LEGAL_UPDATE_PROGRESSIVE_RAG_ONLY_SOURCE_CODES),
        "observation_source_codes": list(LEGAL_UPDATE_PROGRESSIVE_OBSERVATION_SOURCE_CODES),
        "archive_source_codes": list(LEGAL_UPDATE_PROGRESSIVE_ARCHIVE_SOURCE_CODES),
        "excluded_sources": excluded_sources,
        "source_budget": config.source_budget,
        "publish_max_items": config.publish_max_items,
        "item_timeout_seconds": config.item_timeout_seconds,
        "max_attempts": config.max_attempts,
        "plan": plan,
    }


def run_legal_update_progressive_cycle(
    config: LegalAutoFetchConfig,
    *,
    guarded_only: bool,
    dry_run: bool = False,
    pipeline: LegalUpdatePipeline | None = None,
    runner: Any = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Esegue un solo ciclo autofetch controllato sulle sole fonti verdi."""

    if not guarded_only:
        raise ValueError("--guarded-only e' obbligatorio per il ciclo progressivo controllato")
    runtime_pipeline = pipeline or build_legal_update_pipeline(
        config.intelligence_db,
        giurisprudenza_db_path=config.giurisprudenza_db,
        ai_base_url=config.ai_base_url,
        ai_model=config.ai_model,
        export_json_enabled=config.export_json_enabled,
        mirror_giurisprudenza_json_enabled=config.mirror_giurisprudenza_json_enabled,
    )
    plan_payload = build_legal_update_progressive_run_plan(config, pipeline=runtime_pipeline, now=now)
    if dry_run:
        return {
            **plan_payload,
            "mode": "progressive_controlled_cycle_dry_run",
            "dry_run": True,
            "executed": False,
            "enqueued_jobs": [],
            "execution_report": {
                "ok": True,
                "mode": "dry_run",
                "reports": [],
                "published": 0,
                "scarti": [],
                "errors": [],
            },
        }

    result = run_legal_update_autofetch_tick(
        config,
        pipeline=runtime_pipeline,
        source_codes=plan_payload["green_source_codes"],
        runner=runner,
        now=now,
    )
    execution_report = dict(result.get("execution_report") or {})
    return {
        **result,
        "mode": "progressive_controlled_cycle",
        "publication_mode": "guarded",
        "guarded_only": True,
        "dry_run": False,
        "executed": True,
        "green_source_codes": plan_payload["green_source_codes"],
        "excluded_sources": plan_payload["excluded_sources"],
        "published": int((execution_report.get("autopublished") or {}).get("count") or 0),
        "scarti": list(execution_report.get("skipped") or []),
        "errors": list(execution_report.get("errors") or []),
    }


def run_legal_update_autofetch_tick(
    config: LegalAutoFetchConfig,
    *,
    pipeline: LegalUpdatePipeline | None = None,
    source_codes: Sequence[str] = (),
    runner: Any = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    runtime_pipeline = pipeline or build_legal_update_pipeline(
        config.intelligence_db,
        giurisprudenza_db_path=config.giurisprudenza_db,
        ai_base_url=config.ai_base_url,
        ai_model=config.ai_model,
        export_json_enabled=config.export_json_enabled,
        mirror_giurisprudenza_json_enabled=config.mirror_giurisprudenza_json_enabled,
    )
    queue = LegalUpdateJobQueue(_queue_path(config))
    cursor_store = LegalAutoFetchCursorStore(_cursor_path(config))
    cursor_payload = cursor_store.load()
    sources = runtime_pipeline.repository.list_sources(enabled_only=False)
    plan = build_legal_autofetch_plan(
        sources,
        cursor_payload=cursor_payload,
        now=now,
        source_budget=config.source_budget,
        only_source_codes=source_codes,
    )
    enqueued_jobs = []
    generated_at = str(plan.get("generated_at") or _iso(now or datetime.now(tz=UTC)))
    for item in plan["selected"]:
        job = queue.enqueue(
            source_code=item["source_code"],
            source_name=item["source_name"],
            item_url=item["base_url"],
            item_title=item["source_name"],
            item_kind="fonte",
            payload={
                "schema": LEGAL_UPDATE_AUTOFETCH_SCHEMA,
                "mode": "autofetch_governato",
                "source_code": item["source_code"],
                "source_id": item["source_id"],
                "source_name": item["source_name"],
                "base_url": item["base_url"],
                "due_reason": item["due_reason"],
                "quality_questions": item["quality_questions"],
            },
            timeout_seconds=config.item_timeout_seconds,
            max_attempts=config.max_attempts,
        )
        enqueued_jobs.append(job.to_dict())
        cursor_store.mark_enqueued(
            item["source_code"],
            enqueued_at=generated_at,
            job_id=job.job_id,
            due_reason=str(item.get("due_reason") or ""),
        )

    execution_report: dict[str, Any] = {"ok": True, "mode": "enqueue_only", "reports": []}
    selected_codes = [str(item.get("source_code") or "") for item in plan["selected"]]
    if config.execute_due_sources and selected_codes:
        execution_report = run_legal_update_batch_with_timeouts(
            config.to_job_config(),
            source_codes=selected_codes,
            auto_publish=True,
            item_timeout_seconds=config.item_timeout_seconds,
            publish_max_items=config.publish_max_items,
            runner=runner,
        )
        for row in list(execution_report.get("reports") or []):
            code = _source_code(row.get("label"))
            if not code:
                continue
            status = "completed" if row.get("ok") else ("timeout" if row.get("timeout") else "failed")
            cursor_store.mark_result(
                code,
                status=status,
                finished_at=str(row.get("finished_at") or generated_at),
                error=str(row.get("stderr") or row.get("inner_errors") or ""),
            )

    monitor = build_legal_update_operational_monitor(
        config,
        pipeline=runtime_pipeline,
        queue=queue,
        cursor_payload=cursor_store.load(),
    )
    return {
        "ok": bool(execution_report.get("ok", True)),
        "schema": LEGAL_UPDATE_AUTOFETCH_SCHEMA,
        "queue_schema": LEGAL_UPDATE_JOB_QUEUE_SCHEMA,
        "plan": plan,
        "enqueued_jobs": enqueued_jobs,
        "execution_report": execution_report,
        "monitor": monitor,
    }


def build_legal_update_operational_monitor(
    config: LegalAutoFetchConfig,
    *,
    pipeline: LegalUpdatePipeline | None = None,
    queue: LegalUpdateJobQueue | None = None,
    cursor_payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    runtime_pipeline = pipeline or build_legal_update_pipeline(
        config.intelligence_db,
        giurisprudenza_db_path=config.giurisprudenza_db,
        ai_base_url=config.ai_base_url,
        ai_model=config.ai_model,
        export_json_enabled=config.export_json_enabled,
        mirror_giurisprudenza_json_enabled=config.mirror_giurisprudenza_json_enabled,
    )
    runtime_queue = queue or LegalUpdateJobQueue(_queue_path(config))
    recovered_stale_jobs = runtime_queue.recover_stale_running()
    snapshot = runtime_pipeline.dashboard_snapshot()
    sources = runtime_pipeline.repository.list_sources(enabled_only=False)
    activity = runtime_pipeline.repository.source_activity_summary()
    agent_runs = runtime_pipeline.repository.latest_source_agent_runs()
    cursors = dict((cursor_payload or {}).get("sources") or {})
    source_rows = [
        _source_monitor_row(source, activity.get(_source_code(source.get("code")), {}), agent_runs.get(_source_code(source.get("code"))), cursors)
        for source in sources
    ]
    jobs = [job.to_dict() for job in runtime_queue.list_jobs(limit=20)]
    queue_summary = runtime_queue.summary()
    blocked = [
        row for row in source_rows
        if row["status"] in {"da_verificare", "non_pronta"}
    ]
    return {
        "schema": LEGAL_UPDATE_AUTOFETCH_SCHEMA,
        "generated_at": _iso(datetime.now(tz=UTC)),
        "queue": queue_summary,
        "recovered_stale_jobs": recovered_stale_jobs,
        "recent_jobs": jobs,
        "sources": source_rows,
        "sources_total": len(source_rows),
        "sources_ready": sum(1 for row in source_rows if row["status"] == "pronta"),
        "sources_not_ready": len(blocked),
        "quality_questions": list(LEGAL_SOURCE_QUALITY_QUESTIONS),
        "dashboard_counts": snapshot.get("headline") or snapshot,
        "readiness": {
            "status": "pronto" if not blocked and int(queue_summary.get("failed") or 0) == 0 and int(queue_summary.get("timeout") or 0) == 0 else "da_verificare",
            "blocked_sources": len(blocked),
            "queued_jobs": int(queue_summary.get("queued") or 0),
            "running_jobs": int(queue_summary.get("running") or 0),
            "failed_jobs": int(queue_summary.get("failed") or 0),
            "timeout_jobs": int(queue_summary.get("timeout") or 0),
        },
    }


def _source_monitor_row(
    source: Mapping[str, Any],
    activity: Mapping[str, Any],
    agent_run: Mapping[str, Any] | None,
    cursors: Mapping[str, Any],
) -> dict[str, Any]:
    code = _source_code(source.get("code"))
    raw_documents = _positive_int(activity.get("raw_documents"), 0)
    normalized_documents = _positive_int(activity.get("normalized_documents"), 0)
    review_pending = _positive_int(activity.get("review_pending"), 0)
    review_published = _positive_int(activity.get("review_published"), 0)
    cursor = dict(cursors.get(code) or {})
    latest_status = str((agent_run or {}).get("status") or cursor.get("last_status") or "").lower()
    has_acquired_documents = bool(raw_documents or normalized_documents or review_published)
    if not bool(source.get("enabled", True)):
        status = "non_monitorata"
        reason = "Fonte disattivata."
    elif has_acquired_documents:
        status = "pronta"
        if review_published:
            reason = "Fonte acquisita, indicizzata e pubblicata."
        elif normalized_documents:
            reason = "Fonte acquisita e indicizzata per Ricerca Legale e Lex/RAG."
        else:
            reason = "Fonte acquisita nel repository aggiornamenti."
        if latest_status in {"failed", "timeout"}:
            detail = str((agent_run or {}).get("error_message") or cursor.get("last_error") or "Ultimo controllo tecnico da riprendere.")
            reason = f"{reason} Controllo successivo da riprendere: {detail}"
    elif latest_status in {"failed", "timeout"}:
        status = "da_verificare"
        reason = str((agent_run or {}).get("error_message") or cursor.get("last_error") or "Ultimo controllo non riuscito.")
    else:
        status = "non_pronta"
        reason = "Fonte censita ma ancora senza documenti acquisiti."
    return {
        "source_code": code,
        "source_name": str(source.get("name") or code),
        "enabled": bool(source.get("enabled", True)),
        "is_official": bool(source.get("is_official")),
        "status": status,
        "reason": reason,
        "raw_documents": raw_documents,
        "normalized_documents": normalized_documents,
        "review_pending": review_pending,
        "review_published": review_published,
        "last_enqueued_at": str(cursor.get("last_enqueued_at") or ""),
        "last_finished_at": str(cursor.get("last_finished_at") or (agent_run or {}).get("finished_at") or ""),
        "last_job_id": str(cursor.get("last_job_id") or ""),
        "consecutive_failures": _positive_int(cursor.get("consecutive_failures"), 0),
    }


def _queue_path(config: LegalAutoFetchConfig) -> Path:
    if str(config.queue_db_path or "").strip():
        return Path(config.queue_db_path)
    return Path(str(config.intelligence_db or "./intelligence/motori.json")).parent / "legal_update_jobs.sqlite"


def _cursor_path(config: LegalAutoFetchConfig) -> Path:
    if str(config.cursor_path or "").strip():
        return Path(config.cursor_path)
    return Path(str(config.intelligence_db or "./intelligence/motori.json")).parent / "legal_autofetch_cursors.json"


def _source_priority(source: Mapping[str, Any]) -> int:
    score = 0
    if bool(source.get("is_official")):
        score += 10
    category = str(source.get("category") or "").lower()
    if category == "giurisprudenza":
        score += 5
    if category == "normativa":
        score += 4
    return score


def _source_code(value: Any) -> str:
    return "_".join(str(value or "").strip().lower().split())


def _positive_int(value: Any, default: int) -> int:
    try:
        parsed = int(value or 0)
        return parsed if parsed > 0 else default
    except (TypeError, ValueError):
        return default


def _parse_dt(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _iso(value: datetime) -> str:
    normalized = value if value.tzinfo else value.replace(tzinfo=UTC)
    return normalized.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
