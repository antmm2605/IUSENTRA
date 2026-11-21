"""Testo dell'articolo come lo legge l'avvocato: senza i segni grezzi di Normattiva, con le note a parte.

Il testo archiviato resta quello della fonte (impronta SHA-256 invariata): qui si prepara solo la lettura.

Regole, tutte certe per convenzione di Normattiva:
- le note di aggiornamento iniziano dopo la riga di trattini con «AGGIORNAMENTO (n)»: vanno in un riquadro a parte;
- «((348))» è il richiamo di una nota: si toglie; «(129a)» o «(116)» si tolgono solo se la nota con quel numero
  c'è davvero, o se hanno la lettera finale (forma usata solo per i richiami);
- «((testo))» segna il testo modificato: restano le parole, cadono le doppie parentesi;
- l'accento scritto con l'apostrofo (Normattiva non usa le lettere accentate) si corregge solo nei casi univoci
  («e'» parola isolata → «è», «puo'» → «può», «liberta'» → «libertà», «perche'» → «perché»), mai dentro le
  virgolette (citazioni letterali) e mai nelle note, che riportano testi di altri atti. «po'» e «mo'» restano.

Commi: l'archivio conserva il testo su una riga; la divisione in commi viene dall'XML ufficiale di Normattiva
(``lex/normativa/commi.py``) e si applica solo se il testo coincide. Mai dividere per frasi (l'art. 1284 c.c. ha
tre frasi nel primo comma).
"""
from __future__ import annotations

import re
from datetime import date

_NOTE = re.compile(r"\s*-{5,}\s*(?=AGGIORNAMENTO\b)")
_ID_NOTA = re.compile(r"AGGIORNAMENTO\s*\((\d{1,4}[a-z]?)\)")
_RICHIAMO_DOPPIO = re.compile(r"\s?\(\(\d{1,4}[a-z]?\)\)")
_RICHIAMO = re.compile(r"\s?\((\d{1,4}[a-z]?)\)")
_MODIFICA = re.compile(r"\(\((?!\d{1,4}[a-z]?\)\))(.+?)\)\)", re.DOTALL)
_VIRGOLETTE = re.compile(r"(«[^»]*»|“[^”]*”|\"[^\"]*\")")
_ACUTE = {"perche": "perché", "poiche": "poiché", "affinche": "affinché", "benche": "benché", "finche": "finché",
          "sicche": "sicché", "nonche": "nonché", "giacche": "giacché", "purche": "purché", "cosicche": "cosicché",
          "allorche": "allorché", "ne": "né", "se": "sé", "trentatre": "trentatré", "ventitre": "ventitré"}
_NON_ACCENTI = {"po", "mo", "fa", "va", "sta", "da", "di", "to"}
_PAROLA_APOSTROFO = re.compile(r"\b([A-Za-z]+)([aeiouAEIOU])'(?=[\s.,;:)!?]|$)")
_GRAVE = {"a": "à", "i": "ì", "o": "ò", "u": "ù", "A": "À", "I": "Ì", "O": "Ò", "U": "Ù"}


def _accento(trovato: re.Match) -> str:
    radice, vocale = trovato.group(1), trovato.group(2)
    parola = (radice + vocale).lower()
    if parola in _NON_ACCENTI:
        return trovato.group(0)
    if vocale.lower() == "e":
        if parola in _ACUTE:
            corretta = _ACUTE[parola]
            return corretta[0].upper() + corretta[1:] if radice[0].isupper() else corretta
        if parola.endswith("che") or len(parola) <= 2:
            return trovato.group(0)  # dubbio reale (acuto o grave): resta com'è
        return radice + ("È" if vocale == "E" else "è")
    return radice + _GRAVE[vocale]


def _accenti(testo: str) -> str:
    def fuori_virgolette(parte: str) -> str:
        parte = re.sub(r"(?<![\w'])([eE])'(?=\s)", lambda m: "È" if m.group(1) == "E" else "è", parte)
        return _PAROLA_APOSTROFO.sub(_accento, parte)

    return "".join(p if _VIRGOLETTE.fullmatch(p) else fuori_virgolette(p) for p in _VIRGOLETTE.split(testo))


