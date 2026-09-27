"""Scheda di una bozza nella pagina React «Revisione della copertura AI».

Riproduce il dettaglio che lo script storico `admin_coverage_review.js`
leggeva da `GET /admin/copertura-ai/api/drafts/<id>` (rotta
`api_draft_detail`): metadati, governo dell'AI, politica di pubblicazione
automatica, specifica JSON modificabile, differenze rispetto alla bozza
iniziale, report di validazione, esempi usati, storico delle revisioni e
anteprima SQL (`generate_sql(spec_json)`).
"""

from __future__ import annotations

import json
from typing import Any

from web.services.react_piattaforma_copertura_ai_comune import (
    ORIGINI,
    azione_revisione,
    blocchi,
    modifica,
    rischio,
    si_no,
    stato_bozza,
)
from web.services.react_piattaforma_sezioni import _t, actions, azione, campo, data_ora, facts, form, notes, table


def dettaglio(repository: Any, draft_id: int) -> dict[str, Any] | None:
    """Gli stessi dati di `api_draft_detail`, nello stesso ordine di lettura."""
    from pct.legal_taxonomy_sql_generator import generate_sql

    row = repository.get_draft(draft_id)
    if not row:
        return None
    spec_json = dict(row.get("spec_json") or {})
    payload: dict[str, Any] = dict(row)
    payload["spec_json"] = spec_json
    payload["draft_spec_original_json"] = dict(row.get("draft_spec_original_json") or {})
    payload["validation_report_json"] = dict(row.get("validation_report_json") or {})
    payload["retrieval_examples_json"] = list(row.get("retrieval_examples_json") or [])
    payload["review_diff_json"] = dict(row.get("review_diff_json") or {})
    payload["review_history"] = repository.list_review_history(draft_id)
    risk_level = str(row.get("risk_level") or "MEDIUM").strip().upper()
    payload["autopublish_policy"] = repository.get_policy(str(row.get("subbranch_code") or ""), risk_level)
    payload["ai_governance"] = {
        "draft_source": str(row.get("draft_source") or "AI"),
        "risk_level": risk_level,
        "auto_publish_eligible": bool(row.get("auto_publish_eligible")),
        "review_required": not bool(row.get("auto_publish_eligible")) or str(row.get("status") or "") not in {"approved", "published"},
        "reviewer": str(row.get("reviewer") or ""),
        "review_signature": str(row.get("review_signature") or ""),
        "review_reason": str(row.get("review_reason") or ""),
        "decision": str(row.get("last_review_action") or ""),
    }
    # La rotta storica falliva per intero se la specifica non genera SQL, e la
    # bozza non si poteva più aprire né correggere: qui l'errore resta
    # nell'anteprima e la specifica rimane modificabile.
    try:
        payload["sql_preview"] = generate_sql(spec_json)
        payload["sql_error"] = ""
    except ValueError as exc:
        payload["sql_preview"] = ""
        payload["sql_error"] = str(exc)
    return payload


# ------------------------------------------------------------------ decisioni


def motivo_approvazione(bozza: dict[str, Any]) -> str:
    """Come lo script storico: il motivo si ripropone solo per la decisione che lo ha registrato."""
    return _t(bozza.get("review_reason")) if _t(bozza.get("last_review_action")) in {"approved", "published"} else ""


def motivo_rifiuto(bozza: dict[str, Any]) -> str:
    return _t(bozza.get("review_reason")) if _t(bozza.get("last_review_action")) == "rejected" else ""


def _firma(bozza: dict[str, Any]) -> dict[str, Any]:
    return campo("review_signature", "Firma del revisore", value=bozza.get("review_signature"), required=True, placeholder="Es. Avv. Mario Rossi - Superamministratore")


