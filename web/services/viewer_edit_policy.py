"""Nuove versioni dello studio e copie di condivisione delle prove esterne."""
from pathlib import Path

from pct.document_signature_state import document_has_real_digital_signature


def prodotto_dallo_studio(documento) -> bool:
    fonte = str(getattr(documento, "fonte_documento", "") or "").strip().upper()
    esterno = any(getattr(documento, campo, "") for campo in (
        "id_documento_portale", "id_cat_portale", "msg_id_portale", "mittente_portale",
    ))
    return not esterno and fonte in {"EDITOR_AI_LEX", "TEMPLATE_ATTI_COMPILATORE", "REDAZIONE_STUDIO"}


def motivo_sola_lettura(documento) -> str:
    if getattr(documento, "eliminato_il", ""):
        return "Documento rimosso dal fascicolo."
    from web.services.pdf_modificabile import modificabile_come_pdf
    if not modificabile_come_pdf(documento):
        return "Questo formato resta consultabile nel lettore e scaricabile."
    return ""


def nuova_versione_ammessa(documento) -> bool:
    return (prodotto_dallo_studio(documento)
            and not document_has_real_digital_signature(documento)
            and Path(str(getattr(documento, "nome", ""))).suffix.lower() == ".pdf")
