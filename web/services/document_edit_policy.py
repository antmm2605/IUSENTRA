"""Regola condivisa per la modifica dei documenti dello studio."""
from pathlib import Path
from pct.document_signature_state import document_has_real_digital_signature


def pdf_studio_modificabile(documento):
    return False


def motivo_blocco_editor(documento):
    if document_has_real_digital_signature(documento):
        return "Il documento firmato resta in sola consultazione."
    if Path(str(getattr(documento, "nome", ""))).suffix.lower() == ".pdf":
        return (
            "Il PDF viene mostrato con l'anteprima originale per conservare impaginazione, "
            "font, immagini, timbri e spaziature. Per modificarlo importa o sostituisci "
            "una nuova versione del file verificata."
        )
    return ""
