"""Collega la sentenza alle attività della trattazione già decorse.

Il riscontro storico conserva la scadenza e la prova della decisione. Può servire
per ricostruire l'adempimento, il verbale o un motivo di impugnazione.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any
from urllib.parse import quote

MARCATORE = "SUPERATA_DA_SENTENZA"
_MARCATORE_CONCLUSIVA = f"{MARCATORE}:DEFINITIVA:"
_FORMULA_CONCLUSIVA = re.compile(r"\bdefinitivamente\s+(?:pronunciando|decidendo)\b", re.I)
TIPI_PROCEDURALI = {
    "UDIENZA", "DEPOSITO_MEMORIA", "DEPOSITO_ATTO", "RISPOSTA_ECCEZIONE", "ADEMPIMENTO",
    "TERMINE_PERENTORIO", "TERMINE_ORDINATORIO", "ALTRO",
}
_PAROLE_ESCLUSE = ("impugnaz", "appello", "cassazione", "notific", "pagament", "contributo", "prescrizion", "decadenz")


def _valore(oggetto: Any, nome: str) -> str:
    valore = oggetto.get(nome, "") if isinstance(oggetto, dict) else getattr(oggetto, nome, "")
    return str(getattr(valore, "value", valore) or "")


def dispositivo_conclusivo(brano: str) -> bool:
    """Il dispositivo dichiara che il giudice decide in via definitiva."""
    return bool(_FORMULA_CONCLUSIVA.search(brano))


def decisione_superante(scadenza: Any, *, al_giorno: date | None = None) -> tuple[str, str] | None:
    """Data della decisione conclusiva e ID della fonte, quando associati alla scadenza."""
    if al_giorno is None:
        from pct.ora_italiana import oggi_roma

        al_giorno = oggi_roma()
    for riga in _valore(scadenza, "note").splitlines():
        if not riga.startswith(_MARCATORE_CONCLUSIVA):
            continue
        giorno, _, documento = riga[len(_MARCATORE_CONCLUSIVA):].partition(":")
        try:
            giorno = date.fromisoformat(giorno).isoformat()
        except ValueError:
            continue
        scadenza_letta = (_valore(scadenza, "data_scadenza") or _valore(scadenza, "data"))[:10]
        if documento and scadenza_letta and scadenza_letta < giorno <= al_giorno.isoformat():
            return giorno, documento
    return None


def riscontro_storico(fascicolo_id: str, decisione: tuple[str, str]) -> tuple[str, str]:
    giorno, documento = decisione
    href = f"/fascicoli/{quote(fascicolo_id, safe='')}/documenti/{quote(documento, safe='')}/visualizza"
    motivo = (f"Trattazione conclusa dalla sentenza del {date.fromisoformat(giorno):%d/%m/%Y}. "
              "Consulta gli atti e le ricevute del termine nello storico del fascicolo.")
    return motivo, href


def da_segnalare(scadenza: Any, *, fascicolo_id: str, giorno_sentenza: str, conclusiva: bool = False) -> bool:
    """Valuta le scadenze procedurali del fascicolo già passate alla decisione."""
    from pct.scadenze_stato import ESITO_UDIENZA, stato_operativo, termine_note_in_sostituzione

    if _valore(scadenza, "id_fascicolo") != fascicolo_id or _valore(scadenza, "stato") != "APERTO":
        return False
    if _valore(scadenza, "tipo") not in TIPI_PROCEDURALI:
        return False
    if conclusiva and decisione_superante(scadenza) is not None:
        return False
    if not conclusiva and MARCATORE in _valore(scadenza, "note"):
        return False
    try:
        decisione = date.fromisoformat(giorno_sentenza[:10])
        giorno = date.fromisoformat(_valore(scadenza, "data_scadenza")[:10])
    except ValueError:
        return False
    if giorno >= decisione:
        return False
    if termine_note_in_sostituzione(scadenza):
        return True
    if conclusiva:
        return stato_operativo(scadenza, decisione) == ESITO_UDIENZA
    titolo = f"{_valore(scadenza, 'titolo')} {_valore(scadenza, 'descrizione')}".casefold()
    return not any(parola in titolo for parola in _PAROLE_ESCLUSE)


def segnala_scadenze_superate(
    scadenziario: Any, *, fascicolo_id: str, giorno_sentenza: str, origine: str, documento_conclusivo: str = "",
) -> int:
    """Aggiunge l'avviso alle scadenze probabilmente superate dalla sentenza; restituisce quante."""
    if not fascicolo_id or not giorno_sentenza:
        return 0
    giorno_it = f"{giorno_sentenza[8:10]}/{giorno_sentenza[5:7]}/{giorno_sentenza[:4]}"
    segnalate = 0
    for scadenza in list(scadenziario.tutte(solo_aperte=True, id_fascicolo=fascicolo_id)):
        if not da_segnalare(
            scadenza, fascicolo_id=fascicolo_id, giorno_sentenza=giorno_sentenza, conclusiva=bool(documento_conclusivo),
        ):
            continue
        avviso = (f"Possibile scadenza superata dalla sentenza del {giorno_it} ({origine}): verificare se "
                  "l'adempimento è stato fatto e chiudere la scadenza.")
        marcatore = f"{MARCATORE}:{giorno_sentenza[:10]}"
        if documento_conclusivo:
            avviso = (f"Trattazione conclusa dalla sentenza del {giorno_it} ({origine}). "
                      "Il termine resta nello storico per riscontrare l'adempimento.")
            marcatore = f"{_MARCATORE_CONCLUSIVA}{giorno_sentenza[:10]}:{documento_conclusivo}"
        scadenziario.aggiorna(
            _valore(scadenza, "id"),
            descrizione=f"{avviso}\n{_valore(scadenza, 'descrizione')}".strip(),
            note=f"{_valore(scadenza, 'note')}\n{marcatore}".strip(),
        )
        segnalate += 1
    return segnalate


__all__ = ["MARCATORE", "TIPI_PROCEDURALI", "da_segnalare", "decisione_superante", "dispositivo_conclusivo", "riscontro_storico", "segnala_scadenze_superate"]
