"""Regolamenti UE nell'archivio di Lex: testo italiano della Gazzetta ufficiale dell'Unione europea, diviso in articoli.

Fonte: Ufficio delle pubblicazioni dell'Unione europea (``publications.europa.eu/resource/celex/<CELEX>``, negoziazione del
contenuto con ``Accept: application/xhtml+xml`` e ``Accept-Language: ita``). eur-lex.europa.eu risponde con una challenge
anti-bot e non si usa. Per ogni atto si prova il **testo consolidato** piu' recente (CELEX ``0AAAAR NNNN-AAAAMMGG``, elenco
dall'endpoint SPARQL ufficiale ``publications.europa.eu/webapi/rdf/sparql``); se non e' disponibile resta il **testo
originale pubblicato in GUUE** (modifiche successive non incluse). Il titolo dell'atto dice quale dei due e'.

Formati riconosciuti (tutti ridotti a una sequenza di righe con le classi dell'elemento che le contiene):

- GUUE ``oj-`` (2004-oggi, ELI): ``p.oj-ti-art`` «Articolo N», ``p.oj-sti-art`` rubrica, paragrafi ``oj-normal``,
  elenchi in tabelle a due colonne («a)» | testo);
- GUUE «vecchio»: ``p.ti-art`` / ``p.sti-art`` con i paragrafi fino al ``ti-art`` successivo;
- consolidato (CONVEX): ``p.title-article-norm`` / ``p.stitle-article-norm``, paragrafi ``.norm``, elenchi in ``div``
  rientrati o ``grid-container`` (anche dentro ``div#art_N``), marcatori di modifica ``►M1`` ``▼B`` ``◄`` tolti;
- HTML semplice (atti anteriori a maggio 2004, manifestazione ``text/html``): ``<p>Articolo N</p><p>Rubrica</p>``.

Considerando, formula finale, firme, note e allegati sono esclusi. Il testo segue lo stile dell'archivio Normattiva:
``Art. N. (Rubrica). 1. ... 2. ... a) ... b) ...``.
"""

from __future__ import annotations

import datetime as _dt
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

URI_CELEX = "https://publications.europa.eu/resource/celex/{celex}"
SPARQL = "https://publications.europa.eu/webapi/rdf/sparql"
FONTE_TESTO = "publications.europa.eu (GUUE)"


@dataclass(frozen=True)
class RegolamentoUE:
    celex: str            # "32012R1215"
    nome: str             # nome breve d'uso: "Bruxelles I-bis"

    @property
    def anno(self) -> str:
        return self.celex[1:5]

    @property
    def numero(self) -> str:
        return str(int(self.celex[6:]))

    @property
    def chiave(self) -> str:
        return f"reg_ue_{self.anno}_{self.numero}"


# Regolamenti integrati (2.436.11). Le sigle e gli alias per ricerca e citazioni sono in lex/ricerca_giuridica/testo.py.
REGOLAMENTI: tuple[RegolamentoUE, ...] = (
    RegolamentoUE("32012R1215", "Bruxelles I-bis"),
    RegolamentoUE("32007R0861", "controversie di modesta entità"),
    RegolamentoUE("32006R1896", "ingiunzione di pagamento europea"),
    RegolamentoUE("32004R0805", "titolo esecutivo europeo"),
    RegolamentoUE("32014R0655", "ordinanza europea di sequestro conservativo su conti bancari"),
    RegolamentoUE("32008R0593", "Roma I"),
    RegolamentoUE("32007R0864", "Roma II"),
    RegolamentoUE("32019R1111", "Bruxelles II-ter"),
    RegolamentoUE("32010R1259", "Roma III"),
    RegolamentoUE("32012R0650", "successioni"),
    RegolamentoUE("32020R1784", "notificazione degli atti"),
    RegolamentoUE("32020R1783", "assunzione delle prove"),
    RegolamentoUE("32004R0261", "diritti dei passeggeri aerei"),
    RegolamentoUE("32015R0848", "insolvenza"),
    RegolamentoUE("32014R0910", "eIDAS"),
    RegolamentoUE("32024R1689", "intelligenza artificiale"),
)
REGOLAMENTI_PER_CELEX = {r.celex: r for r in REGOLAMENTI}

