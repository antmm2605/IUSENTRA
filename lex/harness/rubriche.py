"""Domande di diritto senza fatti: l'articolo si trova dalla rubrica ufficiale e si risponde con il testo vigente.

«Entro quale termine deve costituirsi il convenuto nel rito ordinario?» non è una fattispecie con fatti da
qualificare: la risposta è il testo di una norma. Le rubriche dei quattro codici (c.c., c.p.c., c.p., c.p.p.) sono
lette una volta dall'archivio Normattiva del software (``scripts/lex_harness_rubriche.py`` →
``dati/rubriche_codici.json``); qui si confrontano le parole della domanda con le rubriche e, se un articolo vince
con certezza, se ne legge il testo vigente (istantanea dell'harness o archivio dal vivo). Nessuna norma a memoria:
se l'articolo non si legge, non si risponde con quell'articolo.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from .norme import NORME, Norma, _archivio_dal_vivo, _istantanea, piano

RUBRICHE = Path(__file__).with_name("dati") / "rubriche_codici.json"
TESTI = Path(__file__).with_name("dati") / "testi_codici.json.gz"
_URN = {"cc": "urn:nir:stato:regio.decreto:1942-03-16;262", "cpc": "urn:nir:stato:regio.decreto:1940-10-28;1443",
        "cp": "urn:nir:stato:regio.decreto:1930-10-19;1398",
        "cpp": "urn:nir:presidente.repubblica:decreto:1988-09-22;447"}

_ESTREMI = {"cc": "r.d. 262/1942", "cpc": "r.d. 1443/1940", "cp": "r.d. 1398/1930", "cpp": "d.p.r. 447/1988"}
_SIGLA = {"cc": "c.c.", "cpc": "c.p.c.", "cp": "c.p.", "cpp": "c.p.p."}
# Parole della domanda che non identificano l'istituto (forma della domanda, richiesta di citare, tempo).
_VUOTE = set("""entro quale quali quando quanto quanti come cosa deve devono devo puo possono essere fare
termine termini giorni giorno mesi anni norma norme articolo articoli cita citare indica indicami dimmi spiega
rito ordinario ordinaria cognizione processo civile penale codice procedura secondo prevede previsto prevista
nella nello negli della dello degli delle dalla dallo dagli dalle sulla sullo sugli sulle alla allo agli alle
anche oppure ovvero quale qual essere stato stata parte parti caso casi regola regole vigente vigenti oggi""".split())
# Riti speciali del c.p.c.: si scelgono solo se la domanda li nomina (la stessa rubrica torna in più riti).
_RITI_SPECIALI = (
    (r"lavor|previdenz|locazion|comodat|affitt", lambda n: 409 <= n <= 447),
    (r"famigli|separazion|divorzi|minor|figli|coniug", lambda n: 473 <= n <= 474),
    (r"semplificat", lambda n: n == 281),
)


@dataclass(frozen=True)
class Candidato:
    sigla: str
    numero: str
    rubrica: str
    punteggio: int

    @property
    def chiave(self) -> str:
        return f"{self.sigla}:{self.numero}"

    @property
    def citazione(self) -> str:
        return f"art. {leggibile(self.numero)} {_SIGLA[self.sigla]}"


def leggibile(numero: str) -> str:
    """«163bis» → «163-bis»; «473bis12» → «473-bis.12»."""
    m = re.fullmatch(r"(\d+)([a-z]*)(\d*)", numero)
    if not m:
        return numero
    return m.group(1) + (f"-{m.group(2)}" if m.group(2) else "") + (f".{m.group(3)}" if m.group(3) else "")


def _radici(testo: str) -> set[str]:
    parole = re.findall(r"[a-z]{4,}", piano(testo))
    return {p[:6] for p in parole if p not in _VUOTE}


@lru_cache(maxsize=1)
def _indice() -> dict[str, dict[str, tuple[str, frozenset[str]]]]:
    try:
        dati = json.loads(RUBRICHE.read_text(encoding="utf-8")).get("rubriche", {})
    except (OSError, ValueError):
        return {}
    return {s: {n: (r, frozenset(_radici(r))) for n, r in voci.items()} for s, voci in dati.items()}


def _codici_della_domanda(t: str) -> tuple[str, ...]:
    if re.search(r"\bc\s*\.?\s*p\s*\.?\s*p\b|procedura penale", t):
        return ("cpp",)
    if re.search(r"\bc\s*\.?\s*p\s*\.?\s*c\b|procedura civile", t):
        return ("cpc",)
    if re.search(r"\bc\s*\.?\s*c\b|codice civile", t):
        return ("cc",)
    if re.search(r"\bc\s*\.?\s*p\b|codice penale", t):
        return ("cp",)
    if re.search(r"penal|reato|imputat|indagat|querel|pubblico ministero", t):
        return ("cpp", "cp")
    if re.search(r"\b(?:rito|udienz|convenut|attor|citazion|comparsa|giudizi|processo|sentenz|appell|ricors|"
                 r"pignorament|precett|esecuzion|notific|costitu\w* in giudizio)", t):
        return ("cpc", "cc")
    return ("cc", "cpc", "cp", "cpp")


def candidati(domanda: str) -> list[Candidato]:
    """Articoli la cui rubrica contiene tutte le sue parole significative presenti nella domanda (almeno due)."""
    t = piano(domanda)
    radici = _radici(domanda)
    if len(radici) < 2:
        return []
    indice = _indice()
    trovati: list[Candidato] = []
    for posto, sigla in enumerate(_codici_della_domanda(t)):
        for numero, (rubrica, parole) in indice.get(sigla, {}).items():
            comuni = radici & parole
            mancanti = len(parole - comuni)
            # La rubrica deve essere richiamata dalla domanda: «Costituzione del convenuto» sì, «Costituzione
            # dell'attore» no; con tre parole in comune si tollera una parola della rubrica non detta («diritto»).
            if (len(comuni) >= 2 and not mancanti) or (len(comuni) >= 3 and mancanti <= 1):
                trovati.append(Candidato(sigla, numero, rubrica, len(comuni) * 10 - mancanti * 5 - posto))
    if not trovati:
        return []
    for segnale, nel_rito in _RITI_SPECIALI:
        speciale = [c for c in trovati if c.sigla == "cpc" and nel_rito(_intero(c.numero))]
        if re.search(segnale, t):
            trovati = speciale or trovati
        elif len(speciale) < len(trovati):
            trovati = [c for c in trovati if c not in speciale]
    migliore = max(c.punteggio for c in trovati)
    return sorted((c for c in trovati if c.punteggio == migliore), key=lambda c: (c.sigla, _intero(c.numero), c.numero))


def _intero(numero: str) -> int:
    m = re.match(r"\d+", numero)
    return int(m.group()) if m else 0


@lru_cache(maxsize=1)
def _testi() -> dict:
    import gzip

    try:
        return json.loads(gzip.decompress(TESTI.read_bytes()).decode("utf-8"))
    except (OSError, ValueError):
        return {}


def url_normattiva(sigla: str, numero: str) -> str:
    """URN Normattiva dell'articolo: «473bis12» → «~art473bis.12» (come nell'istantanea dell'harness)."""
    m = re.fullmatch(r"(\d+[a-z]*)(\d*)", numero)
    articolo = (m.group(1) + (f".{m.group(2)}" if m.group(2) else "")) if m else numero
    return f"https://www.normattiva.it/uri-res/N2Ls?{_URN[sigla]}~art{articolo}"


