"""Il correttore di lettura: cambia una parola solo se la forma giusta è dichiarata.

Il lettore ottico confonde segni che si somigliano e produce parole che in
italiano non esistono: «cornparsa» per «comparsa», «istan2a» per «istanza»,
«perentorìo» per «perentorio», «u1teriore» per «ulteriore». Un correttore
statistico indovinerebbe; qui non si indovina.

La regola è una sola, e vale per ogni correzione:

1. la parola letta **non** è nel lessico (forense, italiano, dizionario di sistema);
2. applicando le sole confusioni dichiarate in `legal_ocr/formulario/confusioni.py`
   (più l'accento interno, che l'italiano non usa, e le coppie di segni che il
   lettore fonde) si ottiene **una sola** parola che **è** nel lessico;
3. quella parola prende la forma di maiuscole dell'originale.

Se le parole candidate sono due, non si corregge: una scelta fra due parole
esistenti sarebbe un'interpretazione del testo, non una correzione della
lettura. Non si tocca nulla dentro un riferimento normativo, un numero, una
data o un codice: quelle forme hanno già le loro regole.

Base della scelta: art. 20 CAD — il documento informatico resta integro e
verificabile, quindi ogni correzione è dichiarata e ricostruibile.
"""

from __future__ import annotations

import re
import unicodedata

from legal_ocr.formulario.confusioni import CIFRA_PER_LETTERA
from legal_ocr.formulario.regola import conserva_maiuscole

VERSIONE_CORRETTORE = "2026.09.15.correttore-lessico.v1"

# Sotto questa lunghezza non si corregge: su parole brevi ogni sostituzione
# produce troppe parole esistenti e la correzione diventa una scelta.
LUNGHEZZA_MINIMA = 4
# Quante lettere deve avere il segmento perché sia una parola e non un numero:
# «2026» e «1.250» sono cifre lette come cifre, e hanno già le loro regole.
LETTERE_MINIME = 3
# Quante sostituzioni al più in una parola: oltre, la lettura è da rifare, non da correggere.
SOSTITUZIONI_MASSIME = 2
SOSTITUZIONI_MASSIME_PAROLA_BREVE = 1
LUNGHEZZA_PAROLA_BREVE = 6
# Tetto ai candidati generati: una parola lunghissima non deve far esplodere il calcolo.
CANDIDATI_MASSIMI = 2000

# Cifre lette al posto di lettere dentro una parola: la tabella è quella del
# formulario, in minuscolo, più «1» che nelle parole vale «l» o «i».
CIFRA_NELLA_PAROLA: dict[str, tuple[str, ...]] = {
    **{cifra: (lettera.lower(),) for cifra, lettera in CIFRA_PER_LETTERA.items()},
    "1": ("l", "i"),
    "0": ("o",),
    "5": ("s",),
    "8": ("b",),
    "6": ("g",),
    "2": ("z",),
}
# Coppie di segni che il lettore fonde o spezza: sono le confusioni tipografiche
# classiche dell'OCR su carattere con grazie.
COPPIE: tuple[tuple[str, str], ...] = (
    ("rn", "m"),
    ("cl", "d"),
    ("ii", "n"),
    ("vv", "w"),
)

_PAROLA = re.compile(r"[A-Za-zÀ-ÿ0-9'’]+")
_SOLO_LETTERE = re.compile(r"^[A-Za-zÀ-ÿ'’]+$")
# Le vocali accentate, minuscole e maiuscole: la forma maiuscola si deriva,
# così l'elenco resta uno solo e non si scrive una sequenza di segni accentati.
_VOCALI_ACCENTATE = "àáâäèéêëìíîïòóôöùúûü"
_ACCENTATE = _VOCALI_ACCENTATE + _VOCALI_ACCENTATE.upper()


def _senza_accento(carattere: str) -> str:
    decomposto = unicodedata.normalize("NFD", carattere)
    return "".join(segno for segno in decomposto if unicodedata.category(segno) != "Mn")