_MESI = {m: i for i, m in enumerate(
    "gennaio febbraio marzo aprile maggio giugno luglio agosto settembre ottobre novembre dicembre".split(), start=1)}
_SUFFISSI = "bis|ter|quater|quinquies|sexies|septies|octies|nonies|novies|decies|undecies|duodecies"
INTESTAZIONE_RE = re.compile(rf"^Articolo\s*(\d{{1,3}})(?:\s*[-‑]?\s*({_SUFFISSI}|[a-z]))?\s*\.?$")
_CLASSI_ARTICOLO = {"ti-art", "oj-ti-art", "title-article-norm"}
_CLASSI_RUBRICA = {"sti-art", "oj-sti-art", "stitle-article-norm"}
# fine dell'articolo corrente: titoli di capo/sezione, allegati, formula finale, firme, fine del documento
_CLASSI_FINE = {
    "ti-section-1", "ti-section-2", "oj-ti-section-1", "oj-ti-section-2", "title-division-1", "title-division-2",
    "title-gr-seq-level-1", "title-gr-seq-level-2", "title-gr-seq-level-3", "oj-ti-grseq-1", "ti-grseq-1",
    "title-annex-1", "title-annex-2", "oj-ti-annex", "ti-annex", "separator-annex", "oj-doc-end", "doc-end",
    "final", "oj-final", "signatory", "oj-signatory", "title-doc-first", "oj-doc-ti", "doc-ti",
}
# fine del dispositivo: dopo allegati, formula finale e firme nessuna riga «Articolo N» e' piu' un articolo
_CLASSI_STOP = {
    "title-annex-1", "title-annex-2", "oj-ti-annex", "ti-annex", "separator-annex", "oj-doc-end", "doc-end",
    "final", "oj-final", "signatory", "oj-signatory",
}
# elementi da non leggere: marcatori di modifica, note, immagini, intestazione della pagina
_CLASSI_SALTA = {
    "arrow", "modref", "footnote", "oj-note", "note", "oj-note-tag", "note-tag", "oj-hd-date", "oj-hd-lg",
    "oj-hd-ti", "oj-hd-oj", "hd-date", "hd-lg", "hd-ti", "hd-oj", "disclaimer", "hd-modifiers", "hd-toc-1",
    "hd-toc-2", "hd-toc-3", "toc-1", "toc-2", "title-fam-member", "title-fam-member-star", "reference",
}
_TAG_SALTA = {"script", "style", "head", "img", "title", "meta", "link", "col", "colgroup"}
_TAG_BLOCCO = {"p", "div", "td", "th", "tr", "table", "tbody", "thead", "li", "ul", "ol", "dl", "dt", "dd", "br",
               "h1", "h2", "h3", "h4", "h5", "h6", "body", "html", "hr", "txt_te"}
_DIVISIONE_TESTO_RE = re.compile(r"^(?:CAPO|SEZIONE|TITOLO|PARTE|CAPITOLO|Capo|Sezione|Titolo|Parte|Capitolo)\s+"
                                 r"(?:[IVXLCDM]+|\d+|PRIMO|SECONDO|TERZO|UNICO)(?:\s*(?:bis|ter|BIS|TER))?\s*$")
_FINE_TESTO_RE = re.compile(r"^(?:Il presente regolamento è obbligatorio in tutti i suoi elementi|Fatto a\s|ALLEGATO\b|"
                            r"Allegato\s+[IVXLCDM\d]+\s*$)")
_ETICHETTA_RE = re.compile(r"^(?:\(?[0-9]{1,3}[a-z]?\)|\(?[a-z]{1,2}\)|\(?[ivxlc]{1,6}\)|[0-9]{1,3}\.|[—–-]|•|\*)$")
# «►M1», «►C2», «▼B», «◄»: marcatori di modifica/rettifica dei consolidati (il codice e' attaccato alla freccia)
_MARCATORI_MODIFICA_RE = re.compile(r"[►▼][A-Z]{1,2}\d{0,3}(?![\w'])|[►▼◄]")


