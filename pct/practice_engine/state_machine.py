"""State machine operativa separata dallo stato generale del fascicolo."""

from __future__ import annotations

from .models import DepositReceipt, PracticeState, ValidationResult


ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    PracticeState.PRE_FASCICOLO.value: {PracticeState.IN_ATTESA_PREVENTIVO.value, PracticeState.PREVENTIVO_INVIATO.value},
    PracticeState.IN_ATTESA_PREVENTIVO.value: {PracticeState.PREVENTIVO_INVIATO.value, PracticeState.PREVENTIVO_ACCETTATO.value},
    PracticeState.PREVENTIVO_INVIATO.value: {PracticeState.PREVENTIVO_ACCETTATO.value},
    PracticeState.PREVENTIVO_ACCETTATO.value: {PracticeState.INCARICO_DA_FIRMARE.value, PracticeState.IN_ATTESA_ACCONTO.value},
    PracticeState.INCARICO_DA_FIRMARE.value: {PracticeState.IN_ATTESA_ACCONTO.value, PracticeState.PRONTO_APERTURA_FASCICOLO.value},
    PracticeState.IN_ATTESA_ACCONTO.value: {PracticeState.PRONTO_APERTURA_FASCICOLO.value},
    PracticeState.PRONTO_APERTURA_FASCICOLO.value: {PracticeState.FASCICOLO_APERTO.value},
    PracticeState.FASCICOLO_APERTO.value: {PracticeState.DOCUMENTI_DA_COMPLETARE.value, PracticeState.ATTO_DA_REDIGERE.value, PracticeState.VALIDAZIONE_IN_CORSO.value},
    PracticeState.DOCUMENTI_DA_COMPLETARE.value: {PracticeState.ATTO_DA_REDIGERE.value, PracticeState.VALIDAZIONE_IN_CORSO.value, PracticeState.BLOCCATO_DA_ERRORI.value},
    PracticeState.ATTO_DA_REDIGERE.value: {PracticeState.ATTO_DA_FIRMARE.value, PracticeState.VALIDAZIONE_IN_CORSO.value},
    PracticeState.ATTO_DA_FIRMARE.value: {PracticeState.VALIDAZIONE_IN_CORSO.value},
    PracticeState.VALIDAZIONE_IN_CORSO.value: {PracticeState.BLOCCATO_DA_ERRORI.value, PracticeState.PRONTO_AL_DEPOSITO.value},
    PracticeState.BLOCCATO_DA_ERRORI.value: {PracticeState.DOCUMENTI_DA_COMPLETARE.value, PracticeState.VALIDAZIONE_IN_CORSO.value},
    PracticeState.PRONTO_AL_DEPOSITO.value: {PracticeState.DEPOSITO_IN_PREPARAZIONE.value},
    PracticeState.DEPOSITO_IN_PREPARAZIONE.value: {PracticeState.DEPOSITO_INVIATO.value, PracticeState.BLOCCATO_DA_ERRORI.value},
    PracticeState.DEPOSITO_INVIATO.value: {PracticeState.IN_ATTESA_RICEVUTE.value, PracticeState.ACCETTATO_PEC.value},
    PracticeState.IN_ATTESA_RICEVUTE.value: {PracticeState.ACCETTATO_PEC.value, PracticeState.CONSEGNATO.value, PracticeState.IN_ATTESA_CONTROLLI.value},
    PracticeState.ACCETTATO_PEC.value: {PracticeState.CONSEGNATO.value, PracticeState.IN_ATTESA_CONTROLLI.value},
    PracticeState.CONSEGNATO.value: {PracticeState.IN_ATTESA_CONTROLLI.value, PracticeState.CONTROLLI_OK.value, PracticeState.CONTROLLI_WARNING.value, PracticeState.CONTROLLI_ERRORE.value},
    PracticeState.IN_ATTESA_CONTROLLI.value: {PracticeState.CONTROLLI_OK.value, PracticeState.CONTROLLI_WARNING.value, PracticeState.CONTROLLI_ERRORE.value},
    PracticeState.CONTROLLI_OK.value: {PracticeState.IN_ATTESA_CANCELLERIA.value, PracticeState.ACCETTATO_DA_CANCELLERIA.value},
    PracticeState.CONTROLLI_WARNING.value: {PracticeState.IN_ATTESA_CANCELLERIA.value, PracticeState.DA_CORREGGERE.value},
    PracticeState.CONTROLLI_ERRORE.value: {PracticeState.DA_CORREGGERE.value},
    PracticeState.IN_ATTESA_CANCELLERIA.value: {PracticeState.ACCETTATO_DA_CANCELLERIA.value, PracticeState.RIFIUTATO_DA_CANCELLERIA.value},
    PracticeState.ACCETTATO_DA_CANCELLERIA.value: {PracticeState.ACQUISITO.value, PracticeState.FASE_SUCCESSIVA.value},
    PracticeState.RIFIUTATO_DA_CANCELLERIA.value: {PracticeState.DA_CORREGGERE.value},
    PracticeState.ACQUISITO.value: {PracticeState.FASE_SUCCESSIVA.value, PracticeState.DEFINITO.value},
    PracticeState.DA_CORREGGERE.value: {PracticeState.DOCUMENTI_DA_COMPLETARE.value, PracticeState.VALIDAZIONE_IN_CORSO.value},
    PracticeState.FASE_SUCCESSIVA.value: {PracticeState.DEFINITO.value, PracticeState.ARCHIVIATO.value},
    PracticeState.DEFINITO.value: {PracticeState.ARCHIVIATO.value},
}


