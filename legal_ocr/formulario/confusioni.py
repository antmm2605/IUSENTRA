"""Le confusioni tipiche del lettore ottico, dichiarate una volta per tutte.

Il motore scambia segni che si somigliano: lo zero con la O, l'uno con la l,
la I e la barra verticale, il cinque con la S, l'otto con la B, il due con la
Z, il sei con la G, il nove con la q. La correzione e' certa solo dove la
struttura dice che cosa deve esserci: una data, un importo, un numero di
ruolo (cifre), una parola (lettere), un codice fiscale (lettere e cifre in
posizioni fisse), una partita IVA, un CAP, un IBAN. Tutte le regole del
formulario che toccano cifre e lettere attingono a questa tabella, cosi' una
confusione nuova si aggiunge in un punto solo.
"""

from __future__ import annotations

import re

from .regola import Regola, regola_regex

# Lettere lette al posto delle cifre: dove serve una cifra, questa e' la cifra.
LETTERA_PER_CIFRA: dict[str, str] = {
    "O": "0", "o": "0", "D": "0", "Q": "0",
    "I": "1", "l": "1", "|": "1", "Ì": "1", "í": "1", "ì": "1",
    "Z": "2", "z": "2",
    "S": "5", "s": "5",
    "G": "6",
    "T": "7",
    "B": "8",
    "q": "9", "g": "9",
}
# Cifre lette al posto delle lettere: dove serve una lettera, questa e' la lettera.
CIFRA_PER_LETTERA: dict[str, str] = {
    "0": "O", "1": "I", "2": "Z", "5": "S", "6": "G", "8": "B",
}
# Le confusioni piu' frequenti, quelle che valgono anche dove la struttura e' meno rigida
# (date, sequenze numeriche): niente D/Q/T/G, che dentro una data sarebbero azzardate.
LETTERA_PER_CIFRA_SICURE: dict[str, str] = {k: v for k, v in LETTERA_PER_CIFRA.items() if k in "OoIl|ÌSsBZz"}

# Aspetto di cifra: cifre vere piu' le lettere che le imitano.
_SEGNO_CIFRA = r"[\dOoIl|ÌSsBZz]"


def a_cifre(valore: str, *, sicure: bool = True) -> str:
    tabella = LETTERA_PER_CIFRA_SICURE if sicure else LETTERA_PER_CIFRA
    return "".join(tabella.get(carattere, carattere) for carattere in valore)


def a_lettere(valore: str) -> str:
    return "".join(CIFRA_PER_LETTERA.get(carattere, carattere) for carattere in valore)


# ── Strutture a forma fissa ───────────────────────────────────────────────