@dataclass
class ArticoloUE:
    numero: str           # "7", "71bis"
    rubrica: str
    righe: list[str] = field(default_factory=list)

    @property
    def visibile(self) -> str:
        return re.sub(r"^(\d+)([a-z]+)$", r"\1-\2", self.numero)

    @property
    def corpo(self) -> str:
        return " ".join(self.righe).strip()

    @property
    def testo(self) -> str:
        """Stile Normattiva: «Art. 71-bis. (Rubrica). 1. ...»."""
        rubrica = f" ({self.rubrica.rstrip('.')})." if self.rubrica else ""
        return f"Art. {self.visibile}.{rubrica} {self.corpo}".strip()


@dataclass
class AttoUE:
    titolo: str                       # "Regolamento (UE) n. 1215/2012 del Parlamento europeo e del Consiglio, del ..."
    data_atto: str                    # "2012-12-12"
    tipo: str                         # "UE" / "CE"
    numero: str                       # "1215"
    anno: str                         # "2012"
    formato: str                      # "oj" / "vecchio" / "consolidato" / "html"
    articoli: list[ArticoloUE] = field(default_factory=list)
    intestazioni: int = 0             # righe «Articolo N» riconosciute come intestazione nel documento

    @property
    def sigla(self) -> str:
        """«Reg. UE 1215/2012», «Reg. CE 861/2007», «Reg. UE 2015/848» (dal 2015 l'anno viene prima)."""
        riferimento = f"{self.anno}/{self.numero}" if int(self.anno) >= 2015 else f"{self.numero}/{self.anno}"
        return f"Reg. {self.tipo} {riferimento}"


# --------------------------------------------------------------------------------------------- #
# Righe del documento                                                                            #
# --------------------------------------------------------------------------------------------- #

@dataclass
class _Riga:
    testo: str
    classi: frozenset[str]


def _pulisci(testo: str) -> str:
    valore = str(testo or "").replace("\xa0", " ").replace(" ", " ").replace(" ", " ")
    valore = valore.replace("’", "'").replace("‘", "'").replace("­", "")
    valore = _MARCATORI_MODIFICA_RE.sub(" ", valore)
    valore = re.sub(r"\s+", " ", valore).strip()
    valore = re.sub(r"\(\s*\)", "", valore)            # rimando a nota tolto: «(1)» -> «()»
    valore = re.sub(r"\s+([,;:.)])", r"\1", valore)
    valore = re.sub(r"\(\s+", "(", valore)
    return re.sub(r"\s{2,}", " ", valore).strip()


def _classi(el) -> set[str]:
    return set(str(el.get("class") or "").split())


def _e_rimando_nota(el) -> bool:
    """«(<a href="#E0001"><span class="superscript">1</span></a>)» e «<span class="oj-note-tag">»: rimandi alle note."""
    tag = el.tag if isinstance(el.tag, str) else ""
    if tag.lower() == "a":
        href = str(el.get("href") or "")
        testo = "".join(el.itertext()).strip()
        if href.startswith("#") and re.fullmatch(r"[\d*†]{1,3}", testo or "x"):
            return True
        if str(el.get("id") or "").startswith("src."):
            return True
    return False


def righe_documento(html: bytes | str) -> list[_Riga]:
    """Il documento come righe di testo (una per blocco), ciascuna con le classi degli elementi che l'hanno aperta."""

    import lxml.html

    if isinstance(html, bytes):
        try:
            # l'HTML semplice dichiara «charset=UNICODE-1-1-UTF-8», che lxml non riconosce (leggerebbe latin-1)
            html = html.decode("utf-8")
        except UnicodeDecodeError:
            html = html.decode("latin-1")
    testo_html = re.sub(r"^\s*<\?xml[^>]*\?>", "", html)
    radice = lxml.html.document_fromstring(testo_html)
    righe: list[_Riga] = []
    corrente: list[str] = []
    classi: set[str] = set()

    def chiudi() -> None:
        testo = _pulisci("".join(corrente))
        if testo:
            righe.append(_Riga(testo, frozenset(classi)))
        corrente.clear()
        classi.clear()

    def visita(el) -> None:
        tag = el.tag.lower() if isinstance(el.tag, str) else ""
        if not tag:  # commenti, istruzioni di elaborazione
            if el.tail:
                corrente.append(el.tail)
            return
        proprie = _classi(el)
        if tag in _TAG_SALTA or proprie & _CLASSI_SALTA or _e_rimando_nota(el):
            if el.tail:
                corrente.append(el.tail)
            return
        blocco = tag in _TAG_BLOCCO
        if blocco:
            chiudi()
        classi.update(proprie)
        if el.text:
            corrente.append(el.text)
        for figlio in el:
            visita(figlio)
        if blocco:
            chiudi()
        else:
            classi.update(proprie)
        if el.tail:
            corrente.append(el.tail)

    visita(radice)
    chiudi()
    return righe