def azioni_decisione(bozza: dict[str, Any]) -> list[dict[str, Any]]:
    """Approva, rifiuta e pubblica con firma e motivazione (come i pulsanti storici)."""
    params = {"draft": bozza.get("id")}
    nome = _t(bozza.get("procedure_code")) or _t(bozza.get("subbranch_code"))
    return [
        azione("approva", "Approva", tone="success", params=params, fields=[
            _firma(bozza),
            campo("review_reason", "Motivo dell'approvazione", "textarea", value=motivo_approvazione(bozza), required=True, placeholder="Spiega perché la bozza è corretta, quali correzioni hai fatto e perché la pubblicazione è difendibile."),
        ]),
        azione("rifiuta", "Rifiuta", tone="danger", params=params, fields=[
            _firma(bozza),
            campo("review_reason", "Motivo del rifiuto", "textarea", value=motivo_rifiuto(bozza), required=True, placeholder="Indica il motivo del rifiuto, il rischio legale o i dati mancanti da correggere."),
        ]),
        azione("pubblica", "Pubblica", tone="primary", params=params, confirm=f"Pubblicare «{nome}»? Una bozza non ancora approvata viene approvata con questa firma, poi lo SQL viene applicato al catalogo.", fields=[
            _firma(bozza),
            campo("review_reason", "Motivo dell'approvazione o della pubblicazione", "textarea", value=motivo_approvazione(bozza)),
        ]),
    ]


# ------------------------------------------------------------------ sezioni


def sezioni_validazione(report: dict[str, Any], titolo: str = "Report di validazione") -> list[dict[str, Any]]:
    report = report or {}
    errori = [_t(e) for e in report.get("errors") or [] if _t(e)]
    avvisi = [_t(a) for a in report.get("warnings") or [] if _t(a)]
    return [
        facts(titolo, [
            ("Punteggio di completezza", _t(report.get("score", 0))),
            ("Errori", str(len(errori))),
            ("Avvisi", str(len(avvisi))),
            ("Blocchi mancanti", blocchi(report.get("missing_blocks")) or "nessuno"),
        ]),
        notes("Errori di validazione", errori, tone="danger"),
        notes("Avvisi di validazione", avvisi, tone="warning"),
    ]


def _panoramica(b: dict[str, Any]) -> dict[str, Any]:
    report = b.get("validation_report_json") or {}
    return facts("Panoramica della bozza", [
        ("Sottobranca", _t(b.get("subbranch_code")) or "-"),
        ("Procedura", _t(b.get("procedure_code")) or "-"),
        ("Stato", stato_bozza(b.get("status"))[0]),
        ("Rischio", rischio(b.get("risk_level"))),
        ("Punteggio di validazione", _t(report.get("score", 0))),
        ("Avvisi", str(len(report.get("warnings") or []))),
        ("Pubblicazione automatica", si_no(b.get("auto_publish_eligible"))),
        ("Creata il", data_ora(b.get("created_at")) or "-"),
        ("Ultima revisione", data_ora(b.get("reviewed_at")) or "-"),
        ("Revisore", _t(b.get("reviewer")) or "-"),
        ("Firma del revisore", _t(b.get("review_signature")) or "-"),
        ("Ultima decisione", azione_revisione(b.get("last_review_action")) if _t(b.get("last_review_action")) else "-"),
        ("Motivo della decisione", _t(b.get("review_reason")) or "Nessuna motivazione registrata."),
    ])


def _governo(b: dict[str, Any]) -> dict[str, Any]:
    gov, pol = b.get("ai_governance") or {}, b.get("autopublish_policy") or {}
    return facts("Governo dell'AI e politica di pubblicazione", [
        ("Origine della bozza", ORIGINI.get(_t(gov.get("draft_source")).upper(), _t(gov.get("draft_source")))),
        ("Livello di rischio", rischio(gov.get("risk_level"))),
        ("Idonea alla pubblicazione automatica", si_no(gov.get("auto_publish_eligible"))),
        ("Revisione umana necessaria", si_no(gov.get("review_required"))),
        ("Pubblicazione automatica consentita dalla politica", si_no(pol.get("auto_publish_allowed"))),
        ("Punteggio minimo per saltare la generazione", _t(pol.get("min_score_to_skip_generation"))),
        ("Revisione umana richiesta dalla politica", si_no(pol.get("require_human_review"))),
    ])


