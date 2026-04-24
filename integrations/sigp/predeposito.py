"""Controlli di predeposito per il modulo SIGP."""

from __future__ import annotations


def check_sigp_predeposito(data: dict) -> dict:
    errors: list[str] = []
    warnings: list[str] = []

    if not str(data.get("ufficio") or "").strip():
        errors.append("Ufficio Giudice di Pace mancante.")
    if not str(data.get("procedimento") or "").strip():
        errors.append("Tipo procedimento mancante.")
    if not str(data.get("tipo_atto") or "").strip():
        errors.append("Tipo atto mancante.")

    difensore = data.get("difensore") or {}
    if not str(difensore.get("codice_fiscale") or "").strip():
        errors.append("Codice fiscale del difensore mancante.")
    if not str(difensore.get("pec") or "").strip():
        warnings.append("PEC del difensore non indicata.")

    parti = data.get("parti") or []
    if not parti:
        errors.append("Almeno una parte deve essere indicata.")

    allegati = data.get("allegati") or []
    if not allegati:
        warnings.append("Nessun allegato presente.")

    for allegato in allegati:
        nome = str(allegato.get("nome") or "allegato")
        size = int(allegato.get("dimensione_bytes") or 0)
        if size <= 0:
            errors.append(f"{nome}: dimensione file non valida.")
        if allegato.get("richiede_pdfa") and not allegato.get("pdfa_ok"):
            errors.append(f"{nome}: file non conforme PDF/A.")
        if allegato.get("richiede_firma") and not allegato.get("firmato"):
            errors.append(f"{nome}: firma digitale mancante.")

    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
    }
