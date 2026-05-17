"""Stato leggibile di Lex AI per le pagine operative dello studio."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable, Mapping


LEGAL_AGENT_FOCUS: tuple[str, ...] = (
    "fonti_legal_update",
    "giurisprudenza_cassazione",
    "ai_locale_rag_runtime",
    "redazione_atti_editor",
)

GIURISPRUDENZA_AGENT_FOCUS: tuple[str, ...] = (
    "giurisprudenza_cassazione",
    "fonti_legal_update",
    "ai_locale_rag_runtime",
)


def _text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _short(value: Any, limit: int = 180) -> str:
    text = _text(value)
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "..."


def _item(iid: str, label: str, value: Any, note: str = "", tone: str = "neutral") -> dict[str, Any]:
    return {"id": iid, "label": label, "value": value, "note": note, "tone": tone}


def _section(sid: str, title: str, kind: str, items: list[dict[str, Any]], empty: str) -> dict[str, Any]:
    return {"id": sid, "title": title, "kind": kind, "items": items, "emptyMessage": empty}


def _metric(mid: str, label: str, value: Any, note: str, tone: str = "neutral") -> dict[str, Any]:
    return {"id": mid, "label": label, "value": value, "note": note, "tone": tone}


def _status_label(value: Any) -> str:
    status = _text(value).lower().replace("_", " ")
    if status == "ok":
        return "Pronto"
    if status in {"da verificare", "pending", "in revisione"}:
        return "Da verificare"
    if status in {"errore", "failed", "fallita"}:
        return "Verifica non riuscita"
    if status:
        return status[:1].upper() + status[1:]
    return "Non ancora controllato"


def _status_tone(value: Any) -> str:
    status = _text(value).lower().replace("_", " ")
    if status == "ok":
        return "success"
    if status in {"errore", "failed", "fallita"}:
        return "danger"
    if status in {"da verificare", "pending", "in revisione", ""}:
        return "warning"
    return "info"


def _capability_tone(value: Any) -> str:
    status = _text(value).lower()
    if status in {"ready_to_measure", "ready_to_test", "ready_to_evaluate"}:
        return "warning"
    if status in {"blocked", "missing_credentials", "missing_endpoint", "missing_index"}:
        return "warning"
    if status in {"disabled", "available_optional"}:
        return "neutral"
    return "info"


def _parse_date(value: Any) -> datetime | None:
    text = _text(value)
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _latest_by_date(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    latest: dict[str, Any] = {}
    latest_dt: datetime | None = None
    for row in rows:
        candidate = dict(row)
        candidate_dt = _parse_date(
            candidate.get("generated_at")
            or candidate.get("ended_at")
            or candidate.get("checked_at")
            or candidate.get("started_at")
        )
        if latest_dt is None or (candidate_dt is not None and candidate_dt >= latest_dt):
            latest = candidate
            latest_dt = candidate_dt
    return latest


def _agent_definitions() -> dict[str, Any]:
    try:
        from lex.operational_knowledge.agents import build_default_agent_registry

        return {agent.agent_id: agent for agent in build_default_agent_registry().all()}
    except Exception:
        return {}


def _load_agents(config: Mapping[str, Any] | None = None) -> dict[str, Any]:
    try:
        from lex.operational_knowledge.nightly_agents import load_operational_agents_payload

        return load_operational_agents_payload(config=dict(config or {}))
    except Exception:
        return {"latest": {}, "runs": []}


def _agent_rows(
    *,
    config: Mapping[str, Any] | None = None,
    focus_agent_ids: Iterable[str] = LEGAL_AGENT_FOCUS,
) -> list[dict[str, Any]]:
    definitions = _agent_definitions()
    payload = _load_agents(config)
    latest = payload.get("latest") if isinstance(payload.get("latest"), dict) else {}
    rows: list[dict[str, Any]] = []
    for agent_id in [agent for agent in focus_agent_ids if _text(agent)]:
        definition = definitions.get(agent_id)
        tenant_runs = latest.get(agent_id) if isinstance(latest.get(agent_id), dict) else {}
        run = _latest_by_date([row for row in tenant_runs.values() if isinstance(row, Mapping)])
        status = _text(run.get("status")) or "da_verificare"
        generated_at = _text(run.get("generated_at") or run.get("ended_at") or run.get("checked_at"))
        rows.append(
            {
                "agent_id": agent_id,
                "label": _text(getattr(definition, "display_name", "")) or agent_id.replace("_", " ").title(),
                "status": status,
                "status_label": _status_label(status),
                "tone": _status_tone(status),
                "generated_at": generated_at,
                "note": _short(run.get("self_check") or run.get("supervisor_check") or "Controllo notturno non ancora confermato."),
            }
        )
    return rows


def build_lex_agent_metric(
    *,
    config: Mapping[str, Any] | None = None,
    focus_agent_ids: Iterable[str] = LEGAL_AGENT_FOCUS,
) -> dict[str, Any]:
    rows = _agent_rows(config=config, focus_agent_ids=focus_agent_ids)
    total = len(rows)
    ok = sum(1 for row in rows if row["status"] == "ok")
    review = total - ok
    latest = max((_text(row.get("generated_at")) for row in rows if _text(row.get("generated_at"))), default="")
    note = f"{ok}/{total} pronti"
    if review:
        note = f"{ok}/{total} pronti, {review} da verificare"
    if latest:
        note = f"{note}. Ultimo controllo: {latest}"
    return _metric("agenti_lex", "Agenti Lex", ok, note, "success" if total and ok == total else "warning")


def build_lex_operational_section(
    *,
    config: Mapping[str, Any] | None = None,
    focus_agent_ids: Iterable[str] = LEGAL_AGENT_FOCUS,
    sid: str = "lex_presidio",
    title: str = "Presidio Lex AI",
) -> dict[str, Any]:
    rows = _agent_rows(config=config, focus_agent_ids=focus_agent_ids)
    total = len(rows)
    ok = sum(1 for row in rows if row["status"] == "ok")
    latest = max((_text(row.get("generated_at")) for row in rows if _text(row.get("generated_at"))), default="")
    items = [
        _item(
            "copertura_agenti",
            "Agenti controllati",
            f"{ok}/{total}" if total else 0,
            f"Ultimo controllo: {latest}" if latest else "Controllo notturno non ancora confermato.",
            "success" if total and ok == total else "warning",
        ),
        _item(
            "ricerca_completa",
            "Ricerca completa",
            "Pronta",
            "Prima archivi locali; se non bastano, fonti ufficiali esterne e allegati pubblici quando disponibili.",
            "info",
        ),
    ]
    for row in rows[:6]:
        items.append(
            _item(
                row["agent_id"],
                row["label"],
                row["status_label"],
                row["note"],
                row["tone"],
            )
        )
    return _section(
        sid,
        title,
        "presidio",
        items,
        "Nessun controllo Lex disponibile.",
    )


_ADVANCED_LABELS: dict[str, tuple[str, str]] = {
    "mtp_serving": (
        "Risposte accelerate",
        "Attivabile solo dopo prove misurate sulle risposte Lex dello studio.",
    ),
    "llm_wiki": (
        "Sintesi fonti compilata",
        "Livello di sintesi sopra le fonti: le citazioni restano collegate al documento originale.",
    ),
    "glm_ocr": (
        "Lettura PDF avanzata",
        "Opzione per convertire PDF legali complessi in testo leggibile prima di usarli in Lex.",
    ),
    "gemini_embedding_2": (
        "Ricerca semantica Gemini",
        "Usabile solo con autorizzazione dello studio e reindicizzazione completa dell'archivio interessato.",
    ),
}


def build_advanced_ai_section() -> dict[str, Any]:
    try:
        from lex.advanced_runtime import build_advanced_ai_capabilities

        payload = build_advanced_ai_capabilities()
        capabilities = payload.get("capabilities") if isinstance(payload.get("capabilities"), dict) else {}
    except Exception:
        capabilities = {}
    items: list[dict[str, Any]] = []
    for cap_id, (label, note) in _ADVANCED_LABELS.items():
        cap = capabilities.get(cap_id) if isinstance(capabilities.get(cap_id), Mapping) else {}
        items.append(
            _item(
                cap_id,
                label,
                _text(cap.get("status_label")) or "Da verificare",
                note,
                _capability_tone(cap.get("status")),
            )
        )
    return _section(
        "ai_avanzata",
        "Funzioni Lex avanzate",
        "presidio",
        items,
        "Stato AI avanzata non disponibile.",
    )


def build_official_archive_section() -> dict[str, Any]:
    try:
        from lex.retrieval.official_sources_retriever import official_archive_snapshot

        snapshot = official_archive_snapshot()
    except Exception:
        snapshot = {}
    normattiva = snapshot.get("normattiva") if isinstance(snapshot.get("normattiva"), Mapping) else {}
    gazzetta = snapshot.get("gazzetta") if isinstance(snapshot.get("gazzetta"), Mapping) else {}
    return _section(
        "archivi_ufficiali",
        "Archivi ufficiali locali",
        "fonti",
        [
            _item(
                "normattiva_locale",
                "Normattiva",
                int(normattiva.get("documents") or 0),
                f"{int(normattiva.get('articles') or 0)} articoli indicizzati",
                "success" if normattiva.get("available") else "neutral",
            ),
            _item(
                "gazzetta_locale",
                "Gazzetta Ufficiale",
                int(gazzetta.get("documents") or 0),
                f"{int(gazzetta.get('chunks') or 0)} estratti indicizzati",
                "success" if gazzetta.get("available") else "neutral",
            ),
        ],
        "Archivi ufficiali non disponibili.",
    )


def _is_verified_citation(record: Mapping[str, Any]) -> bool:
    haystack = " ".join(
        _text(record.get(key)).lower()
        for key in (
            "verificationLabel",
            "citationLabel",
            "sourceKind",
            "sourceLabel",
            "evidenceType",
        )
    )
    return any(token in haystack for token in ("verificat", "citabile", "ufficiale", "cassazione"))


def build_verified_citations_section(
    *,
    config: Mapping[str, Any] | None = None,
    records: Iterable[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    record_list = [dict(record) for record in records if isinstance(record, Mapping)]
    verified = sum(1 for record in record_list if _is_verified_citation(record))
    cassazione = next(
        iter(_agent_rows(config=config, focus_agent_ids=("giurisprudenza_cassazione",))),
        {
            "status_label": "Da verificare",
            "tone": "warning",
            "note": "Controllo Cassazione non ancora confermato.",
        },
    )
    return _section(
        "citazioni_verificate",
        "Citazioni verificate",
        "presidio",
        [
            _item(
                "provvedimenti_citabili",
                "Schede citabili",
                verified,
                "Conteggio delle schede con fonte ufficiale o stato di citabilita' verificabile.",
                "success" if verified else "warning",
            ),
            _item(
                "cassazione",
                "Cassazione e massime",
                cassazione["status_label"],
                cassazione["note"],
                cassazione["tone"],
            ),
            _item(
                "regola",
                "Regola citazioni",
                "Fonte riscontrata",
                "Numero, data, sezione e testo restano da verificare quando la fonte non e' completa.",
                "success",
            ),
            _item(
                "allegati_fonte",
                "Allegati fonte",
                "Letti se presenti",
                "La ricerca completa include allegati pubblici ufficiali quando la fonte li espone.",
                "info",
            ),
        ],
        "Nessuna citazione verificabile disponibile.",
    )