def testo_vigente(c: Candidato) -> dict | None:
    """Testo vigente: istantanea dell'harness, poi testi dei codici letti dall'archivio con le rubriche (stessa
    versione VIGENTE), infine l'archivio Normattiva dal vivo."""
    riga = _istantanea().get(c.chiave) if c.chiave in NORME else None
    if riga and riga.get("testo"):
        return riga
    dati = _testi()
    testo = ((dati.get("testi") or {}).get(c.sigla) or {}).get(c.numero)
    if testo:
        return {"testo": testo, "url": url_normattiva(c.sigla, c.numero), "vigente": True,
                "aggiornamento": str((dati.get("aggiornamento") or {}).get(c.sigla) or "")}
    norma = Norma(c.chiave, f"art. {leggibile(c.numero)} {_ESTREMI[c.sigla]}", c.citazione, c.rubrica)
    return _archivio_dal_vivo(norma)


def disposizione(testo: str) -> str:
    """Il testo dell'articolo senza le note di aggiornamento e i rinvii numerici di Normattiva."""
    corpo = re.split(r"\s-{5,}\s*AGGIORNAMENTO|\s-{5,}", str(testo or ""), maxsplit=1)[0]
    corpo = re.sub(r"\s*\(\(\d+\)\)|\s*\(\d{1,3}\)(?=\s|$)", "", corpo)
    corpo = corpo.replace("((", "").replace("))", "")
    return " ".join(corpo.split())


