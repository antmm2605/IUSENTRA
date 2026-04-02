"""
pct/responsabile_conformita.py - Responsabile deterministico di conformita'
redazione / deposito per il fascicolo.

Obiettivo:
- distinguere workflow interno aperto vs fascicolo davvero pronto alla redazione/deposito
- riusare i motori giuridici e tecnici gia' presenti
- restituire un riepilogo leggibile con semaforo, motivazione, fonti e azioni correttive
"""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, Iterable, List, Optional

from pct.assistente_redazionale import (
    LEVEL_BLOCK,
    LEVEL_WARNING,
    SERVICE_DOCUMENTALE,
    SERVICE_GIURIDICO,
    SERVICE_TECNICO,
    AssistenteRedazionale,
    SCHEMA_CHANNELS,
)
from pct.compilatore_atti import get_modello
from pct.deposito_guidato import ValidationIssue
from pct.motore_preventivo import get_tipo_pratica


SERVICE_REDAZIONALE = "REDAZIONALE"
LEVEL_OK = "OK"


_PRACTICE_MODEL_MAP = {
    "atto_citazione": "CIV_CIT_001",
    "comparsa_risposta": "CIV_COM_001",
    "decreto_ingiuntivo": "CIV_RDI_001",
    "appello_civile": "CIV_APP_001",
    "cassazione_civile": "CIV_CASS_001",
    "diffida": "STR_DIFF_001",
    "lettera_legale": "STR_DIFF_001",
    "negoziazione_assistita": "STR_DIFF_001",
    "mediazione": "STR_DIFF_001",
    "ricorso_tar": "AMM_RIC_001",
    "ricorso_tributario": "TRI_RIC_001",
}

_MODEL_SOURCES: dict[str, list[dict[str, str]]] = {
    "CIV_CIT_001": [
        {
            "label": "PST - Deposito iscrizione a ruolo",
            "url": "https://pst.giustizia.it/PST/en/dettaglio_schede_utente.page?contentId=ACC411&modelId=12",
        },
        {
            "label": "Tribunale di Milano - Guida avvocati iscrizione a ruolo",
            "url": "https://tribunale-milano.giustizia.it/cmsresources/cms/documents/GUIDA_AVVOCATI.pdf",
        },
        {
            "label": "Codice di procedura civile consolidato",
            "url": "https://www.normattiva.it/eli/id/1940/10/28/040U1443/CONSOLIDATED/20240814",
        },
    ],
    "CIV_COM_001": [
        {
            "label": "Codice di procedura civile - artt. 166 e 167",
            "url": "https://www.normattiva.it/eli/id/1940/10/28/040U1443/CONSOLIDATED/20240814",
        },
        {
            "label": "PST - Deposito iscrizione a ruolo",
            "url": "https://pst.giustizia.it/PST/en/dettaglio_schede_utente.page?contentId=ACC411&modelId=12",
        },
    ],
}


def _slug(text: str) -> str:
    import re
    import unicodedata

    norm = unicodedata.normalize("NFKD", text or "")
    ascii_only = "".join(ch for ch in norm if not unicodedata.combining(ch))
    lowered = re.sub(r"[^a-z0-9]+", " ", ascii_only.lower())
    return " ".join(lowered.split())


def _dedupe_sources(*groups: Iterable[Dict[str, str]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str]] = set()
    result: list[dict[str, str]] = []
    for group in groups:
        for item in group or []:
            label = str(item.get("label") or "").strip()
            url = str(item.get("url") or "").strip()
            key = (label, url)
            if not label or key in seen:
                continue
            seen.add(key)
            result.append({"label": label, "url": url})
    return result


def _issue_state(issues: Iterable[ValidationIssue], service: str) -> str:
    scoped = [issue for issue in issues if issue.service == service]
    if any(issue.level == LEVEL_BLOCK for issue in scoped):
        return "blocco"
    if any(issue.level == LEVEL_WARNING for issue in scoped):
        return "warning"
    return "ok"


def _overall_state(issues: Iterable[ValidationIssue]) -> str:
    if any(issue.level == LEVEL_BLOCK for issue in issues):
        return "blocco"
    if any(issue.level == LEVEL_WARNING for issue in issues):
        return "warning"
    return "ok"


def _manual_issue(
    *,
    service: str,
    level: str,
    code: str,
    title: str,
    detail: str,
    source: str,
    suggested_action: str,
    field: str = "",
) -> ValidationIssue:
    return ValidationIssue(
        service=service,
        level=level,
        code=code,
        title=title,
        detail=detail,
        source=source,
        suggested_action=suggested_action,
        field=field,
    )


def _practice_id(preventivo: Any = None, conferimento: Any = None) -> str:
    return (
        str(getattr(conferimento, "id_pratica", "") or "").strip()
        or str(getattr(preventivo, "id_pratica", "") or "").strip()
    )


def _practice_label(practice_id: str, preventivo: Any = None, conferimento: Any = None) -> str:
    pratica = get_tipo_pratica(practice_id) if practice_id else None
    if pratica:
        return pratica.label
    return (
        str(getattr(conferimento, "oggetto", "") or "").strip()
        or str(getattr(preventivo, "oggetto", "") or "").strip()
    )


