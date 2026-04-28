from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class RejectionDiagnosis:
    category: str
    severity: str
    human_message: str
    technical_message: str = ""
    suggested_fix: str = ""
    auto_fix_available: bool = False
    can_resubmit: bool = False
    requires_lawyer_review: bool = True


class RejectionAnalyzer:
    def analyze(self, text: str) -> RejectionDiagnosis:
        lower = str(text or "").lower()
        if "troppo grande" in lower or "dimensione" in lower or "50 mb" in lower:
            return RejectionDiagnosis(
                "file_troppo_grande",
                "high",
                "Il file supera i limiti dimensionali del canale.",
                suggested_fix="Comprimi o separa gli allegati e prepara un nuovo invio.",
                auto_fix_available=True,
                can_resubmit=True,
            )
        if "firma non valida" in lower or "firma digitale" in lower:
            return RejectionDiagnosis(
                "firma_non_valida",
                "critical",
                "La firma digitale non risulta valida.",
                suggested_fix="Rigenera la firma con certificato valido e ripeti la validazione.",
                can_resubmit=True,
            )
        if "certificato scaduto" in lower:
            return RejectionDiagnosis(
                "certificato_scaduto",
                "critical",
                "Il certificato di firma risulta scaduto.",
                suggested_fix="Usa un certificato valido prima di procedere.",
                can_resubmit=False,
            )
        if "pdf/a" in lower or "pdf non conforme" in lower:
            return RejectionDiagnosis(
                "pdf_non_conforme",
                "high",
                "Il PDF non risulta conforme.",
                suggested_fix="Converti o rigenera il PDF in formato conforme.",
                auto_fix_available=True,
                can_resubmit=True,
            )
        return RejectionDiagnosis(
            "errore_sconosciuto",
            "medium",
            "Errore non classificato automaticamente.",
            technical_message=str(text or "")[:500],
            suggested_fix="Verifica il dettaglio tecnico e chiedi revisione dell'avvocato.",
            can_resubmit=False,
        )