def _unisci_etichette(righe: list[str]) -> list[str]:
    """«a)» / «1)» / «—» da soli su una riga (prima colonna delle tabelle degli elenchi) si uniscono al testo seguente."""
    uscita: list[str] = []
    sospesa = ""
    for riga in righe:
        if _ETICHETTA_RE.match(riga):
            sospesa = f"{sospesa} {riga}".strip()
            continue
        uscita.append(f"{sospesa} {riga}".strip() if sospesa else riga)
        sospesa = ""
    if sospesa:
        uscita.append(sospesa)
    return uscita


# --------------------------------------------------------------------------------------------- #
# Titolo e data                                                                                  #
# --------------------------------------------------------------------------------------------- #

_TITOLO_RE = re.compile(
    r"REGOLAMENTO\s+(?:DI ESECUZIONE\s+|DELEGATO\s+)?\((UE|CE|CEE|UE,\s*Euratom)\)\s+(?:N\.?\s*)?(\d{1,4})/(\d{2,4})\s*(.*)$",
    re.I,
)
_DATA_RE = re.compile(r"^(?:del|dell'|dell’)\s*(\d{1,2})(?:°|º)?\s+([a-z]+)\s+(\d{4})", re.I)


def _data_iso(riga: str) -> str:
    m = _DATA_RE.match(riga.strip())
    if not m or m.group(2).lower() not in _MESI:
        return ""
    return _dt.date(int(m.group(3)), _MESI[m.group(2).lower()], int(m.group(1))).isoformat()


def _emittente(testo: str) -> str:
    valore = testo.strip().lower()
    for nome in ("parlamento europeo", "consiglio", "commissione"):
        valore = valore.replace(nome, nome[0].upper() + nome[1:])
    return valore


def titolo_e_data(righe: list[_Riga]) -> tuple[str, str, str, str, str]:
    """(titolo, data ISO, tipo UE/CE, numero, anno) dalle prime righe del documento."""

    for i, riga in enumerate(righe[:400]):
        m = _TITOLO_RE.search(riga.testo)
        if not m:
            continue
        tipo, primo, secondo, resto = m.group(1).upper().replace(" ", ""), m.group(2), m.group(3), m.group(4)
        # «(UE) 2015/848» (anno/numero dal 2015) o «(UE) n. 1215/2012» (numero/anno)
        if len(primo) == 4 and len(secondo) <= 4 and int(primo) >= 2015 and not re.search(r"\bN\.?\s*\d", riga.testo, re.I):
            anno, numero = primo, str(int(secondo))
        else:
            numero, anno = str(int(primo)), secondo if len(secondo) == 4 else ("19" + secondo)
        data = ""
        parti_titolo: list[str] = []
        emittente = resto
        # HTML semplice: «Regolamento (CE) n. 805/2004 del Parlamento europeo e del Consiglio, del 21 aprile 2004, che ...»
        m_data = re.search(r",\s*(del|dell')\s*(\d{1,2})\s+([a-z]+)\s+(\d{4}),?\s*(.*)$", resto or "", re.I)
        if m_data:
            data = _data_iso(f"{m_data.group(1)} {m_data.group(2)} {m_data.group(3)} {m_data.group(4)}")
            emittente = resto[:m_data.start()]
            if data and m_data.group(5):
                parti_titolo.append(m_data.group(5))
        for successiva in ([] if data else righe[i + 1:i + 6]):
            testo = successiva.testo.strip()
            if not data:
                data = _data_iso(testo)
                if data:
                    continue
            if re.match(r"^\(Testo rilevante", testo, re.I) or not testo:
                continue
            if testo.isupper() or re.match(r"^(?:IL PARLAMENTO|IL CONSIGLIO|LA COMMISSIONE)", testo):
                break
            if data:
                parti_titolo.append(testo)
            if len(parti_titolo) >= 2:
                break
        riferimento = f"{anno}/{numero}" if int(anno) >= 2015 else f"n. {numero}/{anno}"
        intestazione = f"Regolamento ({tipo.replace(',', ', ')}) {riferimento} {_emittente(emittente)}".strip()
        giorno = ""
        if data:
            d = _dt.date.fromisoformat(data)
            articolo = "dell'" if d.day in (8, 11) else "del "
            giorno = f", {articolo}{'1°' if d.day == 1 else d.day} {list(_MESI)[d.month - 1]} {d.year}"
        corpo = " ".join(parti_titolo).strip()
        corpo = re.sub(r"\s*\(GU [^)]*\)\s*$", "", corpo)  # rimando alla Gazzetta nel titolo dei consolidati
        titolo = f"{intestazione}{giorno}" + (f", {corpo}" if corpo else "")
        return _pulisci(titolo), data, ("CE" if tipo.startswith("CE") else "UE"), numero, anno
    raise ValueError("titolo dell'atto non trovato (nessuna riga «REGOLAMENTO (UE|CE) ...»)")


