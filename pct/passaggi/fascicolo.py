"""I passaggi del software su un fascicolo: raccoglie i produttori registrati, in ordine.

Funzione pura sui dati già serializzati del fascicolo (come la Lettura): il
contesto (ufficio, giudice, materia) nasce qui una volta sola e vale per
tutti i produttori, così le regole dello studio si confrontano sugli stessi
valori. Per aggiungere un produttore: un adattatore in ``produttori/`` e una
riga in ``passaggi_del_fascicolo``.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Iterable

from .modello import Contesto, Passaggio
from .produttori import passaggi_da_scadenza, passaggi_termini_pec


def contesto_del_fascicolo(fascicolo: dict[str, Any]) -> Contesto:
    materia = str(fascicolo.get("area_pratica") or fascicolo.get("tipo") or "").replace("_", " ").strip().lower()
    return Contesto(
        fascicolo_id=str(fascicolo.get("id") or "").strip(),
        ufficio=str(fascicolo.get("tribunale") or fascicolo.get("ufficio") or "").strip(),
        giudice=str(fascicolo.get("giudice") or "").strip(),
        materia=materia,
    )


def _rg(fascicolo: dict[str, Any]) -> str:
    numero, anno = str(fascicolo.get("numero_rg") or "").strip(), str(fascicolo.get("anno_rg") or "").strip()
    return f"{numero}/{anno}" if numero and anno not in {"", "0"} else numero


def passaggi_del_fascicolo(
    fascicolo: dict[str, Any], *, scadenze: Iterable[dict[str, Any]], termini_pec: Iterable[dict[str, Any]], oggi: date,
) -> list[Passaggio]:
    contesto = contesto_del_fascicolo(fascicolo)
    passaggi: list[Passaggio] = []
    passaggi.extend(passaggi_da_scadenza(list(scadenze), contesto, oggi=oggi, rg=_rg(fascicolo)))
    passaggi.extend(passaggi_termini_pec(list(termini_pec), contesto))
    return passaggi  # ogni produttore restituisce già la propria sequenza in ordine


__all__ = ["contesto_del_fascicolo", "passaggi_del_fascicolo"]