def _differenze(b: dict[str, Any]) -> dict[str, Any]:
    sezioni = (b.get("review_diff_json") or {}).get("sections") or []
    return table(
        "Differenze tra bozza iniziale e versione corrente",
        [("section", "Sezione"), ("change", "Modifica"), ("before", "Prima"), ("after", "Dopo"), ("fields", "Campi")],
        [{
            "section": _t(s.get("section")) or "Sezione",
            "change": modifica(s.get("change")),
            "before": s.get("before"),
            "after": s.get("after"),
            "fields": "; ".join(f"{_t(c.get('field'))}: {_t(c.get('before'))} → {_t(c.get('after'))}" for c in s.get("fields") or []),
        } for s in sezioni],
        subtitle="Confronto tra la bozza generata e la versione oggi in revisione.",
        empty="Nessuna differenza registrata tra la bozza iniziale e la versione corrente.",
    )


def _esempi(b: dict[str, Any]) -> dict[str, Any]:
    return table(
        "Esempi usati per costruire la bozza",
        [("name", "Esempio"), ("channel", "Canale"), ("level", "Profilo")],
        [{
            "name": _t(e.get("name") or e.get("procedure_code") or e.get("subbranch_code")) or "Esempio correlato",
            "channel": _t(e.get("channel_code")) or "-",
            "level": _t(e.get("complexity_level") or e.get("risk_level")) or "-",
        } for e in b.get("retrieval_examples_json") or [] if isinstance(e, dict)],
        empty="Nessun esempio disponibile per questa bozza.",
    )


def _storico(b: dict[str, Any]) -> dict[str, Any]:
    return table(
        "Storico delle revisioni",
        [("event", "Evento"), ("when", "Quando"), ("reviewer", "Revisore"), ("signature", "Firma"), ("reason", "Motivo"), ("diff", "Sezioni modificate")],
        [{
            "event": azione_revisione(r.get("review_action")),
            "when": data_ora(r.get("created_at")) or "-",
            "reviewer": _t(r.get("reviewer")) or "-",
            "signature": _t(r.get("reviewer_signature")) or "-",
            "reason": _t(r.get("review_reason")) or "Nessuna motivazione registrata.",
            "diff": _t(((r.get("diff_json") or {}).get("summary") or {}).get("changed_sections") or 0),
        } for r in b.get("review_history") or []],
        subtitle="Salvataggi, approvazioni, rifiuti e pubblicazioni.",
        empty="Nessun evento di revisione registrato per questa bozza.",
    )


def _istruzioni_sql(sql: str) -> list[str]:
    istruzioni, corrente = [], []
    for riga in sql.splitlines():
        if riga.strip():
            corrente.append(riga.strip())
        if riga.rstrip().endswith(";") and corrente:
            istruzioni.append(" ".join(corrente))
            corrente = []
    if corrente:
        istruzioni.append(" ".join(corrente))
    return istruzioni


def _anteprima_sql(b: dict[str, Any]) -> dict[str, Any]:
    if _t(b.get("sql_error")):
        return notes("Anteprima SQL del pubblicatore", [f"La specifica non genera SQL: {_t(b.get('sql_error'))}. Correggila e salva prima di approvare o pubblicare."], tone="danger")
    return notes("Anteprima SQL del pubblicatore", _istruzioni_sql(_t(b.get("sql_preview"))) or ["Nessuna istruzione SQL generata."], tone="info")


def sezioni_bozza(b: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        _panoramica(b),
        actions("Decisione del revisore", azioni_decisione(b), subtitle="Motivazione e firma rendono la decisione verificabile; pubblica solo dopo l'approvazione."),
        form(
            "Specifica JSON",
            "salva",
            [
                campo("spec_json", "Specifica della bozza", "textarea", value=json.dumps(b.get("spec_json") or {}, ensure_ascii=False, indent=2), required=True),
                campo("review_signature", "Firma del revisore", value=b.get("review_signature"), placeholder="Es. Avv. Mario Rossi - Superamministratore"),
            ],
            submit_label="Salva modifiche",
            subtitle="Correggi la specifica solo se serve: al salvataggio viene rivalidata e lo stato si aggiorna.",
            params={"draft": b.get("id")},
        ),
        _differenze(b),
        *sezioni_validazione(b.get("validation_report_json") or {}),
        _esempi(b),
        _storico(b),
        _governo(b),
        _anteprima_sql(b),
    ]


__all__ = ["azioni_decisione", "dettaglio", "motivo_approvazione", "motivo_rifiuto", "sezioni_bozza", "sezioni_validazione"]
