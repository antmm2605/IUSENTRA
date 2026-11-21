"""L'esito del guardiano anello per anello, come lo legge l'avvocato: letture → termini → passi → economia → quadro.

Ogni codice di incoerenza del guardiano (``pct/catena/guardiano.py``) appartiene a uno dei cinque anelli che l'avvocato
vede nel fascicolo. Per ogni anello l'esito è:

- ``da_verificare``: c'è almeno un avviso aperto (il software non può ripararlo da solo, decide l'avvocato);
- ``riparato``: l'ultimo giro ha trovato un'incoerenza e l'ha riparata con la regola, registrando il motivo;
- ``in_aggiornamento``: le fonti del fascicolo sono cambiate dopo l'ultimo controllo;
- ``verificato``: l'ultimo controllo, sulle fonti attuali, non ha trovato nulla;
- ``non_controllato``: il guardiano non ha ancora controllato il fascicolo.

Base: art. 20 CAD (ogni riparazione resta registrata con il motivo, nulla si cancella).
"""

from __future__ import annotations

from typing import Any, Iterable

ANELLI_VISIBILI: tuple[tuple[str, str, str], ...] = (
    ("letture", "Letture", "documenti e PEC letti, catalogo e fatti"),
    ("termini", "Termini e udienze", "scadenziario e agenda allineati ai termini certi e alle udienze"),
    ("passi", "Prossimi passi", "passi da fare, adempimenti già provati e bozze"),
    ("economia", "Economia", "conto economico, crediti e incassi"),
    ("quadro", "Quadro", "quadro e stato del fascicolo coerenti con la Lettura"),
)

ANELLO_DEL_CODICE: dict[str, str] = {
    "catalogo_dopo_le_letture": "letture",
    "data_smentita_dal_testo": "termini",
    "modello_smentito_dal_testo": "termini",
    "due_date": "termini",
    "studio_senza_avvocati": "termini",
    "proposta_doppia": "termini",
    "norma_diversa": "termini",
    "termine_certo_in_bozza": "termini",
    "termine_certo_senza_scadenza": "termini",
    "scadenza_superata": "termini",
    "termine_della_controparte": "termini",
    "opposizione_e_udienza": "termini",
    "udienza_annullata_in_agenda": "termini",
    "udienza_non_in_agenda": "termini",
    "modalita_udienza_diversa": "termini",
    "passo_gia_fatto": "passi",
    "scadenza_di_adempimento_provato": "passi",
    "bozza_senza_passo": "passi",
    "in_corso_con_giudicato_e_incasso": "economia",
    "definito_con_udienza_futura": "quadro",
    "definito_senza_decisione": "quadro",
    "quadro_diverso_dalla_lettura": "quadro",
}

# «pannello_superato» appartiene all'anello del pannello superato.
ANELLO_DEL_PANNELLO: dict[str, str] = {
    "lettura": "letture", "letture": "letture", "passaggi": "passi", "conto-economico": "economia",
    "quadro": "quadro", "scadenze": "termini", "obblighi-notifica": "termini",
}

ETICHETTE = {
    "verificato": "verificato", "riparato": "riparato dal software", "da_verificare": "da verificare",
    "in_aggiornamento": "in aggiornamento", "non_controllato": "non ancora controllato",
}


def anello_di(voce: dict[str, Any]) -> str:
    """L'anello visibile di un'incoerenza registrata (codice e dati del registro del guardiano)."""
    codice = str(voce.get("codice") or "")
    if codice == "pannello_superato":
        return ANELLO_DEL_PANNELLO.get(str((voce.get("dati") or {}).get("pannello") or ""), "quadro")
    return ANELLO_DEL_CODICE.get(codice, "quadro")


def esito_anelli(*, stato: str, avvisi: Iterable[dict[str, Any]], riparate: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """I cinque anelli con l'esito e quante voci li riguardano. ``stato`` è quello di ``payload_fascicolo``."""
    per_anello: dict[str, dict[str, int]] = {codice: {"avvisi": 0, "riparate": 0} for codice, _n, _d in ANELLI_VISIBILI}
    for voce in avvisi:
        per_anello[anello_di(voce)]["avvisi"] += 1
    for voce in riparate:
        per_anello[anello_di(voce)]["riparate"] += 1
    esito = []
    for codice, nome, descrizione in ANELLI_VISIBILI:
        conteggi = per_anello[codice]
        if conteggi["avvisi"]:
            valore = "da_verificare"
        elif stato == "mai_controllato" or stato == "non_disponibile":
            valore = "non_controllato"
        elif stato == "in_aggiornamento":
            valore = "in_aggiornamento"
        elif conteggi["riparate"]:
            valore = "riparato"
        else:
            valore = "verificato"
        esito.append({"codice": codice, "nome": nome, "descrizione": descrizione, "esito": valore,
                      "etichetta": ETICHETTE[valore], **conteggi})
    return esito


__all__ = ["ANELLI_VISIBILI", "ANELLO_DEL_CODICE", "anello_di", "esito_anelli"]
