"""Trattamento del testo per la ricerca giuridica: normalizzazione, stopword, stemming, analisi della domanda.

Lo stemming è una implementazione dell'algoritmo Snowball per l'italiano (Porter, snowballstem.org),
senza dipendenze esterne: «responsabilità» e «responsabile» diventano entrambe «respons»,
«risarcimento» e «risarcire» diventano «risarc». Lo stesso trattamento si applica al testo indicizzato
e alla domanda, quindi le due parti restano allineate.

La versione dello stemmer (``VERSIONE_ANALIZZATORE``) è registrata nei metadati dell'indice: se cambia,
l'indice va ricostruito (l'importer e la riga di comando lo fanno da soli).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from functools import lru_cache

VERSIONE_ANALIZZATORE = "it-snowball-1"

# Stopword italiane (elenco Snowball ridotto) e parole della domanda che non portano contenuto.
STOPWORD: frozenset[str] = frozenset(
    """
    a ad agli ai al alla alle allo anche avere aveva avevano avra avrai avranno avrebbe c che chi ci cio come con
    contro cui da dagli dai dal dalla dalle dallo degli dei del dell della delle dello di dov dove e ed era erano
    essere essi fa fra fu gli ha hai hanno ho i il in io l la le lei li lo loro lui ma me mi mia mie miei mio ne
    negli nei nel nell nella nelle nello noi non nostra nostre nostri nostro o ogni per perche piu po pero qua
    quale quali quando quanto quella quelle quelli quello questa queste questi questo qui se sei si sia siamo
    siano sono sta su sua sue sugli sui sul sull sulla sulle sullo suo suoi ti tra tu tua tue tuo tuoi tutti
    tutto un una uno vi voi vostra vostro e' cosa cos quali qual sono puo possono deve devono essere stato
    stata stati viene vengono ovvero oppure quindi cioe nonche altresi
    """.split()
)

# Parole tipiche della domanda dell'avvocato che non compaiono nel testo delle norme.
PAROLE_DOMANDA: frozenset[str] = frozenset(
    """
    art artt articolo articoli comma commi codice cod lett lettera n num numero prevede previsto prevista
    dice dispone stabilisce disciplina disciplinata disciplinato regola regolata regolato
    presupposti presupposto requisiti requisito elementi elemento costitutivi condizioni condizione
    significa spiegami spiega dimmi indicami vorrei sapere sai mi quali quale qual cosa cos
    funziona funzionano succede accade applica applicano caso casi norma norme normativa legge
    riferimento riferimenti fonte fonti vigente vigenti italiano italiana ordinamento diritto
    entro
    """.split()
)

_VOCALI = "aeiouàèìòù"
_ACUTE_GRAVE = str.maketrans({"á": "à", "é": "è", "í": "ì", "ó": "ò", "ú": "ù"})


def senza_accenti(testo: str) -> str:
    decomposto = unicodedata.normalize("NFKD", str(testo or ""))
    return "".join(ch for ch in decomposto if not unicodedata.combining(ch))


def normalizza_apostrofi(testo: str) -> str:
    """«responsabilita'» → «responsabilità»: molti scrivono l'accento con l'apostrofo."""

    valore = str(testo or "").replace("’", "'").replace("`", "'")
    mappa = {"a": "à", "e": "è", "i": "ì", "o": "ò", "u": "ù"}
    return re.sub(
        r"([A-Za-z]{2,})([aeiouAEIOU])'(?=\s|$|[.,;:!?)])",
        lambda m: m.group(1) + mappa[m.group(2).lower()],
        valore,
    )


def _r1_r2(parola: str) -> tuple[int, int]:
    def regione(inizio: int) -> int:
        for i in range(inizio + 1, len(parola)):
            if parola[i] not in _VOCALI and parola[i - 1] in _VOCALI:
                return i + 1
        return len(parola)

    r1 = regione(0)
    r2 = regione(r1) if r1 < len(parola) else len(parola)
    return r1, r2


def _rv(parola: str) -> int:
    if len(parola) < 2:
        return len(parola)
    if parola[1] not in _VOCALI:
        for i in range(2, len(parola)):
            if parola[i] in _VOCALI:
                return i + 1
        return len(parola)
    if parola[0] in _VOCALI and parola[1] in _VOCALI:
        for i in range(2, len(parola)):
            if parola[i] not in _VOCALI:
                return i + 1
        return len(parola)
    return 3 if len(parola) >= 3 else len(parola)


