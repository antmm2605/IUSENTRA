"""Motivo leggibile dall'avvocato per una lettura documentale non riuscita.

Il registro conserva il codice tecnico e il messaggio grezzo per l'audit
(art. 3 D.M. 44/2011, art. 20 CAD: integrità e tracciabilità del documento
informatico); all'avvocato si mostra invece che cosa è successo e che cosa
può fare, in italiano e senza eccezioni del motore di lettura.
"""
from __future__ import annotations

from .busta_cifrata import CODICE_BUSTA_CIFRATA

_RIPROVA = "Premere «Riprova errori»; se l'errore si ripete, ricaricare il file originale."

MOTIVI: dict[str, str] = {
    "source_unavailable": "Il file non si trova più nell'archivio del fascicolo. Ricaricare il documento originale.",
    "source_access_denied": "Il file non è accessibile all'archivio del fascicolo. Ricaricare il documento originale.",
    "source_processing_failed": "La lettura automatica del documento non è riuscita. " + _RIPROVA,
    "upload_interrupted": "Il caricamento del file si è interrotto prima della lettura. Ricaricare il documento.",
    "encrypted_document": "Il documento è cifrato e non si può decifrare con la chiave dello studio. Ricaricare la copia in chiaro.",
    "invalid_cms": "La busta firmata non ha una struttura riconosciuta. Ricaricare l'atto firmato originale (.p7m).",
    "pdf_payload_unavailable": "Il PDF dentro la busta firmata non è leggibile. Ricaricare l'atto firmato originale (.p7m).",
    "pdf_magic_mismatch": "Il file ha estensione PDF ma non contiene un PDF leggibile. Ricaricare il PDF originale.",
    "pdf_extraction_failed": "Il PDF non è stato letto (file danneggiato o protetto da password). " + _RIPROVA,
    "pdf_body_ocr_required": "Si legge solo il timbro di firma: il testo dell'atto è un'immagine e l'OCR non è riuscito. "
                             "Premere «Riprova errori» o ricaricare una copia PDF con testo.",
    "no_recoverable_text": "Il documento non contiene testo leggibile automaticamente (es. scansione illeggibile). "
                           "Ricaricare una copia più nitida o in PDF con testo.",
    "docx_extraction_failed": "Il file Word non è stato letto (danneggiato o protetto). Ricaricare il file o salvarlo in PDF.",
    "doc_legacy_extraction_unavailable": "Il formato Word .doc storico non si legge automaticamente. Salvare il file in PDF o .docx e ricaricarlo.",
    "office_native_extraction_failed": "Il file Office non è stato letto (danneggiato o protetto). Salvarlo in PDF e ricaricarlo.",
    "xls_unreadable": "Il foglio Excel non è leggibile. Ricaricare l'originale integro o salvarlo in PDF.",
    "eml_extraction_failed": "Il messaggio di posta non è stato letto. " + _RIPROVA,
    "identity_image_invalid": "L'immagine del documento d'identità non è leggibile. Ricaricare una foto o scansione nitida.",
    "catalog_pipeline_error": "La classificazione del documento non è stata completata. " + _RIPROVA,
}


def motivo_per_avvocato(codice: str | None, messaggio: str | None = None) -> str:
    """Il motivo da mostrare: frase dichiarata per il codice, altrimenti il messaggio registrato."""
    codice = str(codice or "").strip()
    if codice == CODICE_BUSTA_CIFRATA:
        return str(messaggio or "").strip() or MOTIVI["source_processing_failed"]
    if codice == "source_validation_failed" and str(messaggio or "").strip():
        return f"{str(messaggio).strip().rstrip('.')}. Verificare il file e ricaricarlo."
    return MOTIVI.get(codice) or str(messaggio or "").strip() or MOTIVI["source_processing_failed"]


__all__ = ["MOTIVI", "motivo_per_avvocato"]
