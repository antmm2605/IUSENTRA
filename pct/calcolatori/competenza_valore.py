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

Perimetro dichiarato: il modulo risolve la competenza per valore delle due
ipotesi dei commi 1 e 2 dell'art. 7 c.p.c. e riconosce due competenze che il
valore non decide mai (testo vigente letto nella biblioteca del software il
25/11/2026):
- controversie di lavoro e di previdenza, compreso il TFR: «sono in primo grado
  di competenza del tribunale in funzione di giudice del lavoro» (artt. 409,
  413, 442 e 444 c.p.c.), a qualunque valore;
- opposizione a decreto ingiuntivo, anche tardiva (art. 650 c.p.c.): «si
  propone davanti all'ufficio giudiziario al quale appartiene il giudice che ha
  emesso il decreto» (art. 645, primo comma, c.p.c., testo del d.lgs. 164/2024).
Le altre materie attribuite al giudice di pace a prescindere dal valore e le
altre competenze funzionali non sono valutate qui.
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


# Competenze che il valore non decide: il giudice è fissato dalla legge per materia o per funzione.
_COMPETENZE_FISSE: Dict[str, Dict[str, Any]] = {
    "lavoro_previdenza": {
        "label": "Controversia di lavoro o di previdenza (anche TFR e crediti retributivi)",
        "riferimento": "Artt. 409, 413, 442 e 444 c.p.c.",
        "giudice": "Tribunale in funzione di giudice del lavoro",
        "nota": "Le controversie dell'art. 409 c.p.c. (lavoro subordinato privato, collaborazioni, lavoro pubblico "
                "contrattualizzato) e quelle di previdenza e assistenza obbligatorie dell'art. 442 sono in primo grado "
                "di competenza del tribunale in funzione di giudice del lavoro, a qualunque valore (artt. 413 e 444 "
                "c.p.c.): il giudice di pace non è mai competente, neppure per il TFR o per crediti di piccolo importo.",
        "foro": "Foro: dove è sorto il rapporto o si trova l'azienda o la dipendenza cui è addetto il lavoratore "
                "(art. 413, secondo comma); per la previdenza, la residenza dell'attore (art. 444).",
        "fonte": {"title": "Artt. 409, 413 e 444 c.p.c. (Normattiva)",
                  "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:regio.decreto:1940-10-28;1443~art413"},
    },
    "opposizione_decreto_ingiuntivo": {
        "label": "Opposizione a decreto ingiuntivo, anche tardiva",
        "riferimento": "Art. 645, primo comma, c.p.c.; art. 650 c.p.c.",
        "giudice": "Ufficio giudiziario del giudice che ha emesso il decreto",
        "nota": "L'opposizione «si propone davanti all'ufficio giudiziario al quale appartiene il giudice che ha emesso "
                "il decreto» (art. 645, primo comma, c.p.c., nel testo del d.lgs. 164/2024): è una competenza "
                "funzionale, che non si ricalcola con il valore (artt. 7 e 9 c.p.c.). Vale anche per l'opposizione "
                "tardiva dell'art. 650 c.p.c.",
        "foro": "",
        "fonte": {"title": "Art. 645 c.p.c. (Normattiva)",
                  "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:regio.decreto:1940-10-28;1443~art645"},
    },
}


def _competenza_fissa(materia: str, valore: float, introduzione: Any) -> Dict[str, Any]:
    regola = _COMPETENZE_FISSE[materia]
    note = [f"{regola['label']} — {regola['riferimento']}.", regola["nota"]]
    if regola["foro"]:
        note.append(regola["foro"])
    return {
        "materia": materia,
        "materia_label": regola["label"],
        "riferimento": regola["riferimento"],
        "valore": round(valore, 2) if valore > 0 else 0.0,
        "data_introduzione": fmt_date_it(introduzione) if introduzione else "",
        "regime": "competenza_per_materia",
        "regime_label": "Competenza fissata dalla legge, indipendente dal valore",
        "soglia_applicata": 0.0,
        "entro_soglia": False,
        "giudice_competente": regola["giudice"],
        "margine": 0.0,
        "soglie": [],
        "notes": note,
        "warnings": ["Il valore della causa non incide sulla competenza in questa materia."],
        "sources": [regola["fonte"]],
    }


def calcola(payload: Mapping[str, Any]) -> Dict[str, Any]:
    materia = clean_text(payload.get("comp_materia")).lower() or "beni_mobili"
    if materia in _COMPETENZE_FISSE:
        return _competenza_fissa(materia, safe_float(payload.get("comp_valore")),
                                 parse_date(payload.get("comp_data_introduzione")))
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
