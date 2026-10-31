"""Scadenze che nascono dall'udienza e la seguono quando viene rinviata.

Nel rito ordinario di cognizione riformato (D.Lgs. 149/2022) le tre memorie integrative
si depositano a ritroso dalla prima udienza di comparizione e trattazione (art. 171-ter
c.p.c.: almeno 40, 20 e 10 giorni prima). Quando l'udienza è in agenda il software le
propone come bozze da confermare; quando l'udienza viene spostata, le memorie collegate
si ricalcolano dalla nuova data, salvo quelle che l'avvocato ha già cambiato a mano.

Il calcolo è quello dei preset dello scadenziario (`memoria_ex_171_ter_n1/2/3`, verso a
ritroso, art. 155 c.p.c. applicato a ritroso). Si propongono solo i termini ancora futuri.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any, Iterable

MEMORIE_171_TER = ("memoria_ex_171_ter_n1", "memoria_ex_171_ter_n2", "memoria_ex_171_ter_n3")
_PRIMA_UDIENZA = re.compile(
    r"\bprima\s+udienza\b|\budienza\s+di\s+(?:prima\s+)?comparizione\b|\bart\.?\s*183\b|\b171-?ter\b", re.IGNORECASE
)
_MARCATORE = "UDIENZA_DERIVATA:{appuntamento}:{preset}"
_CALCOLATA = re.compile(r"UDIENZA_DERIVATA:\S+ calcolata=(\d{4}-\d{2}-\d{2}) udienza=(\d{4}-\d{2}-\d{2})")
_TIPI_ESCLUSI = {"LAVORO", "PENALE", "AMMINISTRATIVO", "TRIBUTARIO", "STRAGIUDIZIALE", "CONSULENZA"}


def _valore(oggetto: Any, nome: str) -> str:
    valore = getattr(oggetto, nome, "")
    return str(getattr(valore, "value", valore) or "")


def e_prima_udienza_di_cognizione(appuntamento: Any, fascicolo: Any) -> bool:
    """Udienza di prima comparizione del rito ordinario: tipo UDIENZA, fascicolo civile, testo che la qualifica."""
    if _valore(appuntamento, "tipo") != "UDIENZA" or _valore(appuntamento, "stato") in {"COMPLETATO", "ANNULLATO"}:
        return False
    if _valore(fascicolo, "tipo") in _TIPI_ESCLUSI:
        return False
    testo = " ".join(_valore(appuntamento, campo) for campo in ("titolo", "note", "procedimento"))
    return bool(_PRIMA_UDIENZA.search(testo))


def _giorno_udienza(appuntamento: Any) -> date | None:
    try:
        return date.fromisoformat(_valore(appuntamento, "data_ora")[:10])
    except ValueError:
        return None


def _marcatore(appuntamento: Any, preset: str) -> str:
    return _MARCATORE.format(appuntamento=_valore(appuntamento, "id"), preset=preset)


def _collegate(scadenze: Iterable[Any], appuntamento: Any) -> dict[str, Any]:
    trovate: dict[str, Any] = {}
    for scadenza in scadenze:
        note = _valore(scadenza, "note")
        for preset in MEMORIE_171_TER:
            if _marcatore(appuntamento, preset) in note:
                trovate[preset] = scadenza
    return trovate


def allinea_scadenze_udienza(appuntamento: Any, fascicolo: Any, scadenziario: Any, *, oggi: date) -> dict[str, int]:
    """Propone le memorie 171-ter mancanti e ricalcola quelle collegate se l'udienza è stata spostata."""
    esito = {"proposte": 0, "ricalcolate": 0, "da_verificare": 0}
    udienza = _giorno_udienza(appuntamento)
    if udienza is None or not e_prima_udienza_di_cognizione(appuntamento, fascicolo):
        return esito
    collegate = _collegate(scadenziario.tutte(solo_aperte=False, id_fascicolo=_valore(fascicolo, "id")), appuntamento)
    for preset in MEMORIE_171_TER:
        scadenza = collegate.get(preset)
        if scadenza is None:
            esito["proposte"] += _proponi(preset, appuntamento, fascicolo, scadenziario, udienza, oggi)
            continue
        esito_riga = _riallinea(scadenza, preset, appuntamento, scadenziario, udienza)
        if esito_riga:
            esito[esito_riga] += 1
    return esito


