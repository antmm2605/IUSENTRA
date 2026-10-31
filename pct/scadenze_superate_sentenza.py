"""Scadenze procedurali già passate quando arriva la sentenza: avviso all'avvocato, mai chiusura automatica.

Verifica del 31/10/2026 (RG 2848/2026): il termine per le note del 09/10/2026 restava «aperto» dopo
la sentenza del 12/10/2026. Con la sentenza il giudizio di primo grado si chiude (art. 133 c.p.c.):
le attività procedurali di quel grado ancora aperte e già scadute sono con ogni probabilità superate,
ma se l'adempimento sia stato fatto lo sa solo l'avvocato. Per questo il software aggiunge un avviso
e non chiude nulla (regola delle fonti certe, AGENTS.md).

Restano fuori: impugnazioni, notifiche, pagamenti, prescrizioni e decadenze, che dopo la sentenza
restano attuali o nascono proprio da essa.
"""

from __future__ import annotations

from typing import Any

MARCATORE = "SUPERATA_DA_SENTENZA"
TIPI_PROCEDURALI = {
    "UDIENZA", "DEPOSITO_MEMORIA", "DEPOSITO_ATTO", "RISPOSTA_ECCEZIONE", "ADEMPIMENTO",
    "TERMINE_PERENTORIO", "TERMINE_ORDINATORIO", "ALTRO",
}
_PAROLE_ESCLUSE = ("impugnaz", "appello", "cassazione", "notific", "pagament", "contributo", "prescrizion", "decadenz")


def _valore(oggetto: Any, nome: str) -> str:
    valore = getattr(oggetto, nome, "")
    return str(getattr(valore, "value", valore) or "")


def da_segnalare(scadenza: Any, *, fascicolo_id: str, giorno_sentenza: str) -> bool:
    """Scadenza aperta del fascicolo, procedurale, già passata alla data della sentenza e non ancora segnalata."""
    if _valore(scadenza, "id_fascicolo") != fascicolo_id or _valore(scadenza, "stato") != "APERTO":
        return False
    if _valore(scadenza, "tipo") not in TIPI_PROCEDURALI or MARCATORE in _valore(scadenza, "note"):
        return False
    titolo = f"{_valore(scadenza, 'titolo')} {_valore(scadenza, 'descrizione')}".casefold()
    if any(parola in titolo for parola in _PAROLE_ESCLUSE):
        return False
    giorno = _valore(scadenza, "data_scadenza")[:10]
    return bool(giorno) and giorno < giorno_sentenza[:10]


def segnala_scadenze_superate(scadenziario: Any, *, fascicolo_id: str, giorno_sentenza: str, origine: str) -> int:
    """Aggiunge l'avviso alle scadenze probabilmente superate dalla sentenza; restituisce quante."""
    if not fascicolo_id or not giorno_sentenza:
        return 0
    giorno_it = f"{giorno_sentenza[8:10]}/{giorno_sentenza[5:7]}/{giorno_sentenza[:4]}"
    segnalate = 0
    for scadenza in list(scadenziario.tutte(solo_aperte=True, id_fascicolo=fascicolo_id)):
        if not da_segnalare(scadenza, fascicolo_id=fascicolo_id, giorno_sentenza=giorno_sentenza):
            continue
        avviso = (f"Possibile scadenza superata dalla sentenza del {giorno_it} ({origine}): verificare se "
                  "l'adempimento è stato fatto e chiudere la scadenza.")
        scadenziario.aggiorna(
            _valore(scadenza, "id"),
            descrizione=f"{avviso}\n{_valore(scadenza, 'descrizione')}".strip(),
            note=f"{_valore(scadenza, 'note')}\n{MARCATORE}:{giorno_sentenza[:10]}".strip(),
        )
        segnalate += 1
    return segnalate


__all__ = ["MARCATORE", "TIPI_PROCEDURALI", "da_segnalare", "segnala_scadenze_superate"]
