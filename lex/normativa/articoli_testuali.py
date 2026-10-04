"""Divisione in articoli del testo di un atto Normattiva (intestazioni «Art. N» nel corpo del testo).

Molti XML di Normattiva (codici storici, allegati come il codice del processo amministrativo) non hanno un nodo
NIR ``articolo`` per ogni articolo: il testo arriva in paragrafi e va diviso cercando le intestazioni. La regola
precedente (``\\bArt\\.\\s*N\\s*[.)-]``, senza distinzione tra maiuscole e minuscole) aveva tre difetti:

* tagliava gli articoli sui rimandi interni («... le disposizioni dell'art. 1284.»): art. 2317, 1815 c.c. troncati
  e un frammento finito sotto un numero di articolo sbagliato;
* non riconosceva le intestazioni senza punteggiatura dopo il numero («Art. 29 Azione di annullamento»): gli
  articoli del c.p.a. finivano dentro l'articolo precedente;
* non riconosceva le intestazioni con la rubrica tra parentesi («Art. 183-ter (Ordinanza ...)», «Art. 5-bis (...)»)
  né i suffissi oltre «decies» («669-terdecies»): finivano dentro l'articolo base.

Qui l'intestazione e' «Art.»/«ART.»/«Articolo» con l'iniziale maiuscola, non preceduta da lettere o apostrofi
(«dell'art.»), seguita dal numero, dall'eventuale suffisso latino e da punteggiatura, parentesi o da una parola
con l'iniziale maiuscola (la rubrica).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

SUFFISSI_LATINI = (
    "quinquiesdecies|sexiesdecies|septiesdecies|octiesdecies|noviesdecies|quaterdecies|terdecies|duodecies|"
    "undecies|vicies|decies|novies|nonies|octies|septies|sexies|quinquies|quater|ter|bis"
)

INTESTAZIONE_ARTICOLO_RE = re.compile(
    # non preceduta da lettere/apostrofi («dell'art.») ne' da virgolette: «... e' inserito il seguente: «Art. 183-bis.»
    # negli atti di modifica e' il testo citato di un altro atto, non un articolo di questo
    r"(?<![\w'’«\"“])(?<![«“] )(?:Art\.|ART\.|Articolo|ARTICOLO)\s*(?P<number>\d{1,4})"
    r"(?:[\s.-]*(?P<suffix>" + SUFFISSI_LATINI + r")(?![a-z]))?"
    r"(?:\.(?P<sub>\d{1,3})(?=[\s.(]))?"
    r"(?=\s*[.)\-–—(:]|\s+[A-Z(«\"]|\s*$)"
)

# rimando che apre un frammento («art. 1284. ...»): segno di un vecchio taglio sbagliato
RIMANDO_INIZIALE_RE = re.compile(r"^\s*(?:art\.|artt\.|articolo|articoli)\s*\d", re.UNICODE)
SOLO_INTESTAZIONE_MAX = 90
MINIMO_CARATTERI = 24


@dataclass(slots=True)
class Segmento:
    numero: str          # «669-terdecies», «473-bis.14», «29»
    testo: str


def etichetta_numero(match: re.Match[str]) -> str:
    numero = str(int(match.group("number")))
    suffisso = (match.group("suffix") or "").lower().replace("nonies", "novies")
    sotto = match.group("sub")
    return f"{numero}{'-' + suffisso if suffisso else ''}{'.' + sotto if suffisso and sotto else ''}"


def chiave_numero(etichetta: str) -> str:
    """«Art. 669-terdecies.» / «669 terdecies» -> «669terdecies» (per confronti)."""

    t = str(etichetta or "").lower()
    m = re.search(r"(\d{1,4})(?:[\s-]*(" + SUFFISSI_LATINI + r")(?![a-z]))?(?:\.(\d{1,3})(?!\d))?", t)
    if not m:
        return ""
    suffisso = (m.group(2) or "").replace("nonies", "novies")
    return f"{int(m.group(1))}{suffisso}{'.' + str(int(m.group(3))) if suffisso and m.group(3) else ''}"


def dividi_in_articoli(testo: str) -> list[Segmento]:
    """Segmenti «Art. N ...» del testo, nell'ordine; i frammenti piu' corti di 24 caratteri sono scartati."""

    corrispondenze = list(INTESTAZIONE_ARTICOLO_RE.finditer(testo or ""))
    segmenti: list[Segmento] = []
    for indice, m in enumerate(corrispondenze):
        fine = corrispondenze[indice + 1].start() if indice + 1 < len(corrispondenze) else len(testo)
        pezzo = re.sub(r"\s+", " ", testo[m.start():fine]).strip()
        if len(pezzo) < MINIMO_CARATTERI:
            continue
        segmenti.append(Segmento(etichetta_numero(m), pezzo))
    return segmenti


def solo_intestazione(testo: str) -> bool:
    """«Art. 29 - Azione di annullamento»: nodo NIR con il solo titolo, senza il testo dell'articolo."""

    t = re.sub(r"\s+", " ", str(testo or "")).strip()
    if len(t) > SOLO_INTESTAZIONE_MAX:
        return False
    m = INTESTAZIONE_ARTICOLO_RE.match(t)
    if not m:
        return False
    resto = t[m.end():].lstrip(" .-–—:").strip()
    # il solo titolo non ha frasi: nessun punto fermo e nessun comma numerato
    return "." not in resto and not re.search(r"\b\d+\s", resto)


def inizia_con_rimando(testo: str) -> bool:
    """Frammento nato da un taglio su un rimando interno («art. 1284. Per la determinazione...»)."""

    return bool(RIMANDO_INIZIALE_RE.match(str(testo or "")))


def _normalizza_confronto(testo: str) -> str:
    return re.sub(r"\W+", " ", str(testo or "").lower()).strip()


def deduplica(segmenti: list[Segmento]) -> list[Segmento]:
    """Toglie i doppioni: stesso numero e testo uguale o contenuto in un altro segmento con lo stesso numero."""

    risultato: list[Segmento] = []
    normalizzati: list[tuple[str, str]] = []
    for seg in segmenti:
        chiave = chiave_numero(seg.numero)
        norm = _normalizza_confronto(seg.testo)
        doppione = False
        for i, (chiave_altro, norm_altro) in enumerate(normalizzati):
            if chiave_altro != chiave:
                continue
            if norm == norm_altro or norm in norm_altro:
                doppione = True
                break
            if norm_altro in norm:
                # il nuovo contiene il precedente: si tiene il piu' completo, nella posizione del primo
                risultato[i] = seg
                normalizzati[i] = (chiave, norm)
                doppione = True
                break
        if not doppione:
            risultato.append(seg)
            normalizzati.append((chiave, norm))
    return risultato


__all__ = [
    "INTESTAZIONE_ARTICOLO_RE",
    "SUFFISSI_LATINI",
    "Segmento",
    "chiave_numero",
    "deduplica",
    "dividi_in_articoli",
    "etichetta_numero",
    "inizia_con_rimando",
    "solo_intestazione",
]
