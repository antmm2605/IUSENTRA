"""Il giudice rigetta l'istanza di trattazione scritta: l'udienza si tiene nella forma già fissata.

Art. 127-ter, comma 1, c.p.c.: la sostituzione dell'udienza con il deposito di note è disposta dal giudice, che può
non accoglierla («mantenerla nella forma già predisposta»). Il rigetto non apre termini per le note: l'avvocato deve
partecipare all'udienza da remoto (art. 127-bis c.p.c.) o in presenza. Non nasce alcuna bozza «deposito note scritte».
"""

from __future__ import annotations

import re
from typing import Any, Iterable

from .modello import Voce
from .riferimenti import Riferimenti

ESPRESSIONE = (r"\bistanza\b.{0,120}\b(?:trattazione\s+scritta|trattazione\s+cartolare|note\s+scritte|127\s*[-\s]?\s*ter)\b"
               r".{0,2500}\b(?:rigetta|respinge|non\s+accoglie)\b(?:\s+l'\s*istanza)?"
               r"|\b(?:rigetta|respinge)\b\s+l'\s*istanza\s+di\s+(?:trattazione\s+scritta|trattazione\s+cartolare|sostituzione\s+dell'\s*udienza)")
_DA_REMOTO = re.compile(r"\bda\s+remoto\b|\baudiovisiv\w*\b|\bvideoconferenza\b|\b127\s*[-\s]?\s*bis\b", re.I)
_IN_PRESENZA = re.compile(r"\bin\s+presenza\b", re.I)


def _campo(oggetto: Any, nome: str) -> str:
    valore = oggetto.get(nome) if isinstance(oggetto, dict) else getattr(oggetto, nome, "")
    return str(valore or "").strip()


def _collegamento(appuntamenti: Iterable[Any], id_appuntamento: str) -> str:
    """Il link della riunione già registrato in agenda per l'udienza del fascicolo."""
    for appuntamento in appuntamenti or ():
        if id_appuntamento and _campo(appuntamento, "id") == id_appuntamento:
            return _campo(appuntamento, "remote_hearing_url")
    return ""


def voce_rigetto(pulito: str, rif: Riferimenti, appuntamenti: Iterable[Any] = ()) -> Voce:
    """La voce da mostrare all'avvocato: istanza rigettata, udienza del fascicolo con data, ora e collegamento."""
    remoto = bool(_DA_REMOTO.search(pulito))
    if remoto:
        forma, modalita = "da remoto (art. 127-bis c.p.c.)", "da_remoto"
    elif _IN_PRESENZA.search(pulito):
        forma, modalita = "in presenza", "in_presenza"
    else:
        forma, modalita = "nella forma già fissata", ""
    quando = (f" del {rif.udienza:%d/%m/%Y}" + (f" ore {rif.udienza_ora}" if rif.udienza_ora else "")) if rif.udienza else ""
    link = _collegamento(appuntamenti, rif.id_appuntamento) if remoto else ""
    if remoto and link:
        seguito = ": collegamento indicato in agenda"
    elif remoto:
        seguito = ": link di collegamento non in agenda, recuperarlo dal decreto di fissazione o dalla cancelleria"
    elif not rif.udienza:
        seguito = ": verificare data e forma nel decreto di fissazione"
    else:
        seguito = ""
    trovato = re.search(ESPRESSIONE, pulito, re.I | re.S)
    dati: list[tuple[str, str, str]] = [rif.dato_udienza()] if rif.udienza else []
    if link:
        dati.append(("Collegamento", link, "agenda dell'udienza"))
    return Voce("provvedimento.rigetto_trattazione_scritta", "verifica",
                f"Rigetto dell'istanza di trattazione scritta: nessuna nota da depositare; l'udienza{quando} si tiene {forma}{seguito}",
                norme=("cpc_127ter",), prova=pulito[trovato.start():trovato.start() + 300] if trovato else pulito[:300],
                modalita=modalita, giorno=rif.udienza, ora=rif.udienza_ora, id_appuntamento=rif.id_appuntamento,
                dati=tuple(dati), confidenza=0.85)


__all__ = ["ESPRESSIONE", "voce_rigetto"]