def _infer_model_code(*, fascicolo: Any, preventivo: Any = None, conferimento: Any = None) -> str:
    practice_id = _practice_id(preventivo=preventivo, conferimento=conferimento)
    if practice_id and practice_id in _PRACTICE_MODEL_MAP:
        return _PRACTICE_MODEL_MAP[practice_id]

    haystack = " ".join(
        filter(
            None,
            [
                str(getattr(fascicolo, "titolo", "") or ""),
                str(getattr(fascicolo, "oggetto", "") or ""),
                str(getattr(preventivo, "oggetto", "") or ""),
                str(getattr(conferimento, "oggetto", "") or ""),
            ],
        )
    )
    s = _slug(haystack)
    if "citazione" in s:
        return "CIV_CIT_001"
    if "comparsa" in s or "costituzione e risposta" in s:
        return "CIV_COM_001"
    if "decreto ingiuntivo" in s or "monitorio" in s:
        return "CIV_RDI_001"
    if "appello" in s:
        return "CIV_APP_001"
    if "diffida" in s or "messa in mora" in s or "negoziazione" in s or "mediazione" in s:
        return "STR_DIFF_001"

    tipo = str(getattr(getattr(fascicolo, "tipo", None), "value", "")).upper()
    if tipo == "AMMINISTRATIVO":
        return "AMM_RIC_001"
    if tipo == "TRIBUTARIO":
        return "TRI_RIC_001"
    if tipo == "PENALE":
        return "PEN_MEM_001"
    return "CIV_CIT_001"


def _document_payloads(fascicolo: Any) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for doc in getattr(fascicolo, "documenti", []) or []:
        result.append(
            {
                "id": getattr(doc, "id", ""),
                "nome": getattr(doc, "nome", ""),
                "tipo": str(getattr(getattr(doc, "tipo", None), "value", getattr(doc, "tipo", ""))),
                "firmato_digitalmente": bool(getattr(doc, "firmato_digitalmente", False)),
                "data_documento": getattr(doc, "data_documento", ""),
            }
        )
    return result


def _document_issue_level(key: str) -> str:
    if key in {"procura", "notifica", "sentenza"}:
        return LEVEL_BLOCK
    return LEVEL_WARNING


def _parts_breakdown(parti: Optional[list[tuple[Any, Any]]]) -> dict[str, int]:
    counts = {"assistiti": 0, "controparti": 0}
    for parte, _soggetto in parti or []:
        ruolo = str(getattr(getattr(parte, "ruolo", None), "value", "")).upper()
        if ruolo == "ASSISTITO":
            counts["assistiti"] += 1
        if ruolo in {"CONTROPARTE", "DIFENSORE_CONTROPARTE", "CREDITORE", "DEBITORE"}:
            counts["controparti"] += 1
    return counts


