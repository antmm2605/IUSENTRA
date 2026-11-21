"""Indice delle rubriche dei quattro codici dall'archivio Normattiva del software, per l'harness di Lex.

Uso: python scripts/lex_harness_rubriche.py [percorso normattiva.sqlite] [file di uscita]

Per una domanda di diritto senza fatti («entro quale termine deve costituirsi il convenuto?») l'harness trova
l'articolo dalla rubrica ufficiale («Costituzione del convenuto» → art. 166 c.p.c.) e ne legge il testo vigente.
Le rubriche si leggono qui una volta, dagli stessi documenti dell'istantanea ``lex/harness/dati/norme_vigenti.json``
(versione VIGENTE dei codici), e si scrivono in ``lex/harness/dati/rubriche_codici.json``. Gli articoli abrogati
sono esclusi: un articolo che non c'è più non si propone.
"""
from __future__ import annotations

import gzip
import json
import re
import sqlite3
import sys
from datetime import date
from pathlib import Path

RADICE = Path(__file__).resolve().parents[1]
ISTANTANEA = RADICE / "lex" / "harness" / "dati" / "norme_vigenti.json"
USCITA = RADICE / "lex" / "harness" / "dati" / "rubriche_codici.json"
# Testo vigente degli stessi articoli, senza note di aggiornamento: la risposta non aspetta l'archivio di 5 GB
# (una lettura a freddo dell'art. 416 c.p.c. ha richiesto 134 s il 21/11/2026).
TESTI = RADICE / "lex" / "harness" / "dati" / "testi_codici.json.gz"
CODICI = ("cc", "cpc", "cp", "cpp")

_SUFFISSI = sorted(("bis", "ter", "quater", "quinquies", "sexies", "septies", "octies", "novies", "nonies", "decies",
                    "undecies", "duodecies", "terdecies", "quaterdecies", "quinquiesdecies", "sexiesdecies",
                    "septiesdecies", "octiesdecies"), key=len, reverse=True)
_NUMERO = re.compile(r"^Art\.\s*(\d+)(?:[\s\-]*(" + "|".join(_SUFFISSI) + r"))?(?:\.(\d+))?", re.I)
_INTESTAZIONE = re.compile(r"^Art\.\s*\d+(?:[\s\-]*(?:" + "|".join(_SUFFISSI) + r"))?(?:\.\d+)?\.?\s*", re.I)


def numero(etichetta: str) -> str:
    m = _NUMERO.match(etichetta.strip())
    if not m:
        return ""
    return m.group(1) + (m.group(2) or "").lower() + (m.group(3) or "")


def rubrica(testo: str) -> str:
    """«Art. 166. (Costituzione del convenuto). Il convenuto…» → «Costituzione del convenuto»."""
    testo = " ".join(str(testo or "").split())[:600]
    testo = _INTESTAZIONE.sub("", testo)
    if testo.startswith("1 Art."):  # codice di procedura penale: «Art. 336. 1 Art. 336. Querela 1. …»
        testo = _INTESTAZIONE.sub("", testo[2:])
    testo = testo.replace("((", "").replace("))", "").strip()
    m = re.match(r"\(\s*\(?\s*([^()]{3,220}?)\s*\)?\.?\s*\)", testo)
    if m:
        return m.group(1).strip(" .")
    # Codice di procedura penale: rubrica senza parentesi prima del comma 1 («Querela 1. La querela…»).
    m = re.match(r"([A-Z][^0-9]{2,160}?)\s+1\.\s", testo)
    return m.group(1).strip(" .") if m else ""


def senza_note(testo: str) -> str:
    """Il testo dell'articolo senza le note «AGGIORNAMENTO» di Normattiva (restano nell'archivio)."""
    corpo = re.split(r"\s-{5,}\s*AGGIORNAMENTO|\s-{5,}", str(testo or ""), maxsplit=1)[0]
    return " ".join(corpo.split())


def abrogato(testo: str) -> bool:
    return bool(re.search(r"ARTICOLO ABROGATO|CONFERMATO L'ABROGAZIONE|^\W*Art\.[^.]*\.\s*\(*\s*ABROGATO", str(testo)[:240]))


def main() -> int:
    argomenti = [a for a in sys.argv[1:] if not a.startswith("--")]
    db = Path(argomenti[0] if argomenti else "/normattiva-server/normattiva.sqlite")
    uscita = Path(argomenti[1]) if len(argomenti) > 1 else USCITA
    norme = json.loads(ISTANTANEA.read_text(encoding="utf-8"))["norme"]
    documenti = {}
    for chiave, riga in norme.items():
        sigla = chiave.split(":")[0]
        if sigla in CODICI and riga.get("document_id"):
            documenti[sigla] = int(riga["document_id"])
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=30)
    risultato: dict[str, dict[str, str]] = {}
    testi: dict[str, dict[str, str]] = {}
    for sigla, documento in sorted(documenti.items()):
        voci: dict[str, str] = {}
        corpi: dict[str, str] = {}
        for etichetta, testo in conn.execute(
                "select article_number, article_text from normative_articles where document_id = ?", (documento,)):
            n, r = numero(str(etichetta or "")), rubrica(testo)
            if n and r and not abrogato(testo) and n not in voci:
                voci[n] = r
                corpi[n] = senza_note(testo)
        risultato[sigla] = voci
        testi[sigla] = corpi
    dati = {"generata_il": date.today().strftime("%d/%m/%Y"), "archivio": db.name, "documenti": documenti,
            "rubriche": risultato}
    uscita.write_text(json.dumps(dati, ensure_ascii=False, indent=0, sort_keys=True) + "\n", encoding="utf-8")
    aggiornamenti = {}
    for sigla, documento in documenti.items():
        voce = conn.execute("select xml_entry from normative_documents where id = ?", (documento,)).fetchone()
        m = re.search(r"VIGENZA_(\d{4})-(\d{2})-(\d{2})", str(voce[0] if voce else ""))
        aggiornamenti[sigla] = f"{m.group(3)}/{m.group(2)}/{m.group(1)}" if m else ""
    file_testi = Path(argomenti[2]) if len(argomenti) > 2 else TESTI
    contenuto = json.dumps({"generata_il": dati["generata_il"], "archivio": db.name, "aggiornamento": aggiornamenti,
                            "testi": testi}, ensure_ascii=False, sort_keys=True).encode("utf-8")
    file_testi.write_bytes(gzip.compress(contenuto, compresslevel=9, mtime=0))
    print({s: len(v) for s, v in risultato.items()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
