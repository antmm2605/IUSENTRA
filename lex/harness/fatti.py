"""Passo 2 dell'harness: i fatti scritti dall'avvocato, letti senza supporre nulla.

Si estraggono soltanto dati presenti nel testo (date, importi con la parola che li qualifica, parti con il loro ruolo,
luoghi di residenza o sede, immobile) e i segnali che le regole giuridiche usano (caparra confirmatoria, diffida
ex art. 1454 c.c., mediazione non avviata, rinuncia all'esecuzione in forma specifica…). Un dato che non c'è resta
vuoto: la risposta lo chiede o lo segna «[da completare]».
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

from .norme import piano

_DATA = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")
_IMPORTO = re.compile(r"(?:€|euro)\s*(\d{1,3}(?:\.\d{3})+(?:,\d{1,2})?|\d+(?:,\d{1,2})?)(?!\s*%)"
                      r"|(\d{1,3}(?:\.\d{3})+(?:,\d{1,2})?|\d+(?:,\d{1,2})?)\s*(?:€|euro)", re.I)
_NOME = r"([A-ZÀ-Ý][\w'’À-ÿ]+(?:\s+(?:di\s+|de\s+|del\s+)?[A-ZÀ-Ý][\w'’À-ÿ]+){0,3}(?:\s+(?:s\.?r\.?l\.?|s\.?p\.?a\.?|s\.?a\.?s\.?|s\.?n\.?c\.?))?)"
_CITTA = r"([A-ZÀ-Ý][a-zà-ÿ'’]+(?:\s+(?:di\s+)?[A-ZÀ-Ý][a-zà-ÿ'’]+)?)"


def _data(g: re.Match) -> date | None:
    try:
        return date(int(g.group(3)), int(g.group(2)), int(g.group(1)))
    except ValueError:
        return None


def euro(valore: float) -> str:
    testo = f"{valore:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return "€ " + (testo[:-3] if testo.endswith(",00") else testo)


def data_it(d: date | None) -> str:
    return d.strftime("%d/%m/%Y") if d else "[data da completare]"


@dataclass
class Importo:
    valore: float
    qualifica: str      # caparra | prezzo | canone | credito | retribuzione | danno | altro
    contesto: str


@dataclass
class Parte:
    nome: str = ""
    ruolo: str = ""      # testo fra parentesi o ruolo dichiarato
    persona_giuridica: bool = False


@dataclass
class Evento:
    data: date
    testo: str


@dataclass
class Fatti:
    testo: str
    oggi: date
    assistita: Parte = field(default_factory=Parte)
    controparte: Parte = field(default_factory=Parte)
    importi: list[Importo] = field(default_factory=list)
    eventi: list[Evento] = field(default_factory=list)
    residenza_convenuto: str = ""
    luogo_immobile: str = ""
    luogo_lavoro: str = ""
    segnali: set[str] = field(default_factory=set)
    richiesta: str = ""

    def importo(self, qualifica: str) -> Importo | None:
        return next((i for i in self.importi if i.qualifica == qualifica), None)

    def ha(self, segnale: str) -> bool:
        return segnale in self.segnali


_QUALIFICHE = (
    ("caparra", r"caparra"),
    ("prezzo", r"prezzo|corrispettivo della vendita"),
    ("canone", r"canon|mensilit|pigione|affitto"),
    ("retribuzione", r"retribu|stipend|differenz|tfr|trattamento di fine|straordinar|ferie"),
    ("danno", r"dann|risarc"),
    ("deposito", r"deposito cauzionale|cauzion"),
    ("credito", r"fattur|credit|debit|pagament|somm|importo|pagare|insolut|non pagat"),
)

_SEGNALI = {
    "caparra_confirmatoria": r"caparra confirmatoria|titolo di caparra|1385",
    "caparra_penitenziale": r"caparra penitenziale|1386",
    "preliminare": r"preliminare|compromesso",
    "diffida_1454": r"diffida ad adempiere|1454",
    "rogito_mancato": r"non si e presentat|mancata comparizione|non (?:ha )?stipulat|rifiutat\w* di stipulare|non e comparso",
    "no_2932": r"non vuole (?:il )?trasferimento coattivo|non (?:vuole|intende).{0,40}2932|senza (?:il )?2932",
    "mediazione_non_avviata": r"nessuna (?:procedura di )?mediazione|mediazione non (?:e stata )?avviata|non (?:e stata )?avviata (?:alcuna )?mediazione",
    "negoziazione_non_avviata": r"nessuna negoziazione|negoziazione non (?:e stata )?avviata",
    "recesso": r"recedere|recesso",
    "doppio_caparra": r"doppio della caparra|doppio",
    "vendita_a_terzi": r"terzi|agenzia|annuncio",
    "consumatore": r"\bconsumator",
    "professionista_impresa": r"\bimpres|\bsocieta\b|s\.r\.l|srl\b|s\.p\.a|spa\b|professionista|negozio|venditore professionale",
    "circolazione": r"incidente stradale|sinistro stradale|circolazione|tamponament|veicol",
    "abitativo": r"abitativ|appartamento|abitazione",
    "locazione": r"locazion|conduttor|locator|canon",
    "morosita": r"moros|non paga|mancato pagamento|canoni non pagati|non ha pagato",
    "figli_minori": r"figli\w* minor|minore|minorenn",
    "lavoro_subordinato": r"dipendent|subordinat|lavorator|datore di lavoro",
    "licenziamento": r"licenzia",
    "fattura": r"fattur",
    "titolo_giudiziale": r"sentenza|decreto ingiuntivo esecutivo|titolo esecutivo|ordinanza",
    "condominio": r"condomin",
    "interessi": r"interess",
    "rivalutazione": r"rivalutaz",
}


def _parte(etichetta: str, testo: str) -> Parte:
    m = re.search(etichetta + r"\s*:?\s*" + _NOME + r"\s*(?:\(([^)]*)\))?", testo)
    if not m:
        return Parte()
    nome = m.group(1).strip()
    ruolo = (m.group(2) or "").strip()
    pg = re.search(r"s\.?r\.?l|s\.?p\.?a|s\.?a\.?s|s\.?n\.?c|societa", piano(nome)) is not None
    return Parte(nome, ruolo, pg)


def _qualifica(contesto: str) -> str:
    c = piano(contesto)
    for nome, espr in _QUALIFICHE:
        if re.search(espr, c):
            return nome
    return "altro"


def leggi_fatti(testo: str, *, oggi: date | None = None) -> Fatti:
    grezzo = " ".join(str(testo or "").split())
    t = piano(grezzo)
    m_oggi = re.search(r"data di oggi\s*:?\s*(\d{1,2})/(\d{1,2})/(\d{4})", t)
    giorno = _data(m_oggi) if m_oggi else None
    f = Fatti(testo=grezzo, oggi=giorno or oggi or date.today())
    f.assistita = _parte(r"(?i:parte assistita|assisto (?:il|la|lo) (?:locatore|locatrice|conduttore|conduttrice|moglie|marito|"
                         r"lavoratore|lavoratrice|creditore|creditrice|promissario acquirente|promittente venditore)|"
                         r"assistito|assistita|il mio cliente|la mia cliente|mio cliente|mia cliente|ricorrente)", grezzo)
    f.controparte = _parte(r"(?i:controparte|convenuto|resistente|debitore|conduttore moroso)", grezzo)
    if not f.controparte.nome:
        f.controparte = _parte(r"(?i:verso|contro|nei confronti di|dipendente di|alle dipendenze di|il promittente venditore|"
                               r"la promittente venditrice|il venditore|il conduttore|il locatore|il datore di lavoro)", grezzo)
        if f.controparte.nome and f.controparte.nome == f.assistita.nome:
            f.controparte = Parte()
    for m in _IMPORTO.finditer(grezzo):
        grezzo_num = (m.group(1) or m.group(2) or "").replace(".", "").replace(",", ".")
        try:
            valore = float(grezzo_num)
        except ValueError:
            continue
        if valore < 1:
            continue
        contesto = grezzo[max(0, m.start() - 70): m.end() + 40]
        # La qualifica più vicina vince: prima le parole che seguono l'importo («25.000 euro a titolo di caparra»),
        # poi quelle immediatamente prima («canone di 700 euro»), poi il contesto più ampio.
        qualifica = _qualifica(grezzo[m.end(): m.end() + 45])
        if qualifica == "altro":
            qualifica = _qualifica(grezzo[max(0, m.start() - 30): m.start()])
        if qualifica == "altro":
            qualifica = _qualifica(grezzo[max(0, m.start() - 70): m.end() + 15])
        f.importi.append(Importo(valore, qualifica, contesto))
    # Frasi: si separa solo davanti a una maiuscola, così «ex art. 1454» resta nella stessa frase.
    for frase in re.split(r"(?<=[.;])\s+(?=[A-ZÀ-Ý])", grezzo):
        frase = re.sub(r"^(?:Fatti del fascicolo|Fatti)\s*:?\s*", "", frase.strip())
        for m in _DATA.finditer(frase):
            d = _data(m)
            if d and not (m_oggi and d == giorno and "data di oggi" in piano(frase)):
                f.eventi.append(Evento(d, frase.strip()))
                break
    # Le parole chiave non distinguono maiuscole; il nome della città sì («a Lecce non paga» → «Lecce»).
    luogo = r"(?i:residente|residenti|domiciliat\w|con sede legale|con sede)\s+(?i:a|in)\s+" + _CITTA
    candidati = [r"(?i:residenza del convenuto)\s*:?\s*" + _CITTA]
    if f.controparte.nome:
        candidati.append(re.escape(f.controparte.nome) + r"[^.;]{0,60}?" + luogo)
    candidati += [r"(?i:convenuto|controparte|debitore|datore|conduttore)[^.]{0,80}?" + luogo]
    if not f.assistita.nome:
        candidati.append(luogo)
    for espr in candidati:
        m = re.search(espr, grezzo)
        if m:
            f.residenza_convenuto = m.group(1).strip()
            break
    m = re.search(r"(?i:immobile|appartamento|locale|negozio|unita immobiliare|villa|box)[^.]{0,30}?\b(?i:in|a|sito in|sito a)\s+" + _CITTA, grezzo)
    if m:
        f.luogo_immobile = m.group(1).strip()
    m = re.search(r"(?i:sede di lavoro)\s*:?\s*" + _CITTA, grezzo) or re.search(
        r"(?i:lavorato|lavora|prestato servizio|presta servizio|addetto)[^.]{0,40}?\b(?i:a|in|presso la sede di)\s+" + _CITTA, grezzo)
    if m:
        f.luogo_lavoro = m.group(1).strip()
    for nome, espr in _SEGNALI.items():
        if re.search(espr, t):
            f.segnali.add(nome)
    m = re.search(r"richiesta dell avvocato\s*:?\s*(.+?)(?:fatti del fascicolo|$)", t)
    f.richiesta = m.group(1).strip() if m else ""
    return f