def _citation_specific_issues(
    *,
    fascicolo: Any,
    cliente: Any = None,
    config: Optional[dict[str, Any]] = None,
    parti: Optional[list[tuple[Any, Any]]] = None,
    required_documents: Optional[list[dict[str, Any]]] = None,
) -> list[ValidationIssue]:
    config = config or {}
    issues: list[ValidationIssue] = []
    source = "PST iscrizione a ruolo + guida Tribunale di Milano"

    hearing_date = str(
        getattr(fascicolo, "data_prima_udienza", "") or getattr(fascicolo, "data_prossima_udienza", "") or ""
    ).strip()
    if not hearing_date:
        issues.append(
            _manual_issue(
                service=SERVICE_REDAZIONALE,
                level=LEVEL_BLOCK,
                code="citazione_udienza_mancante",
                title="Manca la data della prima comparizione",
                detail=(
                    "Per l'atto di citazione la data della prima udienza / comparizione "
                    "deve essere gia' determinata e coerente con la vocatio in ius."
                ),
                source=source,
                suggested_action="Inserisci nel fascicolo la prima udienza o la data di comparizione prevista dall'atto.",
                field="data_prima_udienza",
            )
        )

    if not str(getattr(fascicolo, "data_notifica_citazione", "") or "").strip():
        issues.append(
            _manual_issue(
                service=SERVICE_GIURIDICO,
                level=LEVEL_BLOCK,
                code="citazione_data_notifica_non_strutturata",
                title="Data di notificazione della citazione non ancora strutturata",
                detail=(
                    "Il fascicolo non espone ancora in modo strutturato la data di notificazione "
                    "della citazione, dato minimo richiesto per una verifica completa della nota di iscrizione a ruolo."
                ),
                source=source,
                suggested_action=(
                    "Aggiungi nel fascicolo o nel wizard un campo strutturato per la data di notificazione "
                    "della citazione e collegalo ai controlli di iscrizione a ruolo."
                ),
                field="data_notifica_citazione",
            )
        )

    if not cliente:
        issues.append(
            _manual_issue(
                service=SERVICE_REDAZIONALE,
                level=LEVEL_BLOCK,
                code="citazione_cliente_mancante",
                title="Parte attrice non collegata in modo certo",
                detail=(
                    "Per l'iscrizione a ruolo servono generalita' e codice fiscale della parte che iscrive."
                ),
                source=source,
                suggested_action="Collega il cliente corretto al fascicolo prima della redazione o del deposito.",
                field="id_cliente",
            )
        )
        return issues

    if not str(getattr(cliente, "codice_fiscale", "") or "").strip():
        issues.append(
            _manual_issue(
                service=SERVICE_REDAZIONALE,
                level=LEVEL_BLOCK,
                code="citazione_cf_attore_mancante",
                title="Codice fiscale della parte attrice mancante",
                detail=(
                    "La parte che iscrive il procedimento deve essere identificata almeno con generalita' e codice fiscale."
                ),
                source=source,
                suggested_action="Completa l'anagrafica del cliente con il codice fiscale.",
                field="codice_fiscale",
            )
        )

    res_via = str(getattr(getattr(cliente, "indirizzo_residenza", None), "via", "") or "").strip()
    res_comune = str(getattr(getattr(cliente, "indirizzo_residenza", None), "comune", "") or "").strip()
    sede_via = str(getattr(getattr(cliente, "indirizzo_sede_legale", None), "via", "") or "").strip()
    sede_comune = str(getattr(getattr(cliente, "indirizzo_sede_legale", None), "comune", "") or "").strip()
    if not ((res_via and res_comune) or (sede_via and sede_comune)):
        issues.append(
            _manual_issue(
                service=SERVICE_REDAZIONALE,
                level=LEVEL_BLOCK,
                code="citazione_generalita_attore_incomplete",
                title="Generalita' / indirizzo della parte attrice incompleti",
                detail=(
                    "Per la nota di iscrizione a ruolo e per l'atto introduttivo servono dati identificativi completi "
                    "della parte, compresa residenza o sede."
                ),
                source=source,
                suggested_action="Completa l'indirizzo del cliente prima della redazione della citazione.",
                field="indirizzo_residenza",
            )
        )

    if not str(getattr(fascicolo, "oggetto", "") or "").strip():
        issues.append(
            _manual_issue(
                service=SERVICE_REDAZIONALE,
                level=LEVEL_BLOCK,
                code="citazione_oggetto_domanda_mancante",
                title="Oggetto della domanda non definito in modo strutturato",
                detail=(
                    "L'oggetto della domanda deve essere presente in forma chiara per la nota di iscrizione a ruolo "
                    "e per il corretto codice oggetto."
                ),
                source=source,
                suggested_action="Completa il campo oggetto del fascicolo con la domanda sostanziale.",
                field="oggetto",
            )
        )

    lawyer_name = str(getattr(fascicolo, "avvocato_referente", "") or config.get("STUDIO_AVVOCATO", "") or "").strip()
    lawyer_cf = str(config.get("STUDIO_CF", "") or "").strip()
    lawyer_pec = str(config.get("PCT_STUDIO_PEC", "") or config.get("SMTP_FROM", "") or "").strip()
    if not lawyer_name:
        issues.append(
            _manual_issue(
                service=SERVICE_REDAZIONALE,
                level=LEVEL_WARNING,
                code="citazione_difensore_non_identificato",
                title="Difensore referente non identificato in modo certo",
                detail="Il fascicolo non espone ancora un difensore referente univoco per l'atto introduttivo.",
                source=source,
                suggested_action="Indica l'avvocato referente nel fascicolo o nelle impostazioni di studio.",
                field="avvocato_referente",
            )
        )
    if not lawyer_cf:
        issues.append(
            _manual_issue(
                service=SERVICE_GIURIDICO,
                level=LEVEL_WARNING,
                code="citazione_cf_difensore_mancante",
                title="Codice fiscale del difensore non disponibile",
                detail="I dati del procuratore non sono ancora completi per la redazione strutturata dell'atto.",
                source=source,
                suggested_action="Configura il CF dello studio / difensore nelle impostazioni generali.",
                field="STUDIO_CF",
            )
        )
    if not lawyer_pec:
        issues.append(
            _manual_issue(
                service=SERVICE_GIURIDICO,
                level=LEVEL_WARNING,
                code="citazione_pec_difensore_mancante",
                title="PEC del difensore non disponibile",
                detail="La PEC del procuratore non e' ancora disponibile nel fascicolo o nella configurazione di studio.",
                source=source,
                suggested_action="Configura la PEC di studio o del difensore prima della redazione finale.",
                field="SMTP_FROM",
            )
        )

    parts = _parts_breakdown(parti)
    if parts["assistiti"] == 0 or parts["controparti"] == 0:
        issues.append(
            _manual_issue(
                service=SERVICE_GIURIDICO,
                level=LEVEL_BLOCK,
                code="citazione_parti_non_strutturate",
                title="Parti processuali non ancora strutturate nel fascicolo",
                detail=(
                    "Per la redazione/deposito introduttivo il fascicolo deve distinguere in modo strutturato almeno "
                    "parte attrice e controparte, non solo con testo libero."
                ),
                source=source,
                suggested_action="Collega assistiti e controparti nella sezione Parti del procedimento.",
                field="parti",
            )
        )

    if not str(getattr(fascicolo, "cf_controparte", "") or "").strip():
        issues.append(
            _manual_issue(
                service=SERVICE_GIURIDICO,
                level=LEVEL_WARNING,
                code="citazione_cf_controparte_non_rilevato",
                title="Codice fiscale / partita IVA della controparte non rilevati",
                detail=(
                    "I dati identificativi della controparte non risultano ancora completi per una nota di iscrizione a ruolo pienamente verificabile."
                ),
                source=source,
                suggested_action="Completa o struttura i dati identificativi della controparte nel fascicolo.",
                field="cf_controparte",
            )
        )

    docs = {row["key"]: row for row in required_documents or []}
    if docs.get("notifica", {}).get("state") == "missing":
        issues.append(
            _manual_issue(
                service=SERVICE_DOCUMENTALE,
                level=LEVEL_BLOCK,
                code="citazione_relata_notifica_mancante",
                title="Relata / prova di notifica non rilevata",
                detail=(
                    "Per la citazione l'iscrizione a ruolo richiede la relata di notifica o la prova notificatoria coerente con l'atto introduttivo."
                ),
                source=source,
                suggested_action="Allega relata, ricevute PEC o prova di notifica della citazione.",
                field="documenti",
            )
        )

    if docs.get("procura", {}).get("state") == "missing":
        issues.append(
            _manual_issue(
                service=SERVICE_DOCUMENTALE,
                level=LEVEL_BLOCK,
                code="citazione_procura_mancante",
                title="Procura alle liti non rilevata",
                detail="Nel fascicolo non e' ancora presente una procura riconoscibile come documento essenziale dell'atto introduttivo.",
                source=source,
                suggested_action="Carica o collega la procura alle liti firmata.",
                field="documenti",
            )
        )

    if docs.get("contributo", {}).get("state") == "missing":
        issues.append(
            _manual_issue(
                service=SERVICE_DOCUMENTALE,
                level=LEVEL_WARNING,
                code="citazione_contributo_non_rilevato",
                title="Ricevuta contributo unificato / diritti non rilevata",
                detail=(
                    "Per l'atto introduttivo la ricevuta del contributo unificato e dei diritti va verificata quando dovuta."
                ),
                source=source,
                suggested_action="Verifica se il contributo e' dovuto e allega la ricevuta telematica o la scansione del pagamento.",
                field="documenti",
            )
        )

    return issues


