"""Le parti della nota di iscrizione a ruolo (NIR) dai soggetti del fascicolo.

- Ricorrente: il cliente, con la natura giuridica della Tabella A della NIR
  (F01 persona fisica; per le società la forma giuridica scritta nella
  denominazione: S.r.l./S.p.A. → G08, S.n.c./S.a.s. → G09, cooperativa → G05,
  consorzio → G04, fondazione → G07, associazione/ONLUS → G06). Se la forma non
  si legge dal nome la natura resta da scegliere.
- Parti resistenti: le controparti, con il tipo di ente dell'elenco del SIGIT
  (Agenzie fiscali, Enti locali, …) quando il nome lo dice senza ambiguità.
  L'agente della riscossione resta da scegliere: il modulo cartaceo lo prevede
  come «Società di riscossione», l'elenco del SIGIT no.
"""

from __future__ import annotations

import re
from typing import Any, Iterable

_FORME = (
    (r"\b(s\.?\s?r\.?\s?l|s\.?\s?p\.?\s?a|s\.?\s?a\.?\s?p\.?\s?a|srls)\b", "G08"),
    (r"\b(s\.?\s?n\.?\s?c|s\.?\s?a\.?\s?s|s\.?\s?s)\b", "G09"),
    (r"\bcooperativ", "G05"),
    (r"\bconsorzi", "G04"),
    (r"\bfondazion", "G07"),
    (r"\b(associazion|onlus|ets)\b", "G06"),
)
_ENTI = (
    (r"agenzia (delle )?entrate(?!.{0,5}riscoss)|agenzia (delle )?dogane|agenzia del demanio", "Agenzie fiscali"),
    (r"\b(comune|provincia|regione|citta metropolitana|citt[àa] metropolitana|unione dei comuni)\b", "Enti locali"),
    (r"\b(ministero|presidenza del consiglio)\b", "Amministrazioni centrali"),
    (r"\b(camera di commercio|inps|inail|consorzio di bonifica|autorit[àa] di sistema)\b", "Enti pubblici"),
)


def natura_giuridica(tipo: str, denominazione: str, forma: str = "") -> str:
    if str(tipo).upper() == "PERSONA_FISICA":
        return "F01"
    testo = f"{forma or ''} {denominazione or ''}".casefold()
    return next((codice for modello, codice in _FORME if re.search(modello, testo)), "")


def tipo_ente(denominazione: str) -> str:
    testo = str(denominazione or "").casefold()
    if "riscossione" in testo:
        return ""
    return next((tipo for modello, tipo in _ENTI if re.search(modello, testo)), "")


def _nome(dati: dict[str, Any]) -> str:
    return (dati.get("ragione_sociale") or " ".join(x for x in (dati.get("cognome"), dati.get("nome")) if x)).strip()


def parti_nir(cliente: dict[str, Any] | None, soggetti: Iterable[tuple[str, dict[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
    ricorrenti, resistenti = [], []
    if cliente:
        nome = _nome(cliente)
        ricorrenti.append({"id": "cliente", "denominazione": nome, "codiceFiscale": cliente.get("codice_fiscale") or cliente.get("partita_iva") or "",
                           "natura": natura_giuridica(cliente.get("tipo", ""), nome, cliente.get("forma_giuridica", "")),
                           "pec": cliente.get("pec") or "", "tipo": cliente.get("tipo", "")})
    for ruolo, dati in soggetti:
        ruolo = str(ruolo).upper()
        nome = _nome(dati)
        if ruolo == "ASSISTITO":
            ricorrenti.append({"id": dati.get("id", ""), "denominazione": nome, "pec": dati.get("pec") or "",
                               "codiceFiscale": dati.get("codice_fiscale") or dati.get("partita_iva") or "",
                               "natura": natura_giuridica(dati.get("tipo", ""), nome, dati.get("forma_giuridica", "")),
                               "tipo": dati.get("tipo", "")})
            continue
        if ruolo != "CONTROPARTE":
            continue
        resistenti.append({"id": dati.get("id", ""), "denominazione": nome, "tipoEnte": tipo_ente(nome),
                           "codiceFiscale": dati.get("codice_fiscale") or dati.get("partita_iva") or "",
                           "provincia": dati.get("provincia", ""), "pec": dati.get("pec") or ""})
    return {"ricorrenti": ricorrenti, "resistenti": resistenti}


__all__ = ["natura_giuridica", "parti_nir", "tipo_ente"]