# --------------------------------------------------------------------------------------------- #
# Divisione in articoli                                                                          #
# --------------------------------------------------------------------------------------------- #

def _numero_articolo(testo: str) -> str | None:
    m = INTESTAZIONE_RE.match(testo.strip())
    if not m:
        return None
    suffisso = (m.group(2) or "").lower().replace("nonies", "novies")
    return f"{int(m.group(1))}{suffisso}"


def _formato(righe: list[_Riga]) -> str:
    tutte: set[str] = set()
    for r in righe:
        tutte |= r.classi
    if "title-article-norm" in tutte:
        return "consolidato"
    if "oj-ti-art" in tutte:
        return "oj"
    if "ti-art" in tutte:
        return "vecchio"
    return "html"


def _sembra_rubrica(testo: str) -> bool:
    return (len(testo) <= 160 and not re.match(r"^(?:\(?\d+[.)]|\(?[a-z]\)|[—–-])", testo)
            and not re.search(r"[.;:,]$", testo) and testo[:1].isupper())


def dividi(html: bytes | str) -> AttoUE:
    """XHTML (o HTML) della GUUE -> atto con titolo, data e articoli (senza considerando, firme e allegati)."""

    righe = righe_documento(html)
    titolo, data, tipo, numero, anno = titolo_e_data(righe)
    formato = _formato(righe)
    # rubrica senza classe propria (consolidati piu' vecchi, HTML semplice): prima riga breve senza punteggiatura finale
    rubrica_per_posizione = formato == "html" or not any(r.classi & _CLASSI_RUBRICA for r in righe)
    atto = AttoUE(titolo=titolo, data_atto=data, tipo=tipo, numero=numero, anno=anno, formato=formato)
    in_articolo: ArticoloUE | None = None
    attesa_rubrica = False
    corpo: list[str] = []
    dispositivo = formato != "html"  # nell'HTML semplice gli articoli iniziano dopo «HANNO ADOTTATO ...»

    def chiudi() -> None:
        nonlocal in_articolo, corpo
        if in_articolo is not None:
            in_articolo.righe = _unisci_etichette(corpo)
            atto.articoli.append(in_articolo)
        in_articolo = None
        corpo = []

    for riga in righe:
        testo = riga.testo
        if not dispositivo:
            if re.search(r"HA(?:NNO)? ADOTTATO IL PRESENTE REGOLAMENTO", testo, re.I):
                dispositivo = True
            continue
        numero_art = _numero_articolo(testo)
        e_intestazione = numero_art is not None and (
            bool(riga.classi & _CLASSI_ARTICOLO) if formato != "html" else True)
        if e_intestazione:
            atto.intestazioni += 1
            chiudi()
            in_articolo = ArticoloUE(numero=numero_art or "", rubrica="")
            attesa_rubrica = True
            continue
        if riga.classi & _CLASSI_STOP or _FINE_TESTO_RE.match(testo):
            chiudi()
            break
        if in_articolo is not None and (riga.classi & _CLASSI_FINE or _DIVISIONE_TESTO_RE.match(testo)):
            chiudi()
            attesa_rubrica = False
            continue
        if in_articolo is None:
            continue
        if attesa_rubrica:
            attesa_rubrica = False
            if riga.classi & _CLASSI_RUBRICA:
                in_articolo.rubrica = testo
                continue
            if rubrica_per_posizione and _sembra_rubrica(testo):
                in_articolo.rubrica = testo
                continue
        corpo.append(testo)
    chiudi()
    return atto


