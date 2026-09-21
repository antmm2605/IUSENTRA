"""Regola condivisa per la modifica dei documenti dello studio."""
from pathlib import Path
from pct.document_signature_state import document_has_real_digital_signature

def pdf_studio_modificabile(documento):
    if Path(str(getattr(documento, "nome", ""))).suffix.lower() != ".pdf":
        return False
    return (
        str(getattr(documento, "fonte_documento", "")).strip().upper() == "CARICAMENTO_STUDIO"
        and not document_has_real_digital_signature(documento)
        and not any(str(getattr(documento, k, "") or "").strip() for k in
                    ("id_documento_portale", "id_cat_portale", "id_repeatto_portale", "msg_id_portale"))
    )

def motivo_blocco_editor(documento):
    if document_has_real_digital_signature(documento):
        return "Il documento firmato resta in sola consultazione."
    if Path(str(getattr(documento, "nome", ""))).suffix.lower() == ".pdf" and not pdf_studio_modificabile(documento):
        return "Puoi modificare soltanto i PDF caricati dallo studio. I documenti acquisiti da portali o altre sorgenti restano in sola consultazione."
    return ""
