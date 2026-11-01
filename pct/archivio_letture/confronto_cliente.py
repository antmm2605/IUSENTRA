"""Quando un nome o un codice fiscale letto negli atti prova davvero una discordanza con l'anagrafica.

Verifica del 01/11/2026 sulle 13 discordanze aperte: 11 erano false. Una discordanza si pubblica solo se il dato
letto è confrontabile e diverso:

- codice fiscale: solo un codice con carattere di controllo valido (D.M. 23/12/1976) può contraddire
  l'anagrafica; un codice che non lo supera è una lettura sbagliata (OCR), non un dato diverso;
- nome: deve essere il nome di una persona (da due a cinque parole, nessun ente pubblico o società
  quando il cliente è una persona) e non deve contenere tutte le parole dell'anagrafica: «Leonora Marzia
  Maione» è la stessa persona di «Maione Marzia» con il secondo nome;
- se accanto al nome letto c'è un codice fiscale valido uguale a quello dell'anagrafica, è la stessa persona.

Nessun dato viene corretto: le regole decidono solo se mostrare la discordanza all'avvocato.
"""

from __future__ import annotations

import re
from typing import Any

from pct.archivio_letture.parti_fascicolo import _PA, _SOCIETA, semplice, stesso_nome

_CF = re.compile(r"\b[A-Z]{6}\d{2}[A-Z]\d{2}[A-Z]\d{3}[A-Z]\b")
_TITOLI = frozenset({"ass", "ed", "prof", "ssa", "dott", "dr", "avv", "sig", "ra", "ing", "arch", "geom", "rag", "on"})


def codice_fiscale_valido(cf: Any) -> bool:
    from pct.codice_fiscale import _checksum

    valore = str(cf or "").strip().upper()
    if not re.fullmatch(r"[A-Z0-9]{16}", valore):
        return False
    try:
        return _checksum(valore[:15]) == valore[15]
    except KeyError:
        return False


def _e_ente(nome: str) -> bool:
    return bool(_PA.search(nome) or _SOCIETA.search(nome))


def nome_confrontabile(nome_letto: Any, nome_anagrafica: Any) -> bool:
    """Il nome letto è quello di una persona e il cliente è una persona: il confronto ha senso."""
    parole = [p for p in semplice(nome_letto).split() if p not in _TITOLI]
    if not 2 <= len(parole) <= 5:
        return False
    return not (_e_ente(str(nome_letto or "")) and not _e_ente(str(nome_anagrafica or "")))


def stessa_persona(nome_letto: Any, nome_anagrafica: Any, *, citazione: Any = "", cf_anagrafica: Any = "") -> bool:
    """Vero quando il nome letto indica la stessa persona dell'anagrafica."""
    if stesso_nome(nome_letto, nome_anagrafica):
        return True
    letto = set(semplice(nome_letto).split()) - _TITOLI
    anagrafica = set(semplice(nome_anagrafica).split())
    if len(anagrafica) >= 2 and anagrafica <= letto:
        return True
    cf = str(cf_anagrafica or "").strip().upper()
    if cf and codice_fiscale_valido(cf):
        return any(trovato == cf for trovato in _CF.findall(str(citazione or "").upper()))
    return False


def discordanza_nome(nome_letto: Any, nome_anagrafica: Any, *, citazione: Any = "", cf_anagrafica: Any = "") -> bool:
    """Una discordanza da mostrare: nome di persona confrontabile che non indica la stessa persona."""
    return nome_confrontabile(nome_letto, nome_anagrafica) and not stessa_persona(
        nome_letto, nome_anagrafica, citazione=citazione, cf_anagrafica=cf_anagrafica)


def discordanza_codice_fiscale(cf_letto: Any, cf_anagrafica: Any) -> bool:
    """Solo un codice letto valido e diverso contraddice l'anagrafica."""
    letto = str(cf_letto or "").strip().upper()
    return bool(letto) and letto != str(cf_anagrafica or "").strip().upper() and codice_fiscale_valido(letto)


__all__ = ["codice_fiscale_valido", "discordanza_codice_fiscale", "discordanza_nome", "nome_confrontabile", "stessa_persona"]
