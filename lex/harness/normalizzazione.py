"""Normalizzazione tollerante delle richieste prima della comprensione e della lettura dei fatti.

L'avvocato scrive in fretta: senza accenti, con refusi, con parole comuni al posto dei termini tecnici («padrone di casa»,
«affitto», «multa», «Equitalia»). Le regole dell'harness riconoscono la fattispecie sui termini tecnici: qui il linguaggio
comune si riporta a quei termini e i refusi sulle parole lunghe si correggono confrontandoli con il lessico giuridico delle
regole stesse. I nomi propri (parole con la maiuscola), le date, gli importi e i numeri non si toccano mai.
"""
from __future__ import annotations

import re
import unicodedata
from difflib import get_close_matches
from functools import lru_cache
from pathlib import Path

# Linguaggio comune -> termine delle regole. Le chiavi sono espressioni senza accenti e in minuscolo; il termine tecnico si
# aggiunge accanto all'espressione originale («affitto (locazione)») così nessuna parola dell'avvocato si perde.
SINONIMI: tuple[tuple[str, str], ...] = (
    (r"padron\w* di casa|proprietari\w* di casa|propietari\w* di casa", "locatore"),
    (r"\baffitt(?:o|i|uario|uaria)\b(?! (?:d |di |dell )?(?:azienda|ramo))", "locazione"),
    (r"\binquilin[oaie]\b", "conduttore"),
    (r"\bpigione\b", "canone"),
    (r"\bmulta\b|\bmulte\b|\bcontravvenzione\b", "verbale"),
    (r"\bequitalia\b|\bagenzia (?:delle )?entrate riscossione\b|\bader\b", "agenzia delle entrate riscossione cartella"),
    (r"\bmi hanno licenziat\w*|\bsono stat[oa] licenziat\w*|\bci hanno licenziat\w*|\bl hanno licenziat\w*", "licenziamento"),
    (r"\bcacciat[oa] dal lavoro|\bmandat[oa] via dal lavoro", "licenziamento"),
    (r"\bmi hanno pignorat\w*|\bci hanno pignorat\w*|\bgli hanno pignorat\w*|\ble hanno pignorat\w*", "pignoramento subito debitore"),
    (r"\bbusta paga\b", "retribuzione"),
    (r"\bliquidazione di fine rapporto|\bliquidazione del lavoro", "tfr"),
    (r"\bcapo\b(?= (?:mi|ci|lo|la|gli|le|ha|non))", "datore di lavoro"),
    (r"\bex moglie\b|\bex marito\b", "ex coniuge"),
    (r"\bmantenimento dei (?:figli|bambini|ragazzi)\b", "mantenimento figli"),
    (r"non (?:mi |ci |le |gli )?passa (?:piu )?(?:i soldi|il mantenimento|l assegno|niente)", "mantenimento non versato"),
    (r"\bcondominio\b|\bamministratore di condominio\b", "condominio"),
    (r"\bvicino di casa\b", "vicino condomino"),
    (r"\bcomprat\w* (?:in|su internet|online|al negozio|dal negozio)", "acquistato consumatore"),
    (r"\bsi e rott[oa]\b|\bnon va piu\b|\bnon funziona piu\b", "non funziona difetto"),
    (r"\bassicurazione\b", "assicurazione"),
    (r"\bincidente stradale\b|\bincidente con la macchina\b|\bincidente in auto\b|\bmi hanno tamponat\w*", "sinistro stradale"),
    (r"\bdenuncia(?:re)? ai carabinieri\b|\bdenuncia(?:re)? alla polizia\b", "querela denuncia"),
    (r"\bavviso bonario\b", "avviso tributario"),
    (r"\bdecreto di pagamento\b|\bingiunzione del tribunale\b", "decreto ingiuntivo"),
    (r"\bbanca\b|\bistituto di credito\b", "banca"),
    (r"\bspa\b|\bsrl\b|\bsnc\b|\bsas\b", "societa"),
    (r"\bdati personali\b|\bgdpr\b", "privacy dati personali"),
    (r"\binps\b", "inps previdenza"),
    (r"\bstatale\b|\bministeriale\b|\bpubblico dipendente\b", "dipendente pubblico"),
    (r"(?:ospedal\w*|\bmedic[oi]\b|chirurg\w*|pronto soccorso|\bintervento\b|\bcurat[oa])[^.?]{0,60}(?:sbagliat|errore|male\b|peggiorat|"
     r"negligen|infezion|non ha (?:visto|capito|diagnosticat))|(?:non ha|mancata|ritardata|sbagliata) (?:diagnos|visto la malattia)|"
     r"\bmalasanit|errore (?:medico|sanitario)", "responsabilita sanitaria medica danni"),
    (r"piano di sopra|appartamento di sopra|acqua (?:dal|che scende dal|che viene dal) (?:soffitto|vicino)|\binfiltrazion\w*|perdit\w* d acqua|macchi\w* di umidita",
     "infiltrazioni danni"),
    (r"si e (?:pres[oa]|tenut[oa]|impossessat[oa]|intestat[oa]) (?:la casa|l immobile|i beni|tutto|l eredita)|tiene (?:per se|tutta) l eredita",
     "erede petizione eredita"),
    (r"\be (?:mancat[oa]|mort[oa]|venut[oa] a mancare|decedut[oa])\b|\bdefunt[oa]\b|\bdecess[oi]\b|\bscompars[oa]\b(?= (?:da|il|la|l))",
     "defunto eredita successione"),
    (r"(?:scritt\w*|pubblicat\w*|postat\w*|condivis\w*)[^.?]{0,80}(?:facebook|instagram|whatsapp|tiktok|social|gruppo|recension|blog|giornale)|"
     r"(?:facebook|instagram|whatsapp|tiktok|social|recension\w*|blog|giornale)[^.?]{0,80}(?:scritt|pubblicat|postat|offes|falsit|ladr|truffator)",
     "diffamazione reputazione danni"),
    (r"\bmi hanno citat\w*|\bci hanno citat\w*|\bsiamo stati citati|\bsono stat[oa] citat\w*", "convenuto citazione ricevuta"),
)

