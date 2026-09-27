"""Pagina «Copertura AI» del pannello di piattaforma (React).

Sostituisce la vista storica `/admin/copertura-ai/` (rotta `dashboard`, modello
`admin/legal_coverage_dashboard.html`): stato dell'archivio condiviso,
indicatori, regia della pipeline, coda delle lacune, coda delle bozze,
istantanee di copertura e storico delle pubblicazioni.

Le quattro azioni chiamano `run_action(action, limit=..., tenant_slug="")` come
`execute_action` storico (`/esegui/<action>` con il campo `limit`, 20 se
assente) e ne ripetono i messaggi e i toni.
"""

from __future__ import annotations

from typing import Any

from web.services.react_piattaforma_copertura_ai_comune import (
    INDIRIZZO_REVISIONE,
    NOMI_AZIONE,
    blocchi,
    indirizzo_bozza,
    lacuna,
    rischio,
    si_no,
    stato_bozza,
    stato_copertura,
)
from web.services.react_piattaforma_sezioni import (
    _t,
    actions,
    azione,
    campo,
    data_ora,
    esito,
    link,
    metrics,
    notes,
    table,
)

MESSAGGI = {
    "audit": "Verifica della copertura aggiornata.",
    "gaps": "Coda delle lacune rigenerata.",
    "drafts": "Bozze generate correttamente.",
    "publish": "Pubblicazione eseguita e archivio riallineato.",
}


def costruisci() -> dict[str, Any]:
    from web.services.legal_coverage_surface import build_legal_coverage_surface

    return build_legal_coverage_surface(tenant_slug="")


def _stato_archivio(runtime: dict[str, Any]) -> dict[str, Any]:
    if runtime.get("db_online"):
        archivio = _t(runtime.get("db_backend_label")).replace("coverage", "della copertura") or "n.d."
        testo = f"Archivio: {archivio} · modello AI: {_t(runtime.get('ollama_model')) or 'modello non configurato'}"
        return notes("Archivio della copertura connesso", [testo, f"Archivio configurato: {si_no(runtime.get('db_configured'))}"], tone="success")
    if runtime.get("db_configured"):
        testo = "L'archivio della copertura condiviso è configurato ma al momento non risponde. Verifica la configurazione di piattaforma e riprova."
    else:
        testo = "Configura l'archivio della copertura condiviso per usare pipeline, revisione e pubblicazione reali."
    return notes("Archivio della copertura non raggiungibile", [testo, f"Archivio configurato: {si_no(runtime.get('db_configured'))}"], tone="warning")


def _campo_limite() -> dict[str, Any]:
    return campo("limit", "Numero massimo di bozze", "number", value="20", help="Come nella console storica: 20 se non indicato.")


def _regia() -> dict[str, Any]:
    return actions("Regia della pipeline", [
        azione("audit", "Esegui la verifica", confirm="Ricalcolare ora la copertura di tutte le sottobranche?"),
        azione("gaps", "Rigenera la coda delle lacune", confirm="Rigenerare la coda delle lacune dalla verifica più recente?"),
        azione("drafts", "Genera bozze con l'AI", fields=[_campo_limite()], detail="Genera nuove bozze per le lacune aperte; le bozze già in revisione non vengono duplicate."),
        azione("publish", "Pubblica le bozze approvate", tone="primary", fields=[_campo_limite()], detail="Trasforma in SQL e applica al catalogo le bozze approvate, con traccia di revisione."),
    ], subtitle="Esegui i passaggi in sequenza oppure un blocco alla volta: verifica → lacune → bozze → revisione → pubblicazione.")


def _code(payload: dict[str, Any]) -> list[dict[str, Any]]:
    lacune = payload.get("gaps") or []
    bozze = payload.get("drafts") or []
    righe_bozze = []
    for b in bozze[:8]:
        etichetta, tono = stato_bozza(b.get("status"))
        righe_bozze.append({"subbranch": b.get("subbranch_code"), "procedure": _t(b.get("procedure_code")) or "n.d.", "state": etichetta, "risk": rischio(b.get("risk_level")), "_href": indirizzo_bozza(b.get("id")), "_tone": tono})
    return [
        table(
            f"Coda delle lacune ({len(lacune)})",
            [("subbranch", "Sottobranca"), ("gap", "Lacuna"), ("priority", "Priorità"), ("score", "Punteggio")],
            [{
                "subbranch": g.get("subbranch_code"),
                "gap": lacuna(g.get("gap_type")),
                "priority": g.get("priority_score"),
                "score": (g.get("gap_payload_json") or {}).get("coverage_score", 0) if isinstance(g.get("gap_payload_json"), dict) else 0,
                "_tone": "warning",
            } for g in lacune[:8]],
            subtitle="Le prime otto lacune aperte per priorità.",
            empty="Nessuna lacuna aperta.",
        ),
        table(
            f"Coda delle bozze ({len(bozze)})",
            [("subbranch", "Sottobranca"), ("procedure", "Procedura"), ("state", "Stato"), ("risk", "Rischio")],
            righe_bozze,
            subtitle="Apri una bozza per controllarla nella coda revisioni.",
            empty="Nessuna bozza disponibile.",
        ),
    ]