_STEP0_PRONOMI = sorted(
    """ci gli la le li lo mi ne si ti vi sene gliela gliele glieli glielo gliene mela mele meli melo mene
    tela tele teli telo tene cela cele celi celo cene vela vele veli velo vene""".split(),
    key=len,
    reverse=True,
)
_STEP1_ELIMINA_R2 = sorted(
    """anza anze ico ici ica ice iche ichi ismo ismi abile abili ibile ibili ista iste isti istà istè istì
    oso osi osa ose mente atrice atrici ante anti""".split(),
    key=len,
    reverse=True,
)
_STEP2_VERBI = sorted(
    """ammo ando ano are arono asse assero assi assimo ata ate ati ato ava avamo avano avate avi avo emmo
    enda ende endi endo erà erai eranno ere erebbe erebbero erei eremmo eremo ereste eresti erete erò erono
    essero ete eva evamo evano evate evi evo yamo iamo immo irà irai iranno ire irebbe irebbero irei iremmo
    iremo ireste iresti irete irò irono isca iscano isce isci isco iscono issero ita ite iti ito iva ivamo
    ivano ivate ivi ivo ono uta ute uti uto ar ir""".split(),
    key=len,
    reverse=True,
)


def _prepara(parola: str) -> str:
    parola = parola.translate(_ACUTE_GRAVE)
    parola = parola.replace("qu", "qU")
    caratteri = list(parola)
    for i in range(1, len(caratteri) - 1):
        if caratteri[i - 1] in _VOCALI and caratteri[i + 1] in _VOCALI:
            if caratteri[i] == "i":
                caratteri[i] = "I"
            elif caratteri[i] == "u":
                caratteri[i] = "U"
    return "".join(caratteri)


@lru_cache(maxsize=200_000)
def stem(parola: str) -> str:
    """Radice Snowball italiana della parola (minuscola), restituita senza accenti."""

    parola = str(parola or "").lower()
    if len(parola) <= 3 or not parola.isalpha():
        return senza_accenti(parola)
    # «responsabilita» scritto senza accento: si tratta come «responsabilità» (stessa radice).
    if parola.endswith(("abilita", "icita", "ivita")) and len(parola) > 6:
        parola = parola[:-1] + "à"
    w = _prepara(parola)
    rv = _rv(w)
    r1, r2 = _r1_r2(w)

    # Step 0: pronomi enclitici dopo gerundio o infinito.
    for pronome in _STEP0_PRONOMI:
        if w.endswith(pronome) and len(w) - len(pronome) >= rv:
            radice = w[: -len(pronome)]
            if radice.endswith(("ando", "endo")) and len(radice) - 4 >= rv:
                w = radice
            elif radice.endswith(("ar", "er", "ir")) and len(radice) - 2 >= rv:
                w = radice + "e"
            break

    # Step 1: suffissi derivativi.
    modificata = False
    lunghezza = len(w)

    def in_r2(suffisso: str) -> bool:
        return w.endswith(suffisso) and len(w) - len(suffisso) >= r2

    def in_r1(suffisso: str) -> bool:
        return w.endswith(suffisso) and len(w) - len(suffisso) >= r1

    def in_rv(suffisso: str) -> bool:
        return w.endswith(suffisso) and len(w) - len(suffisso) >= rv

    candidati = [
        "amente", "azione", "azioni", "atore", "atori", "logia", "logie", "uzione", "uzioni", "usione", "usioni",
        "enza", "enze", "amento", "amenti", "imento", "imenti", "ità", "ivo", "ivi", "iva", "ive", *_STEP1_ELIMINA_R2,
    ]
    suffisso = max((s for s in candidati if w.endswith(s)), key=len, default="")
    if suffisso:
        if suffisso in {"amento", "amenti", "imento", "imenti"}:
            if in_rv(suffisso):
                w = w[: -len(suffisso)]
        elif suffisso in {"azione", "azioni", "atore", "atori"}:
            if in_r2(suffisso):
                w = w[: -len(suffisso)]
                if in_r2("ic"):
                    w = w[:-2]
        elif suffisso in {"logia", "logie"}:
            if in_r2(suffisso):
                w = w[: -len(suffisso)] + "log"
        elif suffisso in {"uzione", "uzioni", "usione", "usioni"}:
            if in_r2(suffisso):
                w = w[: -len(suffisso)] + "u"
        elif suffisso in {"enza", "enze"}:
            if in_r2(suffisso):
                w = w[: -len(suffisso)] + "ente"
        elif suffisso == "amente":
            if in_r1(suffisso):
                w = w[: -len(suffisso)]
                if in_r2("iv"):
                    w = w[:-2]
                    if in_r2("at"):
                        w = w[:-2]
                else:
                    for prec in ("abil", "os", "ic"):
                        if in_r2(prec):
                            w = w[: -len(prec)]
                            break
        elif suffisso == "ità":
            if in_r2(suffisso):
                w = w[:-3]
                for prec in ("abil", "ic", "iv"):
                    if in_r2(prec):
                        w = w[: -len(prec)]
                        break
        elif suffisso in {"ivo", "ivi", "iva", "ive"}:
            if in_r2(suffisso):
                w = w[:-3]
                if in_r2("at"):
                    w = w[:-2]
                    if in_r2("ic"):
                        w = w[:-2]
        elif in_r2(suffisso):
            w = w[: -len(suffisso)]
    modificata = len(w) != lunghezza

    # Step 2: desinenze verbali (solo se lo step 1 non ha tolto nulla).
    if not modificata:
        for verbo in _STEP2_VERBI:
            if in_rv(verbo):
                w = w[: -len(verbo)]
                break

    # Step 3a: vocale finale e «i» che la precede.
    if w and w[-1] in "aeioàèìò" and len(w) - 1 >= rv:
        w = w[:-1]
        if w.endswith("i") and len(w) - 1 >= rv:
            w = w[:-1]
    # Step 3b.
    if (w.endswith("ch") or w.endswith("gh")) and len(w) - 1 >= rv:
        w = w[:-1]
    return senza_accenti(w.replace("I", "i").replace("U", "u"))