_PAROLA = re.compile(r"[a-z]{6,}")
_DESINENZE = frozenset({"", "a", "e", "i", "o", "to", "ta", "ti", "te", "ato", "ata", "ati", "ate", "ito", "ita", "iti", "ite",
                        "uto", "uta", "uti", "ute", "are", "ere", "ire", "ando", "endo", "ano", "ono", "iamo", "ate", "ete",
                        "ito", "va", "vo", "re", "no", "mo", "ta", "zione", "zioni", "mente", "bile", "bili"})


def senza_accenti(testo: str) -> str:
    base = unicodedata.normalize("NFKD", str(testo or "").replace("’", "'"))
    return "".join(c for c in base if not unicodedata.combining(c))


@lru_cache(maxsize=1)
def lessico() -> frozenset[str]:
    """Parole del lessico giuridico: tutte le parole lunghe dei testi e delle espressioni delle regole e delle norme."""
    cartella = Path(__file__).parent
    testi = [p.read_text(encoding="utf-8") for p in (cartella / "fattispecie").glob("*.py")]
    testi += [(cartella / n).read_text(encoding="utf-8") for n in ("comprensione.py", "fatti.py", "norme.py")]
    parole = set()
    for t in testi:
        # Solo parole intere: si tolgono le sequenze delle espressioni regolari («\\b», «\\w») e le radici tronche, che in
        # italiano non finiscono in vocale.
        pulito = re.sub(r"\\[a-zA-Z]", " ", senza_accenti(t).lower())
        parole.update(w for w in _PAROLA.findall(pulito) if w[-1] in "aeiou")
    return frozenset(parole)


def _parola_italiana(parola: str) -> bool:
    """Il vocabolario italiano del correttore OCR (hunspell-it, installato nell'immagine): una parola che conosce non si
    corregge mai."""
    try:
        from legal_ocr.lessico.italiano import conosce

        return conosce(parola)
    except Exception:
        return False


def _stessa_parola(a: str, b: str) -> bool:
    k = 0
    while k < min(len(a), len(b)) and a[k] == b[k]:
        k += 1
    return a[k:] in _DESINENZE and b[k:] in _DESINENZE


