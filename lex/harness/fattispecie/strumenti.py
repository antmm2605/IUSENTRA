"""Strumenti comuni delle regole: date ed importi cercati nei fatti, per parola chiave, senza supporre nulla."""
from __future__ import annotations

import re
from datetime import date

from ..fatti import Evento, Fatti
from ..norme import piano

_DATA = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")
_IMPORTO = re.compile(r"(?:euro\s*|€\s*)(\d{1,3}(?:\.\d{3})+(?:,\d{1,2})?|\d+(?:,\d{1,2})?)|(\d{1,3}(?:\.\d{3})+(?:,\d{1,2})?|\d+(?:,\d{1,2})?)\s*(?:euro|€)", re.I)


def date_in(testo: str) -> list[date]:
    out = []
    for m in _DATA.finditer(testo):
        try:
            out.append(date(int(m.group(3)), int(m.group(2)), int(m.group(1))))
        except ValueError:
            continue
    return out


def importi_in(testo: str) -> list[float]:
    out = []
    for m in _IMPORTO.finditer(testo):
        grezzo = (m.group(1) or m.group(2) or "").replace(".", "").replace(",", ".")
        try:
            out.append(float(grezzo))
        except ValueError:
            continue
    return out


def frasi(f: Fatti) -> list[str]:
    """Le frasi dei fatti. Nel racconto strutturato l'intestazione (data di oggi, parti, richiesta) non è un fatto:
    si legge dopo «Fatti del fascicolo»; ogni riga datata («12/01/2026 - …») è una frase a sé."""
    testo = f.testo
    m = re.search(r"fatti del fascicolo\s*:?\s*", testo, re.I)
    if m:
        testo = testo[m.end():]
    testo = re.sub(r"\s+(?=\d{1,2}/\d{1,2}/\d{4}\s+-\s)", ". ", testo)
    # non si spezza dopo le abbreviazioni («n. 711/2026», «art. 1385», «c. 2»)
    return [x.strip() for x in re.split(r"(?<=[.;])(?<!\bn\.)(?<!\bnn\.)(?<!\bart\.)(?<!\bartt\.)(?<!\bc\.)(?<!\blett\.)(?<!\bsig\.)(?<!\bsigg\.)(?<!\bdott\.)(?<!\bavv\.)(?<!\bgeom\.)"
                                         r"\s+(?=[A-ZÀ-Ý0-9])", testo) if x.strip()]


def frase(f: Fatti, espr: str) -> str:
    """La prima frase dei fatti che contiene l'espressione (testo senza accenti, minuscolo)."""
    return next((x for x in frasi(f) if re.search(espr, piano(x))), "")


def evento(f: Fatti, espr: str) -> Evento | None:
    return next((e for e in f.eventi if re.search(espr, piano(e.testo))), None)


def data_di(f: Fatti, espr: str, *, ultima: bool = False) -> date | None:
    """Data della frase che contiene l'espressione; ``ultima`` per la data più a destra («datata 01/09, ricevuta il 02/09»)."""
    x = frase(f, espr)
    d = date_in(x)
    return (d[-1] if ultima else d[0]) if d else None


def data_dopo(f: Fatti, espr: str) -> date | None:
    """Data scritta subito dopo l'espressione («notificato il 04/12/2026»), nei soli fatti."""
    m = re.search(espr + r"[^0-9]{0,25}(\d{1,2}/\d{1,2}/\d{4})", piano(" ".join(frasi(f))))
    d = date_in(m.group(1)) if m else []
    return d[0] if d else None


def importo_di(f: Fatti, espr: str) -> float | None:
    x = frase(f, espr)
    v = importi_in(x)
    return v[0] if v else None


def mesi_fra(dal: date, al: date) -> int:
    return (al.year - dal.year) * 12 + al.month - dal.month - (1 if al.day < dal.day else 0)


def forma(c) -> str:
    return "atto" if c.tipo == "redazione" else "parere (consulenza)"