_SIGLE = (
    (r"c\.\s*p\.\s*p\.", " cpp "),
    (r"c\.\s*p\.\s*c\.", " cpc "),
    (r"c\.\s*p\.\s*a\.", " cpa "),
    (r"c\.\s*d\.\s*s\.", " cds "),
    (r"c\.\s*c\.", " cc "),
    (r"c\.\s*p\.(?=[\s,;)]|$)", " cp "),
    (r"d\.\s*lgs\.?", " dlgs "),
    (r"d\.\s*l\.(?=\s)", " dl "),
    (r"d\.\s*p\.\s*r\.", " dpr "),
    (r"d\.\s*m\.", " dm "),
)


def _sostituisci_sigle(testo: str) -> str:
    valore = f" {testo} "
    for schema, sostituto in _SIGLE:
        valore = re.sub(schema, sostituto, valore, flags=re.I)
    return valore


def parole(testo: str) -> list[str]:
    """Parole minuscole (lettere e cifre) del testo, con le sigle dei codici compattate (c.c. → cc)."""

    valore = normalizza_apostrofi(testo).lower()
    valore = _sostituisci_sigle(valore)
    return re.findall(r"[a-zàèéìíòóùú0-9]+", valore)


def termini_indice(testo: str) -> list[str]:
    """Radici da indicizzare: senza stopword, senza accenti, numeri conservati."""

    risultato: list[str] = []
    for parola in parole(testo):
        piana = senza_accenti(parola)
        if piana in STOPWORD:
            continue
        if parola.isdigit():
            risultato.append(parola)
            continue
        if len(piana) < 2:
            continue
        risultato.append(stem(parola))
    return risultato


def testo_indice(testo: str) -> str:
    return " ".join(termini_indice(testo))


# --------------------------------------------------------------------------------------------- #
# Codici e riferimenti                                                                           #
# --------------------------------------------------------------------------------------------- #

@dataclass(frozen=True, slots=True)
class Codice:
    chiave: str
    etichetta: str
    numero: str
    data_atto: str
    alias: tuple[str, ...]
    sigla: str


