"""Stato operativo di una scadenza: una sola regola per scadenziario, viste e barra in alto.

Verifica del 31/10/2026 (V28): le «scadute da chiudere» erano quasi tutte udienze già
passate, e tre conteggi diversi (scadenziario, viste, barra in alto) davano numeri
diversi. Un'udienza non è un adempimento che scade: è un evento che si è tenuto (o è
stato rinviato) e di cui va registrato l'esito dal verbale o dal provvedimento
successivo (artt. 126 e 127-ter c.p.c.). Per questo un'udienza passata e ancora
aperta è «esito da registrare», non «scaduta»; gli adempimenti passati restano
«scaduti da chiudere». Nessuna voce si chiude da sola: decide l'avvocato.

Il giorno di riferimento è quello di Roma (``pct.ora_italiana.oggi_roma``).
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import Any

BOZZA = "bozza"
ANNULLATA = "annullata"
COMPLETATA = "completata"
APERTA = "aperta"
SCADUTA = "scaduta"
ESITO_UDIENZA = "esito_udienza"
STORICA = "storica"
MARCATORE_FONTE_ESTRANEA = "RETTIFICA_FONTE_ALTRO_RUOLO"


def _valore(oggetto: Any, nome: str) -> str:
    valore = oggetto.get(nome, "") if isinstance(oggetto, Mapping) else getattr(oggetto, nome, "")
    return str(getattr(valore, "value", valore) or "")


def annullata_per_fonte_estranea(scadenza: Any) -> bool:
    """Distingue la rettifica della fonte da una proposta scartata dall'avvocato."""
    return _valore(scadenza, "stato").upper() == "ANNULLATO" and any(
        riga.startswith(f"{MARCATORE_FONTE_ESTRANEA}:") for riga in _valore(scadenza, "note").splitlines()
    )


def _giorno(scadenza: Any) -> date | None:
    calendario = getattr(scadenza, "data_calendario_obj", None)
    if isinstance(calendario, date):
        return calendario
    valore = _valore(scadenza, "data_scadenza") or _valore(scadenza, "data")
    try:
        return date.fromisoformat(valore[:10])
    except ValueError:
        from pct.formatting import parse_datetime_rome

        data = parse_datetime_rome(valore)
        return data.date() if data else None


def data_termine_corrente(scadenza: Any) -> str:
    """Data dello scadenziario, con l'orario legale se appartiene alla stessa data."""
    corrente = _valore(scadenza, "data_scadenza").strip()
    data_calcolata = _valore(scadenza, "legal_due_at").strip()
    if not corrente or (len(data_calcolata) > 10 and data_calcolata[:10] == corrente):
        return data_calcolata
    return corrente


def termine_note_in_sostituzione(scadenza: Any) -> bool:
    """Riconosce anche le registrazioni storiche del termine di deposito come UDIENZA."""
    from pct.note_127_ter.comunicazione import e_termine_note_127_ter
    from pct.note_127_ter.proposta import CODICE_NOTE_127_TER, MODALITA_NOTE_SCRITTE, TITOLO_NOTE_127_TER

    titolo = _valore(scadenza, "titolo")
    if _valore(scadenza, "deadline_profile_code").upper() == CODICE_NOTE_127_TER or titolo.startswith(TITOLO_NOTE_127_TER):
        return True
    return (_valore(scadenza, "hearing_mode").lower() == MODALITA_NOTE_SCRITTE
            and e_termine_note_127_ter(titolo))


def termine_perentorio(scadenza: Any) -> bool:
    return (bool(getattr(scadenza, "perentorio", False))
            or _valore(scadenza, "tipo").upper() == "TERMINE_PERENTORIO"
            or termine_note_in_sostituzione(scadenza))


def stato_operativo(scadenza: Any, oggi: date | None = None) -> str:
    stato = _valore(scadenza, "stato").upper()
    if stato == "BOZZA":
        return BOZZA
    if stato == "ANNULLATO":
        return ANNULLATA
    if stato == "COMPLETATO":
        return COMPLETATA
    if oggi is None:
        from pct.ora_italiana import oggi_roma

        oggi = oggi_roma()
    from pct.scadenze_superate_sentenza import decisione_superante

    if decisione_superante(scadenza, al_giorno=oggi):
        return STORICA
    giorno = _giorno(scadenza)
    passata = stato == "SCADUTO" or bool(giorno and giorno < oggi)
    if not passata:
        return APERTA
    if _valore(scadenza, "tipo").upper() == "UDIENZA" and not termine_note_in_sostituzione(scadenza):
        return ESITO_UDIENZA
    return SCADUTA


def scaduta_da_chiudere(scadenza: Any, oggi: date | None = None) -> bool:
    return stato_operativo(scadenza, oggi) == SCADUTA


def esito_udienza_da_registrare(scadenza: Any, oggi: date | None = None) -> bool:
    return stato_operativo(scadenza, oggi) == ESITO_UDIENZA


def aperta(scadenza: Any, oggi: date | None = None) -> bool:
    return stato_operativo(scadenza, oggi) == APERTA


__all__ = [
    "ANNULLATA", "APERTA", "BOZZA", "COMPLETATA", "ESITO_UDIENZA", "SCADUTA", "STORICA",
    "aperta", "esito_udienza_da_registrare", "scaduta_da_chiudere", "stato_operativo",
    "data_termine_corrente", "termine_note_in_sostituzione", "termine_perentorio",
]