# Codice fiscale: 6 lettere, 2 cifre, 1 lettera, 2 cifre, 1 lettera, 3 cifre, 1 lettera.
_CF_STRUTTURA = "LLLLLLNNLNNLNNNL"
_CF_TOKEN = re.compile(r"(?<![\w])(?:C\.?\s*F\.?|cod(?:ice)?\.?\s*fisc(?:ale)?\.?|codice\s+fiscale)\s*:?\s*([A-Za-z0-9|]{16})(?![\w])", re.IGNORECASE)
_CF_NUDO = re.compile(r"(?<![\w])([A-Z0-9|]{16})(?![\w])")
_CF_PESI_DISPARI = {**{str(i): v for i, v in enumerate([1, 0, 5, 7, 9, 13, 15, 17, 19, 21])}, **dict(zip("ABCDEFGHIJKLMNOPQRSTUVWXYZ", [1, 0, 5, 7, 9, 13, 15, 17, 19, 21, 2, 4, 18, 20, 11, 3, 6, 8, 12, 14, 16, 10, 22, 25, 24, 23]))}
_CF_PESI_PARI = {**{str(i): i for i in range(10)}, **{c: i for i, c in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ")}}


def _cf_controllo(primi_15: str) -> str:
    somma = 0
    for indice, carattere in enumerate(primi_15):
        somma += _CF_PESI_DISPARI[carattere] if indice % 2 == 0 else _CF_PESI_PARI[carattere]
    return "ABCDEFGHIJKLMNOPQRSTUVWXYZ"[somma % 26]


def correggi_codice_fiscale(token: str) -> str:
    """Il codice fiscale secondo la sua struttura; invariato se dopo la correzione non torna."""
    grezzo = str(token or "").upper()
    if len(grezzo) != 16:
        return token
    corretto = []
    for atteso, carattere in zip(_CF_STRUTTURA, grezzo):
        if atteso == "L":
            lettera = CIFRA_PER_LETTERA.get(carattere, carattere)
            if not lettera.isalpha():
                return token
            corretto.append(lettera)
        else:
            cifra = LETTERA_PER_CIFRA.get(carattere, carattere)
            if not cifra.isdigit():
                return token
            corretto.append(cifra)
    codice = "".join(corretto)
    return codice if _cf_controllo(codice[:15]) == codice[15] else token


def _cf_dopo_etichetta(match: re.Match[str]) -> str:
    intero = match.group(0)
    token = match.group(1)
    corretto = correggi_codice_fiscale(token)
    return intero if corretto == token else intero[: -len(token)] + corretto


def _cf_nudo(match: re.Match[str]) -> str:
    token = match.group(1)
    if token.isdigit() or token.isalpha():
        return token
    return correggi_codice_fiscale(token)


# Partita IVA: 11 cifre dopo l'etichetta.
_PIVA = re.compile(rf"((?<![\w])(?:P\.?\s*IVA|partita\s+IVA)\s*:?\s*)({_SEGNO_CIFRA}{{11}})(?![\w])", re.IGNORECASE)
# CAP: 5 cifre davanti a una localita' (parola con iniziale maiuscola) o dopo «CAP».
_CAP = re.compile(rf"((?<![\w])(?:CAP\s*:?\s*|\b(?=[\dOoIl|ÌSsBZz]{{5}}\s+[A-ZÀ-Ý][a-zà-ÿ]{{2,}})))({_SEGNO_CIFRA}{{5}})(?![\w])")
# IBAN italiano: IT + 2 cifre + 1 lettera (CIN) + 10 cifre (ABI+CAB) + 12 alfanumerici,
# scritto anche a gruppi di quattro con spazi.
_IBAN = re.compile(r"(?<![\w])(IT[\dOoIl|ÌSsBZz]{2}(?:\s?[A-Za-z0-9|]){23})(?![\w])")
# Parole maiuscole degli atti in cui l'uno letto al posto di una lettera si scioglie senza dubbi.
_LESSICO_MAIUSCOLO = {
    "TRIBUNALE", "CORTE", "APPELLO", "CASSAZIONE", "GIUDICE", "GIUDIZIO", "REPUBBLICA", "ITALIANA", "ITALIA", "SENTENZA",
    "ORDINANZA", "DECRETO", "VERBALE", "UDIENZA", "PROCURA", "CANCELLERIA", "SEZIONE", "CIVILE", "PENALE", "LAVORO",
    "MILANO", "ROMA", "NAPOLI", "TORINO", "PALERMO", "GENOVA", "BOLOGNA", "FIRENZE", "BARI", "CATANIA", "VENEZIA", "VERONA",
    "PARTE", "PARTI", "ATTORE", "CONVENUTO", "RICORRENTE", "RESISTENTE", "AVVOCATO", "LEGALE", "STUDIO", "NOTIFICA",
    "ISTANZA", "RICORSO", "CITAZIONE", "MEMORIA", "ALLEGATO", "ALLEGATI", "DELIBERA", "CONTRATTO", "SOCIETA", "SRL", "SPA",
    "ITALIANO", "GENNAIO", "APRILE", "LUGLIO", "LIQUIDA", "LIQUIDAZIONE", "TOTALE", "SALDO", "CAPITALE", "INTERESSI", "LEGGE",
}
# Cifre dentro una parola: «R0MA», «TRIBUNA1E», «C0RTE» — almeno tre lettere, al piu' due cifre.
_PAROLA_CON_CIFRE = re.compile(r"(?<![\w])(?=[A-Za-zÀ-ÿ]*[0158][A-Za-zÀ-ÿ0158]*)(?=(?:[^\W\d_]*\d){1,2}(?!\d))([A-ZÀ-Ý][A-ZÀ-Ý0158]{2,}|[A-ZÀ-Ý][a-zà-ÿ0158]{2,})(?![\w])")
_NUMERO_RUOLO = re.compile(rf"((?<![\w])(?:R\.?\s*G\.?|N\.?\s*R\.?\s*G\.?|R\.?\s*G\.?\s*N\.?\s*R\.?)\s*(?:n\.?\s*)?)({_SEGNO_CIFRA}{{1,7}})\s*/\s*({_SEGNO_CIFRA}{{2,4}})(?![\w])", re.IGNORECASE)


def _piva(match: re.Match[str]) -> str:
    return f"{match.group(1)}{a_cifre(match.group(2))}"


def _cap(match: re.Match[str]) -> str:
    cifre = a_cifre(match.group(2))
    return f"{match.group(1)}{cifre}" if cifre.isdigit() else match.group(0)


def _iban(match: re.Match[str]) -> str:
    compatto = match.group(1).replace(" ", "").upper()
    if len(compatto) != 27:
        return match.group(1)
    controllo = a_cifre(compatto[2:4])
    cin = CIFRA_PER_LETTERA.get(compatto[4], compatto[4])
    coordinate = a_cifre(compatto[5:15])
    conto = compatto[15:]
    if not (controllo.isdigit() and cin.isalpha() and coordinate.isdigit()):
        return match.group(1)
    return f"IT{controllo}{cin}{coordinate}{conto}"


def _scioglie_uno_maiuscolo(parola: str) -> str:
    """«TRIBUNA1E»: l'uno e' una I o una L? Decide il lessico degli atti; altrimenti resta."""
    posizioni = [i for i, c in enumerate(parola) if c == "1"]
    if not posizioni:
        return parola
    for lettere in ("I", "L", "IL", "LI"):
        if len(lettere) != len(posizioni) and len(lettere) != 1:
            continue
        candidata = list(parola)
        for indice, posizione in enumerate(posizioni):
            candidata[posizione] = lettere[indice] if len(lettere) == len(posizioni) else lettere
        testo = "".join(candidata)
        if testo in _LESSICO_MAIUSCOLO:
            return testo
    return parola


def _parola(match: re.Match[str]) -> str:
    parola = match.group(1)
    lettere = sum(1 for c in parola if c.isalpha())
    cifre = sum(1 for c in parola if c.isdigit())
    if lettere < 3 or cifre == 0 or cifre > 2:
        return parola
    if parola.isupper():
        # 0, 5, 8 non sono ambigui; l'uno si scioglie solo con il lessico.
        senza_uno = "".join(CIFRA_PER_LETTERA.get(c, c) if c != "1" else c for c in parola)
        return _scioglie_uno_maiuscolo(senza_uno)
    if parola[1:].islower():
        return "".join({"0": "o", "1": "l", "5": "s", "8": "B"}.get(c, c) if i else CIFRA_PER_LETTERA.get(c, c) for i, c in enumerate(parola))
    return parola


def _numero_ruolo(match: re.Match[str]) -> str:
    return f"{match.group(1)}{a_cifre(match.group(2))}/{a_cifre(match.group(3))}"


REGOLE: tuple[Regola, ...] = (
    regola_regex("conf.codice_fiscale.v1", "codice fiscale", "Lettere e cifre nelle posizioni del codice fiscale, con carattere di controllo verificato.", _CF_TOKEN, _cf_dopo_etichetta),
    regola_regex("conf.codice_fiscale_nudo.v1", "codice fiscale senza etichetta", "Sedici caratteri con la struttura del codice fiscale e controllo verificato.", _CF_NUDO, _cf_nudo),
    regola_regex("conf.partita_iva.v1", "partita IVA", "Undici cifre dopo «P.IVA»: lettere lette al posto delle cifre.", _PIVA, _piva),
    regola_regex("conf.cap.v1", "CAP", "Cinque cifre del CAP davanti alla localita'.", _CAP, _cap),
    regola_regex("conf.iban.v1", "IBAN", "IBAN italiano nella sua struttura: cifre e lettera di controllo.", _IBAN, _iban),
    regola_regex("conf.numero_ruolo.v1", "numero di ruolo", "Cifre del numero di ruolo e dell'anno dopo R.G.", _NUMERO_RUOLO, _numero_ruolo),
    regola_regex("conf.parola.v1", "cifre dentro una parola", "0, 1, 5, 8 lette al posto di O, I, S, B in una parola.", _PAROLA_CON_CIFRE, _parola),
)

__all__ = ["CIFRA_PER_LETTERA", "LETTERA_PER_CIFRA", "LETTERA_PER_CIFRA_SICURE", "REGOLE", "a_cifre", "a_lettere", "correggi_codice_fiscale"]