def mancanti(atto: AttoUE) -> list[int]:
    """Numeri da 1 all'ultimo «Articolo N» senza articolo (nei consolidati: articoli soppressi, assenti dal testo)."""
    base = {int(a.numero) for a in atto.articoli if a.numero.isdigit()}
    return sorted(set(range(1, ultimo_articolo(atto) + 1)) - base)


def controlla(atto: AttoUE, *, soppressi_ammessi: Iterable[int] = ()) -> list[str]:
    """Errori bloccanti: numerazione con buchi o doppioni, articoli vuoti, intestazioni d'articolo dentro un testo.

    ``soppressi_ammessi``: numeri che possono mancare (articoli soppressi che il testo consolidato non riporta).
    """

    errori: list[str] = []
    if not atto.articoli:
        return ["nessun articolo trovato"]
    if atto.intestazioni and atto.intestazioni != len(atto.articoli):
        errori.append(f"intestazioni «Articolo N» nel documento: {atto.intestazioni}, articoli letti: {len(atto.articoli)}")
    if not atto.data_atto:
        errori.append("data dell'atto non trovata")
    visti: set[str] = set()
    for art in atto.articoli:
        if art.numero in visti:
            errori.append(f"articolo {art.visibile} ripetuto")
        visti.add(art.numero)
        if not art.corpo:
            errori.append(f"articolo {art.visibile} vuoto")
        for r in art.righe:
            if _numero_articolo(r) is not None:
                errori.append(f"articolo {art.visibile}: contiene l'intestazione «{r}» di un altro articolo")
    assenti = [n for n in mancanti(atto) if n not in set(soppressi_ammessi)]
    if assenti:
        errori.append(f"articoli mancanti: {assenti[:10]} (ultimo: Articolo {ultimo_articolo(atto)})")
    ordine = [int(re.match(r"\d+", a.numero).group(0)) for a in atto.articoli]
    if ordine != sorted(ordine):
        errori.append("articoli fuori ordine")
    corpi: dict[str, str] = {}
    for art in atto.articoli:
        if len(art.corpo) > 80 and art.corpo in corpi:
            errori.append(f"articoli {corpi[art.corpo]} e {art.visibile} con lo stesso testo")
        corpi.setdefault(art.corpo, art.visibile)
    return errori


def ultimo_articolo(atto: AttoUE) -> int:
    return max((int(re.match(r"\d+", a.numero).group(0)) for a in atto.articoli), default=0)


# --------------------------------------------------------------------------------------------- #
# Righe JSONL (stesso formato di lex/normativa/integrazioni/leggi_essenziali.jsonl)              #
# --------------------------------------------------------------------------------------------- #

def urn_atto(atto: AttoUE) -> str:
    return f"urn:nir:unione.europea:regolamento:{atto.data_atto};{atto.numero}"


def titolo_con_versione(atto: AttoUE, consolidato_al: str = "") -> str:
    titolo = atto.titolo.rstrip(".")
    if consolidato_al:
        giorno = _dt.date.fromisoformat(consolidato_al).strftime("%d/%m/%Y")
        return f"{titolo}. [Testo consolidato al {giorno}, Ufficio delle pubblicazioni UE]"
    return f"{titolo}. [Testo originale pubblicato in GUUE: modifiche successive non incluse]"


