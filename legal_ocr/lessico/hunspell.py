"""Il dizionario italiano di sistema, letto come lo legge Hunspell.

Un dizionario Hunspell non è un elenco di parole: è un elenco di **radici** con
le sigle delle regole che le flettono. `udienza/QTUqrs` non contiene «udienze»,
che nasce dalla regola `SFX Q a e [^gc]a` dichiarata nel file `.aff`: togli la
«a», metti «e». Leggere il solo `.dic` e fermarsi alle radici significa non
conoscere i plurali, i femminili e le forme verbali — cioè quasi tutto
l'italiano scritto in un atto.

Qui i due file vengono usati entrambi, come li usa Hunspell: il `.aff` per la
codifica dichiarata (`SET`), la forma delle sigle (`FLAG`) e le regole di
suffisso e prefisso; il `.dic` per le radici con le loro sigle. La verifica di
una parola non espande il dizionario in memoria (sarebbero milioni di forme):
applica le regole **al contrario**, come fa Hunspell. «udienze» → tolgo «e»,
rimetto «a» → «udienza», che esiste e porta la sigla Q: la parola è italiana.

Non serve l'eseguibile `hunspell`: qui non si chiede un suggerimento, si chiede
se una parola esiste, e questo si decide sui due file. Nessuna funzione del
gestionale si blocca se il dizionario non è installato: senza, restano le
parole dichiarate nel repository.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

# I file del dizionario italiano installati dal pacchetto `hunspell-it`.
PERCORSI_AFF: tuple[str, ...] = (
    "/usr/share/hunspell/it_IT.aff",
    "/usr/share/myspell/dicts/it_IT.aff",
    "/usr/share/myspell/it_IT.aff",
)
# Limiti di sicurezza: oltre questi un file non è il dizionario atteso.
RADICI_MASSIME = 400_000
REGOLE_MASSIME = 20_000
# Quanti segni al più può togliere un affisso: oltre, non è una flessione.
AFFISSO_MASSIMO = 12


@dataclass(frozen=True, slots=True)
class Affisso:
    """Una regola di flessione del file `.aff`: togli `toglie`, metti `mette`."""

    sigla: str
    toglie: str
    mette: str
    condizione: re.Pattern[str] | None
    incrociabile: bool

    def base(self, parola: str, *, suffisso: bool) -> str:
        """La radice che questa regola produrrebbe dalla parola flessa, se applicabile."""
        if suffisso:
            if self.mette and not parola.endswith(self.mette):
                return ""
            tronca = parola[: len(parola) - len(self.mette)] if self.mette else parola
            radice = tronca + self.toglie
        else:
            if self.mette and not parola.startswith(self.mette):
                return ""
            tronca = parola[len(self.mette):] if self.mette else parola
            radice = self.toglie + tronca
        if not radice or radice == parola:
            return ""
        if self.condizione is not None and not self.condizione.search(radice):
            return ""
        return radice


def _condizione(testo: str, *, suffisso: bool) -> re.Pattern[str] | None:
    """La condizione Hunspell (`.`, `[abc]`, `[^abc]`, lettere) come espressione regolare."""
    grezzo = str(testo or "").strip()
    if not grezzo or grezzo == ".":
        return None
    pezzi: list[str] = []
    indice = 0
    while indice < len(grezzo):
        carattere = grezzo[indice]
        if carattere == "[":
            chiusura = grezzo.find("]", indice)
            if chiusura < 0:
                return None
            pezzi.append(grezzo[indice:chiusura + 1])
            indice = chiusura + 1
            continue
        pezzi.append("." if carattere == "." else re.escape(carattere))
        indice += 1
    corpo = "".join(pezzi)
    try:
        return re.compile(corpo + "$" if suffisso else "^" + corpo)
    except re.error:
        return None


def _sigle(testo: str, modo: str) -> tuple[str, ...]:
    """Le sigle di una radice, secondo il modo dichiarato da `FLAG` nel file `.aff`."""
    grezzo = str(testo or "").strip()
    if not grezzo:
        return ()
    if modo == "num":
        return tuple(pezzo.strip() for pezzo in grezzo.split(",") if pezzo.strip())
    if modo == "long":
        return tuple(grezzo[indice:indice + 2] for indice in range(0, len(grezzo) - 1, 2))
    return tuple(grezzo)


@dataclass(frozen=True, slots=True)
class DizionarioItaliano:
    """Le radici con le loro sigle e le regole che le flettono."""

    percorso: str
    radici: dict[str, frozenset[str]]
    suffissi: tuple[Affisso, ...]
    prefissi: tuple[Affisso, ...]

    @property
    def disponibile(self) -> bool:
        return bool(self.radici)

    def _radice_valida(self, radice: str, sigla: str) -> bool:
        return sigla in self.radici.get(radice, frozenset())

    def conosce(self, parola: str) -> bool:
        """Se la parola è italiana: radice del dizionario o sua flessione dichiarata."""
        piatta = str(parola or "").casefold()
        if not piatta:
            return False
        if piatta in self.radici:
            return True
        # Un solo suffisso: «udienze» → «udienza» con la sigla Q.
        for regola in self.suffissi:
            radice = regola.base(piatta, suffisso=True)
            if radice and self._radice_valida(radice, regola.sigla):
                return True
        # Un solo prefisso: «l'atto» → «atto» con la sigla dell'elisione.
        for regola in self.prefissi:
            radice = regola.base(piatta, suffisso=False)
            if radice and self._radice_valida(radice, regola.sigla):
                return True
        # Prefisso e suffisso insieme, solo dove entrambe le regole lo ammettono.
        for prefisso in self.prefissi:
            if not prefisso.incrociabile:
                continue
            senza_prefisso = prefisso.base(piatta, suffisso=False)
            if not senza_prefisso:
                continue
            for suffisso in self.suffissi:
                if not suffisso.incrociabile:
                    continue
                radice = suffisso.base(senza_prefisso, suffisso=True)
                if radice and self._radice_valida(radice, suffisso.sigla) and self._radice_valida(radice, prefisso.sigla):
                    return True
        return False


def _leggi_aff(percorso: Path) -> tuple[str, str, list[Affisso], list[Affisso]]:
    """Codifica dichiarata, modo delle sigle e regole di suffisso e prefisso."""
    codifica, modo = "utf-8", "char"
    grezzo = percorso.read_bytes()
    testa = grezzo[:4096].decode("latin-1", errors="ignore")
    for riga in testa.splitlines():
        if riga.startswith("SET "):
            codifica = riga.split(None, 1)[1].strip() or "utf-8"
        elif riga.startswith("FLAG "):
            dichiarato = riga.split(None, 1)[1].strip().lower()
            modo = "num" if dichiarato == "num" else ("long" if dichiarato == "long" else "char")
    try:
        testo = grezzo.decode(codifica, errors="replace")
    except LookupError:
        testo = grezzo.decode("utf-8", errors="replace")
    suffissi: list[Affisso] = []
    prefissi: list[Affisso] = []
    incrocio: dict[tuple[str, str], bool] = {}
    for riga in testo.splitlines():
        campi = riga.split()
        if len(campi) < 4 or campi[0] not in {"SFX", "PFX"}:
            continue
        tipo, sigla = campi[0], campi[1]
        if campi[2] in {"Y", "N"} and len(campi) == 4 and campi[3].isdigit():
            incrocio[(tipo, sigla)] = campi[2] == "Y"
            continue
        toglie = "" if campi[2] == "0" else campi[2]
        mette = "" if campi[3] == "0" else campi[3].split("/", 1)[0]
        if len(toglie) > AFFISSO_MASSIMO or len(mette) > AFFISSO_MASSIMO:
            continue
        regola = Affisso(
            sigla=sigla, toglie=toglie, mette=mette,
            condizione=_condizione(campi[4] if len(campi) > 4 else ".", suffisso=tipo == "SFX"),
            incrociabile=incrocio.get((tipo, sigla), False),
        )
        (suffissi if tipo == "SFX" else prefissi).append(regola)
        if len(suffissi) + len(prefissi) > REGOLE_MASSIME:
            break
    return codifica, modo, suffissi, prefissi


def _leggi_dic(percorso: Path, codifica: str, modo: str) -> dict[str, frozenset[str]]:
    """Le radici del dizionario con le sigle delle regole che le flettono."""
    radici: dict[str, set[str]] = {}
    grezzo = percorso.read_bytes()
    try:
        testo = grezzo.decode(codifica, errors="replace")
    except LookupError:
        testo = grezzo.decode("utf-8", errors="replace")
    for indice, riga in enumerate(testo.splitlines()):
        if indice == 0 and riga.strip().isdigit():
            continue
        voce = riga.split("\t", 1)[0].strip()
        if not voce or voce.startswith(("/", "#")):
            continue
        parola, _, sigle = voce.partition("/")
        parola = parola.strip().casefold()
        if not parola or any(carattere.isspace() for carattere in parola):
            continue
        radici.setdefault(parola, set()).update(_sigle(sigle, modo))
        if len(radici) > RADICI_MASSIME:
            break
    return {parola: frozenset(sigle) for parola, sigle in radici.items()}


@lru_cache(maxsize=1)
def dizionario_italiano() -> DizionarioItaliano:
    """Il dizionario italiano installato sull'host, oppure uno vuoto se non c'è."""
    for percorso_aff in PERCORSI_AFF:
        aff = Path(percorso_aff)
        dic = aff.with_suffix(".dic")
        if not (aff.is_file() and dic.is_file()):
            continue
        try:
            codifica, modo, suffissi, prefissi = _leggi_aff(aff)
            radici = _leggi_dic(dic, codifica, modo)
        except OSError:
            continue
        if radici:
            return DizionarioItaliano(str(dic), radici, tuple(suffissi), tuple(prefissi))
    return DizionarioItaliano("", {}, (), ())


__all__ = [
    "AFFISSO_MASSIMO", "Affisso", "DizionarioItaliano", "PERCORSI_AFF", "RADICI_MASSIME",
    "REGOLE_MASSIME", "dizionario_italiano",
]
