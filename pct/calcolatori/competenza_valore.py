"""Competenza per valore del giudice di pace — art. 7, commi 1 e 2, c.p.c.

Base normativa:
- Art. 7, primo comma, c.p.c.: il giudice di pace è competente per le cause
  relative a beni mobili entro il valore indicato dalla norma, quando dalla
  legge non sono attribuite alla competenza di altro giudice.
- Art. 7, secondo comma, c.p.c.: il giudice di pace è competente per le cause di
  risarcimento del danno prodotto dalla circolazione di veicoli e di natanti
  entro il valore indicato dalla norma.
- Art. 3, comma 1, D.Lgs. 10 ottobre 2022, n. 149 (GU n. 243 del 17 ottobre
  2022, S.O. n. 38): al primo comma dell'art. 7 c.p.c. la parola «cinquemila» è
  sostituita da «diecimila»; al secondo comma «ventimila» è sostituita da
  «venticinquemila».
- Art. 35, comma 1, D.Lgs. 149/2022, come sostituito dall'art. 1, comma 380,
  lett. a), L. 29 dicembre 2022, n. 197 (GU n. 303 del 29 dicembre 2022, S.O.
  n. 43): le disposizioni del decreto, salvo che non sia diversamente disposto,
  hanno effetto dal 28 febbraio 2023 e si applicano ai procedimenti instaurati
  successivamente a tale data; ai procedimenti pendenti al 28 febbraio 2023 si
  applicano le disposizioni anteriormente vigenti.

Perimetro dichiarato: il modulo risolve la sola competenza per valore delle due
ipotesi dei commi 1 e 2 dell'art. 7 c.p.c. Le materie attribuite al giudice di
pace a prescindere dal valore, le competenze funzionali e le competenze
riservate ad altro giudice non sono valutate qui.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Mapping

from pct.calcolatori._base import clean_text, fmt_date_it, parse_date, safe_float

# Art. 35, comma 1, D.Lgs. 149/2022 nel testo sostituito dalla L. 197/2022:
# le nuove soglie valgono per i procedimenti instaurati DOPO questa data.
DATA_RIFORMA_CARTABIA = date(2023, 2, 28)

_MATERIE: Dict[str, Dict[str, Any]] = {
    "beni_mobili": {
        "label": "Cause relative a beni mobili",
        "riferimento": "Art. 7, primo comma, c.p.c.",
        "soglia_vigente": 10000.0,
        "soglia_anteriore": 5000.0,
    },
    "danno_circolazione": {
        "label": "Risarcimento del danno da circolazione di veicoli e natanti",
        "riferimento": "Art. 7, secondo comma, c.p.c.",
        "soglia_vigente": 25000.0,
        "soglia_anteriore": 20000.0,
    },
}

_FONTI = [
    {
        "title": "Art. 7 c.p.c. (Normattiva)",
        "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:regio.decreto:1940-10-28;1443",
    },
    {
        "title": "D.Lgs. 149/2022, art. 3, comma 1 (Gazzetta Ufficiale)",
        "url": "https://www.gazzettaufficiale.it/eli/id/2022/10/17/22G00158/sg",
    },
    {
        "title": "L. 197/2022, art. 1, comma 380 — disciplina transitoria (Gazzetta Ufficiale)",
        "url": "https://www.gazzettaufficiale.it/eli/id/2022/12/29/22G00211/sg",
    },
]


def calcola(payload: Mapping[str, Any]) -> Dict[str, Any]:
    materia = clean_text(payload.get("comp_materia")).lower() or "beni_mobili"
    if materia not in _MATERIE:
        raise ValueError("Tipo di causa non riconosciuto per la competenza per valore.")

    valore = safe_float(payload.get("comp_valore"))
    if valore <= 0:
        raise ValueError(
            "Indica il valore della causa determinato secondo gli artt. 10 e seguenti c.p.c.: "
            "senza un valore determinato la competenza per valore non è calcolabile."
        )

    introduzione = parse_date(payload.get("comp_data_introduzione"))
    if introduzione is None:
        raise ValueError(
            "Indica la data di instaurazione del procedimento: le soglie dell'art. 7 c.p.c. "
            "dipendono dalla disciplina transitoria della riforma Cartabia."
        )

    riforma_applicabile = introduzione > DATA_RIFORMA_CARTABIA
    regola = _MATERIE[materia]
    soglia = float(regola["soglia_vigente"] if riforma_applicabile else regola["soglia_anteriore"])
    entro_soglia = valore <= soglia

    giudice = "Giudice di pace" if entro_soglia else "Tribunale"
    margine = round(soglia - valore, 2)

    note: List[str] = [
        f"{regola['label']} — {regola['riferimento']}.",
    ]
    if riforma_applicabile:
        note.append(
            "Procedimento instaurato dopo il 28 febbraio 2023: si applicano le soglie elevate "
            "dall'art. 3, comma 1, D.Lgs. 149/2022 (art. 35, comma 1, dello stesso decreto, come "
            "sostituito dall'art. 1, comma 380, L. 197/2022)."
        )
    else:
        note.append(
            "Procedimento instaurato entro il 28 febbraio 2023: si applicano le soglie anteriori "
            "alla riforma Cartabia (art. 35, comma 1, D.Lgs. 149/2022, come sostituito dall'art. 1, "
            "comma 380, L. 197/2022)."
        )
    if entro_soglia:
        note.append(
            "Competenza del giudice di pace salvo che la causa sia attribuita dalla legge alla "
            "competenza di altro giudice (art. 7, primo comma, c.p.c.)."
        )
    else:
        note.append("Valore oltre la soglia dell'art. 7 c.p.c.: la causa resta di competenza del tribunale.")

    avvisi: List[str] = [
        "Il calcolo copre la sola competenza per valore delle ipotesi dei commi 1 e 2 dell'art. 7 "
        "c.p.c.: le materie attribuite al giudice di pace a prescindere dal valore, le competenze "
        "funzionali e quelle riservate ad altro giudice vanno verificate a parte.",
        "Il valore della causa va determinato secondo gli artt. 10 e seguenti c.p.c.: qui è "
        "assunto come dato di ingresso, non ricalcolato.",
    ]

    soglie: List[Dict[str, Any]] = [
        {
            "materia": voce["label"],
            "riferimento": voce["riferimento"],
            "soglia_dal_28_02_2023": voce["soglia_vigente"],
            "soglia_precedente": voce["soglia_anteriore"],
        }
        for voce in _MATERIE.values()
    ]

    return {
        "materia": materia,
        "materia_label": regola["label"],
        "riferimento": regola["riferimento"],
        "valore": round(valore, 2),
        "data_introduzione": fmt_date_it(introduzione),
        "regime": "cartabia" if riforma_applicabile else "anteriore",
        "regime_label": (
            "Soglie vigenti (procedimenti instaurati dopo il 28/02/2023)"
            if riforma_applicabile
            else "Soglie anteriori alla riforma Cartabia"
        ),
        "soglia_applicata": round(soglia, 2),
        "entro_soglia": entro_soglia,
        "giudice_competente": giudice,
        "margine": margine,
        "soglie": soglie,
        "notes": note,
        "warnings": avvisi,
        "sources": list(_FONTI),
    }