def righe_jsonl(atto: AttoUE, *, chiave: str, url: str, consolidato_al: str = "", raccolto_il: str = "") -> list[dict[str, Any]]:
    raccolto = raccolto_il or _dt.date.today().isoformat()
    titolo = titolo_con_versione(atto, consolidato_al)
    return [
        {
            "atto": atto.sigla, "chiave": chiave, "articolo": art.numero, "rubrica": art.rubrica, "testo": art.testo,
            "titolo_atto": titolo, "data_atto": atto.data_atto, "urn": urn_atto(atto), "fonte_testo": FONTE_TESTO,
            "url": url, "raccolto_il": raccolto,
        }
        for art in atto.articoli
    ]


# --------------------------------------------------------------------------------------------- #
# Scaricamento (Ufficio delle pubblicazioni)                                                     #
# --------------------------------------------------------------------------------------------- #

def consolidati_disponibili(celex: str, *, sessione=None, timeout: float = 90.0) -> list[str]:
    """CELEX consolidati dell'atto (es. ['02012R1215-20150110', '02012R1215-20150226']) dall'endpoint SPARQL ufficiale."""

    import requests

    radice = "0" + celex[1:]
    query = (
        "PREFIX cdm: <http://publications.europa.eu/ontology/cdm#> SELECT DISTINCT ?celex WHERE { "
        f"?w cdm:resource_legal_id_celex ?celex . FILTER(STRSTARTS(STR(?celex), \"{radice}-\")) }}"
    )
    client = sessione or requests
    risposta = client.get(SPARQL, params={"query": query}, headers={"Accept": "application/sparql-results+json"},
                          timeout=timeout)
    risposta.raise_for_status()
    valori = [b["celex"]["value"] for b in risposta.json().get("results", {}).get("bindings", [])]
    return sorted({v for v in valori if re.fullmatch(rf"{radice}-\d{{8}}", v)})


def data_consolidato(celex_consolidato: str) -> str:
    m = re.search(r"-(\d{4})(\d{2})(\d{2})$", celex_consolidato)
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else ""


def scarica_documento(celex: str, cartella_cache: Path, *, sessione=None, offline: bool = False,
                      timeout: float = 180.0) -> tuple[Path | None, str]:
    """XHTML (o, per gli atti piu' vecchi, HTML) in italiano; cache in ``cartella_cache``. (percorso, esito)."""

    cartella_cache.mkdir(parents=True, exist_ok=True)
    for estensione in ("xhtml", "html"):
        percorso = cartella_cache / f"{celex}.{estensione}"
        if percorso.exists() and percorso.stat().st_size > 1000:
            return percorso, "cache"
    if offline:
        return None, "non in cache"
    import requests

    client = sessione or requests
    for accept, estensione in (("application/xhtml+xml", "xhtml"), ("text/html", "html")):
        risposta = client.get(URI_CELEX.format(celex=celex), headers={"Accept": accept, "Accept-Language": "ita"},
                              timeout=timeout, allow_redirects=True)
        tipo = risposta.headers.get("Content-Type", "")
        if risposta.status_code == 200 and ("html" in tipo) and len(risposta.content) > 1000:
            percorso = cartella_cache / f"{celex}.{estensione}"
            percorso.write_bytes(risposta.content)
            return percorso, f"scaricato ({accept})"
    return None, f"HTTP {risposta.status_code}"


@dataclass
class EsitoAtto:
    regolamento: RegolamentoUE
    celex_usato: str = ""
    consolidato_al: str = ""
    atto: AttoUE | None = None
    errori: list[str] = field(default_factory=list)
    note: list[str] = field(default_factory=list)
    soppressi: list[int] = field(default_factory=list)

    @property
    def valido(self) -> bool:
        return self.atto is not None and not self.errori


def _atto_originale(reg: RegolamentoUE, cartella_cache: Path, *, sessione=None, offline: bool = False) -> AttoUE | None:
    try:
        percorso, _stato = scarica_documento(reg.celex, cartella_cache, sessione=sessione, offline=offline)
        return dividi(percorso.read_bytes()) if percorso else None
    except Exception:  # noqa: BLE001
        return None