def _refuso_di(parola: str, s: str) -> bool:
    """La parola letta è un refuso tipico della parola del lessico s?"""
    if s[0] != parola[0]:
        return False
    # Lettere mancanti (anche una doppia tolta: «sfrato», «stipendo»), al massimo due.
    if len(parola) < len(s) <= len(parola) + 2:
        resto = iter(s)
        return all(c in resto for c in parola)
    # Una doppia in più («decretto»).
    if len(parola) == len(s) + 1:
        return any(parola[i] == parola[i + 1] and parola[:i] + parola[i + 1:] == s for i in range(len(parola) - 1))
    if len(parola) == len(s):
        diverse = [k for k, (a, b) in enumerate(zip(parola, s)) if a != b]
        # Due lettere vicine scambiate («pignoramneto»).
        if len(diverse) == 2 and diverse[1] == diverse[0] + 1 and parola[diverse[0]] == s[diverse[1]] and parola[diverse[1]] == s[diverse[0]]:
            return True
        # Una sola consonante sbagliata («sentensa», «aplello»); mai una vocale, che cambia parola («distratto» / «distretto»).
        return len(diverse) == 1 and parola[diverse[0]] not in "aeiou" and s[diverse[0]] not in "aeiou"
    return False


# Parole che il dizionario italiano conosce solo come forme rare o disusate e che negli atti sono sempre il refuso di un
# termine giuridico: per queste il dizionario non basta a lasciarle com'è (resta la regola dell'unico candidato).
REFUSI_NEL_DIZIONARIO: frozenset[str] = frozenset({
    "sfrato",        # da «sfratare» (disusato, togliere i frati): negli atti è «sfratto»
})


@lru_cache(maxsize=4096)
def _corretta(parola: str) -> str:
    if parola in lessico() or (_parola_italiana(parola) and parola not in REFUSI_NEL_DIZIONARIO):
        return parola
    # Come legal_ocr/lessico: si corregge solo se UNA SOLA parola del lessico è un refuso tipico della parola letta
    # (le forme flesse della stessa parola, «sfratto» e «sfratti», contano come una sola).
    simili = [x for x in get_close_matches(parola, lessico(), n=8, cutoff=0.8) if _refuso_di(parola, x)]
    if not simili or any(not _stessa_parola(simili[0], x) for x in simili[1:]):
        return parola
    s = simili[0]
    # Una forma flessa diversa ma completa («licenziato» accanto a «licenzia») non è un refuso.
    if _stessa_parola(s, parola) and len(parola) >= len(s) and not (len(parola) == len(s) + 1 and _refuso_di(parola, s)):
        return parola
    return s


def correggi_refusi(testo: str) -> str:
    def sost(m: re.Match) -> str:
        w = m.group(0)
        if w[0].isupper() or not w.isalpha() or len(w) < 6:
            return w
        c = _corretta(w)
        return c if c != w else w

    return re.sub(r"[A-Za-z]+", sost, testo)


# Negazioni ed eccezioni: la parola esclusa non deve far vincere proprio quell'istituto («diffamazione senza querela»,
# «salvo la prescrizione», «non vogliamo fare causa»). La parola si sostituisce con un segnaposto neutro.
_ESCLUSA = re.compile(r"\b(senza|salvo|tranne|eccetto|escluso|esclusa|non (?:voglio|vogliamo|vuole|vogliono|intendo|intendiamo)"
                      r"(?: fare| presentare| sporgere| proporre| chiedere)?)\s+(?:la |il |lo |l |le |i |gli |un |una |alcuna |nessuna )?"
                      r"(querel\w*|denunc\w*|caus[ae]|mediazion\w*|negoziazion\w*|transazion\w*|prescrizion\w*|decadenz\w*|"
                      r"opposizion\w*|ricors\w*|appell\w*|sfratt\w*|separazion\w*|divorzi\w*)", re.IGNORECASE)


def togli_negati(testo: str) -> str:
    return _ESCLUSA.sub(lambda m: f"{m.group(1)} [istituto escluso]", testo)


def normalizza_richiesta(testo: str) -> str:
    """Testo pronto per comprensione e fatti: accenti tolti, refusi corretti, termini tecnici affiancati al linguaggio comune."""
    if not testo:
        return ""
    t = togli_negati(correggi_refusi(senza_accenti(testo)))
    basso = t.lower()
    aggiunte = []
    for espr, termine in SINONIMI:
        if re.search(espr, basso) and termine not in basso:
            aggiunte.append(termine)
    return t + (" [" + "; ".join(dict.fromkeys(aggiunte)) + "]" if aggiunte else "")
