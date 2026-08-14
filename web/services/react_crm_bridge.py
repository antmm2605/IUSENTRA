"""Bridge React per la pipeline CRM di intake (lead con verifica conflitti).

Espone il payload di /api/v1/ui/crm: colonne kanban per stato, statistiche di
conversione per fonte, esito della verifica conflitti ex art. 24 CDF per ogni
scheda. Le scritture passano dalle route operative (web/bootstrap/crm_routes).
"""

from __future__ import annotations

from datetime import date
from typing import Any, Callable

from pct.crm_intake import FONTI_LEAD, STATI_LEAD

_STATO_LABEL = {
    "NUOVO": "Nuovi contatti",
    "CONTATTATO": "Contattati",
    "APPUNTAMENTO": "Appuntamento",
    "PREVENTIVO": "Preventivo inviato",
    "VINTO": "Incarico assunto",
    "PERSO": "Persi",
}

_STATO_TONE = {
    "NUOVO": "info",
    "CONTATTATO": "neutral",
    "APPUNTAMENTO": "warning",
    "PREVENTIVO": "warning",
    "VINTO": "success",
    "PERSO": "danger",
}

_FONTE_LABEL = {
    "passaparola": "Passaparola",
    "sito_studio": "Sito dello studio",
    "referral_professionista": "Referral professionista",
    "directory_ordine": "Directory Ordine",
    "social": "Social",
    "altro": "Altro",
}

_CONFLITTO_LABEL = {
    "nessuno": "Nessun riscontro",
    "da_valutare": "Da valutare",
    "potenziale_conflitto": "Potenziale conflitto",
}

_CONFLITTO_TONE = {
    "nessuno": "success",
    "da_valutare": "warning",
    "potenziale_conflitto": "danger",
}


def _text(value: Any, fallback: str = "") -> str:
    cleaned = " ".join(str(value or "").split()).strip()
    return cleaned or fallback


def _lead_payload(lead: Any) -> dict[str, Any]:
    esito = dict(getattr(lead, "conflitto_esito", {}) or {})
    livello = _text(esito.get("livello"))
    verificato = bool(getattr(lead, "conflitto_verificato", False))
    lead_id = _text(getattr(lead, "id", ""))
    return {
        "id": lead_id,
        "denominazione": _text(getattr(lead, "denominazione", ""), "Contatto"),
        "codiceFiscale": _text(getattr(lead, "codice_fiscale", "")),
        "partitaIva": _text(getattr(lead, "partita_iva", "")),
        "email": _text(getattr(lead, "email", "")),
        "telefono": _text(getattr(lead, "telefono", "")),
        "fonte": _text(getattr(lead, "fonte", ""), "altro"),
        "fonteLabel": _FONTE_LABEL.get(_text(getattr(lead, "fonte", ""), "altro"), "Altro"),
        "materia": _text(getattr(lead, "materia", "")),
        "esigenza": _text(getattr(lead, "esigenza", "")),
        "stato": _text(getattr(lead, "stato", ""), "NUOVO"),
        "referente": _text(getattr(lead, "referente", "")),
        "note": _text(getattr(lead, "note", "")),
        "clienteId": _text(getattr(lead, "cliente_id", "")),
        "motivoPerso": _text(getattr(lead, "motivo_perso", "")),
        "creatoIl": _text(getattr(lead, "creato_il", ""))[:10],
        "conflitto": {
            "verificato": verificato,
            "livello": livello,
            "label": _CONFLITTO_LABEL.get(livello, "Verifica da eseguire") if verificato else "Verifica da eseguire",
            "tone": _CONFLITTO_TONE.get(livello, "neutral") if verificato else "neutral",
            "riscontri": [
                {
                    "tipo": _text(r.get("tipo")),
                    "etichetta": _text(r.get("etichetta")),
                    "certo": bool(r.get("certo")),
                    "ruolo": _text(r.get("ruolo")),
                }
                for r in list(esito.get("riscontri") or [])
                if isinstance(r, dict)
            ],
        },
        "actions": {
            "stato": f"/crm/lead/{lead_id}/stato",
            "verificaConflitti": f"/crm/lead/{lead_id}/verifica-conflitti",
            "converti": f"/crm/lead/{lead_id}/converti",
        },
    }


def build_react_crm_payload(*, get_crm: Callable[[], Any]) -> dict[str, Any]:
    crm = get_crm()
    pipeline = crm.pipeline()
    stats = crm.statistiche()
    columns = [
        {
            "stato": stato,
            "label": _STATO_LABEL.get(stato, stato),
            "tone": _STATO_TONE.get(stato, "neutral"),
            "count": len(pipeline.get(stato, [])),
            "leads": [_lead_payload(lead) for lead in pipeline.get(stato, [])],
        }
        for stato in STATI_LEAD
    ]
    return {
        "source": "repository_reali",
        "generatedAt": date.today().isoformat(),
        "contracts": {
            "mock_fallback": False,
            "writes": "operational_routes",
            "route_owner": "react_shell",
        },
        "columns": columns,
        "summary": {
            "totale": int(stats.get("totale") or 0),
            "aperti": sum(
                int(stats.get("per_stato", {}).get(stato) or 0)
                for stato in ("NUOVO", "CONTATTATO", "APPUNTAMENTO", "PREVENTIVO")
            ),
            "vinti": int(stats.get("per_stato", {}).get("VINTO") or 0),
            "persi": int(stats.get("per_stato", {}).get("PERSO") or 0),
            "tassoConversione": float(stats.get("tasso_conversione") or 0.0),
            "perFonte": [
                {
                    "fonte": fonte,
                    "label": _FONTE_LABEL.get(fonte, fonte),
                    "count": int(count or 0),
                }
                for fonte, count in sorted(
                    dict(stats.get("per_fonte") or {}).items(), key=lambda kv: -int(kv[1] or 0)
                )
            ],
        },
        "options": {
            "fonti": [{"value": fonte, "label": _FONTE_LABEL.get(fonte, fonte)} for fonte in FONTI_LEAD],
            "stati": [
                {"value": stato, "label": _STATO_LABEL.get(stato, stato), "tone": _STATO_TONE.get(stato, "neutral")}
                for stato in STATI_LEAD
            ],
        },
        "actions": {
            "nuovo": "/crm/lead/nuovo",
            "clienti": "/clienti",
            "preventivi": "/preventivi/nuovo",
        },
        "fonteDeontologica": "Verifica conflitti ex artt. 23-24 Codice Deontologico Forense; preventivo scritto ex L. 247/2012 art. 13.",
    }