def _accento_interno(parola: str) -> str:
    """La parola senza gli accenti che non stanno sull'ultima lettera.

    In italiano l'accento grafico cade sulla vocale finale: «però», «città»,
    «perché». Un accento in mezzo alla parola è quasi sempre un segno letto
    male («perentorìo»), e toglierlo è una correzione, non una scelta.
    """
    if len(parola) < 2:
        return parola
    testa = "".join(_senza_accento(carattere) if carattere in _ACCENTATE else carattere for carattere in parola[:-1])
    return testa + parola[-1]


def _candidati(parola: str) -> set[str]:
    """Le parole ottenibili dalla parola letta con le sole confusioni dichiarate."""
    massime = SOSTITUZIONI_MASSIME if len(parola) > LUNGHEZZA_PAROLA_BREVE else SOSTITUZIONI_MASSIME_PAROLA_BREVE
    livello = {parola}
    trovati: set[str] = set()
    for _passo in range(massime):
        successivo: set[str] = set()
        for corrente in livello:
            for indice, carattere in enumerate(corrente):
                for lettera in CIFRA_NELLA_PAROLA.get(carattere, ()):
                    successivo.add(corrente[:indice] + lettera + corrente[indice + 1:])
            for coppia, singolo in COPPIE:
                for trovato in (match.start() for match in re.finditer(re.escape(coppia), corrente)):
                    successivo.add(corrente[:trovato] + singolo + corrente[trovato + len(coppia):])
                for trovato in (match.start() for match in re.finditer(re.escape(singolo), corrente)):
                    successivo.add(corrente[:trovato] + coppia + corrente[trovato + len(singolo):])
            senza = _accento_interno(corrente)
            if senza != corrente:
                successivo.add(senza)
        successivo -= trovati | livello | {parola}
        if not successivo:
            break
        trovati |= successivo
        livello = successivo
        if len(trovati) > CANDIDATI_MASSIMI:
            break
    return trovati


def _sa(parola: str, lessico: frozenset[str] | None) -> bool:
    """Se la parola esiste: nel lessico passato, oppure nel dizionario italiano con le flessioni."""
    if lessico is not None:
        return parola in lessico
    from .italiano import conosce

    return conosce(parola)


def correggi_parola(parola: str, *, lessico: frozenset[str] | None = None) -> str:
    """La parola corretta, oppure la parola letta se non c'è una sola forma giusta."""
    grezza = str(parola or "")
    lettere = sum(1 for carattere in grezza if carattere.isalpha())
    if len(grezza) < LUNGHEZZA_MINIMA or lettere < LETTERE_MINIME or lettere <= sum(1 for carattere in grezza if carattere.isdigit()):
        return grezza
    piatta = grezza.casefold()
    if _sa(piatta, lessico):
        return grezza
    candidati = {
        candidato.casefold()
        for candidato in _candidati(piatta)
        if _SOLO_LETTERE.match(candidato) and _sa(candidato.casefold(), lessico)
    }
    if len(candidati) != 1:
        return grezza
    return conserva_maiuscole(grezza, candidati.pop())


def correggi_testo(testo: str, *, lessico: frozenset[str] | None = None) -> tuple[str, int]:
    """Il testo con le parole riportate al lessico, e quante parole sono cambiate."""
    from legal_ocr.formulario.riferimenti_normativi import e_riferimento_normativo

    grezzo = str(testo or "")
    if not grezzo.strip():
        return grezzo, 0
    conosciute = lessico
    cambiate = 0
    pezzi: list[str] = []
    ultimo = 0
    for match in _PAROLA.finditer(grezzo):
        parola = match.group(0)
        pezzi.append(grezzo[ultimo:match.start()])
        ultimo = match.end()
        if e_riferimento_normativo(grezzo, match.start(), match.end()):
            pezzi.append(parola)
            continue
        corretta = correggi_parola(parola, lessico=conosciute)
        if corretta != parola:
            cambiate += 1
        pezzi.append(corretta)
    pezzi.append(grezzo[ultimo:])
    return "".join(pezzi), cambiate


__all__ = [
    "CANDIDATI_MASSIMI", "CIFRA_NELLA_PAROLA", "COPPIE", "LETTERE_MINIME", "LUNGHEZZA_MINIMA", "SOSTITUZIONI_MASSIME",
    "VERSIONE_CORRETTORE", "correggi_parola", "correggi_testo",
]
