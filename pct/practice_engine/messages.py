"""Messaggi utente della Regia Operativa.

Formato: problema breve e azione consigliata, sempre in italiano.
"""

from __future__ import annotations


def problem_action(problem: str, action: str) -> str:
    problem = str(problem or "").strip().rstrip(".")
    action = str(action or "").strip().rstrip(".")
    if problem and action:
        return f"{problem}. {action}."
    return f"{problem or action}."


MISSING_PROCURA = problem_action(
    "Impossibile depositare: manca la Procura alle liti",
    "Carica una procura firmata oppure generala dal modello",
)
MISSING_MAIN_ACT = problem_action(
    "Impossibile depositare: manca l'atto principale",
    "Carica o genera l'atto principale prima del predeposito",
)
MAIN_ACT_NOT_PDFA = problem_action(
    "Impossibile depositare: l'atto principale non e' in formato PDF/A",
    "Converti il documento e ripeti la verifica",
)
MAIN_ACT_NOT_SIGNED = problem_action(
    "Impossibile depositare: l'atto principale non e' firmato digitalmente",
    "Firma il documento prima del deposito",
)
CU_RECEIPT_MISSING = problem_action(
    "Attenzione: il Contributo Unificato risulta pagato, ma manca la ricevuta allegata",
    "Collega la ricevuta allo slot documentale",
)
DEPOSIT_SENT_NOT_ACQUIRED = problem_action(
    "Deposito inviato, ma non ancora acquisito",
    "Sono presenti accettazione e consegna PEC; manca l'esito della cancelleria",
)
DEPOSIT_ACQUIRED = problem_action(
    "Deposito acquisito correttamente",
    "Tutte le ricevute risultano presenti e collegate al fascicolo",
)
NO_REAL_TRANSPORT = problem_action(
    "Invio reale non disponibile: canale o credenziali non configurati",
    "Configura il connettore autorizzato oppure importa una ricevuta ufficiale acquisita dal portale",
)
SIMULATED_BUSTA = problem_action(
    "La busta disponibile e' una simulazione tecnica",
    "Non puo' essere dichiarata busta ministeriale reale senza trasporto configurato",
)
