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
    righe: list[str] = field(default_factory=list)   # il testo con gli a capo: elenchi puntati e righe datate
    sede_assistita: str = ""

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
    "locazione": r"locazion|conduttor|locator|canon|inquilin|affitt(?!o (?:d |di |dell )?(?:azienda|ramo))|pigion",
    "morosita": r"moros|non (?:mi |ci |gli |le )?paga|mancato pagamento|canoni non pagati|non (?:mi |ci |gli |le )?ha pagato|non versa|arretrat|insolut",
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


# Limiti dell'estrazione: il lavoro non cresce senza misura con il testo dell'utente.
TESTO_MASSIMO = 20000
IMPORTI_MASSIMI = 200
EVENTI_MASSIMI = 200


def leggi_fatti(testo: str, *, oggi: date | None = None) -> Fatti:
    testo = str(testo or "")[:TESTO_MASSIMO]
    grezzo = " ".join(testo.split())
    t = piano(grezzo)
    # «Data di oggi: 16/11/2026», «Oggi è il 16/11/2026», «in data odierna (16/11/2026)»
    m_oggi = re.search(r"(?:data di oggi|oggi e il|oggi e|oggi,|in data odierna|data odierna)\s*:?\s*\(?(\d{1,2})/(\d{1,2})/(\d{4})", t)
    giorno = _data(m_oggi) if m_oggi else None
    f = Fatti(testo=grezzo, oggi=giorno or oggi or date.today())
    f.righe = [r.strip() for r in str(testo or "").splitlines() if r.strip()]
    # La parte assistita in tutte le formulazioni dell'avvocato: «Parte assistita: X», «Assisto X», «il mio cliente è X»,
    # «per conto di X», «difendo X», «rappresento X», «nell'interesse di X», «Cliente: X».
    f.assistita = _parte(r"(?i:parte assistita|assisto (?:il|la|lo) (?:locatore|locatrice|conduttore|conduttrice|moglie|marito|"
                         r"lavoratore|lavoratrice|creditore|creditrice|promissario acquirente|promittente venditore)|"
                         r"(?:il|la) mi[oa] client[ea] (?:e|è)|assisto|difendo|rappresento|per conto (?:di|del|della)|"
                         r"nell'interesse (?:di|del|della)|cliente\s*:|"
                         r"assistito|assistita|il mio cliente|la mia cliente|mio cliente|mia cliente|ricorrente)", grezzo)
    if f.assistita.nome and re.fullmatch(r"(?i)(?:il|la|lo|l|un|una|e|è)", f.assistita.nome.split()[0]):
        f.assistita = Parte()
    f.controparte = _parte(r"(?i:controparte|convenuto|resistente|debitore|conduttore moroso)", grezzo)
    if not f.controparte.nome:
        f.controparte = _parte(r"(?i:verso|contro|nei confronti di|dipendente di|alle dipendenze di|commissionat\w* a|affidat\w* a|"
                               r"incassare da|deve avere da|credito verso|debitrice|debitore|da parte di|il promittente venditore|"
                               r"la promittente venditrice|il venditore|il conduttore|il locatore|il datore di lavoro)", grezzo)
        if f.controparte.nome and f.controparte.nome == f.assistita.nome:
            f.controparte = Parte()
    if not f.controparte.nome:
        # «Beta Impianti s.p.a. non paga due fatture», «Rossi non ha pagato»
        m = re.search(_NOME + r"\s+(?:non (?:paga|ha pagato|ha saldato|ha restituito)|e debitric\w|è debitric\w|deve pagare)", grezzo)
        if m and m.group(1) != f.assistita.nome:
            nome = m.group(1).strip()
            f.controparte = Parte(nome, "", re.search(r"s\.?r\.?l|s\.?p\.?a|s\.?a\.?s|s\.?n\.?c|societa", piano(nome)) is not None)
    # Sede o residenza della parte assistita («Alfa s.r.l., con sede a Vicenza», «Assisto Alfa s.r.l. (Vicenza)»).
    if f.assistita.nome:
        m = re.search(re.escape(f.assistita.nome) + r"[^.;]{0,40}?(?:(?i:con sede|residente|domiciliat\w)\s+(?i:a|in)\s+|\()" + _CITTA, grezzo)
        if m:
            f.sede_assistita = m.group(1).strip()
    for m in _IMPORTO.finditer(grezzo):
        if len(f.importi) >= IMPORTI_MASSIMI:
            break
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
    # Frasi: con l'elenco dei «Fatti:» ogni voce è una frase; altrimenti si separa solo davanti a una maiuscola,
    # così «ex art. 1454» resta nella stessa frase.
    i_fatti = next((i for i, r in enumerate(f.righe) if re.match(r"(?i)(?:fatti del fascicolo|fatti|i fatti)\s*:?\s*$", r)), None)
    sorgente = ([r.lstrip("-•* ").strip() for r in f.righe[i_fatti + 1:]] if i_fatti is not None
                else re.split(r"(?<=[.;])\s+(?=[A-ZÀ-Ý])", grezzo))
    for frase in sorgente[:EVENTI_MASSIMI * 2]:
        if len(f.eventi) >= EVENTI_MASSIMI:
            break
        frase = re.sub(r"^(?:Fatti del fascicolo|Fatti)\s*:?\s*", "", frase.strip())
        for m in _DATA.finditer(frase):
            d = _data(m)
            if d and not (m_oggi and d == giorno and re.search(r"data di oggi|\boggi\b|data odierna", piano(frase))):
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
    if not f.richiesta and f.righe:
        # Testo libero: la richiesta è la domanda o il comando rivolto a Lex («Cosa facciamo…?», «Prepara l'atto…»);
        # se il testo è su più righe, il primo capoverso prima di «Oggi è il», delle parti e dei «Fatti:».
        primo = f.righe[0] if len(f.righe) > 1 else ""
        domande_primo = [x for x in re.split(r"(?<=[.?!])\s+(?=[A-ZÀ-Ý])", primo) if "?" in x or re.match(
            r"(?i)(?:prepar|redig|scriv|predispon|stend|fammi|mi serve|vorrei|valuta|dimmi|indica)", x.strip())]
        if primo and not re.match(r"(?i)(?:oggi|data di oggi|parte assistita|controparte|fatti)\b", primo):
            # Il primo capoverso può contenere fatti e domanda insieme: la richiesta è la domanda, se c'è.
            f.richiesta = piano(" ".join(domande_primo) if domande_primo and re.search(r"\d{1,2}/\d{1,2}/\d{4}", primo) else primo)
        else:
            frasi_testo = re.split(r"(?<=[.?!])\s+(?=[A-ZÀ-Ý])", grezzo)
            chieste = [x for x in frasi_testo if "?" in x or re.match(
                r"(?i)(?:prepar|redig|scriv|predispon|stend|fammi|mi serve|vorrei|valuta|dimmi|indica|cosa|come|quale|"
                r"possiamo|devo|dobbiamo)", x.strip())]
            f.richiesta = piano(" ".join(chieste))
    return f