CODICI: tuple[Codice, ...] = (
    Codice("codice_civile", "Codice civile", "262", "1942-03-16",
           ("codice civile", "cod civ", "cc"), "c.c."),
    Codice("codice_procedura_civile", "Codice di procedura civile", "1443", "1940-10-28",
           ("codice di procedura civile", "codice procedura civile", "cod proc civ", "cpc"), "c.p.c."),
    Codice("codice_penale", "Codice penale", "1398", "1930-10-19",
           ("codice penale", "cod pen", "cp"), "c.p."),
    Codice("codice_procedura_penale", "Codice di procedura penale", "447", "1988-09-22",
           ("codice di procedura penale", "codice procedura penale", "cod proc pen", "cpp"), "c.p.p."),
    Codice("codice_processo_amministrativo", "Codice del processo amministrativo", "104", "2010-07-02",
           ("codice del processo amministrativo", "codice processo amministrativo", "cpa"), "c.p.a."),
    Codice("codice_strada", "Codice della strada", "285", "1992-04-30",
           ("codice della strada", "codice strada", "cds"), "c.d.s."),
    Codice("codice_consumo", "Codice del consumo", "206", "2005-09-06",
           ("codice del consumo", "codice consumo", "cod cons"), "cod. cons."),
    Codice("codice_crisi", "Codice della crisi d'impresa e dell'insolvenza", "14", "2019-01-12",
           ("codice della crisi", "codice crisi", "ccii"), "CCII"),
    Codice("codice_privacy", "Codice in materia di protezione dei dati personali", "196", "2003-06-30",
           ("codice privacy", "codice della privacy", "codice in materia di protezione dei dati personali"), "d.lgs. 196/2003"),
    Codice("statuto_lavoratori", "Statuto dei lavoratori", "300", "1970-05-20",
           ("statuto dei lavoratori", "statuto lavoratori"), "l. 300/1970"),
    # atti integrati nell'archivio (lex/normativa/integrazioni/leggi_essenziali.jsonl): non sono su Normattiva Open Data
    Codice("gdpr", "Regolamento (UE) 2016/679 (GDPR)", "679", "2016-04-27",
           ("gdpr", "rgpd", "regolamento ue 2016/679", "regolamento 2016/679", "regolamento generale sulla protezione dei dati",
            "regolamento europeo sulla privacy", "regolamento privacy"), "GDPR"),
    Codice("codice_deontologico_forense", "Codice deontologico forense", "", "2014-01-31",
           ("codice deontologico forense", "codice deontologico", "deontologia forense", "deontologico forense"), "c.d.f."),
)
CODICI_PER_CHIAVE = {codice.chiave: codice for codice in CODICI}
# Suffissi latini degli articoli aggiunti: le forme lunghe prima delle corte (altrimenti «terdecies» diventa «ter»)
_SUFFISSI_ARTICOLO = (
    "quinquiesdecies|sexiesdecies|septiesdecies|octiesdecies|noviesdecies|quaterdecies|terdecies|duodecies|"
    "undecies|vicies|decies|novies|nonies|octies|septies|sexies|quinquies|quater|ter|bis"
)
_ARTICOLO_RE = re.compile(
    rf"\b(?:art(?:t)?\.?|articol[oi])\s*(?P<lista>\d{{1,4}}(?:[\s-]*(?:{_SUFFISSI_ARTICOLO}))?"
    rf"(?:\s*(?:,|e|ed|-)\s*\d{{1,4}}(?:[\s-]*(?:{_SUFFISSI_ARTICOLO}))?)*)",
    re.I,
)
_NUMERO_ARTICOLO_RE = re.compile(rf"(\d{{1,4}})(?:[\s-]*({_SUFFISSI_ARTICOLO})(?![a-z]))?(?:\.(\d{{1,3}})(?!\d))?", re.I)
_ARTICOLO_SIGLA_RE = re.compile(
    rf"\b(?P<numero>\d{{1,4}})(?:[\s-]*(?P<suffisso>{_SUFFISSI_ARTICOLO}))?\s+(?P<sigla>cc|cpc|cp|cpp|cpa|cds)\b",
    re.I,
)
_ATTO_RE = re.compile(
    r"\b(?:legge|l|dlgs|decreto legislativo|dl|decreto legge|dpr|dm)\s+(?:n\s+)?(?P<numero>\d{1,5})\s+(?:del\s+)?(?P<anno>(?:19|20)\d{2})\b",
    re.I,
)


def articolo_normalizzato(valore: str) -> str:
    """«Art. 2043.» → «2043», «art. 360-bis» → «360bis»; stringa vuota se non c'è un numero."""

    match = _NUMERO_ARTICOLO_RE.search(str(valore or ""))
    if not match:
        return ""
    suffisso = (match.group(2) or "").lower().replace("nonies", "novies")
    # «473-bis.14» (rito di famiglia): il sottonumero distingue gli articoli che condividono il suffisso
    sotto = f".{int(match.group(3))}" if suffisso and match.group(3) else ""
    return f"{int(match.group(1))}{suffisso}{sotto}"


