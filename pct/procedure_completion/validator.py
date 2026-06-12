"""Regole fail-closed del Procedure Completion Engine (output machine-readable)."""

from __future__ import annotations

import re
from typing import Any

from pct.procedure_completion.models import (
    ProcedureCompletionCard,
    ProcedureCompletionValidationReport,
)

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_CF_RE = re.compile(r"\b[A-Z]{6}\d{2}[A-Z]\d{2}[A-Z]\d{3}[A-Z]\b")
_IBAN_RE = re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b")


def _contiene_dati_personali(testo: str) -> bool:
    valore = str(testo or "")
    return bool(_EMAIL_RE.search(valore) or _CF_RE.search(valore) or _IBAN_RE.search(valore))


def validate_card(card: ProcedureCompletionCard) -> ProcedureCompletionValidationReport:
    report = ProcedureCompletionValidationReport()

    fonti_ufficiali = card.fonti_ufficiali_o_tecniche
    citazioni = card.citazioni_verificabili

    # Nessuna fonte ufficiale/tecnica => non approvabile.
    if not fonti_ufficiali:
        report.errors.append("Nessuna fonte ufficiale o tecnica collegata: scheda non approvabile.")

    # Nessuna citazione verificabile => non approvabile/pubblicabile.
    if not citazioni:
        report.errors.append("Nessuna citazione verificabile: scheda non approvabile ne' pubblicabile.")

    # Articolo citato senza fonte/versione => blocking_error.
    for cit in card.citations:
        riferimento = str(cit.get("riferimento") or "").strip()
        if not riferimento:
            continue
        if not (cit.get("source_id") or cit.get("url")):
            report.blocking_errors.append(f"Citazione senza fonte collegata: {riferimento}.")
        elif not str(cit.get("versione") or "").strip():
            report.warnings.append(f"Citazione senza data di versione/verifica: {riferimento}.")

    # Termine processuale senza base normativa/regola => blocking_error.
    for termine in card.termini_processuali:
        etichetta = str(termine.get("termine") or "").strip()
        base = str(termine.get("base_normativa") or "").strip()
        fonte = str(termine.get("fonte_id") or "").strip()
        if etichetta and not (base or fonte):
            report.blocking_errors.append(f"Termine processuale senza base normativa: {etichetta}.")

    # Adempimento fiscale senza fonte fiscale => warning/gap.
    for adempimento in card.adempimenti_fiscali:
        if str(adempimento.get("adempimento") or "").strip() and not str(adempimento.get("fonte") or "").strip():
            report.warnings.append(
                f"Adempimento fiscale senza fonte fiscale: {adempimento.get('adempimento')}."
            )

    # Allegati obbligatori senza evidenza/fonte => warning.
    for allegato in card.allegati_obbligatori:
        if isinstance(allegato, dict):
            nome = str(allegato.get("allegato") or allegato.get("nome") or "").strip()
            if nome and not (allegato.get("fonte_id") or allegato.get("evidenza")):
                report.warnings.append(f"Allegato obbligatorio senza evidenza tracciata: {nome}.")

    # Nessun template collegato => needs_review (non blocca, ma non e' pubblicabile come completa).
    if not card.template_selected.get("template_id"):
        report.warnings.append("Atto principale non collegato a un template: scheda da revisionare.")

    # Dati personali in fonti interne => privacy_review_required.
    for src in card.sources:
        if str(src.get("source_type")) == "internal" and _contiene_dati_personali(
            f"{src.get('title', '')} {src.get('excerpt', '')}"
        ):
            report.privacy_review_required = True
            report.warnings.append("Fonte interna con possibili dati personali: richiesta verifica privacy.")
            break

    # Fonti professionali devono restare summary_only.
    for src in card.sources:
        if str(src.get("source_type")) == "professional" and str(src.get("copyright_policy")) != "summary_only":
            report.blocking_errors.append(
                "Fonte professionale esterna senza policy summary_only: copia estesa non ammessa."
            )

    # Gap bloccanti gia' dichiarati nella scheda.
    for gap in card.gap_evidenza:
        if str(gap.get("severita")) == "blocking":
            report.blocking_errors.append(str(gap.get("descrizione") or gap.get("codice_gap") or "Gap bloccante."))

    report.valid = not report.blocking_errors
    report.approvable = bool(fonti_ufficiali) and bool(citazioni) and not report.blocking_errors
    report.publishable = (
        report.approvable
        and card.status in {"approved", "published"}
        and bool(card.review_avvocato.get("reviewer"))
        and not report.privacy_review_required
    )
    return report


__all__ = ["validate_card"]