def _specialized_issues(
    *,
    model_code: str,
    fascicolo: Any,
    cliente: Any = None,
    config: Optional[dict[str, Any]] = None,
    parti: Optional[list[tuple[Any, Any]]] = None,
    required_documents: Optional[list[dict[str, Any]]] = None,
) -> list[ValidationIssue]:
    if model_code == "CIV_CIT_001":
        return _citation_specific_issues(
            fascicolo=fascicolo,
            cliente=cliente,
            config=config,
            parti=parti,
            required_documents=required_documents,
        )
    return []


def _documental_issues(required_documents: list[dict[str, Any]]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for item in required_documents:
        if item.get("state") != "missing":
            continue
        key = str(item.get("key") or "")
        issues.append(
            _manual_issue(
                service=SERVICE_DOCUMENTALE,
                level=_document_issue_level(key),
                code=f"doc_{key}_missing",
                title=f"{item.get('label', key)} non rilevato",
                detail=str(item.get("detail") or "Documento essenziale non ancora rilevato."),
                source="Responsabile conformita' documentale",
                suggested_action=f"Carica o collega '{item.get('label', key)}' tra i documenti del fascicolo.",
                field="documenti",
            )
        )
    return issues


def _redaction_issues(
    *,
    fascicolo: Any,
    cliente: Any = None,
    parti: Optional[list[tuple[Any, Any]]] = None,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    parts = _parts_breakdown(parti)
    if not str(getattr(fascicolo, "oggetto", "") or "").strip():
        issues.append(
            _manual_issue(
                service=SERVICE_REDAZIONALE,
                level=LEVEL_BLOCK,
                code="redazione_oggetto_mancante",
                title="Oggetto della pratica non definito",
                detail="Manca ancora un oggetto strutturato da riusare in atto, riepiloghi e controlli.",
                source="Responsabile conformita' redazionale",
                suggested_action="Compila l'oggetto della pratica in modo coerente con la domanda o la difesa.",
                field="oggetto",
            )
        )
    if not str(getattr(fascicolo, "note", "") or "").strip():
        issues.append(
            _manual_issue(
                service=SERVICE_REDAZIONALE,
                level=LEVEL_WARNING,
                code="redazione_fatti_mancanti",
                title="Quadro fattuale iniziale non ancora sintetizzato",
                detail="Nel fascicolo non e' ancora presente una nota iniziale sui fatti o sul contesto operativo della pratica.",
                source="Responsabile conformita' redazionale",
                suggested_action="Aggiungi una sintesi iniziale dei fatti per guidare redazione e controlli successivi.",
                field="note",
            )
        )
    if cliente and parts["assistiti"] == 0:
        issues.append(
            _manual_issue(
                service=SERVICE_REDAZIONALE,
                level=LEVEL_WARNING,
                code="redazione_assistito_non_strutturato",
                title="Assistito non ancora strutturato tra le parti",
                detail="Il cliente e' collegato al fascicolo, ma non risulta ancora censito come parte processuale strutturata.",
                source="Responsabile conformita' redazionale",
                suggested_action="Aggiungi l'assistito nella sezione Parti del procedimento.",
                field="parti",
            )
        )
    if str(getattr(fascicolo, "controparte", "") or "").strip() and parts["controparti"] == 0:
        issues.append(
            _manual_issue(
                service=SERVICE_REDAZIONALE,
                level=LEVEL_WARNING,
                code="redazione_controparte_non_strutturata",
                title="Controparte non ancora strutturata tra le parti",
                detail="La controparte e' presente in testo libero ma non ancora come soggetto processuale strutturato.",
                source="Responsabile conformita' redazionale",
                suggested_action="Struttura la controparte nella sezione Parti del procedimento.",
                field="parti",
            )
        )
    return issues


def _positive_controls(
    *,
    practice_id: str,
    practice_label: str,
    model: dict[str, Any],
    profile: Any,
    schema_channel: Any,
    resolver: dict[str, Any],
    fascicolo: Any,
    required_documents: list[dict[str, Any]],
) -> dict[str, list[dict[str, str]]]:
    processuale: list[dict[str, str]] = []
    documentale: list[dict[str, str]] = []
    tecnico: list[dict[str, str]] = []
    redazionale: list[dict[str, str]] = []

    if practice_id or practice_label:
        processuale.append(
            {
                "state": "ok",
                "title": "Materia / procedimento identificati",
                "detail": practice_label or model.get("name", ""),
            }
        )
    if str(getattr(fascicolo, "tribunale", "") or "").strip():
        processuale.append(
            {
                "state": "ok",
                "title": "Ufficio / sede presenti",
                "detail": str(getattr(fascicolo, "tribunale", "") or "").strip(),
            }
        )
    if profile.registry_suggestion:
        processuale.append(
            {
                "state": "ok",
                "title": "Registro guida determinato",
                "detail": profile.registry_suggestion,
            }
        )

    if resolver.get("office_found"):
        tecnico.append(
            {
                "state": "ok",
                "title": "Ufficio risolto sul catalogo",
                "detail": str(resolver.get("office_name") or ""),
            }
        )
    if schema_channel.label:
        tecnico.append(
            {
                "state": "ok",
                "title": "Canale tecnico determinato",
                "detail": schema_channel.label,
            }
        )

    present_docs = [row for row in required_documents if row.get("state") == "ok"]
    for row in present_docs:
        documentale.append(
            {
                "state": "ok",
                "title": f"{row.get('label', row.get('key', 'Documento'))} presente",
                "detail": ", ".join(row.get("matched") or []) or "Documento rilevato",
            }
        )

    if str(getattr(fascicolo, "oggetto", "") or "").strip():
        redazionale.append(
            {
                "state": "ok",
                "title": "Oggetto pratica compilato",
                "detail": str(getattr(fascicolo, "oggetto", "") or "").strip(),
            }
        )

    return {
        "processuale": processuale,
        "documentale": documentale,
        "tecnico_pst": tecnico,
        "redazionale": redazionale,
    }


def _items_from_issues(issues: list[dict[str, Any]]) -> list[dict[str, str]]:
    return [
        {
            "state": "blocco" if issue.get("level") == LEVEL_BLOCK else ("warning" if issue.get("level") == LEVEL_WARNING else "ok"),
            "title": str(issue.get("title") or "").strip(),
            "detail": str(issue.get("detail") or "").strip(),
            "action": str(issue.get("suggested_action") or "").strip(),
        }
        for issue in issues
    ]


def _section_state(items: list[dict[str, str]]) -> str:
    if any(item.get("state") == "blocco" for item in items):
        return "blocco"
    if any(item.get("state") == "warning" for item in items):
        return "warning"
    return "ok"


def _score_from_issues(issues: list[dict[str, Any]]) -> int:
    blocks = sum(1 for issue in issues if issue.get("level") == LEVEL_BLOCK)
    warnings = sum(1 for issue in issues if issue.get("level") == LEVEL_WARNING)
    penalty = min(85, (blocks * 18) + (warnings * 5))
    return max(0, 100 - penalty)


def _count_states(items: list[dict[str, str]]) -> dict[str, int]:
    return {
        "ok": sum(1 for item in items if item.get("state") == "ok"),
        "warning": sum(1 for item in items if item.get("state") == "warning"),
        "blocco": sum(1 for item in items if item.get("state") == "blocco"),
    }


def _section_payload(label: str, items: list[dict[str, str]]) -> dict[str, Any]:
    counts = _count_states(items)
    return {
        "label": label,
        "state": _section_state(items),
        "items": items,
        "counts": counts,
        "has_items": bool(items),
        "passed_count": counts["ok"],
        "warning_count": counts["warning"],
        "blocking_count": counts["blocco"],
    }


def _gate_reason(
    *,
    allowed: bool,
    applicable: bool,
    issues: list[dict[str, Any]],
    fallback_allowed: str,
    fallback_blocked: str,
    fallback_na: str,
) -> str:
    if not applicable:
        return fallback_na
    if allowed:
        return fallback_allowed
    for issue in issues:
        if issue.get("level") == LEVEL_BLOCK:
            return str(issue.get("suggested_action") or issue.get("detail") or fallback_blocked).strip()
    for issue in issues:
        if issue.get("level") == LEVEL_WARNING:
            return str(issue.get("suggested_action") or issue.get("detail") or fallback_blocked).strip()
    return fallback_blocked


def _readiness_labels(state: str) -> tuple[str, str]:
    if state == "ok":
        return (
            "Fascicolo conforme ai dati minimi per redazione / deposito",
            "I dati strutturati oggi presenti sono coerenti con una predisposizione operativa dell'atto.",
        )
    if state == "warning":
        return (
            "Fascicolo quasi pronto, ma con verifiche ancora aperte",
            "Puoi lavorare sulla redazione, ma restano dati o documenti da confermare prima del deposito.",
        )
    return (
        "Fascicolo non ancora conforme per redazione / deposito",
        "Il workflow interno e' avviato, ma mancano dati o documenti minimi per parlare di conformita' procedurale/PST.",
    )


def build_fascicolo_compliance_summary(
    *,
    fascicolo: Any,
    cliente: Any = None,
    preventivo: Any = None,
    conferimento: Any = None,
    config: Optional[dict[str, Any]] = None,
    utente: Any = None,
    office_cache_path: str = "",
    parti: Optional[list[tuple[Any, Any]]] = None,
) -> dict[str, Any]:
    config = config or {}
    model_code = _infer_model_code(fascicolo=fascicolo, preventivo=preventivo, conferimento=conferimento)
    model = get_modello(model_code)
    if not model:
        return {
            "available": False,
            "workflow_label": "Apertura interna del workflow completata",
            "readiness_label": "Manca ancora un profilo di conformita' tipizzato per questa pratica.",
            "summary": "Il fascicolo e' aperto internamente ma la conformita' procedurale va ancora configurata per questa tipologia.",
        }

    assistant = AssistenteRedazionale(audit_db_path="", office_cache_path=office_cache_path)
    profile = assistant._build_profile(model, fascicolo=fascicolo)
    schema_channel = SCHEMA_CHANNELS.get(profile.channel, SCHEMA_CHANNELS["PEC"])
    lawyer_name = str(getattr(fascicolo, "avvocato_referente", "") or config.get("STUDIO_AVVOCATO", "") or "").strip()
    object_text = str(getattr(fascicolo, "oggetto", "") or getattr(fascicolo, "titolo", "") or model.get("name", "")).strip()
    facts_text = str(getattr(fascicolo, "note", "") or "").strip()
    client_name = str(getattr(cliente, "nome_completo", "") or getattr(fascicolo, "nome_cliente", "") or "").strip()
    court_name = str(getattr(fascicolo, "tribunale", "") or "").strip()
    document_date = str(getattr(fascicolo, "data_apertura", "") or date.today().isoformat()).strip()
    payload = {
        "model_code": model["code"],
        "title": model["name"],
        "act_type": model["name"],
        "area": str(model.get("area", "") or "").upper(),
        "matter": profile.materia,
        "case_id": str(getattr(fascicolo, "id", "") or "").strip(),
        "id_cliente": str(getattr(fascicolo, "id_cliente", "") or getattr(cliente, "id", "") or "").strip(),
        "attachments_list": [getattr(doc, "nome", "") for doc in getattr(fascicolo, "documenti", []) if getattr(doc, "nome", "")],
        "subject": object_text,
        "court_name": court_name,
        "recipient_or_court": court_name,
        "client_or_sender": client_name,
        "counterparty_or_recipient": str(getattr(fascicolo, "controparte", "") or "").strip(),
        "lawyer": lawyer_name,
        "signature": lawyer_name,
        "place": str(getattr(getattr(cliente, "indirizzo_residenza", None), "comune", "") or config.get("STUDIO_INDIRIZZO", "") or "").strip(),
        "document_date": document_date,
        "facts": facts_text,
        "requests_or_conclusions": object_text,
        "claimant": client_name,
        "plaintiff": client_name,
        "appellant": client_name,
        "defendant": str(getattr(fascicolo, "controparte", "") or "").strip(),
        "respondent": str(getattr(fascicolo, "controparte", "") or "").strip(),
        "appellee": str(getattr(fascicolo, "controparte", "") or "").strip(),
        "competent_tar": court_name,
        "competent_tax_court": court_name,
        "proceeding_authority": court_name,
        "assisted_person": client_name,
        "respondent_administration": str(getattr(fascicolo, "controparte", "") or "").strip(),
        "tax_authority_or_resistant_party": str(getattr(fascicolo, "controparte", "") or "").strip(),
    }
    synthetic_fascicolo = assistant._build_fascicolo_proxy(model, payload, fascicolo=fascicolo, cliente=cliente)
    resolver = assistant.resolver.resolve(
        synthetic_fascicolo,
        profile.to_procedural_profile(),
        profile.registry_suggestion,
    )
    document_payloads = _document_payloads(fascicolo)
    context = {
        "tipo_atto": profile.tipo_atto_code,
        "codice_registro": profile.registry_suggestion,
        "oggetto": str(getattr(fascicolo, "oggetto", "") or getattr(fascicolo, "titolo", "") or model["name"]).strip(),
        "numero_rg": str(getattr(fascicolo, "numero_rg", "") or "").strip(),
        "anno_rg": int(getattr(fascicolo, "anno_rg", 0) or 0),
        "operatore": str(getattr(utente, "username", "") or getattr(utente, "nome_completo", "") or "").strip(),
        "id_cliente": str(getattr(fascicolo, "id_cliente", "") or getattr(cliente, "id", "") or "").strip(),
        "controparte": str(getattr(fascicolo, "controparte", "") or "").strip(),
        "tribunale": str(getattr(fascicolo, "tribunale", "") or "").strip(),
        "recipient_or_court": str(getattr(fascicolo, "tribunale", "") or "").strip(),
    }

    issues: list[ValidationIssue] = []
    if profile.channel == "PCT_TELEMATICO":
        issues.extend(
            assistant.legal_validator.validate(
                fascicolo=synthetic_fascicolo,
                profile=profile.to_procedural_profile(),
                resolver=resolver,
                context=context,
                selected_documents=document_payloads,
                all_documents=document_payloads,
            )
        )
    else:
        issues.extend(
            assistant._validate_non_pct_legal(
                profile=profile,
                model=model,
                payload=payload,
                resolver=resolver,
            )
        )

    issues.extend(
        assistant._validate_schema_preview(
            profile=profile,
            resolver=resolver,
            schema_channel=schema_channel,
        )
    )

    required_documents = assistant._evaluate_required_documents(profile, {"attachments_list": payload["attachments_list"]})
    issues.extend(_documental_issues(required_documents))
    issues.extend(
        _specialized_issues(
            model_code=model_code,
            fascicolo=fascicolo,
            cliente=cliente,
            config=config,
            parti=parti,
            required_documents=required_documents,
        )
    )
    issues.extend(
        _redaction_issues(
            fascicolo=fascicolo,
            cliente=cliente,
            parti=parti,
        )
    )

    overall = _overall_state(issues)
    readiness_label, summary = _readiness_labels(overall)
    issue_dicts = [issue.to_dict() for issue in issues]
    positive_controls = _positive_controls(
        practice_id=_practice_id(preventivo=preventivo, conferimento=conferimento),
        practice_label=_practice_label(_practice_id(preventivo=preventivo, conferimento=conferimento), preventivo=preventivo, conferimento=conferimento),
        model=model,
        profile=profile,
        schema_channel=schema_channel,
        resolver=resolver,
        fascicolo=fascicolo,
        required_documents=required_documents,
    )
    processuale_issues = [issue for issue in issue_dicts if issue.get("service") == SERVICE_GIURIDICO]
    documentale_issues = [issue for issue in issue_dicts if issue.get("service") == SERVICE_DOCUMENTALE]
    tecnico_issues = [issue for issue in issue_dicts if issue.get("service") == SERVICE_TECNICO]
    redazionali_issues = [issue for issue in issue_dicts if issue.get("service") == SERVICE_REDAZIONALE]

    sections = {
        "processuale": _section_payload(
            "Controlli processuali",
            positive_controls["processuale"] + _items_from_issues(processuale_issues),
        ),
        "documentale": _section_payload(
            "Controlli documentali",
            positive_controls["documentale"] + _items_from_issues(documentale_issues),
        ),
        "tecnico_pst": _section_payload(
            "Controlli tecnici PST",
            positive_controls["tecnico_pst"] + _items_from_issues(tecnico_issues),
        ),
        "redazionale": _section_payload(
            "Controlli redazionali",
            positive_controls["redazionale"] + _items_from_issues(redazionali_issues),
        ),
    }

    processuale_state = sections["processuale"]["state"]
    documentale_state = sections["documentale"]["state"]
    tecnico_state = sections["tecnico_pst"]["state"]
    redazionale_state = sections["redazionale"]["state"]

    semaforo = {
        "workflow": "ok",
        "generale": overall,
        "processuale": processuale_state,
        "giuridico": processuale_state,
        "tecnico_pst": tecnico_state,
        "tecnico_ministeriale": tecnico_state,
        "documentale": documentale_state,
        "redazionale": redazionale_state,
    }

    blocking_issues = [issue for issue in issue_dicts if issue.get("level") == LEVEL_BLOCK]
    warning_issues = [issue for issue in issue_dicts if issue.get("level") == LEVEL_WARNING]
    info_issues = [issue for issue in issue_dicts if issue.get("level") == LEVEL_OK]
    next_steps: list[str] = []
    for issue in blocking_issues + warning_issues:
        action = str(issue.get("suggested_action") or "").strip()
        if action and action not in next_steps:
            next_steps.append(action)
    if not next_steps:
        next_steps.append("Puoi passare al redattore guidato o al pre-deposito con i dati oggi presenti.")

    practice_id = _practice_id(preventivo=preventivo, conferimento=conferimento)
    score = _score_from_issues(issue_dicts)
    passed_controls = []
    for section in sections.values():
        for item in section["items"]:
            if item.get("state") == "ok":
                passed_controls.append(item)

    corrections: list[dict[str, str]] = []
    seen_corrections: set[str] = set()
    for issue in blocking_issues + warning_issues:
        key = str(issue.get("code") or issue.get("title") or "").strip()
        if not key or key in seen_corrections:
            continue
        seen_corrections.add(key)
        corrections.append(
            {
                "code": str(issue.get("code") or "").strip(),
                "field": str(issue.get("field") or "").strip(),
                "service": str(issue.get("service") or "").strip(),
                "level": str(issue.get("level") or "").strip(),
                "state": "blocco" if issue.get("level") == LEVEL_BLOCK else "warning",
                "title": str(issue.get("title") or "").strip(),
                "detail": str(issue.get("detail") or "").strip(),
                "action": str(issue.get("suggested_action") or "").strip(),
                "source": str(issue.get("source") or "").strip(),
            }
        )

    can_generate_final_act = processuale_state != "blocco" and documentale_state != "blocco" and redazionale_state != "blocco"
    can_generate_xml = bool(schema_channel.supports_xml) and processuale_state != "blocco" and documentale_state != "blocco" and tecnico_state != "blocco" and redazionale_state != "blocco"
    can_prepare_deposit = profile.channel != "PEC" and processuale_state != "blocco" and documentale_state != "blocco" and tecnico_state != "blocco" and redazionale_state != "blocco"
    can_close_review = overall != "blocco"
    action_gates = {
        "generate_final_act": {
            "label": "Genera atto definitivo",
            "applicable": True,
            "allowed": can_generate_final_act,
            "reason": _gate_reason(
                allowed=can_generate_final_act,
                applicable=True,
                issues=blocking_issues + warning_issues,
                fallback_allowed="La redazione finale puo' procedere con i dati oggi presenti.",
                fallback_blocked="Restano dati processuali, documentali o redazionali da correggere prima della bozza definitiva.",
                fallback_na="Sempre applicabile.",
            ),
        },
        "generate_xml": {
            "label": "Genera XML ministeriale",
            "applicable": bool(schema_channel.supports_xml),
            "allowed": can_generate_xml,
            "reason": _gate_reason(
                allowed=can_generate_xml,
                applicable=bool(schema_channel.supports_xml),
                issues=processuale_issues + tecnico_issues + documentale_issues + redazionali_issues,
                fallback_allowed="I dati strutturati sono sufficienti per la generazione XML.",
                fallback_blocked="Completa i dati strutturati e risolvi i blocchi processuali/tecnici prima di generare l'XML.",
                fallback_na="Per questo canale non e' previsto un XML ministeriale.",
            ),
        },
        "prepare_deposit": {
            "label": "Prepara deposito",
            "applicable": profile.channel != "PEC",
            "allowed": can_prepare_deposit,
            "reason": _gate_reason(
                allowed=can_prepare_deposit,
                applicable=profile.channel != "PEC",
                issues=blocking_issues + warning_issues,
                fallback_allowed="Il fascicolo e' pronto per il pre-deposito tecnico.",
                fallback_blocked="Sono ancora presenti blocchi o verifiche aperte che impediscono il pre-deposito.",
                fallback_na="Per il canale PEC non esiste una busta ministeriale da preparare.",
            ),
        },
        "close_review": {
            "label": "Chiudi verifica",
            "applicable": True,
            "allowed": can_close_review,
            "reason": _gate_reason(
                allowed=can_close_review,
                applicable=True,
                issues=blocking_issues + warning_issues,
                fallback_allowed="Puoi chiudere la verifica mantenendo il report come snapshot operativo.",
                fallback_blocked="La verifica non puo' essere chiusa finche restano errori bloccanti.",
                fallback_na="Sempre applicabile.",
            ),
        },
    }

    return {
        "available": True,
        "workflow_label": "Apertura interna del workflow completata",
        "readiness_label": readiness_label,
        "summary": summary,
        "overall_state": overall,
        "badge_class": {"ok": "success", "warning": "warning text-dark", "blocco": "danger"}.get(overall, "secondary"),
        "general": {
            "state": overall,
            "label": {"ok": "Pronto", "warning": "Da verificare", "blocco": "Bloccante"}.get(overall, "Da verificare"),
            "score": score,
            "blocking_count": len(blocking_issues),
            "warning_count": len(warning_issues),
            "info_count": len(info_issues),
            "passed_count": len(passed_controls),
        },
        "practice_id": practice_id,
        "practice_label": _practice_label(practice_id, preventivo=preventivo, conferimento=conferimento) or model["name"],
        "model_code": model_code,
        "model_name": model["name"],
        "channel": profile.channel,
        "channel_label": schema_channel.label,
        "competence_rule": profile.competence_rule,
        "registry_suggestion": profile.registry_suggestion,
        "grade_label": profile.grade_label,
        "resolver": resolver,
        "semaforo": semaforo,
        "sections": sections,
        "passed_controls": passed_controls[:12],
        "corrections": corrections[:12],
        "action_gates": action_gates,
        "required_documents": required_documents,
        "missing_documents": [row for row in required_documents if row.get("state") == "missing"],
        "blocking_issues": blocking_issues,
        "warning_issues": warning_issues,
        "info_issues": info_issues,
        "issues": issue_dicts,
        "next_steps": next_steps[:6],
        "sources": _dedupe_sources(profile.sources, schema_channel.sources, _MODEL_SOURCES.get(model_code, [])),
    }
