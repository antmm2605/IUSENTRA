"""Regole configurabili per i controlli di deposito dei template atti."""
from __future__ import annotations

from copy import deepcopy
from typing import Any


RULESET_VERSION = "2026.04.26.1"
RULESET_UPDATED_AT = "26/04/2026"


CHANNEL_PORTAL_LABELS: dict[str, str] = {
    "PST": "PST / PCT Civile",
    "PST_GDP": "Giudice di Pace / SIGP",
    "PST_CONCORSUALE": "PST / Procedure concorsuali",
    "PAT": "PAT / SIGA Amministrativo",
    "PTT": "PTT / SIGIT Tributario",
    "PDP": "PDP Penale",
    "PEC": "PEC / Stragiudiziale",
    "NESSUNO": "Atti interni studio",
    "MISTO": "Canale da selezionare",
}


def _rule(
    codice: str,
    label: str,
    *,
    severita: str = "warning",
    blocca_deposito: bool = False,
    fonte: str = "Regola configurabile IUSENTRA",
    suggerimento: str = "Completa il dato richiesto prima della generazione o del deposito.",
) -> dict[str, Any]:
    return {
        "codice": codice,
        "label": label,
        "fonte_normativa": fonte,
        "versione_regola": RULESET_VERSION,
        "data_ultimo_aggiornamento": RULESET_UPDATED_AT,
        "severita": severita,
        "blocca_deposito": blocca_deposito,
        "messaggio_utente": label,
        "suggerimento_correzione": suggerimento,
    }


COMMON_DOCUMENT_RULES = [
    _rule("DOC_ALLEGATI", "Verifica allegati obbligatori", severita="errore", blocca_deposito=True),
    _rule("DOC_DIMENSIONE", "Verifica dimensione e leggibilita dei file"),
    _rule("DOC_COERENZA", "Verifica coerenza tra tipo atto, procedimento e allegati"),
]


DEPOSIT_RULES_BY_CHANNEL: dict[str, list[dict[str, Any]]] = {
    "PST": [
        _rule("PST_PDFA", "Verifica PDF/A per il deposito telematico", severita="errore", blocca_deposito=True),
        _rule("PST_FIRMA", "Verifica firma digitale quando richiesta", severita="errore", blocca_deposito=True),
        _rule("PST_DATI_ATTO", "Verifica DatiAtto.xml se previsto dal tipo atto", severita="errore", blocca_deposito=True),
        _rule("PST_UFFICIO_RITO", "Verifica ufficio, registro, rito e procedimento"),
        _rule("PST_PROCURA", "Verifica procura alle liti se richiesta"),
        _rule("PST_CU", "Verifica contributo unificato, marca o diritti se applicabili"),
        *COMMON_DOCUMENT_RULES,
    ],
    "PST_GDP": [
        _rule("SIGP_RITO", "Verifica compatibilita rito/procedimento Giudice di Pace", severita="errore", blocca_deposito=True),
        _rule("SIGP_DATI_RG", "Verifica ufficio, RG e anno quando disponibili"),
        _rule("SIGP_FORMATO", "Verifica formato documento e allegati"),
        _rule("SIGP_FIRMA_PDFA", "Verifica firma/PDF-A secondo configurazione del canale"),
        *COMMON_DOCUMENT_RULES,
    ],
    "PST_CONCORSUALE": [
        _rule("CONC_RITO", "Verifica procedura concorsuale e organo competente", severita="errore", blocca_deposito=True),
        _rule("CONC_DOCUMENTI", "Verifica documenti della procedura e titoli del credito"),
        _rule("CONC_FIRMA", "Verifica firma digitale quando richiesta"),
        *COMMON_DOCUMENT_RULES,
    ],
    "PAT": [
        _rule("PAT_TIPO_ATTO", "Verifica tipologia ricorso, memoria o istanza PAT", severita="errore", blocca_deposito=True),
        _rule("PAT_FIRMA", "Verifica firma digitale", severita="errore", blocca_deposito=True),
        _rule("PAT_FORMATO", "Verifica formato ammesso dal canale"),
        _rule("PAT_PARTI", "Verifica dati parte, ufficio e oggetto"),
        _rule("PAT_CU", "Verifica contributo se applicabile"),
        *COMMON_DOCUMENT_RULES,
    ],
    "PTT": [
        _rule("PTT_RICORSO", "Verifica ricorso, appello o controdeduzioni tributarie", severita="errore", blocca_deposito=True),
        _rule("PTT_FIRMA", "Verifica firma digitale", severita="errore", blocca_deposito=True),
        _rule("PTT_PROCURA", "Verifica procura e allegati fiscali"),
        _rule("PTT_CONTRIBUTO", "Verifica contributo tributario se gestito"),
        *COMMON_DOCUMENT_RULES,
    ],
    "PDP": [
        _rule("PDP_NATURA", "Verifica natura atto e ufficio/procedimento penale", severita="errore", blocca_deposito=True),
        _rule("PDP_DIFESA", "Verifica nomina difensore o procura se richiesta"),
        _rule("PDP_FORMATO", "Verifica formato e firma secondo configurazione"),
        *COMMON_DOCUMENT_RULES,
    ],
    "PEC": [
        _rule("PEC_DESTINATARIO", "Verifica destinatario, PEC e oggetto", severita="errore", blocca_deposito=True),
        _rule("PEC_MITTENTE", "Verifica mittente e difensore"),
        _rule("PEC_ALLEGATI", "Verifica allegati e prova invio/ricevute se gestite"),
    ],
    "NESSUNO": [
        _rule("STD_DATI", "Verifica dati minimi del documento interno"),
        _rule("STD_COLLEGAMENTO", "Verifica collegamento a cliente, fascicolo, preventivo o incarico"),
        _rule("STD_FIRMA", "Verifica eventuale firma cliente o avvocato"),
    ],
}


