"""Regola condivisa per la modifica dei documenti dello studio."""
from pathlib import Path
from pct.document_signature_state import document_has_real_digital_signature


#: Le provenienze che valgono come "caricato dallo studio". La stringa vuota
#: non c'e' piu': un documento senza provenienza registrata e' un documento di
#: cui non sappiamo la storia, e su una regola che protegge la prova il valore
#: di partenza dev'essere chiuso, non aperto. Prima passava per roba dello
#: studio qualunque documento a cui nessuno avesse valorizzato il campo.
_PDF_FONTI_STUDIO_MODIFICABILI = {
    "CARICAMENTO_STUDIO",
    "APERTURA_FASCICOLO_VELOCE",
    "COPIA_RUOTATA_DA_LETTORE",
    "EDITOR_AI_LEX",
    "TEMPLATE_ATTI_COMPILATORE",
}


def pdf_studio_modificabile(documento):
    if document_has_real_digital_signature(documento):
        return False
    if Path(str(getattr(documento, "nome", ""))).suffix.lower() != ".pdf":
        return False
    fonte = str(getattr(documento, "fonte_documento", "") or "").strip().upper()
    return fonte in _PDF_FONTI_STUDIO_MODIFICABILI


def motivo_blocco_editor(documento):
    if document_has_real_digital_signature(documento):
        return "Il documento firmato resta in sola consultazione."
    if Path(str(getattr(documento, "nome", ""))).suffix.lower() == ".pdf":
        if pdf_studio_modificabile(documento):
            return (
                "Il PDF resta in anteprima nativa per conservare impaginazione, "
                "font, immagini, timbri e spaziature. Usa Modifica PDF sicura "
                "per aggiungere testo, evidenziazioni o coperture come overlay "
                "e salvare una nuova versione senza conversione HTML."
            )
        if not str(getattr(documento, "fonte_documento", "") or "").strip():
            return (
                "Questo PDF non ha una provenienza registrata, quindi resta in "
                "sola consultazione: la modifica e' riservata ai documenti che "
                "risultano caricati dallo studio."
            )
        return (
            "Puoi modificare soltanto i PDF caricati dallo studio. I documenti "
            "acquisiti da portali, PEC, notifiche o altre sorgenti restano in "
            "sola consultazione per preservare la prova originale."
        )
    return ""