def prepara(reg: RegolamentoUE, cartella_cache: Path, *, consolidato: bool = True, sessione=None, offline: bool = False,
            oggi: str = "") -> EsitoAtto:
    """Consolidato piu' recente se disponibile (e divisibile senza errori), altrimenti originale GUUE."""

    esito = EsitoAtto(regolamento=reg)
    candidati: list[str] = []
    if consolidato:
        limite = oggi or _dt.date.today().isoformat()
        try:
            if offline:
                elenco = sorted(p.stem for p in cartella_cache.glob(f"0{reg.celex[1:]}-*.*"))
            else:
                elenco = consolidati_disponibili(reg.celex, sessione=sessione)
            candidati = [c for c in sorted(elenco, reverse=True) if data_consolidato(c) <= limite][:1]
            if not candidati:
                esito.note.append("nessun testo consolidato nell'elenco dell'Ufficio delle pubblicazioni")
        except Exception as exc:  # noqa: BLE001 - l'originale resta disponibile
            esito.note.append(f"elenco dei consolidati non disponibile ({exc.__class__.__name__})")
    for celex in [*candidati, reg.celex]:
        try:
            percorso, stato = scarica_documento(celex, cartella_cache, sessione=sessione, offline=offline)
        except Exception as exc:  # noqa: BLE001
            esito.note.append(f"{celex}: download non riuscito ({exc.__class__.__name__})")
            continue
        if percorso is None:
            esito.note.append(f"{celex}: {stato}")
            continue
        try:
            atto = dividi(percorso.read_bytes())
        except ValueError as exc:
            esito.note.append(f"{celex}: {exc}")
            continue
        errori = controlla(atto)
        lacune = mancanti(atto)
        if errori and lacune and celex != reg.celex:
            # nei consolidati gli articoli soppressi non compaiono: ammessi solo se esistono nel testo originale
            originale = _atto_originale(reg, cartella_cache, sessione=sessione, offline=offline)
            presenti = {a.numero for a in originale.articoli} if originale else set()
            soppressi = [n for n in lacune if str(n) in presenti]
            errori = controlla(atto, soppressi_ammessi=soppressi)
            if soppressi and not errori:
                esito.soppressi = soppressi
                esito.note.append(f"articoli soppressi, assenti dal consolidato: {', '.join(map(str, soppressi))}")
        if errori and celex != reg.celex:
            esito.note.append(f"{celex}: consolidato scartato ({'; '.join(errori[:3])})")
            continue
        esito.celex_usato = celex
        esito.consolidato_al = data_consolidato(celex) if celex != reg.celex else ""
        esito.atto = atto
        esito.errori = errori
        return esito
    esito.errori.append("nessun testo utilizzabile")
    return esito


def sostituisci_nel_jsonl(percorso: Path, nuove: Iterable[dict[str, Any]]) -> tuple[int, int]:
    """Riscrive il JSONL togliendo le righe delle chiavi presenti in ``nuove`` e aggiungendo queste in fondo.

    Restituisce (righe tolte, righe aggiunte). L'ordine delle altre righe resta invariato.
    """

    import json

    nuove = list(nuove)
    chiavi = {r["chiave"] for r in nuove}
    tenute: list[str] = []
    tolte = 0
    if percorso.exists():
        for riga in percorso.read_text(encoding="utf-8").splitlines():
            if not riga.strip():
                continue
            if json.loads(riga).get("chiave") in chiavi:
                tolte += 1
                continue
            tenute.append(riga)
    tenute.extend(json.dumps(r, ensure_ascii=False) for r in nuove)
    percorso.write_text("\n".join(tenute) + "\n", encoding="utf-8")
    return tolte, len(nuove)


__all__ = [
    "AttoUE",
    "ArticoloUE",
    "EsitoAtto",
    "FONTE_TESTO",
    "REGOLAMENTI",
    "REGOLAMENTI_PER_CELEX",
    "RegolamentoUE",
    "consolidati_disponibili",
    "controlla",
    "data_consolidato",
    "dividi",
    "mancanti",
    "prepara",
    "righe_documento",
    "righe_jsonl",
    "scarica_documento",
    "sostituisci_nel_jsonl",
    "titolo_con_versione",
    "titolo_e_data",
    "ultimo_articolo",
    "urn_atto",
]