def normalizza_canale(canale: str | None) -> str:
    value = str(canale or "NESSUNO").strip().upper()
    if value in {"", "NO", "NONE"}:
        return "NESSUNO"
    if value in {"PCT", "PST/PCT", "PST_CIVILE"}:
        return "PST"
    if value in {"SIGP", "GDP", "PST-GDP"}:
        return "PST_GDP"
    if value in {"STRAGIUDIZIALE"}:
        return "PEC"
    return value


def portale_deposito_label(canale: str | None) -> str:
    normalized = normalizza_canale(canale)
    return CHANNEL_PORTAL_LABELS.get(normalized, normalized.replace("_", " ").title())


def regole_deposito_per_canale(canale: str | None) -> list[dict[str, Any]]:
    normalized = normalizza_canale(canale)
    return deepcopy(DEPOSIT_RULES_BY_CHANNEL.get(normalized, DEPOSIT_RULES_BY_CHANNEL["NESSUNO"]))


def compliance_template_summary(canale: str | None, controlli_template: list[Any] | None = None) -> dict[str, Any]:
    rules = regole_deposito_per_canale(canale)
    extra_checks = [
        _rule(
            f"TPL_{idx:03d}",
            str(check),
            severita="info",
            fonte="Catalogo master template atti IUSENTRA",
            suggerimento="Controllo descrittivo previsto dal template master.",
        )
        for idx, check in enumerate(controlli_template or [], start=1)
        if str(check or "").strip()
    ]
    all_rules = rules + extra_checks
    blocking = [rule for rule in all_rules if rule.get("blocca_deposito")]
    return {
        "canale": normalizza_canale(canale),
        "portale": portale_deposito_label(canale),
        "ruleset_version": RULESET_VERSION,
        "updated_at": RULESET_UPDATED_AT,
        "regole": all_rules,
        "totale": len(all_rules),
        "bloccanti": len(blocking),
        "completo": bool(all_rules),
    }


__all__ = [
    "CHANNEL_PORTAL_LABELS",
    "RULESET_UPDATED_AT",
    "RULESET_VERSION",
    "compliance_template_summary",
    "normalizza_canale",
    "portale_deposito_label",
    "regole_deposito_per_canale",
]