def presenta(testo: str) -> dict[str, str]:
    testo = str(testo or "")
    parti = _NOTE.split(testo, maxsplit=1)
    corpo, note = parti[0], (parti[1].strip() if len(parti) > 1 else "")
    note_presenti = set(_ID_NOTA.findall(note))
    corpo = _RICHIAMO_DOPPIO.sub("", corpo)
    corpo = _RICHIAMO.sub(lambda m: "" if (m.group(1) in note_presenti or m.group(1)[-1].isalpha()) else m.group(0), corpo)
    corpo = _MODIFICA.sub(lambda m: m.group(1), corpo)
    corpo = _accenti(" ".join(corpo.split()))
    corpo = re.sub(r"\s+([.,;:])", r"\1", corpo)
    return {"testo": corpo, "note": note}


def saggio_legale_vigente(oggi: date | None = None) -> dict[str, str] | None:
    """Il saggio degli interessi legali in vigore (art. 1284 c.c.), dalla tabella del software con D.M. e G.U."""
    from pct.normative_tables import canonical_table_definitions

    oggi_iso = (oggi or date.today()).isoformat()
    for riga in canonical_table_definitions().get("interesse_legale", {}).get("rows") or []:
        inizio, fine = str(riga.get("start") or ""), str(riga.get("end") or "9999-12-31")
        if inizio and inizio <= oggi_iso <= fine and riga.get("rate") is not None:
            return {"misura": f"{float(riga['rate']):.2f}".replace(".", ",") + "%",
                    "dal": "/".join(reversed(inizio.split("-"))), "al": "/".join(reversed(fine.split("-"))),
                    "decreto": str(riga.get("decreto") or ""), "gazzetta": str(riga.get("gazzetta") or "")}
    return None


_CODICE_CIVILE = "urn:nir:stato:regio.decreto:1942-03-16;262"


_NUMERO_PROPRIO = re.compile(r"^(?:\(\()?\s*(\d{1,3}(?:[\s-]*(?:bis|ter|quater|quinquies|sexies|septies|octies|novies|decies))?)\.\s+")


def numera_commi(commi: list[str]) -> list[dict[str, str]]:
    """Il numero del comma: quello scritto nella legge («3-bis.») se c'è, altrimenti la posizione (codici)."""
    uscita = []
    for posizione, testo in enumerate(commi, 1):
        proprio = _NUMERO_PROPRIO.match(testo)
        if proprio:
            uscita.append({"numero": proprio.group(1).replace(" ", ""), "testo": testo[proprio.end():].strip()
                           if not testo.startswith("((") else "((" + testo[proprio.end():].strip()})
        else:
            uscita.append({"numero": str(posizione), "testo": testo})
    return uscita


def arricchisci(item: dict) -> dict:
    """Aggiunge la lettura preparata all'articolo restituito dall'archivio (il testo originale resta in «text»)."""
    lettura = presenta(item.get("text") or "")
    item["text_lettura"], item["note_aggiornamento"] = lettura["testo"], lettura["note"]
    # Commi numerati solo dalla struttura dell'XML ufficiale e solo se il testo archiviato è lo stesso.
    from lex.normativa.commi import commi_articolo, intestazione_articolo

    commi = commi_articolo(item.get("text") or "", str(item.get("data_atto") or ""), str(item.get("numero") or ""),
                           str(item.get("number") or ""))
    if commi:
        item["commi"] = numera_commi([presenta(comma)["testo"] for comma in commi])
        item["intestazione_lettura"] = presenta(intestazione_articolo(
            item.get("text") or "", str(item.get("data_atto") or ""), str(item.get("numero") or ""),
            str(item.get("number") or "")))["testo"]
    numero = re.sub(r"[\s.-]", "", str(item.get("number") or "")).lower()
    if numero == "1284" and str(item.get("urn") or "").startswith(_CODICE_CIVILE):
        item["saggio_legale_vigente"] = saggio_legale_vigente()
    return item