def has_final_positive_receipt(channel: str, receipts: list[DepositReceipt]) -> bool:
    channel = str(channel or "").upper()
    expected = {
        "PCT_CIVILE": {"ESITO_CANCELLERIA"},
        "PCT_LAVORO": {"ESITO_CANCELLERIA"},
        "PST_GDP": {"ESITO_CANCELLERIA", "ESITO_SIGP"},
        "SIGP_GDP": {"ESITO_SIGP", "ESITO_PORTALE"},
        "PDP_PENALE": {"ESITO_PDP"},
        "PAT_AMMINISTRATIVO": {"ESITO_PAT"},
        "PTT_TRIBUTARIO": {"ESITO_PTT"},
        "PEC_ONLY": {"ESITO_PORTALE", "ALTRO"},
        "PEC": {"ESITO_PORTALE", "ALTRO"},
    }
    valid_types = expected.get(channel, {"ESITO_PORTALE"})
    return any(receipt.positive and receipt.receipt_type in valid_types for receipt in receipts)


def can_transition(
    current: str,
    target: str,
    *,
    channel: str = "",
    receipts: list[DepositReceipt] | None = None,
    validation_results: list[ValidationResult] | None = None,
) -> tuple[bool, str]:
    current = str(current or PracticeState.PRE_FASCICOLO.value)
    target = str(target or "")
    if target == PracticeState.ACQUISITO.value and not has_final_positive_receipt(channel, receipts or []):
        return False, "Deposito acquisito non consentito senza esito finale positivo del canale."
    if target == PracticeState.PRONTO_AL_DEPOSITO.value and any(item.blocking for item in validation_results or []):
        return False, "Pronto al deposito non consentito con blocchi aperti."
    allowed = ALLOWED_TRANSITIONS.get(current, set())
    if target in allowed or current == target:
        return True, "Transizione consentita."
    return False, f"Transizione operativa non consentita da {current} a {target}."


def derive_state(*, depositable: bool, validation_results: list[ValidationResult], slots_missing: bool, has_session: bool = False) -> str:
    if any(item.blocking for item in validation_results):
        return PracticeState.BLOCCATO_DA_ERRORI.value
    if slots_missing:
        return PracticeState.DOCUMENTI_DA_COMPLETARE.value
    if depositable:
        return PracticeState.PRONTO_AL_DEPOSITO.value
    if has_session:
        return PracticeState.FASE_SUCCESSIVA.value
    return PracticeState.FASCICOLO_APERTO.value