def _proponi(preset: str, appuntamento: Any, fascicolo: Any, scadenziario: Any, udienza: date, oggi: date) -> int:
    from pct.scadenziario import StatoTermine

    numero = preset[-1]
    scadenza = scadenziario.nuova_da_preset(
        preset, f"Memoria integrativa n. {numero} ex art. 171-ter c.p.c.", udienza.isoformat(),
        id_fascicolo=_valore(fascicolo, "id"), id_appuntamento=_valore(appuntamento, "id"),
    )
    if scadenza.data_scadenza < oggi.isoformat():
        scadenziario.elimina(scadenza.id)
        return 0
    scadenziario.aggiorna(
        scadenza.id, stato=StatoTermine.BOZZA.value,
        note=(f"{_marcatore(appuntamento, preset)} calcolata={scadenza.data_scadenza} udienza={udienza.isoformat()}\n"
              "Proposta dalla prima udienza in agenda: da confermare (art. 171-ter c.p.c.)."),
    )
    return 1


def _riallinea(scadenza: Any, preset: str, appuntamento: Any, scadenziario: Any, udienza: date) -> str:
    if _valore(scadenza, "stato") in {"COMPLETATO", "ANNULLATO"}:
        return ""
    trovato = _CALCOLATA.search(_valore(scadenza, "note"))
    if trovato is None or trovato.group(2) == udienza.isoformat():
        return ""
    calcolata, udienza_precedente = trovato.groups()
    if _valore(scadenza, "data_scadenza") != calcolata:
        nota = (f"Udienza spostata dal {udienza_precedente} al {udienza.isoformat()}: la data era stata cambiata "
                "a mano, verificare il termine.")
        if nota not in _valore(scadenza, "note"):
            scadenziario.aggiorna(scadenza.id, note=f"{_valore(scadenza, 'note')}\n{nota}".strip())
            return "da_verificare"
        return ""
    nuova = scadenziario.calcola_avanzata(start_at=udienza, profile=_profilo(preset))
    giorno = nuova.legal_due_at[:10]
    note = _valore(scadenza, "note").replace(trovato.group(0), f"{_marcatore(appuntamento, preset)} calcolata={giorno} "
                                                               f"udienza={udienza.isoformat()}")
    scadenziario.aggiorna(scadenza.id, data_scadenza=giorno, legal_due_at=nuova.legal_due_at,
                          raw_due_at=nuova.raw_due_at, data_decorrenza=udienza.isoformat(),
                          source_event_at=udienza.isoformat(),
                          note=f"{note}\nRicalcolata per il rinvio dell'udienza dal {udienza_precedente}.")
    return "ricalcolate"


def _profilo(preset: str) -> Any:
    from pct.scadenziario import profilo_da_preset

    return profilo_da_preset(preset)


def allinea_udienze(
    appuntamenti: Iterable[Any], scadenziario: Any, tipi_fascicolo: dict[str, str], *, oggi: date,
) -> dict[str, int]:
    """Giro periodico: allinea le memorie di ogni prima udienza futura collegata a un fascicolo."""
    totale = {"proposte": 0, "ricalcolate": 0, "da_verificare": 0}
    for appuntamento in appuntamenti:
        fascicolo_id = _valore(appuntamento, "id_fascicolo")
        udienza = _giorno_udienza(appuntamento)
        if not fascicolo_id or udienza is None or udienza < oggi:
            continue
        fascicolo = type("Fascicolo", (), {"id": fascicolo_id, "tipo": tipi_fascicolo.get(fascicolo_id, "")})()
        for chiave, numero in allinea_scadenze_udienza(appuntamento, fascicolo, scadenziario, oggi=oggi).items():
            totale[chiave] += numero
    return totale


__all__ = ["MEMORIE_171_TER", "allinea_scadenze_udienza", "allinea_udienze", "e_prima_udienza_di_cognizione"]
