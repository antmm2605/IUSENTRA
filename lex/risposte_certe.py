"""Risposte certe di Lex: calcoli che hanno una sola risposta giusta.

Termini processuali e contributo unificato non si chiedono a un modello
linguistico: si calcolano con i motori di IUSENTRA, che applicano la norma
(art. 155 c.p.c., sospensione feriale L. 742/1969, festività nazionali,
scaglioni dell'art. 13 D.P.R. 115/2002). Qui Lex riconosce la domanda, estrae
date e importi scritti dall'avvocato e risponde con il calcolo e la sua base
normativa. Se manca un dato necessario lo chiede, invece di supporlo.

Le domande non riconosciute con certezza tornano al percorso ordinario di Lex.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Callable

_MESI = {
    "gennaio": 1, "febbraio": 2, "marzo": 3, "aprile": 4, "maggio": 5, "giugno": 6,
    "luglio": 7, "agosto": 8, "settembre": 9, "ottobre": 10, "novembre": 11, "dicembre": 12,
}
_DATA_NUMERICA = re.compile(r"\b(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})\b")
_DATA_ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_DATA_LETTERE = re.compile(r"\b(\d{1,2})(?:°|º)?\s+(" + "|".join(_MESI) + r")\s+(\d{4})\b")
_IMPORTO = re.compile(r"(?:€|euro)\s*(\d{1,3}(?:\.\d{3})+(?:,\d{1,2})?|\d+(?:,\d{1,2})?)|(\d{1,3}(?:\.\d{3})+(?:,\d{1,2})?|\d+(?:,\d{1,2})?)\s*(?:€|euro)")


@dataclass
class RispostaCerta:
    testo: str
    fonti: list[dict[str, str]] = field(default_factory=list)
    tipo: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"answer": self.testo, "sources": list(self.fonti), "kind": self.tipo, "deterministic": True}


def _norm(testo: str) -> str:
    base = unicodedata.normalize("NFKD", str(testo or "").lower())
    return "".join(c for c in base if not unicodedata.combining(c))


def date_nella_domanda(testo: str) -> list[date]:
    trovate: list[tuple[int, date]] = []
    t = _norm(testo)
    for m in _DATA_LETTERE.finditer(t):
        try:
            trovate.append((m.start(), date(int(m.group(3)), _MESI[m.group(2)], int(m.group(1)))))
        except ValueError:
            pass
    for m in _DATA_ISO.finditer(t):
        try:
            trovate.append((m.start(), date(int(m.group(1)), int(m.group(2)), int(m.group(3)))))
        except ValueError:
            pass
    for m in _DATA_NUMERICA.finditer(t):
        anno = int(m.group(3))
        anno = anno + 2000 if anno < 100 else anno
        try:
            trovate.append((m.start(), date(anno, int(m.group(2)), int(m.group(1)))))
        except ValueError:
            pass
    return [d for _, d in sorted(trovate, key=lambda x: x[0])]


def importo_nella_domanda(testo: str) -> float | None:
    m = _IMPORTO.search(_norm(testo))
    if not m:
        return None
    grezzo = (m.group(1) or m.group(2) or "").replace(".", "").replace(",", ".")
    try:
        return float(grezzo)
    except ValueError:
        return None


def _it(d: date) -> str:
    giorni = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]
    return f"{giorni[d.weekday()]} {d.strftime('%d/%m/%Y')}"


def _euro(valore: float) -> str:
    testo = f"{valore:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"€ {testo}"


def _calcola(codice: str, dal: date) -> dict[str, Any]:
    from pct.termini_processuali import DEFAULT_TEMPLATES, ItalianDeadlineCalculator

    modello = next(t for t in DEFAULT_TEMPLATES if t.code == codice)
    return ItalianDeadlineCalculator().calculate_template(dal, modello)


_FONTI_TERMINI = [
    {"title": "Art. 155 c.p.c. — computo dei termini", "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:regio.decreto:1940-10-28;1443~art155"},
    {"title": "L. 7 ottobre 1969, n. 742 — sospensione feriale", "url": "https://www.normattiva.it/eli/id/1969/11/06/069U0742/CONSOLIDATED"},
]
_AVVERTENZA_TERMINI = (
    "Calcolo del motore dei termini di IUSENTRA: esclude il giorno iniziale, sospende dal 1° al 31 agosto "
    "(L. 742/1969) e proroga al primo giorno non festivo (art. 155 c.p.c.). Verifica che la data di partenza "
    "sia quella giusta per il tuo caso."
)


def _risposta_171_ter(testo: str, date_: list[date]) -> RispostaCerta | None:
    if not re.search(r"171[\s-]*ter|memorie integrative", testo):
        return None
    if not date_:
        return RispostaCerta(
            "Per calcolare le memorie integrative dell'art. 171-ter c.p.c. mi serve la data dell'udienza di prima "
            "comparizione (es. «udienza del 20/01/2027»). Le memorie si depositano almeno 40, 20 e 10 giorni prima "
            "dell'udienza (termini liberi, a ritroso).",
            _FONTI_TERMINI, "termini_171_ter",
        )
    udienza = date_[-1]
    righe = [f"Udienza di prima comparizione: {_it(udienza)}.", ""]
    for numero, codice, contenuto in (
        (1, "CIV_MEMORIA_171_TER_1", "domande ed eccezioni conseguenti alla riconvenzionale o alle eccezioni altrui; precisazione o modifica delle domande"),
        (2, "CIV_MEMORIA_171_TER_2", "replica alle domande ed eccezioni nuove; mezzi di prova e produzioni documentali"),
        (3, "CIV_MEMORIA_171_TER_3", "replica alle eccezioni nuove e prova contraria"),
    ):
        esito = _calcola(codice, udienza)
        righe.append(f"- Memoria n. {numero}: entro **{_it(date.fromisoformat(esito['deadline']))}** — {contenuto}.")
    costituzione = _calcola("CIV_COSTITUZIONE_CONVENUTO_166", udienza)
    righe.extend([
        f"- Costituzione del convenuto: entro {_it(date.fromisoformat(costituzione['deadline']))} (almeno 70 giorni prima, art. 166 c.p.c.).",
        "",
        "Base normativa: art. 171-ter c.p.c. (termini liberi a ritroso di 40, 20 e 10 giorni dall'udienza).",
        "",
        _AVVERTENZA_TERMINI,
    ])
    return RispostaCerta("\n".join(righe), _FONTI_TERMINI + [{"title": "Art. 171-ter c.p.c.", "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:regio.decreto:1940-10-28;1443~art171ter"}], "termini_171_ter")


def _risposta_impugnazione(testo: str, date_: list[date]) -> RispostaCerta | None:
    if re.search(r"penal|tar\b|consiglio di stato|tributar|lavoro|amministrativ", testo):
        return None
    cassazione = bool(re.search(r"cassazione", testo)) and bool(re.search(r"ricorr|ricorso|impugn|termine|entro", testo))
    appello = bool(re.search(r"\bappell", testo))
    if not (cassazione or appello):
        return None
    if not re.search(r"termin|entro|quando|scad|quanto tempo|giorni", testo):
        return None
    nome = "ricorso per cassazione" if cassazione else "appello"
    per_nome = "per il ricorso per cassazione" if cassazione else "per l'appello"
    breve = "CIV_CASSAZIONE_BREVE" if cassazione else "CIV_APPELLO_BREVE"
    giorni = 60 if cassazione else 30
    notificata = bool(re.search(r"(?<!non )notificat", testo))
    pubblicata = bool(re.search(r"pubblicat|depositat", testo)) and not notificata
    if not date_:
        return RispostaCerta(
            f"Termine {per_nome} (sentenza civile): {giorni} giorni dalla notificazione della sentenza (termine breve, "
            "art. 325 c.p.c.); se la sentenza non è notificata, sei mesi dalla pubblicazione (termine lungo, art. 327 c.p.c.). "
            "Indicami la data di notificazione o di pubblicazione e calcolo la scadenza.",
            _FONTI_TERMINI, "termini_impugnazione",
        )
    dal = date_[0]
    if pubblicata:
        from pct.termini_processuali import ItalianDeadlineCalculator

        esito = ItalianDeadlineCalculator().calculate(dal, 6, period_type="months", suspend_august=True, template_code="CIV_LUNGO_327", reference_law="Art. 327 c.p.c.")
        righe = [
            f"Sentenza pubblicata il {_it(dal)}, non notificata: termine lungo di sei mesi (art. 327 c.p.c.).",
            f"Scadenza {per_nome}: **{_it(date.fromisoformat(esito['deadline']))}**.",
            f"Se la sentenza viene notificata prima, decorre il termine breve di {giorni} giorni (art. 325 c.p.c.).",
        ]
    else:
        esito = _calcola(breve, dal)
        righe = [
            f"Sentenza notificata il {_it(dal)}: termine breve di {giorni} giorni (art. 325 c.p.c.).",
            f"Scadenza {per_nome}: **{_it(date.fromisoformat(esito['deadline']))}**.",
            "Resta comunque fermo il termine lungo di sei mesi dalla pubblicazione (art. 327 c.p.c.), se scade prima.",
        ]
    righe.extend(["", _AVVERTENZA_TERMINI])
    return RispostaCerta("\n".join(righe), _FONTI_TERMINI, "termini_impugnazione")


def _risposta_opposizione_di(testo: str, date_: list[date]) -> RispostaCerta | None:
    if not re.search(r"(oppo\w*).{0,40}decreto ingiuntivo|decreto ingiuntivo.{0,40}(oppo\w*)", testo):
        return None
    if not re.search(r"termin|entro|quando|scad|giorni|quanto tempo", testo):
        return None
    base = (
        "Opposizione a decreto ingiuntivo: 40 giorni dalla notificazione del decreto (art. 641 c.p.c.); "
        "50 giorni se l'intimato risiede in un altro Stato dell'Unione europea, 60 giorni se risiede in uno Stato extra UE. "
        "L'opposizione si propone con atto di citazione davanti all'ufficio che ha emesso il decreto (art. 645 c.p.c.)."
    )
    if not date_:
        return RispostaCerta(base + " Indicami la data di notificazione e calcolo la scadenza.", _FONTI_TERMINI, "termini_opposizione_di")
    esito = _calcola("CIV_OPPOSIZIONE_DI", date_[0])
    testo_risposta = "\n".join([
        f"Decreto notificato il {_it(date_[0])}: scadenza dell'opposizione **{_it(date.fromisoformat(esito['deadline']))}** (40 giorni, art. 641 c.p.c.).",
        "",
        base,
        "",
        _AVVERTENZA_TERMINI,
    ])
    return RispostaCerta(testo_risposta, _FONTI_TERMINI, "termini_opposizione_di")


def _risposta_contributo(testo: str, _date: list[date], strumenti: Callable[[], Any] | None) -> RispostaCerta | None:
    if "contributo unificato" not in testo:
        return None
    valore = importo_nella_domanda(testo)
    if valore is None:
        return RispostaCerta(
            "Per calcolare il contributo unificato mi servono il valore della causa (es. «42.350 euro») e il tipo di "
            "procedimento (ordinario, decreto ingiuntivo, lavoro, appello, cassazione). Scaglioni: art. 13 D.P.R. 115/2002.",
            [{"title": "D.P.R. 115/2002, art. 13", "url": "https://www.normattiva.it/eli/id/2002/06/15/002G0139/CONSOLIDATED"}],
            "contributo_unificato",
        )
    categoria = "civile_ordinario"
    if re.search(r"decreto ingiuntivo|monitorio|ingiunzione", testo) and not re.search(r"opposizion", testo):
        categoria = "decreto_ingiuntivo"
    elif re.search(r"lavoro|previdenz", testo):
        categoria = "lavoro"
    grado = "cassazione" if "cassazione" in testo else "appello" if re.search(r"\bappell", testo) else "primo_grado"
    try:
        gestore = strumenti() if strumenti else None
        if gestore is None:
            from pct.strumenti_legali import GestioneStrumentiLegali

            gestore = GestioneStrumentiLegali()
        esito = gestore.calcola_contributo_unificato({"cu_categoria": categoria, "cu_grado": grado, "cu_valore": valore})
    except Exception:
        return None
    totale = esito.get("totale", esito.get("importo", esito.get("contributo")))
    if totale is None:
        return None
    etichette = {"civile_ordinario": "processo civile ordinario", "decreto_ingiuntivo": "ricorso per decreto ingiuntivo", "lavoro": "controversia di lavoro"}
    gradi = {"primo_grado": "primo grado", "appello": "appello (+50%)", "cassazione": "cassazione (doppio)"}
    righe = [
        f"Contributo unificato per {etichette[categoria]}, {gradi[grado]}, valore {_euro(valore)}: **{_euro(float(totale))}**.",
    ]
    for nota in list(esito.get("notes") or esito.get("note") or [])[:3]:
        righe.append(f"- {nota}")
    righe.extend([
        "",
        "Base normativa: art. 13 D.P.R. 115/2002 (scaglioni vigenti nelle tabelle normative di IUSENTRA). "
        "All'iscrizione a ruolo si aggiunge l'anticipazione forfettaria di € 27,00 (art. 30 D.P.R. 115/2002), "
        "salvo i casi in cui non è dovuta.",
    ])
    return RispostaCerta("\n".join(righe), [{"title": "D.P.R. 115/2002, art. 13", "url": "https://www.normattiva.it/eli/id/2002/06/15/002G0139/CONSOLIDATED"}], "contributo_unificato")


def risposta_certa(domanda: str, *, strumenti: Callable[[], Any] | None = None) -> RispostaCerta | None:
    testo = _norm(domanda)
    if not testo.strip():
        return None
    date_ = date_nella_domanda(domanda)
    for gestore in (_risposta_171_ter, _risposta_opposizione_di, _risposta_impugnazione):
        esito = gestore(testo, date_)
        if esito is not None:
            return esito
    return _risposta_contributo(testo, date_, strumenti)
