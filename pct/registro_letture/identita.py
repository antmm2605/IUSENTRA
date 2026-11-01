"""Identità canonica del fascicolo per la riga di sintesi del registro delle letture.

Un solo modo di dire chi è il cliente, che pratica è, davanti a quale ufficio, in che stato e con quali date,
così che elenco, panoramica, pannelli e motori di lettura non ricavino valori diversi da campi diversi
(verifica del 01/11/2026: «definito» contro «Aperto», prossima udienza già trascorsa, 90 documenti contro 78).

Regole:
- ``prossima_udienza`` è solo una data futura (dal fascicolo o dalle udienze registrate tra le attività);
- ``data_definizione`` è la data di chiusura di un fascicolo definito; per un fascicolo archiviato vale solo se
  è diversa dalla data di archiviazione, che resta a parte;
- ``documenti_presenti`` sono i file presenti nel fascicolo, non la fotografia del portale.

Base normativa: art. 3 D.M. 44/2011 e art. 20 CAD (identità e integrità dei documenti informatici del fascicolo).
"""

from __future__ import annotations

from datetime import date
from typing import Any


def _testo(valore: Any) -> str:
    if valore is None:
        return ""
    grezzo = getattr(valore, "value", valore)
    return str(grezzo).strip()


def _giorno(valore: Any) -> date | None:
    testo = _testo(valore)[:10]
    try:
        return date.fromisoformat(testo)
    except ValueError:
        return None


def prossima_udienza(fascicolo: Any, *, oggi: date) -> str:
    """La prima udienza da oggi in poi; vuota se non ce ne sono (una data passata non è «prossima»)."""
    candidati: list[date] = []
    diretta = _giorno(getattr(fascicolo, "data_prossima_udienza", ""))
    if diretta is not None:
        candidati.append(diretta)
    for attivita in list(getattr(fascicolo, "attivita", []) or []):
        etichetta = f"{_testo(getattr(attivita, 'tipo', ''))} {_testo(getattr(attivita, 'titolo', ''))}".upper()
        if "UDIENZA" not in etichetta:
            continue
        giorno = _giorno(getattr(attivita, "data", ""))
        if giorno is not None:
            candidati.append(giorno)
    future = sorted(g for g in candidati if g >= oggi)
    return future[0].isoformat() if future else ""


def date_di_chiusura(fascicolo: Any) -> tuple[str, str]:
    """(data_definizione, data_archiviazione) senza confondere le due."""
    stato = _testo(getattr(fascicolo, "stato", "")).upper()
    chiusura = _testo(getattr(fascicolo, "data_chiusura", ""))[:10]
    archivio = getattr(fascicolo, "archivio", None)
    archiviazione = _testo(getattr(archivio, "data_archiviazione", "") if archivio is not None else "")[:10]
    definizione = _testo(getattr(fascicolo, "data_definizione", ""))[:10]
    if not definizione and stato == "DEFINITO":
        definizione = chiusura
    if stato == "ARCHIVIATO":
        if not archiviazione:
            archiviazione = chiusura
        elif not definizione and chiusura and chiusura != archiviazione:
            definizione = chiusura
    return definizione, archiviazione


def identita_fascicolo(fascicolo: Any, *, oggi: date) -> dict[str, Any]:
    definizione, archiviazione = date_di_chiusura(fascicolo)
    return {
        "id_cliente": _testo(getattr(fascicolo, "id_cliente", "")),
        "cliente": _testo(getattr(fascicolo, "nome_cliente", "")),
        "tipo_pratica": _testo(getattr(fascicolo, "tipo", "")).upper(),
        "ufficio": _testo(getattr(fascicolo, "tribunale", "")),
        "numero_rg": _testo(getattr(fascicolo, "numero_rg", "")),
        "anno_rg": _testo(getattr(fascicolo, "anno_rg", "")),
        "stato": _testo(getattr(fascicolo, "stato", "")).upper(),
        "data_apertura": _testo(getattr(fascicolo, "data_apertura", ""))[:10],
        "data_definizione": definizione,
        "data_archiviazione": archiviazione,
        "prossima_udienza": prossima_udienza(fascicolo, oggi=oggi),
    }


__all__ = ["date_di_chiusura", "identita_fascicolo", "prossima_udienza"]