def _frase_del_termine(testo: str) -> str:
    for frase in re.split(r"(?<=[.;])\s+", testo):
        if re.search(r"\bgiorni\b|\bmesi\b|\banni\b|\bentro\b|\bprima dell", frase):
            return frase.strip()
    return ""


@dataclass
class RispostaRubrica:
    testo: str
    fonti: list[dict[str, str]]
    norme: list[str]


def rispondi_da_rubrica(domanda: str, tipo: str) -> RispostaRubrica | None:
    trovati = candidati(domanda)
    if not trovati or len(trovati) > 3:
        return None
    letti = [(c, r) for c in trovati if (r := testo_vigente(c)) and r.get("testo") and r.get("vigente", True)]
    if not letti:
        return None
    principale, riga = letti[0]
    corpo = disposizione(riga["testo"])
    agg = f", aggiornamento dell'archivio {riga['aggiornamento']}" if riga.get("aggiornamento") else ""
    righe = ["**Cosa ho capito**",
             f"- Domanda di diritto senza fatti del caso: rispondo con la norma vigente che la disciplina, "
             f"trovata dalla rubrica ufficiale («{principale.rubrica}»).", ""]
    frase = _frase_del_termine(corpo) if tipo == "termine" or re.search(r"\btermin|\bentro\b|quando", piano(domanda)) else ""
    if len(letti) == 1:
        righe += ["**Risposta**", f"- {principale.citazione} ({principale.rubrica}): «{frase or corpo[:600]}»", ""]
    else:
        righe += ["**Risposta**", f"- La rubrica «{principale.rubrica}» compare in più articoli: indica il contratto, "
                  "il rito o l'istituto per scegliere quello giusto. Li riporto tutti, nel testo vigente.", ""]
    righe += [f"**Testo vigente di {principale.citazione}** (archivio Normattiva di IUSENTRA{agg})", "", f"> {corpo}", ""]
    for c, r in letti[1:]:
        righe.append(f"- {c.citazione} ({c.rubrica}): «{disposizione(r['testo'])[:400]}»")
    if len(letti) > 1:
        righe.append("")
    if re.search(r"d\.\s*lgs\.?\s*(?:10 ottobre 2022, n\.\s*)?149", str(riga["testo"]), re.I):
        righe.append("_Nota di vigenza: il testo è quello introdotto dal d.lgs. 149/2022, che si applica ai "
                     "procedimenti instaurati dal 28/02/2023; per quelli pendenti a quella data valgono le "
                     "disposizioni anteriori (art. 35 d.lgs. 149/2022)._")
        righe.append("")
    if riga.get("url"):
        righe.append(f"Fonte ufficiale: {riga['url']}")
    fonti = [{"title": f"Normattiva — {c.citazione}", "url": str(r.get("url") or "")} for c, r in letti if r.get("url")]
    return RispostaRubrica("\n".join(righe).strip(), fonti, [c.chiave for c, _ in letti])
