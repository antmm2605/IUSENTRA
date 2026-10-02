#!/usr/bin/env python3
"""Archivio Normattiva completo sul PC: scarica, importa, indicizza, verifica, impacchetta.

Usa lo stesso codice del server (``tools/normattiva_multi_sync.py``, ``lex/normativa/normattiva_importer.py``,
``lex/ricerca_giuridica``): stessi endpoint, stesso formato, stesso schema SQLite. I dati finiscono in

    <base>/normativa/raw/                       ZIP scaricati
    <base>/normativa/manifests/                 manifest dei download
    <base>/normativa/normattiva.sqlite          database (documenti, articoli, chunk, indice FTS5)
    <base>/normativa/vettori_normattiva/        indice vettoriale
    <base>/normativa/index/normattiva_chunks.jsonl
    <base>/pacchetti/lex-fonti-AAAAMMGG-HHMM.tar.zst (+ .sha256)

``<base>`` e' ``$IUSENTRA_LEX_LOCALE_DIR`` oppure ``~/iusentra-lex-fonti`` (opzione ``--base``).

Sottocomandi: scarica, importa, vettori, verifica, pacchetto. Ogni comando si puo' interrompere e rilanciare.
Il pacchetto si installa sul server con ``deploy/hetzner/carica_fonti_lex.sh``.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import io
import json
import os
import platform
import shutil
import sqlite3
import subprocess
import sys
import tarfile
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

RADICE = Path(__file__).resolve().parents[1]
if str(RADICE) not in sys.path:
    sys.path.insert(0, str(RADICE))

VERSIONE_PACCHETTO = 1
RICERCHE_DI_PROVA = (
    ("art. 2043 c.c.", "2043"),
    ("presupposti responsabilita' extracontrattuale", ""),
    ("termine per proporre appello", ""),
)


# ---------------------------------------------------------------------------------------------- #
# Percorsi                                                                                        #
# ---------------------------------------------------------------------------------------------- #

@dataclass(frozen=True)
class Percorsi:
    base: Path

    @property
    def normativa(self) -> Path:
        return self.base / "normativa"

    @property
    def raw(self) -> Path:
        return self.normativa / "raw"

    @property
    def manifest(self) -> Path:
        return self.normativa / "manifests" / "normattiva_download_manifest.json"

    @property
    def db(self) -> Path:
        return self.normativa / "normattiva.sqlite"

    @property
    def jsonl(self) -> Path:
        return self.normativa / "index" / "normattiva_chunks.jsonl"

    @property
    def report(self) -> Path:
        return self.normativa / "reports" / "normattiva_import_report.json"

    @property
    def vettori(self) -> Path:
        return self.normativa / "vettori_normattiva"

    @property
    def pacchetti(self) -> Path:
        return self.base / "pacchetti"


def percorsi_da_args(args: argparse.Namespace) -> Percorsi:
    base = args.base or os.getenv("IUSENTRA_LEX_LOCALE_DIR") or str(Path.home() / "iusentra-lex-fonti")
    return Percorsi(Path(base).expanduser().resolve())


def spazio_libero_gib(percorso: Path) -> float:
    percorso.mkdir(parents=True, exist_ok=True)
    return shutil.disk_usage(percorso).free / 1024**3


def sha256_file(percorso: Path, blocco: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with percorso.open("rb") as f:
        while True:
            dati = f.read(blocco)
            if not dati:
                break
            h.update(dati)
    return h.hexdigest()


def _gib(byte: int) -> str:
    return f"{byte / 1024**3:.2f} GiB"


# ---------------------------------------------------------------------------------------------- #
# scarica                                                                                         #
# ---------------------------------------------------------------------------------------------- #

def verifica_zip_scaricati(raw: Path, manifest: Path) -> list[str]:
    """Controlla ogni ZIP del manifest: esiste, non e' vuoto, sha256 uguale al manifest, archivio leggibile.

    Gli ZIP danneggiati vengono eliminati cosi' che il prossimo ``scarica`` li riscarichi.
    Restituisce l'elenco dei problemi (vuoto se tutto e' integro).
    """

    problemi: list[str] = []
    if not manifest.exists():
        return [f"manifest assente: {manifest}"]
    dati = json.loads(manifest.read_text(encoding="utf-8"))
    for voce in list(dati.get("items") or []):
        percorso = Path(str(voce.get("output_path") or ""))
        nome = str(voce.get("collection_name") or percorso.name)
        if not percorso.is_file():
            problemi.append(f"{nome}: file mancante ({percorso.name})")
            continue
        atteso = str(voce.get("sha256") or "")
        if percorso.stat().st_size == 0:
            problemi.append(f"{nome}: file vuoto")
            percorso.unlink(missing_ok=True)
            continue
        try:
            with zipfile.ZipFile(percorso) as archivio:
                rotto = archivio.testzip()
        except zipfile.BadZipFile as exc:
            problemi.append(f"{nome}: ZIP non valido ({exc})")
            percorso.unlink(missing_ok=True)
            continue
        if rotto:
            problemi.append(f"{nome}: voce danneggiata {rotto}")
            percorso.unlink(missing_ok=True)
            continue
        if atteso and voce.get("content_type") not in {"existing-file", "existing-sha"} and sha256_file(percorso) != atteso:
            problemi.append(f"{nome}: sha256 diverso dal manifest")
            percorso.unlink(missing_ok=True)
    return problemi


def _nomi_attesi(insieme: str) -> list[str]:
    from lex.normativa.normattiva_client import NormattivaClient
    from tools.normattiva_multi_sync import DEFAULT_STUDIO_LEGALE_CORE

    if insieme == "core":
        return list(DEFAULT_STUDIO_LEGALE_CORE)
    return NormattivaClient().list_collection_names()


def cmd_scarica(args: argparse.Namespace) -> int:
    p = percorsi_da_args(args)
    p.raw.mkdir(parents=True, exist_ok=True)
    libero = spazio_libero_gib(p.raw)
    print(f"Cartella dati: {p.normativa}  (spazio libero {libero:.1f} GiB)")
    if libero < args.spazio_minimo_gib:
        print(f"Spazio insufficiente: servono almeno {args.spazio_minimo_gib} GiB liberi (opzione --spazio-minimo-gib).")
        return 2
    for parziale in p.raw.glob("*.zip.part"):
        parziale.unlink(missing_ok=True)  # download interrotto: si riparte da quella collezione

    comando = [
        sys.executable,
        str(RADICE / "tools" / "normattiva_multi_sync.py"),
        "--download-core" if args.insieme == "core" else "--download-all-from-api",
        "--replace-existing",
        "--vigenza",
        args.vigenza,
        "--out",
        str(p.raw),
        "--manifest",
        str(p.manifest),
        "--sleep",
        str(args.pausa),
    ]
    problemi: list[str] = []
    for tentativo in range(1, args.tentativi + 1):
        print(f"\n== Download Normattiva ({args.insieme}, {args.vigenza}), tentativo {tentativo}/{args.tentativi} ==")
        esito = subprocess.run(comando, cwd=str(RADICE))
        if esito.returncode != 0:
            print(f"Il downloader e' terminato con codice {esito.returncode}.")
        problemi = verifica_zip_scaricati(p.raw, p.manifest)
        if not problemi and esito.returncode == 0:
            break
        for riga in problemi:
            print(f"  PROBLEMA: {riga}")
        if tentativo < args.tentativi:
            print("Rilancio il download delle sole collezioni mancanti o danneggiate...")
            time.sleep(args.pausa)

    mancanti: list[str] = []
    try:
        manifest = json.loads(p.manifest.read_text(encoding="utf-8")) if p.manifest.exists() else {}
        presenti = {str(v.get("collection_name")) for v in manifest.get("items", []) if Path(str(v.get("output_path"))).is_file()}
        mancanti = [n for n in _nomi_attesi(args.insieme) if n not in presenti]
    except Exception as exc:  # elenco online non raggiungibile: il controllo dei file resta valido
        print(f"Elenco collezioni non verificato: {exc}")
    zips = sorted(p.raw.glob("*.zip"))
    totale = sum(z.stat().st_size for z in zips)
    print(f"\nZIP in {p.raw}: {len(zips)}  ({_gib(totale)})")
    if mancanti:
        print("Collezioni senza ZIP (il servizio le espone ma restituisce un flusso vuoto, o il download e' fallito):")
        for nome in mancanti:
            print(f"  - {nome}")
        print("Se sono le stesse 4 note sul server (Testi Unici e Regolamenti), e' normale; altrimenti rilancia 'scarica'.")
    if problemi:
        print("Download NON integro: rilancia il comando 'scarica'.")
        return 1
    print("Download integro. Prossimo passo: importa")
    return 0


# ---------------------------------------------------------------------------------------------- #
# importa                                                                                         #
# ---------------------------------------------------------------------------------------------- #

def conteggi_db(db: Path) -> dict[str, Any]:
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        def uno(sql: str) -> Any:
            try:
                return conn.execute(sql).fetchone()[0]
            except sqlite3.Error:
                return None

        return {
            "documenti": uno("SELECT COUNT(*) FROM normative_documents"),
            "articoli": uno("SELECT COUNT(*) FROM normative_articles"),
            "chunk": uno("SELECT COUNT(*) FROM normative_chunks"),
            "chunk_fts": uno("SELECT COUNT(*) FROM normative_fts_info"),
            "ultimo_import": uno("SELECT MAX(imported_at) FROM normative_documents"),
            "ultimo_atto": uno("SELECT MAX(data_atto) FROM normative_documents"),
            "ultima_pubblicazione": uno("SELECT MAX(data_pubblicazione) FROM normative_documents"),
        }
    finally:
        conn.close()


def cmd_importa(args: argparse.Namespace) -> int:
    from lex.normativa.normattiva_importer import import_raw_dir, write_report

    p = percorsi_da_args(args)
    if not list(p.raw.glob("*.zip")):
        print(f"Nessuno ZIP in {p.raw}: esegui prima 'scarica'.")
        return 2
    if spazio_libero_gib(p.normativa) < args.spazio_minimo_gib:
        print(f"Spazio insufficiente: servono almeno {args.spazio_minimo_gib} GiB liberi.")
        return 2
    print(f"Import in {p.db} (upsert: si puo' rilanciare senza duplicare; indice FTS5 aggiornato alla fine).")
    inizio = time.monotonic()
    stats = import_raw_dir(
        raw_dir=p.raw,
        db_path=p.db,
        jsonl_path=p.jsonl,
        indice_fts=True,
    )
    if args.ricostruisci_fts:
        from lex.ricerca_giuridica.indice_fts import sincronizza_fts

        conn = sqlite3.connect(str(p.db))
        try:
            esito = sincronizza_fts(conn, ricostruisci=True)
            print(f"Indice FTS ricostruito: {esito.indicizzati} chunk")
        finally:
            conn.close()
    write_report(stats, p.report)
    if args.controllo_integrita:
        conn = sqlite3.connect(f"file:{p.db}?mode=ro", uri=True)
        try:
            risultato = conn.execute("PRAGMA integrity_check").fetchone()[0]
        finally:
            conn.close()
        print(f"integrity_check: {risultato}")
        if risultato != "ok":
            return 1
    conteggi = conteggi_db(p.db)
    print(f"\nImport in {(time.monotonic() - inizio) / 60:.1f} min  errori={stats.errors}")
    print(json.dumps(conteggi, ensure_ascii=False, indent=2))
    print(f"DB: {p.db}  ({_gib(p.db.stat().st_size)})")
    if stats.errors:
        print("Ci sono errori: vedi i messaggi sopra e il report " + str(p.report))
        return 1
    print("Prossimo passo: vettori")
    return 0


# ---------------------------------------------------------------------------------------------- #
# vettori                                                                                         #
# ---------------------------------------------------------------------------------------------- #

def stima_velocita(embedder: Any, db: Path, campioni: int = 256, batch: int = 32) -> float:
    """Misura i chunk/secondo dell'Ollama locale su un campione sparso dei chunk reali."""

    from lex.ricerca_giuridica.embedding import testo_documento

    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        totale = int(conn.execute("SELECT COUNT(*) FROM normative_chunks").fetchone()[0])
        passo = max(1, totale // campioni)
        righe = conn.execute(
            "SELECT c.chunk_text, COALESCE(d.titolo, '') FROM normative_chunks c JOIN normative_documents d ON d.id = c.document_id "
            "WHERE c.id % ? = 0 LIMIT ?",
            (passo, campioni),
        ).fetchall()
    finally:
        conn.close()
    testi = [testo_documento(titolo, testo or "") for testo, titolo in righe]
    if not testi:
        return 0.0
    embedder.embed(testi[:2])  # riscaldamento: caricamento del modello in memoria
    # stessa modalita' della costruzione: N richieste in volo, ognuna con batch/N chunk
    from lex.ricerca_giuridica.indice_vettoriale import embed_in_flusso, richieste_contemporanee

    passo = max(1, -(-batch // richieste_contemporanee(embedder)))
    lotti = [testi[i : i + passo] for i in range(0, len(testi), passo)]
    inizio = time.monotonic()
    for _lotto, _matrice in embed_in_flusso(embedder, lotti, lambda voce: voce):
        pass
    secondi = max(time.monotonic() - inizio, 1e-6)
    return len(testi) / secondi


def cmd_vettori(args: argparse.Namespace) -> int:
    from lex.ricerca_giuridica import indice_vettoriale
    from lex.ricerca_giuridica.embedding import OllamaEmbedder

    p = percorsi_da_args(args)
    if not p.db.exists():
        print(f"Database assente: {p.db}. Esegui prima 'importa'.")
        return 2
    embedder = OllamaEmbedder(modello=args.modello, url=args.url, paralleli=args.paralleli or 0)
    try:
        embedder.embed(["prova"])
    except Exception as exc:
        print(f"Ollama non risponde su {embedder.url} con il modello {embedder.modello}: {exc}")
        print(f"Avvia Ollama e scarica il modello:  ollama pull {embedder.modello}")
        return 3

    conteggi = conteggi_db(p.db)
    totale = int(conteggi["chunk"] or 0)
    gia = 0
    esistente = indice_vettoriale.IndiceVettoriale.apri(p.vettori)
    if esistente is not None and not args.ricomincia:
        gia = esistente.righe
    da_fare = max(0, totale - gia) if not args.ricomincia else totale
    velocita = stima_velocita(embedder, p.db, batch=max(1, int(args.batch)))
    print(f"Chunk nel database: {totale}; gia' vettorizzati (righe indice): {gia}; da fare circa: {da_fare}")
    if velocita > 0:
        ore = da_fare / velocita / 3600
        print(f"Velocita' misurata ora: {velocita:.1f} chunk/s  ->  tempo stimato {ore:.1f} ore (stima: dipende dalla GPU e dalla lunghezza dei chunk)")
    else:
        print("Stima non calcolabile (nessun chunk di prova).")
    if args.stima:
        return 0

    argv = ["costruisci", "--db", str(p.db), "--out", str(p.vettori), "--batch", str(args.batch)]
    if args.paralleli:
        argv += ["--paralleli", str(args.paralleli)]
    if args.modello:
        argv += ["--modello", args.modello]
    if args.url:
        argv += ["--url", args.url]
    if args.massimo:
        argv += ["--massimo", str(args.massimo)]
    if args.ricomincia:
        argv += ["--ricomincia"]
    print("Costruzione indice vettoriale (Ctrl-C per fermarsi: si riprende dall'ultimo blocco salvato)...")
    codice = indice_vettoriale.main(argv)
    if codice == 0:
        print("Prossimo passo: verifica")
    return codice


# ---------------------------------------------------------------------------------------------- #
# verifica                                                                                        #
# ---------------------------------------------------------------------------------------------- #

def stato_vettori(cartella: Path, chunk_db: int) -> dict[str, Any]:
    from lex.ricerca_giuridica.indice_vettoriale import IndiceVettoriale

    indice = IndiceVettoriale.apri(cartella)
    if indice is None:
        return {"presente": False}
    import numpy as np

    ids = np.fromfile(cartella / "ids.i64", dtype=np.int64, count=indice.righe) if indice.righe else np.zeros(0, dtype=np.int64)
    attive = int((ids >= 0).sum())
    return {
        "presente": True,
        "modello": indice.meta.get("modello"),
        "modello_versione": str(indice.meta.get("modello_versione") or "")[:16],
        "dimensioni": indice.meta.get("dimensioni"),
        "righe_attive": attive,
        "copertura": round(attive / chunk_db, 4) if chunk_db else 0.0,
        "aggiornato": indice.meta.get("aggiornato"),
    }


def esegui_ricerche_di_prova(db: Path) -> list[dict[str, Any]]:
    from lex.ricerca_giuridica.ibrida import MotoreRicercaNormattiva, ricerca_semantica_abilitata

    motore = MotoreRicercaNormattiva(db, usa_semantica=ricerca_semantica_abilitata())
    semantica = motore.stato()["semantica_attiva"]
    if semantica:
        inizio = time.monotonic()
        pronto = motore.riscalda(180.0)
        print(f"Modello di embedding {'pronto' if pronto else 'NON disponibile'} in {time.monotonic() - inizio:.1f}s")
    else:
        print(f"Ricerca semantica non attiva: {motore.stato()['motivo_semantica']}")
    esiti: list[dict[str, Any]] = []
    for domanda, articolo_atteso in RICERCHE_DI_PROVA:
        inizio = time.monotonic()
        try:
            risultati = motore.cerca(domanda, limite=5)
            errore = ""
        except Exception as exc:
            risultati, errore = [], str(exc)
        secondi = time.monotonic() - inizio
        riga: dict[str, Any] = {
            "domanda": domanda,
            "secondi": round(secondi, 2),
            "risultati": len(risultati),
            "modalita": (risultati[0]["ricerca"]["modalita"] if risultati else ""),
            "migliori": [
                f"{r.get('titolo', '')[:60]} | art. {r.get('articolo_o_chunk')} | {r.get('vigenza')}" for r in risultati[:3]
            ],
            "errore": errore,
        }
        ok = bool(risultati) and not errore
        if semantica and risultati and riga["modalita"] not in {"ibrida", "semantica"}:
            # con l'indice vettoriale presente la ricerca deve usare anche i vettori
            ok = False
            riga["errore"] = riga["errore"] or f"ricerca solo {riga['modalita']}: {risultati[0]['ricerca'].get('motivo_semantica', '')}"
        if articolo_atteso:
            ok = ok and any(articolo_atteso in str(r.get("articolo_o_chunk") or "") for r in risultati)
        riga["ok"] = ok
        esiti.append(riga)
    return esiti


def cmd_verifica(args: argparse.Namespace) -> int:
    p = percorsi_da_args(args)
    if not p.db.exists():
        print(f"Database assente: {p.db}")
        return 2
    conteggi = conteggi_db(p.db)
    print("== Conteggi ==")
    print(f"documenti: {conteggi['documenti']}  articoli: {conteggi['articoli']}  chunk: {conteggi['chunk']}  chunk nell'indice FTS: {conteggi['chunk_fts']}")
    print(f"ultimo import: {conteggi['ultimo_import']}  atto piu' recente: {conteggi['ultimo_atto']}  ultima pubblicazione: {conteggi['ultima_pubblicazione']}")
    print(f"DB: {_gib(p.db.stat().st_size)}")
    ok = True
    if not conteggi["chunk"]:
        print("ERRORE: nessun chunk nel database")
        ok = False
    elif conteggi["chunk_fts"] != conteggi["chunk"]:
        print("ATTENZIONE: l'indice FTS non copre tutti i chunk (rilancia 'importa' o 'importa --ricostruisci-fts')")
        ok = False
    vettori = stato_vettori(p.vettori, int(conteggi["chunk"] or 0))
    print("== Indice vettoriale ==")
    print(json.dumps(vettori, ensure_ascii=False))
    if vettori["presente"] and vettori["copertura"] < 0.999:
        print("ATTENZIONE: indice vettoriale incompleto (rilancia 'vettori')")
        ok = False
    if not vettori["presente"]:
        print("ATTENZIONE: indice vettoriale assente (la ricerca sarebbe solo lessicale)")
    print("== Ricerche di prova ==")
    for esito in esegui_ricerche_di_prova(p.db):
        stato = "OK " if esito["ok"] else "KO "
        print(f"{stato}{esito['domanda']!r}: {esito['risultati']} risultati in {esito['secondi']}s, modalita' {esito['modalita'] or '-'}")
        for riga in esito["migliori"]:
            print(f"      {riga}")
        if esito["errore"]:
            print(f"      errore: {esito['errore']}")
        ok = ok and esito["ok"]
    print("ESITO:", "OK" if ok else "DA CONTROLLARE")
    return 0 if ok else 1


# ---------------------------------------------------------------------------------------------- #
# pacchetto                                                                                       #
# ---------------------------------------------------------------------------------------------- #

FILE_VETTORI = ("vettori.i8", "scale.f32", "ids.i64", "impronte.u64", "meta.json")


def _file_del_pacchetto(p: Percorsi, *, con_vettori: bool, con_jsonl: bool) -> list[tuple[Path, str]]:
    voci: list[tuple[Path, str]] = [(p.db, "normativa/normattiva.sqlite")]
    if con_vettori:
        for nome in FILE_VETTORI:
            voci.append((p.vettori / nome, f"normativa/vettori_normattiva/{nome}"))
    if con_jsonl and p.jsonl.exists():
        voci.append((p.jsonl, "normativa/index/normattiva_chunks.jsonl"))
    return voci


def _aggiunge_testo(archivio: tarfile.TarFile, nome: str, testo: str) -> None:
    dati = testo.encode("utf-8")
    info = tarfile.TarInfo(nome)
    info.size = len(dati)
    info.mtime = int(time.time())
    info.mode = 0o644
    archivio.addfile(info, io.BytesIO(dati))


def crea_pacchetto(
    p: Percorsi,
    *,
    destinazione: Path | None = None,
    con_vettori: bool = True,
    con_jsonl: bool = False,
    consenti_parziale: bool = False,
    livello_zstd: int = 6,
    formato: str = "auto",
    adesso: dt.datetime | None = None,
) -> Path:
    """Crea ``lex-fonti-AAAAMMGG-HHMM.tar.zst`` (o .tar.gz se zstd manca) con DB, vettori e metadati.

    Dentro l'archivio i percorsi sono relativi alla radice dati del server (``normativa/...``), piu'
    ``PACCHETTO.json`` (metadati) e ``SHA256SUMS``. Accanto all'archivio viene scritto ``<archivio>.sha256``.
    """

    if not p.db.exists():
        raise FileNotFoundError(f"database assente: {p.db}")
    for estraneo in (p.db.with_name(p.db.name + "-wal"), p.db.with_name(p.db.name + "-journal")):
        if estraneo.exists() and estraneo.stat().st_size:
            raise RuntimeError(f"il database ha transazioni aperte ({estraneo.name}): chiudi i programmi che lo usano")
    conn = sqlite3.connect(str(p.db))
    try:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        conn.close()
    conteggi = conteggi_db(p.db)
    if not conteggi["chunk"]:
        raise RuntimeError("il database non contiene chunk: niente da impacchettare")
    vettori: dict[str, Any] = {"presente": False}
    if con_vettori:
        vettori = stato_vettori(p.vettori, int(conteggi["chunk"]))
        if not vettori["presente"]:
            raise RuntimeError("indice vettoriale assente: costruiscilo con 'vettori' oppure usa --senza-vettori")
        if vettori["copertura"] < 0.999 and not consenti_parziale:
            raise RuntimeError(
                f"indice vettoriale incompleto ({vettori['copertura'] * 100:.1f}% dei chunk): completa 'vettori' o usa --consenti-parziale"
            )
    voci = _file_del_pacchetto(p, con_vettori=con_vettori, con_jsonl=con_jsonl)
    for sorgente, _ in voci:
        if not sorgente.is_file():
            raise FileNotFoundError(f"file mancante: {sorgente}")

    momento = adesso or dt.datetime.now()
    nome = f"lex-fonti-{momento.strftime('%Y%m%d-%H%M')}"
    usa_zstd = formato in {"auto", "zst"} and shutil.which("zstd") is not None
    if formato == "zst" and not usa_zstd:
        raise RuntimeError("formato zst richiesto ma 'zstd' non e' installato (sudo apt install zstd)")
    uscita_dir = Path(destinazione) if destinazione else p.pacchetti
    uscita_dir.mkdir(parents=True, exist_ok=True)
    percorso = uscita_dir / (nome + (".tar.zst" if usa_zstd else ".tar.gz"))
    if percorso.exists():
        raise FileExistsError(f"esiste gia': {percorso}")

    file_meta = []
    for sorgente, arcname in voci:
        file_meta.append({"percorso": arcname, "byte": sorgente.stat().st_size, "sha256": sha256_file(sorgente)})
    metadati = {
        "formato": "iusentra-lex-fonti",
        "versione_pacchetto": VERSIONE_PACCHETTO,
        "creato": momento.isoformat(timespec="seconds"),
        "creato_su": platform.node(),
        "conteggi": conteggi,
        "vettori": vettori,
        "con_jsonl": any(a.endswith(".jsonl") for _, a in voci),
        "file": file_meta,
    }
    sums = "".join(f"{f['sha256']}  {f['percorso']}\n" for f in file_meta)

    tmp = percorso.with_name(percorso.name + ".part")
    processo = None
    try:
        if usa_zstd:
            processo = subprocess.Popen(
                ["zstd", f"-{int(livello_zstd)}", "-T0", "-q", "-f", "-o", str(tmp)], stdin=subprocess.PIPE
            )
            archivio = tarfile.open(fileobj=processo.stdin, mode="w|")
        else:
            archivio = tarfile.open(tmp, mode="w:gz", compresslevel=6)
        with archivio:
            _aggiunge_testo(archivio, "PACCHETTO.json", json.dumps(metadati, ensure_ascii=False, indent=2))
            _aggiunge_testo(archivio, "SHA256SUMS", sums)
            for sorgente, arcname in voci:
                archivio.add(str(sorgente), arcname=arcname, recursive=False)
        if processo is not None:
            processo.stdin.close()
            if processo.wait() != 0:
                raise RuntimeError("zstd e' terminato con errore")
        tmp.replace(percorso)
    except BaseException:
        if processo is not None and processo.poll() is None:
            processo.kill()
        tmp.unlink(missing_ok=True)
        raise
    scrivi_checksum_pacchetto(percorso)
    return percorso


def scrivi_checksum_pacchetto(percorso: Path) -> Path:
    destinazione = percorso.with_name(percorso.name + ".sha256")
    destinazione.write_text(f"{sha256_file(percorso)}  {percorso.name}\n", encoding="utf-8")
    return destinazione


def controlla_pacchetto(percorso: Path) -> dict[str, Any]:
    """Rilegge il pacchetto: checksum esterno, SHA256SUMS interno e metadati. Solleva ValueError se qualcosa non torna."""

    sidecar = percorso.with_name(percorso.name + ".sha256")
    if not sidecar.exists():
        raise ValueError(f"checksum mancante: {sidecar.name}")
    atteso = sidecar.read_text(encoding="utf-8").split()[0]
    if sha256_file(percorso) != atteso:
        raise ValueError("sha256 del pacchetto diverso da quello dichiarato")
    if percorso.name.endswith(".tar.zst"):
        processo = subprocess.Popen(["zstd", "-dc", str(percorso)], stdout=subprocess.PIPE)
        archivio = tarfile.open(fileobj=processo.stdout, mode="r|")
    else:
        processo = None
        archivio = tarfile.open(percorso, mode="r:gz")
    metadati: dict[str, Any] = {}
    interni: dict[str, str] = {}
    sums: dict[str, str] = {}
    with archivio:
        for membro in archivio:
            if not membro.isfile():
                continue
            if membro.name == "PACCHETTO.json":
                metadati = json.loads(archivio.extractfile(membro).read().decode("utf-8"))
            elif membro.name == "SHA256SUMS":
                for riga in archivio.extractfile(membro).read().decode("utf-8").splitlines():
                    h, _, n = riga.partition("  ")
                    sums[n] = h
            else:
                h = hashlib.sha256()
                flusso = archivio.extractfile(membro)
                while True:
                    blocco = flusso.read(1024 * 1024)
                    if not blocco:
                        break
                    h.update(blocco)
                interni[membro.name] = h.hexdigest()
    if processo is not None:
        processo.wait()
    if not metadati or not sums:
        raise ValueError("PACCHETTO.json o SHA256SUMS mancanti")
    if set(sums) != set(interni):
        raise ValueError(f"contenuto diverso da SHA256SUMS: {sorted(set(sums) ^ set(interni))}")
    for nome, h in interni.items():
        if sums[nome] != h:
            raise ValueError(f"checksum errato per {nome}")
    return metadati


def cmd_pacchetto(args: argparse.Namespace) -> int:
    p = percorsi_da_args(args)
    try:
        spazio_necessario = p.db.stat().st_size / 1024**3 * 0.7
    except OSError:
        spazio_necessario = 0
    if spazio_libero_gib(p.pacchetti) < max(1.0, spazio_necessario):
        print(f"Spazio insufficiente in {p.pacchetti}: servono circa {spazio_necessario:.1f} GiB.")
        return 2
    try:
        percorso = crea_pacchetto(
            p,
            destinazione=Path(args.destinazione) if args.destinazione else None,
            con_vettori=not args.senza_vettori,
            con_jsonl=args.con_jsonl,
            consenti_parziale=args.consenti_parziale,
            livello_zstd=args.livello,
            formato=args.formato,
        )
        print("Verifica del pacchetto appena creato...")
        metadati = controlla_pacchetto(percorso)
    except (RuntimeError, FileNotFoundError, FileExistsError, ValueError) as exc:
        print(f"ERRORE: {exc}")
        return 1
    print(f"Pacchetto: {percorso}  ({_gib(percorso.stat().st_size)})")
    print(f"Checksum:  {percorso.name}.sha256")
    print(f"Contenuto: {metadati['conteggi']['documenti']} documenti, {metadati['conteggi']['articoli']} articoli, {metadati['conteggi']['chunk']} chunk")
    print("\nCopia sul server (dal PC, in WSL):")
    print(f"  scp {percorso} {percorso}.sha256 UTENTE@SERVER:/opt/iusentra/import/")
    return 0


# ---------------------------------------------------------------------------------------------- #
# riga di comando                                                                                 #
# ---------------------------------------------------------------------------------------------- #

def costruisci_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lex_normattiva_locale.py",
        description="Archivio Normattiva completo sul PC: scarica, importa, vettori, verifica, pacchetto.",
    )
    parser.add_argument("--base", help="cartella di lavoro (default: $IUSENTRA_LEX_LOCALE_DIR o ~/iusentra-lex-fonti)")
    sotto = parser.add_subparsers(dest="comando", required=True)

    s = sotto.add_parser("scarica", help="scarica gli ZIP Normattiva (con ripresa e verifica di integrita')")
    s.add_argument("--insieme", choices=["completo", "core"], default="completo",
                   help="completo = tutte le collezioni dell'elenco ufficiale; core = le 14 del download notturno del server")
    s.add_argument("--vigenza", choices=["ORIGINALE", "VIGENTE"], default="ORIGINALE",
                   help="come il server (ORIGINALE); VIGENTE e' sperimentale")
    s.add_argument("--pausa", type=float, default=1.0, help="secondi tra un download e l'altro (come il server)")
    s.add_argument("--tentativi", type=int, default=3)
    s.add_argument("--spazio-minimo-gib", type=float, default=10.0)
    s.set_defaults(func=cmd_scarica)

    i = sotto.add_parser("importa", help="importa gli ZIP nel database (senza duplicati) e aggiorna l'indice FTS")
    i.add_argument("--ricostruisci-fts", action="store_true")
    i.add_argument("--controllo-integrita", action="store_true", help="esegue PRAGMA integrity_check (qualche minuto)")
    i.add_argument("--spazio-minimo-gib", type=float, default=10.0)
    i.set_defaults(func=cmd_importa)

    v = sotto.add_parser("vettori", help="costruisce l'indice vettoriale con Ollama locale (riprende dal checkpoint)")
    v.add_argument("--modello", default="", help="default: LEX_EMBED_MODEL o embeddinggemma:300m")
    v.add_argument("--url", default="", help="default: LEX_EMBED_URL o http://127.0.0.1:11434")
    v.add_argument("--batch", type=int, default=32)
    v.add_argument("--paralleli", type=int, default=0, help="richieste Ollama contemporanee (richiede OLLAMA_NUM_PARALLEL)")
    v.add_argument("--massimo", type=int, default=None, help="si ferma dopo N chunk (costruzione a tappe)")
    v.add_argument("--ricomincia", action="store_true", help="cancella l'indice e ricostruisce da zero")
    v.add_argument("--stima", action="store_true", help="misura la velocita' e stampa la stima dei tempi, senza costruire")
    v.set_defaults(func=cmd_vettori)

    c = sotto.add_parser("verifica", help="conteggi, data di aggiornamento e 3 ricerche di prova")
    c.set_defaults(func=cmd_verifica)

    k = sotto.add_parser("pacchetto", help="crea il .tar.zst con DB, indice FTS, vettori, metadati e SHA-256")
    k.add_argument("--destinazione", help="cartella di uscita (default: <base>/pacchetti)")
    k.add_argument("--senza-vettori", action="store_true")
    k.add_argument("--consenti-parziale", action="store_true", help="permette un indice vettoriale incompleto")
    k.add_argument("--con-jsonl", action="store_true", help="include anche il JSONL dei chunk (il server lo rigenera ogni notte)")
    k.add_argument("--livello", type=int, default=6, help="livello zstd (default 6)")
    k.add_argument("--formato", choices=["auto", "zst", "gz"], default="auto")
    k.set_defaults(func=cmd_pacchetto)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = costruisci_parser().parse_args(argv)
    try:
        return int(args.func(args))
    except KeyboardInterrupt:
        print("\nInterrotto: rilancia lo stesso comando per riprendere.")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
