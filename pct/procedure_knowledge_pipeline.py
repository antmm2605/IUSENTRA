"""Pipeline fonti multi-sorgente e schede conoscitive originali IUSENTRA."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
import re
from typing import Any

from pct.procedure_lifecycle_repository import ProcedureLifecycleRepository


SOURCE_TYPES = {
    "official",
    "jurisprudence",
    "professional",
    "internal",
    "technical",
    "local_practice",
    "licensed_database",
}

COPYRIGHT_POLICIES = {
    "official_public",
    "summary_only",
    "internal_confidential",
    "licensed_use",
    "no_reuse",
    "unknown_review_required",
}

REQUIRED_CARD_SECTIONS = (
    "presupposti",
    "documenti_necessari",
    "termini",
    "competenza",
    "atto_da_redigere",
    "allegati",
    "firma_digitale",
    "deposito",
    "ricevute_attese",
    "accettazione",
    "adempimenti_successivi",
    "notifiche",
    "relata",
    "prova_notifica",
    "errori_ricorrenti",
    "rischi",
    "scelte_strategiche",
    "fonti_consultate",
    "data_verifica",
)

PERSONAL_DATA_RE = re.compile(
    r"(?i)([A-Z]{6}[0-9]{2}[A-Z][0-9]{2}[A-Z][0-9]{3}[A-Z]|[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,})"
)


@dataclass(frozen=True)
class ValidationReport:
    valid: bool
    errors: list[str]
    warnings: list[str]
    blocking_errors: list[str]
    privacy_review_required: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _default_policy(source_type: str) -> str:
    if source_type == "official":
        return "official_public"
    if source_type == "internal":
        return "internal_confidential"
    if source_type == "licensed_database":
        return "licensed_use"
    return "summary_only"


def validate_source_evidence(evidence: dict[str, Any]) -> ValidationReport:
    errors: list[str] = []
    warnings: list[str] = []
    source_type = _clean(evidence.get("source_type"))
    policy = _clean(evidence.get("copyright_policy")) or _default_policy(source_type)
    quote = _clean(evidence.get("original_quote_short"))
    principle = _clean(evidence.get("extracted_principle"))
    url = _clean(evidence.get("source_url"))
    title = _clean(evidence.get("source_title"))
    privacy_review_required = False

    if source_type not in SOURCE_TYPES:
        errors.append("source_type non ammesso.")
    if policy not in COPYRIGHT_POLICIES:
        errors.append("copyright_policy non ammessa.")
    if not url and not title:
        errors.append("source_url o source_title obbligatorio.")
    if not _clean(evidence.get("procedure_code")):
        errors.append("procedure_code obbligatorio.")
    if not _clean(evidence.get("evidence_kind")):
        errors.append("evidence_kind obbligatorio.")

    if source_type == "professional":
        if not principle:
            errors.append("Per fonti professionali extracted_principle è obbligatorio.")
        if quote and len(quote) > 500:
            errors.append("Per fonti professionali original_quote_short deve restare entro 500 caratteri.")
        if policy != "summary_only":
            warnings.append("Le fonti professionali esterne dovrebbero usare summary_only.")
    elif quote and len(quote) > 500 and source_type not in {"official", "internal", "licensed_database"}:
        errors.append("original_quote_short supera 500 caratteri per una fonte non riutilizzabile estesamente.")

    if source_type == "internal":
        if policy != "internal_confidential":
            warnings.append("Le fonti interne dovrebbero essere marcate internal_confidential.")
        body = " ".join(str(evidence.get(key) or "") for key in ("source_title", "extracted_principle", "original_quote_short", "notes"))
        privacy_review_required = bool(PERSONAL_DATA_RE.search(body))
        if privacy_review_required:
            warnings.append("Possibili dati personali in fonte interna: review privacy richiesta.")

    if source_type == "official":
        if policy != "official_public":
            warnings.append("Le fonti ufficiali dovrebbero essere marcate official_public.")
        if not url:
            errors.append("Per fonti ufficiali source_url è obbligatorio.")
        if not _clean(evidence.get("last_checked_at")):
            warnings.append("last_checked_at mancante per fonte ufficiale.")

    return ValidationReport(
        valid=not errors,
        errors=errors,
        warnings=warnings,
        blocking_errors=list(errors),
        privacy_review_required=privacy_review_required,
    )


def add_source_evidence(repo: ProcedureLifecycleRepository, **evidence: Any) -> int:
    source_type = _clean(evidence.get("source_type"))
    evidence.setdefault("copyright_policy", _default_policy(source_type))
    if source_type == "professional":
        evidence.setdefault("review_status", "needs_review")
    validation = validate_source_evidence(evidence)
    if validation.errors:
        raise ValueError("; ".join(validation.errors))
    if validation.privacy_review_required:
        evidence["notes"] = _clean(evidence.get("notes") or "") + " privacy_review_required"
    return repo.add_source_evidence(evidence)


def build_original_knowledge_card(
    procedure_code: str,
    xsd_code: str | None,
    sources: list[dict[str, Any]],
) -> dict[str, Any]:
    today = date.today().isoformat()
    consulted = [
        {
            "source_id": source.get("source_id"),
            "source_type": source.get("source_type"),
            "title": source.get("source_title"),
            "url": source.get("source_url"),
            "last_checked_at": source.get("last_checked_at"),
        }
        for source in sources
    ]
    principles = [
        _clean(source.get("extracted_principle"))
        for source in sources
        if _clean(source.get("extracted_principle"))
    ]
    base_note = (
        "Dalle fonti confrontate emergono principi operativi riformulati in modo autonomo da IUSENTRA; "
        "la scheda non copia contenuti professionali esterni e conserva link, tipo fonte e data di verifica."
    )
    return {
        "presupposti": principles[:3] or ["Presupposti da completare con review dell'avvocato."],
        "documenti_necessari": ["Documenti della pratica da raccogliere e verificare prima del deposito o della notifica."],
        "termini": ["Termini da verificare sul caso concreto e sulle fonti ufficiali applicabili."],
        "competenza": ["Competenza da qualificare in base a ufficio, rito, valore e materia."],
        "atto_da_redigere": ["Atto principale da selezionare secondo procedura operativa e codice XSD."],
        "allegati": ["Allegati obbligatori e facoltativi da inventariare nel fascicolo."],
        "firma_digitale": ["La firma digitale non è automatica: serve richiesta, firma esterna e verifica registrata."],
        "deposito": ["Il deposito richiede pacchetto validato e canale autorizzato o stub non operativo."],
        "ricevute_attese": ["PEC accettazione, PEC consegna, esiti controlli e accettazione o rifiuto ufficio quando previsti."],
        "accettazione": ["Nessuna accettazione può essere dichiarata senza ricevuta o prova validata."],
        "adempimenti_successivi": ["Valutazione post-accettazione da mantenere in review se non codificata."],
        "notifiche": ["Notifica da trattare come workflow separato con destinatario, indirizzo, relata e prove."],
        "relata": ["Relata da associare all'atto notificato e alle evidenze disponibili."],
        "prova_notifica": ["La prova di notifica va acquisita e conservata prima di marcare il workflow come provato."],
        "errori_ricorrenti": ["Codice XSD non verificato, fonte non tracciata, ricevute mancanti, review non completata."],
        "rischi": ["Rischio operativo medio o alto se mancano fonti ufficiali, evidenze o review."],
        "scelte_strategiche": ["Scelte da documentare nella scheda pratica e validare con l'avvocato."],
        "fonti_consultate": consulted,
        "data_verifica": today,
        "nota_originalita": base_note,
        "procedure_code": procedure_code,
        "xsd_code": xsd_code,
    }


def _card_validation(sources: list[dict[str, Any]], card_json: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    for section in REQUIRED_CARD_SECTIONS:
        if section not in card_json:
            errors.append(f"Sezione obbligatoria mancante: {section}")
    if not any(source.get("source_type") in {"official", "technical"} for source in sources):
        errors.append("Serve almeno una fonte ufficiale o tecnica.")
    if any(source.get("review_status") not in {"validated", "approved"} for source in sources):
        warnings.append("Una o più fonti richiedono review prima della pubblicazione.")
    return {"errors": errors, "warnings": warnings, "blocking_errors": list(errors)}


def save_knowledge_card(
    repo: ProcedureLifecycleRepository,
    *,
    procedure_code: str,
    xsd_code: str | None,
    title: str,
    sources: list[dict[str, Any]],
    risk_level: str = "MEDIUM",
) -> int:
    card_json = build_original_knowledge_card(procedure_code, xsd_code, sources)
    validation = _card_validation(sources, card_json)
    return repo.create_knowledge_card(
        {
            "procedure_code": procedure_code,
            "xsd_code": xsd_code,
            "title": title,
            "status": "draft" if validation["errors"] else "needs_review",
            "risk_level": risk_level,
            "requires_human_review": 1,
            "generated_from_sources_json": [source.get("id") for source in sources if source.get("id")],
            "card_json": card_json,
            "summary_original": card_json["nota_originalita"],
            "validation_report_json": validation,
        }
    )


def submit_knowledge_card_for_review(repo: ProcedureLifecycleRepository, card_id: int, reason: str = "") -> None:
    card = repo.get_knowledge_card(card_id)
    if not card:
        raise ValueError("Scheda non trovata.")
    repo.update_knowledge_card_status(card_id, status="needs_review", review_reason=reason)


def approve_knowledge_card(repo: ProcedureLifecycleRepository, card_id: int, reviewer: str, reason: str = "") -> None:
    if not _clean(reviewer):
        raise ValueError("Reviewer obbligatorio per approvare la scheda.")
    card = repo.get_knowledge_card(card_id)
    if not card:
        raise ValueError("Scheda non trovata.")
    validation = dict(card.get("validation_report_json") or {})
    if validation.get("blocking_errors"):
        raise ValueError("Scheda con errori bloccanti: non approvabile.")
    repo.update_knowledge_card_status(
        card_id,
        status="approved",
        reviewer=reviewer,
        review_reason=reason or "Scheda revisionata dall'avvocato.",
        validation_report=validation,
    )


def publish_knowledge_card(repo: ProcedureLifecycleRepository, card_id: int) -> None:
    card = repo.get_knowledge_card(card_id)
    if not card:
        raise ValueError("Scheda non trovata.")
    if card.get("status") != "approved":
        raise ValueError("La scheda deve essere approved prima della pubblicazione.")
    validation = dict(card.get("validation_report_json") or {})
    if validation.get("blocking_errors"):
        raise ValueError("Scheda con errori bloccanti: pubblicazione negata.")
    sources = repo.list_source_evidence(str(card.get("procedure_code") or ""), card.get("xsd_code"))
    if not any(row.get("source_type") in {"official", "technical"} for row in sources):
        raise ValueError("Pubblicazione negata: manca una fonte ufficiale o tecnica.")
    if any(row.get("review_status") not in {"validated", "approved"} for row in sources):
        raise ValueError("Pubblicazione negata: una o più fonti non sono validate.")
    repo.update_knowledge_card_status(card_id, status="published", published=True)
