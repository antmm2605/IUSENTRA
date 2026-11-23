"""Passaggi delle pronunce che citano le norme delle schede di istituto (lex/conoscenza/dati/passaggi_pronunce.json).

Per ogni pronuncia dell'indice precalcolato per norma (``lex/harness/dati/giurisprudenza_per_norma.json``) si legge il
testo nell'archivio (Cassazione SentenzeWeb; archivio dello studio per la Corte costituzionale, solo pronunce
pubbliche) e si cerca il punto in cui la pronuncia cita QUELL'articolo di QUELL'atto. Entra solo la pronuncia con il
passaggio trovato; se il passaggio è in una massima lo si dichiara («massima»). Nessuna classificazione favorevole o
contraria: la decide l'avvocato.

Tre passi, perché gli archivi sono leggibili solo nel container dell'applicazione:
1. ``prepara --uscita ingresso.json`` (nel worktree): norme con citazione e pronunce dell'indice;
2. ``leggi --ingresso ingresso.json --uscita letti.json`` (nel container, solo libreria standard, sola lettura);
3. ``scrivi --letti letti.json`` (nel worktree): scrive il file dei passaggi.

Variabili del passo 2: ``SENTENZEWEB_DB`` (predefinito /public-sentenzeweb/giurisprudenza_corpus.db) e
``STUDIO_CORPUS_DB`` (archivio dello studio con le pronunce della Corte costituzionale).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
from datetime import date
from pathlib import Path

RADICE = Path(__file__).resolve().parents[1]

_CODICI = {
    "c.c.": r"(?:c\.\s?c\.|cod\.\s?civ\.?|codice civile)",
    "c.p.c.": r"(?:c\.\s?p\.\s?c\.|cod\.\s?proc\.\s?civ\.?|codice di procedura civile)",
    "c.p.p.": r"(?:c\.\s?p\.\s?p\.|cod\.\s?proc\.\s?pen\.?|codice di procedura penale)",
    "c.p.": r"(?:c\.\s?p\.(?!\s?[acp]\.)|cod\.\s?pen\.?|codice penale)",
    "c.p.a.": r"(?:c\.\s?p\.\s?a\.|cod\.\s?proc\.\s?amm\.?|codice del processo amministrativo|d\.\s?lgs\.?\s*(?:n\.\s*)?104(?:/|\s+del\s+)2010)",
}


def modello_citazione(citazione: str) -> str | None:
    """Espressione che riconosce la citazione dell'articolo nel testo di una pronuncia («art. 414 c.p.c.»,
    «articolo 63 del d.lgs. n. 165 del 2001»)."""
    m = re.match(r"art\.\s*([\d]+)(?:-?\s?(bis|ter|quater|quinquies|sexies|septies|octies))?\s+(.+)$", citazione.strip(), re.I)
    if not m:
        return None
    numero, suffisso, atto = m.group(1), m.group(2), m.group(3).strip().lower()
    art = rf"\bart(?:icol[oi]|t?\.)\s*{numero}" + (rf"\s?-?\s?{suffisso}\b" if suffisso else r"(?![\d]|\s?-?\s?(?:bis|ter|quater)\b)")
    if atto in _CODICI:
        atto_rx = _CODICI[atto]
    else:
        n = re.search(r"(\d+)/(\d{4})", atto)
        if not n:
            return None
        atto_rx = rf"(?:n\.\s*)?{n.group(1)}(?:/|\s+del\s+(?:\d{{1,2}}\s+\w+\s+)?){n.group(2)}"
    return art + r"[^.;]{0,90}?" + atto_rx


def passaggio(testo: str, rx: str) -> str:
    m = re.search(rx, testo or "", re.I)
    if not m:
        return ""
    inizio = max(testo.rfind(". ", 0, m.start()) + 2, m.start() - 350, 0)
    fine = testo.find(". ", m.end())
    fine = min(fine + 1 if fine != -1 else len(testo), m.end() + 350)
    return " ".join(testo[inizio:fine].split())


# ------------------------------------------------------------------------------------------------ 1. prepara
def prepara(uscita: Path) -> None:
    sys.path.insert(0, str(RADICE))
    from lex.harness.norme import NORME

    indice = json.loads((RADICE / "lex" / "harness" / "dati" / "giurisprudenza_per_norma.json").read_text(encoding="utf-8"))
    norme = {}
    for chiave, pronunce in (indice.get("norme") or {}).items():
        if chiave in NORME and pronunce:
            rx = modello_citazione(NORME[chiave].citazione)
            if rx:
                norme[chiave] = {"citazione": NORME[chiave].citazione, "rx": rx, "pronunce": pronunce}
    uscita.write_text(json.dumps({"generato_il": indice.get("generato_il", ""), "norme": norme}, ensure_ascii=False))
    print(f"norme da leggere: {len(norme)}")


# ------------------------------------------------------------------------------------------------ 2. leggi
def _apri(percorso: str):
    if not percorso or not Path(percorso).is_file():
        return None
    c = sqlite3.connect(f"file:{percorso}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    return c


def leggi(ingresso: Path, uscita: Path) -> None:
    dati = json.loads(ingresso.read_text(encoding="utf-8"))
    cass = _apri(os.environ.get("SENTENZEWEB_DB", "/public-sentenzeweb/giurisprudenza_corpus.db"))
    studio = _apri(os.environ.get("STUDIO_CORPUS_DB", ""))
    letti, conteggi = {}, {"pronunce": 0, "con_passaggio": 0, "massime": 0, "non_trovate": 0}
    for chiave, voce in dati["norme"].items():
        uscite = []
        for p in voce["pronunce"]:
            conteggi["pronunce"] += 1
            costituzionale = "costituzional" in p.get("organo", "").lower()
            db = studio if costituzionale else cass
            if db is None:
                continue
            colonne = "id, organo_giudicante, testo_integrale, massima_ufficiale, principio_sintetico, hash_contenuto"
            uuid = re.search(r"id%3A(\w+)", p.get("url", ""))
            if uuid and not costituzionale:
                # Identificativo SentenzeWeb dell'URL ufficiale: lettura per indice, senza scansioni dell'archivio.
                righe = db.execute(f"SELECT {colonne} FROM sentenze WHERE uuid_interno=?",
                                   ("sentenzeweb:" + uuid.group(1),)).fetchall()
            else:
                righe = db.execute(f"SELECT {colonne} FROM sentenze WHERE numero_sentenza IN (?, ?) AND anno_sentenza=?",
                                   (str(p["numero"]), str(p["numero"]).zfill(5), int(p["anno"]))).fetchall()
            ramo = "pen" if "penale" in p.get("organo", "").lower() else ("civ" if "civile" in p.get("organo", "").lower() else "")
            righe = [r for r in righe if not ramo or ramo in str(r["organo_giudicante"] or "").lower()] or righe
            trovato = None
            for r in righe:
                testo = str(r["testo_integrale"] or "")
                t = passaggio(testo, voce["rx"])
                if t:
                    trovato = (t, "testo integrale", r["hash_contenuto"] or hashlib.sha256(testo.encode()).hexdigest())
                    break
                massime = [str(r["massima_ufficiale"] or "")]
                if costituzionale:
                    massime += [str(x[0] or "") for x in db.execute("SELECT testo FROM massime WHERE sentenza_id=?", (r["id"],))]
                for mx in massime:
                    t = passaggio(mx, voce["rx"])
                    if t:
                        trovato = (t, "massima", hashlib.sha256(mx.encode()).hexdigest())
                        break
                if trovato:
                    break
            if not trovato:
                conteggi["non_trovate"] += 1
                continue
            conteggi["con_passaggio"] += 1
            conteggi["massime"] += trovato[1] == "massima"
            sez = f", sez. {p['sezione']}" if p.get("sezione") else ""
            uscite.append({"organo": p["organo"], "sezione": p.get("sezione", ""), "numero": p["numero"], "anno": p["anno"],
                           "data": p.get("data", ""), "url": p.get("url", ""), "archivio": p.get("archivio", ""),
                           "estremi": f"{p['organo']}{sez}, n. {p['numero']}/{p['anno']}",
                           "citazione_norma": voce["citazione"], "passaggio": trovato[0], "tipo_testo": trovato[1],
                           "versione": str(trovato[2])[:16]})
        letti[chiave] = uscite
    uscita.write_text(json.dumps({"letto_il": date.today().isoformat(), "conteggi": conteggi, "norme": letti},
                                 ensure_ascii=False))
    print(json.dumps(conteggi))


# ------------------------------------------------------------------------------------------------ 3. scrivi
def scrivi(letti: Path) -> None:
    dati = json.loads(letti.read_text(encoding="utf-8"))
    out = {"metodo": "pronunce dell'indice per norma lette nel testo: entra solo chi cita l'articolo dell'atto, con il "
                     "passaggio; «massima» quando il passaggio è solo nella massima",
           "letto_il": dati["letto_il"], "conteggi": dati["conteggi"],
           "norme": {k: v for k, v in sorted(dati["norme"].items()) if v}}
    destinazione = RADICE / "lex" / "conoscenza" / "dati" / "passaggi_pronunce.json"
    destinazione.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{destinazione}: {sum(len(v) for v in out['norme'].values())} pronunce con passaggio su {len(out['norme'])} norme")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("passo", choices=("prepara", "leggi", "scrivi"))
    ap.add_argument("--ingresso", type=Path)
    ap.add_argument("--uscita", type=Path)
    ap.add_argument("--letti", type=Path)
    a = ap.parse_args()
    if a.passo == "prepara":
        prepara(a.uscita)
    elif a.passo == "leggi":
        leggi(a.ingresso, a.uscita)
    else:
        scrivi(a.letti)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
