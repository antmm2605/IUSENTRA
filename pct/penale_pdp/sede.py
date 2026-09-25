"""Distretto, circondario e sede da scegliere nella maschera «Ufficio Destinazione» del PDP.

Fonte: i codificati del Portale Deposito atti Penali (``distretti``,
``circondari``, ``sediuffici``), consultati in sola lettura il 25/09/2026 e
salvati in ``pct/data/cataloghi/pdp_sedi_penali.json`` con le stesse
scritture del portale («BOLZANO/BOZEN», «FORLI'», «PROCURA DELLA REPUBBLICA DI
REGGIO DI CALABRIA»). Il codice di sede della Procura coincide con il codice
ministeriale dell'ufficio; per il resto si riconosce il circondario dal nome
dell'ufficio indicato nel fascicolo.
"""

from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

_CATALOGO = Path(__file__).resolve().parents[1] / "data" / "cataloghi" / "pdp_sedi_penali.json"
_VUOTO = {"distretto": "", "circondario": "", "sede": "", "codiceSede": ""}
# Tribunali soppressi dalla revisione della geografia giudiziaria (D.Lgs. 155/2012, tabella A):
# sul PDP si sceglie il circondario che li ha accorpati. Caserta non è sede di tribunale:
# il suo circondario è Santa Maria Capua Vetere.
_ACCORPATI = {
    "alba": "ASTI", "acquiterme": "ALESSANDRIA", "chiavari": "GENOVA", "sanremo": "IMPERIA",
    "orvieto": "TERNI", "arianoirpino": "BENEVENTO", "caserta": "SANTA MARIA CAPUA VETERE",
    "melfi": "POTENZA", "rossano": "CASTROVILLARI", "nicosia": "ENNA", "modica": "RAGUSA",
}


def _chiave(valore: str) -> str:
    base = unicodedata.normalize("NFKD", str(valore or "")).casefold()
    parole = re.findall(r"[a-z]+", "".join(c for c in base if not unicodedata.combining(c)))
    return "".join(p for p in parole if p not in {"di", "d", "del", "della", "nell", "nel", "bozen"})


@lru_cache(maxsize=1)
def _circondari() -> tuple[dict[str, Any], ...]:
    return tuple(json.loads(_CATALOGO.read_text(encoding="utf-8"))["circondari"])


def fonte() -> dict[str, Any]:
    return dict(json.loads(_CATALOGO.read_text(encoding="utf-8"))["fonte"])


def _esito(voce: dict[str, Any], ufficio_codice: str) -> dict[str, str]:
    # Il catalogo salvato contiene le sedi di PM-U (Procura) e DIB-U (Tribunale dibattimento):
    # per gli altri uffici (GIP, minori, Procura generale) la sede resta da scegliere sul PDP.
    codice = str(ufficio_codice or "").upper()
    sedi = voce["procura"] if codice == "PM-U" else voce["tribunale"] if codice == "DIB-U" else []
    sede = sedi[0] if sedi else {"codice": "", "descrizione": ""}
    return {"distretto": voce["distretto"], "circondario": voce["circondario"],
            "sede": sede["descrizione"], "codiceSede": sede["codice"]}


def sede_pdp(nome_ufficio: str, uffici: Iterable[dict[str, Any]] = (), ufficio_codice: str = "PM-U") -> dict[str, str]:
    """{distretto, circondario, sede, codiceSede} come li mostra il PDP; vuoti se l'ufficio non si riconosce."""
    # «TRIBUNALE DI CUNEO ex TRIBUNALE DI MONDOVI»: conta l'ufficio attuale, non quello accorpato.
    nome = _chiave(re.split(r"(?i)\s+ex\s+", str(nome_ufficio or ""))[0])
    if not nome:
        return dict(_VUOTO)
    # 1. Codice ministeriale della Procura nel bundle uffici = codice sede del PDP.
    codici = {str(u.get("codice_ministero") or "") for u in uffici
              if _chiave(u.get("nome") or "") == nome or _chiave(u.get("descrizione_ministero") or "") == nome}
    for voce in _circondari():
        if any(s["codice"] in codici for s in voce["procura"] + voce["tribunale"]):
            return _esito(voce, ufficio_codice)
    # 2. Il comune del tribunale del bundle (es. «Tribunale di Massa Carrara» ha sede a Massa).
    for ufficio in uffici:
        citta = re.sub(r"(?i)^tribunale( ordinario)? di ", "", str(ufficio.get("nome") or ""))
        if ufficio.get("tipo") != "TRIBUNALE" or not citta or not nome.endswith(_chiave(citta)):
            continue
        comune = _chiave(str(ufficio.get("comune_ministero") or "").split(" - ")[0])
        voce = next((v for v in _circondari() if _chiave(v["circondario"]) == comune), None)
        if voce and len(_chiave(citta)) > len(_chiave(voce["circondario"])):
            return _esito(voce, ufficio_codice)
    # 3. Tribunale soppresso: circondario che lo ha accorpato.
    for soppresso, circondario in _ACCORPATI.items():
        if nome.endswith(soppresso):
            voce = next(v for v in _circondari() if v["circondario"] == circondario)
            return _esito(voce, ufficio_codice)
    # 4. Il nome dell'ufficio finisce con il circondario (il più lungo vince: «Napoli Nord» prima di «Napoli»).
    candidati = []
    for voce in _circondari():
        chiavi = {_chiave(voce["circondario"])} | {_chiave(re.sub(r"(?i)^.*? di ", "", s["descrizione"]))
                                                 for s in voce["procura"] + voce["tribunale"]}
        migliore = max((len(k) for k in chiavi if k and nome.endswith(k)), default=0)
        if migliore:
            candidati.append((migliore, voce))
    if not candidati:
        return dict(_VUOTO)
    return _esito(max(candidati, key=lambda c: c[0])[1], ufficio_codice)


__all__ = ["fonte", "sede_pdp"]
