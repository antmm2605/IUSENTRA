"""Istantanea delle norme dell'harness di Lex dall'archivio Normattiva del software.

Uso: python scripts/lex_harness_norme.py [percorso normattiva.sqlite] [--solo chiave,chiave]

Legge una sola volta l'archivio (una scansione per tutti gli atti del catalogo, poi gli articoli per documento con
l'indice), con le stesse regole di ``web.services.ricerca_legale_norma_citata`` (atto univoco per numero e anno, versione
VIGENTE più recente, articolo con il numero richiesto), e scrive ``lex/harness/dati/norme_vigenti.json`` con testo,
URN Normattiva, data dell'aggiornamento dell'archivio e impronta SHA-256. Le norme non trovate sono elencate a parte:
l'harness non le afferma finché non sono nell'archivio.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
import time
from datetime import date
from pathlib import Path

RADICE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RADICE))

from lex.harness.norme import ISTANTANEA, NORME  # noqa: E402
from web.services import ricerca_legale_norma_citata as nc  # noqa: E402


RACCOLTE_PRINCIPALI = ("Codici", "DL e leggi di conversione", "Decreti Legislativi", "Integrazione leggi essenziali",
                       "Testi Unici", "Leggi costituzionali", "Leggi delega e relativi provvedimenti delegati")


def main() -> int:
    valori = {sys.argv[i + 1] for i, a in enumerate(sys.argv[:-1]) if a in ("--solo", "--raccolte")}
    argomenti = [a for a in sys.argv[1:] if not a.startswith("--") and a not in valori]
    db = Path(argomenti[0] if argomenti else "/home/antmm2605/iusentra-normattiva-dal-server/normattiva.sqlite")
    solo = set()
    if "--solo" in sys.argv:
        solo = set(sys.argv[sys.argv.index("--solo") + 1].split(","))
    precedente = json.loads(ISTANTANEA.read_text(encoding="utf-8")) if ISTANTANEA.is_file() else {"norme": {}}
    voci = {k: n for k, n in NORME.items() if not solo or k in solo}
    estremi = {}
    for k, n in voci.items():
        e = nc.estremi(n.estremi)
        if e:
            # «473-bis.11»: l'estrattore generale si ferma al suffisso latino; il numero esatto è quello del catalogo.
            e["articolo"] = nc._normale(n.estremi.split()[1])
            e["comma"] = ""
        estremi[k] = e
    numeri = sorted({e["numero"] for e in estremi.values() if e})
    t0 = time.time()
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=30)
    conn.row_factory = sqlite3.Row
    # Con l'indice delle raccolte si evita di scorrere tutto l'archivio (oltre 5 GB): prima le raccolte piccole che
    # contengono codici e leggi speciali, poi, solo per gli atti non trovati, le altre raccolte.
    righe: list[dict] = []
    # Atti già letti in un'istantanea precedente (stesso numero/anno): si rileggono per identificativo, senza scansione.
    atti = {n.estremi.split(" ", 2)[2] for n in voci.values()}
    noti = sorted({int(v["document_id"]) for k, v in (precedente.get("norme") or {}).items()
                   if k in NORME and v.get("document_id") and NORME[k].estremi.split(" ", 2)[2] in atti})
    if noti:
        base = [dict(r) for r in conn.execute(
            "SELECT id, numero, data_atto, titolo, vigenza, xml_entry, zip_path FROM normative_documents WHERE id IN (%s)"
            % ",".join("?" * len(noti)), noti)]
        righe += base
    gruppi: tuple = (RACCOLTE_PRINCIPALI, None)
    if "--raccolte" in sys.argv:
        gruppi = (tuple(sys.argv[sys.argv.index("--raccolte") + 1].split(",")),)
    for gruppo in gruppi:
        mancano = [n for n in numeri if not any(r["numero"] == n for r in righe)]
        if not mancano:
            break
        filtro = (" AND collection_name IN (%s)" % ",".join("?" * len(gruppo))) if gruppo else ""
        righe += [dict(r) for r in conn.execute(
            "SELECT id, numero, data_atto, titolo, vigenza, xml_entry, zip_path FROM normative_documents "
            + ("INDEXED BY idx_normative_documents_collection " if gruppo else "")
            + "WHERE numero IN (%s)" % ",".join("?" * len(mancano)) + filtro, [*mancano, *(gruppo or ())])]
        print(f"raccolte {'principali' if gruppo else 'tutte'}: {len(righe)} documenti candidati in {time.time() - t0:.0f}s", flush=True)
        if "--solo-principali" in sys.argv:
            break
    norme = dict(precedente.get("norme") or {})
    mancanti = [m for m in precedente.get("mancanti") or [] if m.split(":", 2)[0] + ":" + m.split(":", 2)[1] not in voci]
    for chiave, e in estremi.items():
        if not e:
            mancanti.append(f"{chiave}: estremi non riconosciuti")
            continue
        prefissi = nc._PREFISSI_ARCHIVIO.get(e["prefisso"], (e["prefisso"],))
        cand = [r for r in righe if r["numero"] == e["numero"] and str(r["data_atto"] or "").startswith(e["anno"])
                and any(str(r["xml_entry"] or "").startswith(p + "_") for p in prefissi)]
        if len({r["data_atto"] for r in cand}) != 1:
            mancanti.append(f"{chiave}: atto non univoco o assente ({len(cand)} candidati)")
            continue
        documento, articolo = None, None
        # Dalla vigente più recente; se un'edizione non contiene l'articolo (solo il decreto di approvazione), la successiva.
        for documento in nc._documenti_ordinati(cand):
            articolo = nc._articolo(conn, documento["id"], e)
            if articolo is not None:
                break
        if articolo is None or not (articolo.get("article_text") or "").strip():
            mancanti.append(f"{chiave}: articolo assente nell'archivio")
            continue
        testo = " ".join(str(articolo["article_text"]).split())
        vig = nc._vigenza_file(documento)
        norme[chiave] = {
            "citazione": NORME[chiave].citazione, "testo": testo, "url": nc._url(e, documento),
            "titolo_atto": str(documento.get("titolo") or "").strip()[:200],
            "aggiornamento": f"{vig[8:]}/{vig[5:7]}/{vig[:4]}" if vig else "",
            "vigente": (documento.get("vigenza") or "").upper() == "VIGENTE",
            "document_id": documento["id"], "article_id": articolo["id"],
            "sha256": hashlib.sha256(testo.encode()).hexdigest(),
        }
        print(f"{chiave}: letto ({len(testo)} caratteri, aggiornamento {norme[chiave]['aggiornamento']})", flush=True)
    ISTANTANEA.parent.mkdir(parents=True, exist_ok=True)
    ISTANTANEA.write_text(json.dumps({"generata_il": date.today().strftime("%d/%m/%Y"), "archivio": str(db.name),
                                      "norme": dict(sorted(norme.items())), "mancanti": mancanti},
                                     ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"scritte {len(norme)} norme, mancanti {len(mancanti)}", *mancanti, sep="\n")
    return 0




# Atti assenti dall'archivio: testo vigente scaricato da Normattiva (Akoma Ntoso), stessa lettura dell'importatore.
URN_NORMATTIVA = {
    "dlgs231": "urn:nir:stato:decreto.legislativo:2002-10-09;231",
    "dpr600": "urn:nir:presidente.repubblica:decreto:1973-09-29;600",
    "l241": "urn:nir:stato:legge:1990-08-07;241",
}


def da_normattiva(chiavi: list[str]) -> int:
    from lxml import etree

    from lex.normativa.biblioteca.normattiva_akn import NS, _numero, _testo, scarica

    istantanea = json.loads(ISTANTANEA.read_text(encoding="utf-8"))
    oggi = date.today()
    per_atto: dict[str, list[str]] = {}
    for k in chiavi:
        per_atto.setdefault(k.split(":")[0], []).append(k)
    for prefisso, voci in per_atto.items():
        urn = URN_NORMATTIVA.get(prefisso)
        if not urn:
            print(f"{prefisso}: URN non censito")
            continue
        atto = scarica(urn, oggi.strftime("%Y%m%d"))
        radice = etree.fromstring(atto.xml, etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=True))
        articoli = {}
        for el in radice.iter("{%s}article" % NS["a"]):
            num = el.find("a:num", NS)
            if num is not None:
                articoli.setdefault(_numero(_testo(num)), el)
        for k in voci:
            numero = k.split(":")[1]
            el = articoli.get(numero)
            if el is None:
                print(f"{k}: articolo non trovato nel testo Normattiva")
                continue
            testo = _testo(el)
            istantanea["norme"][k] = {
                "citazione": NORME[k].citazione, "testo": testo, "url": f"https://www.normattiva.it/uri-res/N2Ls?{urn}~art{numero}",
                "titolo_atto": atto.titolo_pagina[:200], "aggiornamento": date.fromisoformat(atto.data_espressione).strftime("%d/%m/%Y") if atto.data_espressione else "", "vigente": True,
                "origine": f"Normattiva, testo vigente al {oggi.strftime('%d/%m/%Y')} (Akoma Ntoso)",
                "sha256": hashlib.sha256(testo.encode()).hexdigest(),
            }
            istantanea["mancanti"] = [m for m in istantanea.get("mancanti", []) if not m.startswith(k + ":")]
            print(f"{k}: letto da Normattiva ({len(testo)} caratteri)")
    ISTANTANEA.write_text(json.dumps(istantanea, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    if "--normattiva" in sys.argv:
        raise SystemExit(da_normattiva(sys.argv[sys.argv.index("--normattiva") + 1].split(",")))
    raise SystemExit(main())
