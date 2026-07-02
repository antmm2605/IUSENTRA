"""Strumenti Lex read-only sul controllo economico delle sentenze (governati).

Regole non negoziabili:
- **Lex non deduce importi**: questi tool leggono solo audit/eventi gia' prodotti
  dal motore verificato; non ricalcolano nulla.
- **Astensione**: se l'audit non e' riconciliato al fascicolo (RG non combacia),
  il tool restituisce un'astensione controllata, non un dato economico.
- **Fail-closed**: gated da `lex.economicContextTools` (default-off); qualunque
  errore di accesso all'archivio -> astensione, mai eccezione propagata.

Segue la stessa forma dei tool governati esistenti (`legal_studio_tools`):
funzioni pure `{"ok": bool, ...}`, tenant-aware, con dispatcher.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


_ABSTAIN_RG = (
    "RG/identità del provvedimento non verificati rispetto al fascicolo: "
    "non aggiorno il contesto economico, è richiesta revisione umana."
)


def _flag_enabled() -> bool:
    try:
        from web.services.feature_flags import is_feature_enabled

        return bool(is_feature_enabled("lex.economicContextTools"))
    except Exception:
        raw = str(os.environ.get("IUSENTRA_FF_LEX_ECONOMICCONTEXTTOOLS", "") or "").strip().lower()
        return raw in {"1", "true", "on", "yes", "si"}


def _resolve_db_path(explicit: str = "") -> str:
    if explicit:
        return explicit
    try:
        from web.services.tenant_paths import tenant_data_path

        resolved = tenant_data_path("SENTENZA_ECONOMIC_DB", require_tenant=False)
        if resolved:
            return str(resolved)
    except Exception:
        pass
    env = os.environ.get("IUSENTRA_SENTENZA_ECONOMIC_DB") or os.environ.get("SENTENZA_ECONOMIC_DB")
    if env:
        return env
    return str(Path("data") / "economico" / "sentenza_economic.db")


def _open_repo(db_path: str = ""):
    from pct.sentenza_economic_repository import SentenzaEconomicRepository

    return SentenzaEconomicRepository(_resolve_db_path(db_path))


def _disabled() -> dict[str, Any]:
    return {"ok": False, "code": "feature_disabled", "abstain": True, "message": "Strumenti economici Lex non attivi per questo studio."}


def _abstain(message: str) -> dict[str, Any]:
    return {"ok": False, "abstain": True, "message": message}


def _rg_verificato(audit: dict[str, Any]) -> bool:
    match = audit.get("audit", {}).get("match") if isinstance(audit.get("audit"), dict) else None
    if isinstance(match, dict):
        return bool(match.get("rg_match"))
    return bool(audit.get("safe_to_attach"))


def get_fascicolo_economic_context(fascicolo_id: str, *, tenant_id: str = "", db_path: str = "") -> dict[str, Any]:
    if not _flag_enabled():
        return _disabled()
    if not tenant_id or not fascicolo_id:
        return _abstain("Contesto tenant/fascicolo mancante: non posso leggere il contesto economico.")
    try:
        repo = _open_repo(db_path)
        audits = repo.list_sentenza_audits(tenant_id, fascicolo_id=fascicolo_id)
        events = repo.list_economic_events(tenant_id, fascicolo_id=fascicolo_id)
    except Exception:
        return _abstain("Archivio economico sentenze non disponibile.")
    from pct.sentenza_economic_dashboard import build_sentenze_economiche_summary

    summary = build_sentenze_economiche_summary(audits, events)
    return {
        "ok": True,
        "fascicolo_id": fascicolo_id,
        "sentenze_lette": summary["totals"]["sentenze_lette"],
        "totals": summary["totals"],
        "worklist": summary["worklist"],
    }


def get_sentenza_economic_audit(audit_id: str, *, tenant_id: str = "", db_path: str = "") -> dict[str, Any]:
    if not _flag_enabled():
        return _disabled()
    if not tenant_id or not audit_id:
        return _abstain("Contesto tenant/audit mancante.")
    try:
        audit = _open_repo(db_path).get_sentenza_audit(tenant_id, audit_id)
    except Exception:
        return _abstain("Archivio economico sentenze non disponibile.")
    if not audit:
        return {"ok": False, "code": "not_found", "message": "Audit economico non trovato."}
    if not _rg_verificato(audit):
        return _abstain(_ABSTAIN_RG)
    return {"ok": True, "audit": audit}


def list_sentenza_economic_events(fascicolo_id: str, *, tenant_id: str = "", db_path: str = "") -> dict[str, Any]:
    if not _flag_enabled():
        return _disabled()
    if not tenant_id or not fascicolo_id:
        return _abstain("Contesto tenant/fascicolo mancante.")
    try:
        events = _open_repo(db_path).list_economic_events(tenant_id, fascicolo_id=fascicolo_id)
    except Exception:
        return _abstain("Archivio economico sentenze non disponibile.")
    return {"ok": True, "fascicolo_id": fascicolo_id, "eventi": events, "totale": len(events)}


def explain_contributo_unificato_status(fascicolo_id: str, *, tenant_id: str = "", db_path: str = "") -> dict[str, Any]:
    if not _flag_enabled():
        return _disabled()
    if not tenant_id or not fascicolo_id:
        return _abstain("Contesto tenant/fascicolo mancante.")
    try:
        rows = _open_repo(db_path).list_contributo_unificato(tenant_id, fascicolo_id=fascicolo_id)
    except Exception:
        return _abstain("Archivio economico sentenze non disponibile.")
    if not rows:
        return {"ok": True, "fascicolo_id": fascicolo_id, "status": "sconosciuto", "spiegazione": "Nessun controllo contributo unificato registrato per questo fascicolo.", "voci": []}
    ultimo = rows[0]
    return {
        "ok": True,
        "fascicolo_id": fascicolo_id,
        "status": ultimo.get("status", "incerto"),
        "spiegazione": (
            "Stato del contributo unificato ex D.P.R. 115/2002 ricavato dai documenti verificati. "
            "Gli alert non si chiudono senza ricevuta o stato esente/prenotato a debito."
        ),
        "voci": rows,
    }


def explain_spese_liquidate(audit_id: str, *, tenant_id: str = "", db_path: str = "") -> dict[str, Any]:
    if not _flag_enabled():
        return _disabled()
    if not tenant_id or not audit_id:
        return _abstain("Contesto tenant/audit mancante.")
    try:
        audit = _open_repo(db_path).get_sentenza_audit(tenant_id, audit_id)
    except Exception:
        return _abstain("Archivio economico sentenze non disponibile.")
    if not audit:
        return {"ok": False, "code": "not_found", "message": "Audit economico non trovato."}
    if not _rg_verificato(audit):
        return _abstain(_ABSTAIN_RG)
    spese = audit.get("audit", {}).get("sentenza", {}).get("spese_liquidate", {}) if isinstance(audit.get("audit"), dict) else {}
    beneficiario = spese.get("beneficiario_credito", "incerto")
    if beneficiario == "avvocato":
        base = "Spese distratte in favore dell'avvocato ex art. 93 c.p.c. (credito diretto del difensore)."
    elif beneficiario == "cliente":
        base = "Spese liquidate a favore della parte ex art. 91 c.p.c. (credito del cliente, non dell'avvocato)."
    elif beneficiario == "erario":
        base = "Gratuito patrocinio: compenso liquidato con decreto di pagamento, importi prenotati a debito (artt. 82-85 D.P.R. 115/2002)."
    else:
        base = "Beneficiario del credito non determinabile con certezza dal testo: richiesta verifica."
    return {"ok": True, "audit_id": audit_id, "beneficiario_credito": beneficiario, "spiegazione": base, "spese_liquidate": spese}


_TOOL_REGISTRY: list[dict[str, str]] = [
    {"name": "get_fascicolo_economic_context", "label": "Contesto economico sentenze del fascicolo", "area": "economico"},
    {"name": "get_sentenza_economic_audit", "label": "Audit economico sentenza", "area": "economico"},
    {"name": "list_sentenza_economic_events", "label": "Eventi economici del fascicolo", "area": "economico"},
    {"name": "explain_contributo_unificato_status", "label": "Stato contributo unificato", "area": "economico"},
    {"name": "explain_spese_liquidate", "label": "Spiegazione spese liquidate", "area": "economico"},
]


def list_tools() -> list[dict[str, str]]:
    return list(_TOOL_REGISTRY)


def dispatch_tool(name: str, **kwargs: Any) -> dict[str, Any]:
    mapping = {
        "get_fascicolo_economic_context": get_fascicolo_economic_context,
        "get_sentenza_economic_audit": get_sentenza_economic_audit,
        "list_sentenza_economic_events": list_sentenza_economic_events,
        "explain_contributo_unificato_status": explain_contributo_unificato_status,
        "explain_spese_liquidate": explain_spese_liquidate,
    }
    func = mapping.get(name)
    if func is None:
        return {"ok": False, "code": "unknown_tool", "message": f"Strumento economico sconosciuto: {name}."}
    return func(**kwargs)


__all__ = [
    "get_fascicolo_economic_context",
    "get_sentenza_economic_audit",
    "list_sentenza_economic_events",
    "explain_contributo_unificato_status",
    "explain_spese_liquidate",
    "list_tools",
    "dispatch_tool",
]
