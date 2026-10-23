"""Varianti limitate e dichiarate per cercare metadati OpenGA.

Non cambiano fatti o fonti, non filtrano obbligatoriamente per territorio e non
sostituiscono la domanda originale. Nessun riferimento a casi del benchmark.
"""

import re
from lex.ricerca_giuridica.testo import senza_accenti

_UNITA = ["", "uno", "due", "tre", "quattro", "cinque", "sei", "sette", "otto", "nove"]
_DECINE = {
    10: "dieci",
    20: "venti",
    30: "trenta",
    40: "quaranta",
    50: "cinquanta",
    60: "sessanta",
    70: "settanta",
    80: "ottanta",
    90: "novanta",
}
_SPECIALI = [
    "dieci",
    "undici",
    "dodici",
    "tredici",
    "quattordici",
    "quindici",
    "sedici",
    "diciassette",
    "diciotto",
    "diciannove",
]


def _numeri():
    result = {word: str(10 + i) for i, word in enumerate(_SPECIALI)}
    for decina, parola in _DECINE.items():
        if decina == 10:
            continue
        for unita, suffisso in enumerate(_UNITA):
            radice = parola[:-1] if unita in {1, 8} else parola
            result[radice + suffisso] = str(decina + unita)
    return result


_NUMERI = _numeri()


def varianti_query(query, sedi):
    """Una variante generale additiva: numeri 10-99 e aggettivi geografici."""
    originale = str(query or "").strip()
    if not originale:
        return []
    motivi = []
    cities = sorted({str(s).rsplit(" - ", 1)[-1].strip().lower() for s in sedi if " - " in str(s)})

    def replace(match):
        word = senza_accenti(match.group().lower())
        if word in _NUMERI:
            motivi.append("numero_in_lettere")
            return _NUMERI[word]
        for city in cities:
            roots = [city[:-1]] if city[-1:] in "aeiou" else [city]
            if city.endswith("ia"):
                roots.append(city[:-2])
            for root in roots:
                if " " not in city and len(root) >= 3 and word != city and word.startswith(root):
                    suffix = word[len(root) :]
                    if suffix in {
                        "o", "a", "i", "e", "itano", "itana", "itani", "itane",
                        "ese",
                        "esi",
                        "ino",
                        "ina",
                        "ini",
                        "ine",
                        "ano",
                        "ana",
                        "ani",
                        "ane",
                        "ense",
                        "ensi",
                        "etano",
                        "etana",
                        "etani",
                        "etane",
                    }:
                        motivi.append("aggettivo_geografico")
                        return city
        return match.group()

    normalizzata = re.sub(r"[A-Za-zÀ-ÿ]+", replace, originale)
    variants = []
    if normalizzata != originale:
        variants.append({"query": normalizzata, "motivi": sorted(set(motivi))})
    return variants[:1]


def sedi_menzionate(query, sedi):
    """Suggerimenti geografici additivi; non sostituiscono mai un filtro esplicito."""
    queries = [str(query)] + [v["query"] for v in varianti_query(query, sedi)]
    result = []
    for sede in sorted(sedi):
        if " - " not in sede:
            continue
        city = senza_accenti(sede.rsplit(" - ", 1)[-1].strip().lower())
        if any(re.search(r"(?<!\w)" + re.escape(city) + r"(?!\w)", senza_accenti(q.lower())) for q in queries):
            result.append(sede)
    return result[:2]


def sede_richiesta(query, sedi):
    """Solo il primo TAR esplicitamente richiesto; mai il giudice citato in seguito.

    Una citta senza il nome dell'organo non determina competenza o filtro.
    Se un nome regionale ha piu sedi si restituisce ambiguita, non una scelta.
    """
    titles = list(sedi.values()) if isinstance(sedi, dict) else list(sedi)
    normalized = senza_accenti(str(query).lower()).replace("’", "'")
    match = re.search(r"\btar\b", normalized)
    if not match:
        if re.search(r"\bconsiglio di stato\b", normalized):
            return [code for code, title in (sedi.items() if isinstance(sedi, dict) else [(s, s) for s in sedi]) if title.startswith("CdS GIURISDIZIONALE")]
        return []
    segment = normalized[match.end():match.end() + 35]
    geo_titles = titles + ["Regione - " + title[4:].split(" - ", 1)[0] for title in titles if title.startswith("TAR ")]
    variants = varianti_query(segment, geo_titles)
    segment = variants[0]["query"] if variants else segment
    segment = senza_accenti(segment.lower()).replace("’", "'")
    found = []
    for code, title in sorted(sedi.items()) if isinstance(sedi, dict) else [(s, s) for s in sedi]:
        if not title.startswith("TAR ") or " - " not in title:
            continue
        region, city = title[4:].split(" - ", 1)
        for name, specificity in [(city, 0), (region, 1)]:
            key = senza_accenti(name.lower()).replace("’", "'")
            if key.startswith("l'"):
                key = key[2:]
            place = re.search(r"(?<!\w)" + re.escape(key) + r"(?!\w)", segment)
            if place:
                found.append((specificity, place.start(), code))
    if not found:
        return []
    best = min((specificity, pos) for specificity, pos, code in found)
    return sorted({code for specificity, pos, code in found if (specificity, pos) == best})


def query_sostanziale(query, sedi):
    """Compressione additiva per embedding, senza introdurre parole o sinonimi.

    Si eliminano solo stopword e formule di richiesta, mai numeri o codici.
    La domanda originale resta un canale distinto e tracciato.
    """
    from lex.ricerca_giuridica.testo import STOPWORD, PAROLE_DOMANDA, parole
    ignore = set(STOPWORD) | set(PAROLE_DOMANDA) | {"cerco", "cerca", "cercare", "davanti", "controversia", "controversie", "relativo", "relativa", "relativi", "relative"}
    tokens = [w for w in parole(str(query)) if senza_accenti(w.lower()) not in ignore]
    compact = " ".join(tokens)
    return compact if len(compact) < .85 * len(str(query)) else ""