def codice_da_atto(numero: str | None, data_atto: str | None, titolo: str | None = "") -> str:
    numero = str(numero or "").strip()
    data_atto = str(data_atto or "").strip()[:10]
    for codice in CODICI:
        if numero == codice.numero and data_atto == codice.data_atto and (numero or data_atto):
            return codice.chiave
    if "costituzione" in senza_accenti(str(titolo or "")).lower() and data_atto == "1947-12-27":
        return "costituzione"
    return ""


@dataclass(slots=True)
class AnalisiDomanda:
    testo: str
    articoli: list[str] = field(default_factory=list)
    codice: str = ""
    atto_numero: str = ""
    atto_anno: str = ""
    termini: list[str] = field(default_factory=list)
    espansioni: list[str] = field(default_factory=list)

    @property
    def riferimento_esatto(self) -> bool:
        return bool(self.articoli and (self.codice or self.atto_numero))


def _codice_in_testo(testo_normalizzato: str) -> str:
    valore = f" {testo_normalizzato} "
    for codice in sorted(CODICI, key=lambda c: -max(len(a) for a in c.alias)):
        for alias in codice.alias:
            if f" {alias} " in valore:
                return codice.chiave
    if re.search(r"\bcost(?:ituzione)?\b", valore):
        return "costituzione"
    return ""


# Tesauro minimo: termini della dottrina e della pratica → parole con cui li scrive il legislatore.
# Serve alla ricerca lessicale; la ricerca semantica copre il resto.
TESAURO: tuple[tuple[str, str], ...] = (
    ("responsabilita extracontrattuale", "fatto illecito danno ingiusto risarcimento doloso colposo"),
    ("responsabilita aquiliana", "fatto illecito danno ingiusto risarcimento"),
    ("illecito civile", "fatto illecito danno ingiusto"),
    ("responsabilita contrattuale", "inadempimento obbligazione risarcimento debitore"),
    ("danno morale", "danno non patrimoniale"),
    ("danno esistenziale", "danno non patrimoniale"),
    ("danno biologico", "danno non patrimoniale"),
    ("prescrizione ordinaria", "prescrizione dieci anni diritti estinguono"),
    ("prescrizione breve", "prescrizione cinque anni"),
    ("giusta causa", "recesso giusta causa prosecuzione rapporto"),
    ("licenziamento", "recesso contratto lavoro"),
    ("diffida ad adempiere", "intimare iscritto adempiere congruo termine risoluto"),
    ("risoluzione per inadempimento", "risoluzione contratto inadempimento prestazioni corrispettive"),
    ("eccessiva onerosita", "prestazione eccessivamente onerosa avvenimenti straordinari imprevedibili"),
    ("impossibilita sopravvenuta", "prestazione divenuta impossibile causa non imputabile"),
    ("termine per l appello", "termine proporre appello"),
    ("termine per appellare", "termine proporre appello"),
    ("termine lungo", "decorsi sei mesi pubblicazione sentenza"),
    ("ricorso per cassazione", "termine ricorso cassazione"),
    ("decreto ingiuntivo", "ingiunzione decreto opposizione"),
    ("opposizione a decreto ingiuntivo", "opposizione ingiunzione quaranta giorni notificazione"),
    ("querela", "querela diritto tre mesi notizia fatto reato"),
    ("remissione della querela", "remissione querela estingue reato"),
    ("garanzia per vizi", "vizi cosa venduta compratore"),
    ("vizi della cosa venduta", "vizi cosa venduta garanzia compratore"),
    ("usucapione", "possesso continuato acquista proprieta"),
    ("caparra", "caparra confirmatoria recedere"),
    ("clausola penale", "clausola inadempimento ritardo prestazione"),
    ("legittima difesa", "difendere diritto offesa ingiusta"),
    ("stato di necessita", "salvare pericolo attuale danno grave persona"),
    ("onere della prova", "provare fatti fondamento diritto"),
    ("compensazione", "debiti estinguono quantita corrispondenti"),
    ("mora del debitore", "costituzione mora intimazione richiesta scritto"),
    ("mutuo", "mutuo quantita danaro restituire"),
    ("comodato", "comodato cosa consegna servirsene"),
    ("locazione", "locazione godimento cosa corrispettivo"),
    ("mandato", "mandato atti giuridici conto"),
    ("arricchimento senza causa", "arricchito senza giusta causa danno indennizzare"),
    ("indebito", "pagamento non dovuto ripetere"),
    ("sospensione feriale", "decorso termini processuali sospeso agosto"),
    ("diritto di difesa", "difesa diritto inviolabile"),
    ("legittima", "riserva legittimari quota"),
    ("simulazione", "contratto simulato effetto parti"),
    ("nullita del contratto", "contratto nullo contrario norme imperative"),
    ("annullabilita", "contratto annullabile incapacita"),
)
_TESAURO_NORMALIZZATO = tuple((senza_accenti(chiave), valore) for chiave, valore in TESAURO)