def _storico(payload: dict[str, Any]) -> list[dict[str, Any]]:
    righe = []
    for s in (payload.get("snapshots") or [])[:12]:
        etichetta, tono = stato_copertura(s.get("coverage_status"))
        righe.append({"subbranch": s.get("subbranch_code"), "score": s.get("coverage_score"), "state": etichetta, "procedures": s.get("procedure_count"), "missing": blocchi(s.get("missing_blocks_json")), "_tone": tono})
    return [
        table(
            "Istantanee di copertura",
            [("subbranch", "Sottobranca"), ("score", "Punteggio"), ("state", "Stato"), ("procedures", "Procedure"), ("missing", "Blocchi mancanti")],
            righe,
            empty="Nessuna istantanea disponibile.",
        ),
        table(
            "Storico delle pubblicazioni",
            [("procedure", "Procedura"), ("subbranch", "Sottobranca"), ("mode", "Modalità"), ("when", "Pubblicata il")],
            [{"procedure": h.get("procedure_code"), "subbranch": h.get("subbranch_code"), "mode": f"Pubblicazione {_t(h.get('published_mode'))}".strip(), "when": data_ora(h.get("published_at")) or "n.d."} for h in payload.get("history") or []],
            empty="Nessuna pubblicazione disponibile.",
        ),
    ]


def adatta(payload: dict[str, Any]) -> dict[str, Any]:
    runtime = payload.get("runtime") or {}
    h = payload.get("headline") or {}
    return {
        "title": "Copertura AI e pubblicazione automatica controllata",
        "subtitle": "Archivio → verifica → coda delle lacune → bozze AI con esempi → revisione → pubblicazione SQL → apprendimento dalle decisioni.",
        "links": [link("Apri la coda revisioni", INDIRIZZO_REVISIONE, tone="primary")],
        "sections": [
            notes("Archivio della copertura condiviso da tutti gli studi", [
                "Una sola esecuzione aggiorna verifica, lacune, bozze, revisione e pubblicazione per l'intera piattaforma.",
                f"Studi attivi coperti: {_t(runtime.get('tenant_count') or 0)}.",
            ], tone="info"),
            _stato_archivio(runtime),
            metrics([
                {"label": "Copertura media", "value": h.get("coverage_medio", 0)},
                {"label": "Sottobranche pronte", "value": h.get("subbranch_ready", 0), "tone": "success"},
                {"label": "Sottobranche parziali", "value": h.get("subbranch_parziali", 0), "tone": "warning" if h.get("subbranch_parziali") else "neutral"},
                {"label": "Lacune aperte", "value": h.get("gap_aperti", 0), "tone": "warning" if h.get("gap_aperti") else "success"},
                {"label": "Bozze in revisione", "value": h.get("draft_review", 0)},
                {"label": "Apprendimento dalle decisioni", "value": h.get("training_implicito", 0)},
            ]),
            _regia(),
            *_code(payload),
            *_storico(payload),
        ],
    }


def _messaggio(chiave: str, risultato: dict[str, Any]) -> tuple[str, str]:
    """Stesse regole di `execute_action`: avviso quando non si genera o non si pubblica nulla."""
    risultato = risultato or {}
    if chiave == "drafts" and int(risultato.get("draft_total") or 0) == 0 and int(risultato.get("skipped_pending_review_total") or 0):
        return "Le bozze erano già in revisione: nessuna duplicazione generata.", "warning"
    if chiave == "publish" and int(risultato.get("published_total") or 0) == 0:
        return "Nessuna bozza approvata da pubblicare. Apri la coda revisioni, approva una bozza e ripeti la pubblicazione.", "warning"
    return MESSAGGI.get(chiave, "Operazione completata."), "success"


def esegui(chiave: str, params: dict[str, str], values: dict[str, str]) -> dict[str, Any]:
    from flask import current_app

    from web.services.legal_coverage_surface import run_action

    if chiave not in MESSAGGI:
        return esito(False, "Azione non disponibile in questa pagina.")
    try:
        risultato = run_action(chiave, limit=int(values.get("limit") or 20), tenant_slug="")
        messaggio, tono = _messaggio(chiave, risultato)
        if risultato:
            current_app.logger.info("Coverage action %s -> %s", chiave, risultato)
        return esito(True, messaggio, tone=tono)
    except Exception as exc:
        current_app.logger.exception("Errore action coverage %s", chiave)
        return esito(False, f"Errore durante l'azione «{NOMI_AZIONE[chiave]}»: {exc}")


AZIONI = set(MESSAGGI)

__all__ = ["AZIONI", "adatta", "costruisci", "esegui"]