def corrispondenze_tesauro(domanda: str) -> list[tuple[frozenset[str], frozenset[str]]]:
    """Voci del tesauro presenti nella domanda: (radici della voce, radici con cui la scrive il legislatore)."""

    normalizzato = " ".join(senza_accenti(parola) for parola in parole(normalizza_apostrofi(domanda)))
    return [
        (frozenset(termini_indice(chiave)), frozenset(termini_indice(valore)))
        for chiave, valore in _TESAURO_NORMALIZZATO
        if f" {chiave} " in f" {normalizzato} "
    ]


def analizza_domanda(domanda: str, *, usa_tesauro: bool = True) -> AnalisiDomanda:
    testo = normalizza_apostrofi(domanda)
    elenco = parole(testo)
    normalizzato = " ".join(senza_accenti(parola) for parola in elenco)
    analisi = AnalisiDomanda(testo=testo)

    articoli: list[str] = []
    for match in _ARTICOLO_RE.finditer(testo):
        for numero in _NUMERO_ARTICOLO_RE.finditer(match.group("lista")):
            valore = articolo_normalizzato(numero.group(0))
            if valore and valore not in articoli:
                articoli.append(valore)
    sigla_codice = ""
    for match in _ARTICOLO_SIGLA_RE.finditer(normalizzato):
        valore = articolo_normalizzato(f"{match.group('numero')} {match.group('suffisso') or ''}")
        if valore and valore not in articoli:
            articoli.append(valore)
        sigla_codice = sigla_codice or match.group("sigla").lower()
    analisi.articoli = articoli
    analisi.codice = _codice_in_testo(normalizzato)
    atto = _ATTO_RE.search(normalizzato)
    if atto and not analisi.codice:
        analisi.atto_numero = str(int(atto.group("numero")))
        analisi.atto_anno = atto.group("anno")

    escluse = set(STOPWORD) | set(PAROLE_DOMANDA)
    if analisi.codice:
        codice = CODICI_PER_CHIAVE.get(analisi.codice)
        for alias in codice.alias if codice else ("costituzione", "cost"):
            escluse.update(alias.split())
        escluse.update({"civile", "penale", "procedura", "processo", "amministrativo", "strada"})
    if articoli:
        escluse.update(_SUFFISSI_ARTICOLO.split("|"))
    if analisi.atto_numero:
        escluse.update({"dlgs", "dl", "dpr", "dm", "legge", "decreto", "legislativo"})
    termini: list[str] = []
    for parola in elenco:
        piana = senza_accenti(parola)
        if piana in escluse or len(piana) < 2:
            continue
        if parola.isdigit():
            # I numeri contano solo se non sono già il riferimento all'articolo o all'atto.
            if parola.lstrip("0") in {a.rstrip("abcdefghijklmnopqrstuvwxyz") for a in articoli}:
                continue
            if parola in {analisi.atto_numero, analisi.atto_anno}:
                continue
            termini.append(parola)
            continue
        if len(piana) < 3:
            continue
        radice = stem(parola)
        if radice not in termini:
            termini.append(radice)
    analisi.termini = termini

    if usa_tesauro:
        espansioni: list[str] = []
        for chiave, valore in _TESAURO_NORMALIZZATO:
            if f" {chiave} " in f" {normalizzato} ":
                for radice in termini_indice(valore):
                    if radice not in termini and radice not in espansioni:
                        espansioni.append(radice)
        analisi.espansioni = espansioni
    return analisi


__all__ = [
    "AnalisiDomanda",
    "CODICI",
    "CODICI_PER_CHIAVE",
    "Codice",
    "STOPWORD",
    "TESAURO",
    "VERSIONE_ANALIZZATORE",
    "analizza_domanda",
    "articolo_normalizzato",
    "codice_da_atto",
    "corrispondenze_tesauro",
    "normalizza_apostrofi",
    "parole",
    "senza_accenti",
    "stem",
    "termini_indice",
    "testo_indice",
]
