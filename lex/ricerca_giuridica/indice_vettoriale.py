"""Indice vettoriale dei chunk Normattiva: int8 con scala per riga su file memmappati, ricerca esatta.

Formato ``iusentra-vettori-int8-v1`` (una cartella, copiabile così com'è sul server):

- ``meta.json``: modello, versione (digest Ollama), dimensioni, prefissi, numero di righe, date;
- ``vettori.i8``: matrice N×D int8 (vettore normalizzato diviso per la sua scala);
- ``scale.f32``: N float32 (scala della riga: max |v| / 127);
- ``ids.i64``: N int64, id del chunk in ``normative_chunks`` (-1 = chunk non più presente);
- ``impronte.u64``: N uint64, impronta del testo indicizzato (per ricalcolare solo i chunk cambiati).

La scrittura è solo in coda e ogni blocco aggiorna ``meta.json``: un'interruzione lascia l'indice
valido fino all'ultimo blocco completo e la ripresa salta i chunk già presenti (checkpoint).

La ricerca è un prodotto scalare esatto a blocchi (numpy): per 640.000 chunk × 768 dimensioni
servono circa 490 MB su disco e, su CPU, poche centinaia di millisecondi per domanda.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import sqlite3
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from .embedding import PREFISSO_DOCUMENTO, PREFISSO_DOMANDA, Embedder, normalizza_righe, testo_documento
from .testo import CODICI_PER_CHIAVE, VERSIONE_ANALIZZATORE, articolo_normalizzato, codice_da_atto

logger = logging.getLogger(__name__)

FORMATO = "iusentra-vettori-int8-v1"
_FILE_VETTORI = "vettori.i8"
_FILE_SCALE = "scale.f32"
_FILE_IDS = "ids.i64"
_FILE_IMPRONTE = "impronte.u64"
_FILE_META = "meta.json"


class IndiceIncompatibile(RuntimeError):
    pass


def _adesso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def quantizza(matrice: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    matrice = normalizza_righe(matrice)
    massimi = np.abs(matrice).max(axis=1)
    massimi[massimi == 0] = 1.0
    scale = (massimi / 127.0).astype(np.float32)
    valori = np.clip(np.rint(matrice / scale[:, None]), -127, 127).astype(np.int8)
    return valori, scale


def impronta_testo(testo: str) -> int:
    return int.from_bytes(hashlib.blake2b(testo.encode("utf-8"), digest_size=8).digest(), "little") & 0x7FFFFFFFFFFFFFFF


@dataclass
class IndiceVettoriale:
    cartella: Path
    meta: dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------ apertura e verifica
    @classmethod
    def apri(cls, cartella: str | Path) -> IndiceVettoriale | None:
        percorso = Path(cartella)
        file_meta = percorso / _FILE_META
        if not file_meta.exists():
            return None
        try:
            meta = json.loads(file_meta.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if meta.get("formato") != FORMATO:
            logger.warning("Indice vettoriale %s: formato %r non riconosciuto, ignorato.", percorso, meta.get("formato"))
            return None
        indice = cls(cartella=percorso, meta=meta)
        indice._mappe: dict[str, Any] | None = None
        return indice

    @property
    def dimensioni(self) -> int:
        return int(self.meta.get("dimensioni") or 0)

    @property
    def righe(self) -> int:
        return int(self.meta.get("righe") or 0)

    def verifica_modello(self, modello: str, versione: str = "") -> tuple[bool, str]:
        """Il modello dell'indice deve essere quello configurato: mai vettori di modelli diversi."""

        atteso = str(self.meta.get("modello") or "")
        if atteso != str(modello or ""):
            return False, f"indice costruito con «{atteso}», configurato «{modello}»"
        digest = str(self.meta.get("modello_versione") or "")
        if digest and versione and digest != versione:
            return False, f"versione del modello diversa (indice {digest[:12]}, Ollama {versione[:12]})"
        return True, ""

    def _carica(self) -> dict[str, Any]:
        mappe = getattr(self, "_mappe", None)
        if mappe is not None and mappe.get("righe") == self.righe:
            return mappe
        n, d = self.righe, self.dimensioni
        if n <= 0 or d <= 0:
            self._mappe = {"righe": n, "vettori": None}
            return self._mappe
        self._mappe = {
            "righe": n,
            "vettori": np.memmap(self.cartella / _FILE_VETTORI, dtype=np.int8, mode="r", shape=(n, d)),
            "scale": np.fromfile(self.cartella / _FILE_SCALE, dtype=np.float32, count=n),
            "ids": np.fromfile(self.cartella / _FILE_IDS, dtype=np.int64, count=n),
        }
        return self._mappe

    # ------------------------------------------------------------------ ricerca
    def cerca(self, vettore: np.ndarray, *, k: int = 50, blocco: int = 8192) -> list[tuple[int, float]]:
        """Prodotto scalare esatto a blocchi; restituisce (id chunk, coseno) in ordine decrescente."""

        mappe = self._carica()
        vettori = mappe.get("vettori")
        if vettori is None:
            return []
        domanda = normalizza_righe(np.asarray(vettore, dtype=np.float32))[0]
        if domanda.shape[0] != self.dimensioni:
            raise IndiceIncompatibile(
                f"vettore della domanda con {domanda.shape[0]} dimensioni, indice con {self.dimensioni}"
            )
        scale = mappe["scale"]
        ids = mappe["ids"]
        k = max(1, int(k))
        migliori_punti: list[np.ndarray] = []
        migliori_righe: list[np.ndarray] = []
        for inizio in range(0, vettori.shape[0], blocco):
            parte = np.asarray(vettori[inizio : inizio + blocco], dtype=np.float32)
            punti = (parte @ domanda) * scale[inizio : inizio + blocco]
            punti[ids[inizio : inizio + blocco] < 0] = -np.inf
            quanti = min(k, punti.shape[0])
            scelti = np.argpartition(-punti, quanti - 1)[:quanti]
            migliori_punti.append(punti[scelti])
            migliori_righe.append(scelti + inizio)
        punti = np.concatenate(migliori_punti)
        righe = np.concatenate(migliori_righe)
        ordine = np.argsort(-punti)[:k]
        return [
            (int(ids[righe[i]]), float(punti[i]))
            for i in ordine
            if np.isfinite(punti[i]) and int(ids[righe[i]]) >= 0
        ]


# ---------------------------------------------------------------------------------------------- #
# Costruzione e aggiornamento                                                                     #
# ---------------------------------------------------------------------------------------------- #

def _titolo_chunk(riga: sqlite3.Row) -> str:
    codice = codice_da_atto(riga["numero"], riga["data_atto"], riga["titolo"])
    nome = CODICI_PER_CHIAVE[codice].etichetta if codice in CODICI_PER_CHIAVE else str(riga["titolo"] or "")
    articolo = articolo_normalizzato(str(riga["article_number"] or ""))
    parti = [nome.strip()]
    if articolo:
        parti.append(f"art. {articolo}")
    rubrica = str(riga["article_title"] or "").strip()
    if rubrica:
        parti.append(rubrica)
    return " ".join(part for part in parti if part)[:300]


def _ripara_code(cartella: Path, dimensioni: int) -> int:
    """Allinea i file alla stessa lunghezza (ultimo blocco completo) dopo un'interruzione."""

    if dimensioni <= 0:
        return 0
    lunghezze = []
    for nome, larghezza in ((_FILE_VETTORI, dimensioni), (_FILE_SCALE, 4), (_FILE_IDS, 8), (_FILE_IMPRONTE, 8)):
        percorso = cartella / nome
        lunghezze.append((percorso.stat().st_size // larghezza) if percorso.exists() else 0)
    righe = min(lunghezze)
    for nome, larghezza in ((_FILE_VETTORI, dimensioni), (_FILE_SCALE, 4), (_FILE_IDS, 8), (_FILE_IMPRONTE, 8)):
        percorso = cartella / nome
        if percorso.exists() and percorso.stat().st_size != righe * larghezza:
            with percorso.open("r+b") as handle:
                handle.truncate(righe * larghezza)
    return righe


def _scrivi_meta(cartella: Path, meta: dict[str, Any]) -> None:
    temporaneo = cartella / (_FILE_META + ".tmp")
    temporaneo.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporaneo, cartella / _FILE_META)


@dataclass
class EsitoCostruzione:
    nuovi: int = 0
    ricalcolati: int = 0
    eliminati: int = 0
    invariati: int = 0
    righe: int = 0
    secondi: float = 0.0
    interrotto_al_massimo: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "nuovi": self.nuovi,
            "ricalcolati": self.ricalcolati,
            "eliminati": self.eliminati,
            "invariati": self.invariati,
            "righe": self.righe,
            "secondi": round(self.secondi, 1),
            "interrotto_al_massimo": self.interrotto_al_massimo,
        }


def costruisci_indice(
    conn: sqlite3.Connection,
    cartella: str | Path,
    embedder: Embedder,
    *,
    batch: int = 32,
    massimo: int | None = None,
    ricomincia: bool = False,
    progresso: Callable[[int, int, float], None] | None = None,
) -> EsitoCostruzione:
    """Costruisce o aggiorna l'indice: solo chunk nuovi o con testo cambiato (ripresa automatica)."""

    inizio = time.monotonic()
    percorso = Path(cartella)
    percorso.mkdir(parents=True, exist_ok=True)
    esito = EsitoCostruzione()
    versione = ""
    try:
        versione = str(embedder.versione() or "")
    except Exception:
        versione = ""

    meta_file = percorso / _FILE_META
    meta: dict[str, Any] = {}
    if meta_file.exists() and not ricomincia:
        meta = json.loads(meta_file.read_text(encoding="utf-8"))
        indice = IndiceVettoriale(cartella=percorso, meta=meta)
        compatibile, motivo = indice.verifica_modello(embedder.modello, versione)
        if not compatibile:
            raise IndiceIncompatibile(
                f"{motivo}: non si mescolano vettori di modelli diversi. Usa --ricomincia per ricostruire."
            )
    if ricomincia or not meta:
        for nome in (_FILE_VETTORI, _FILE_SCALE, _FILE_IDS, _FILE_IMPRONTE, _FILE_META):
            (percorso / nome).unlink(missing_ok=True)
        meta = {
            "formato": FORMATO,
            "modello": embedder.modello,
            "modello_versione": versione,
            "dimensioni": 0,
            "quantizzazione": "int8 simmetrica per riga (scala = max|v|/127)",
            "prefisso_domanda": PREFISSO_DOMANDA,
            "prefisso_documento": PREFISSO_DOCUMENTO,
            "analizzatore": VERSIONE_ANALIZZATORE,
            "righe": 0,
            "creato": _adesso(),
        }
    dimensioni = int(meta.get("dimensioni") or 0)
    righe = _ripara_code(percorso, dimensioni) if dimensioni else 0
    meta["righe"] = righe

    esistenti: dict[int, int] = {}
    impronte = np.zeros(0, dtype=np.uint64)
    if righe:
        ids = np.fromfile(percorso / _FILE_IDS, dtype=np.int64, count=righe)
        impronte = np.fromfile(percorso / _FILE_IMPRONTE, dtype=np.uint64, count=righe)
        esistenti = {int(valore): posizione for posizione, valore in enumerate(ids) if valore >= 0}

    precedente = conn.row_factory
    conn.row_factory = sqlite3.Row
    try:
        totale = int(conn.execute("SELECT COUNT(*) FROM normative_chunks").fetchone()[0])
        ids_db: set[int] = set()
        da_embeddare: list[tuple[int, str, int, int | None]] = []  # (chunk_id, testo, impronta, riga esistente)
        fatti = 0

        def scarica() -> None:
            nonlocal righe, dimensioni
            if not da_embeddare:
                return
            matrice = embedder.embed([voce[1] for voce in da_embeddare])
            if dimensioni == 0:
                dimensioni = int(matrice.shape[1])
                meta["dimensioni"] = dimensioni
            if matrice.shape[1] != dimensioni:
                raise IndiceIncompatibile(f"il modello restituisce {matrice.shape[1]} dimensioni, l'indice {dimensioni}")
            valori, scale = quantizza(matrice)
            nuovi = [i for i, voce in enumerate(da_embeddare) if voce[3] is None]
            vecchi = [i for i, voce in enumerate(da_embeddare) if voce[3] is not None]
            if vecchi:
                mappa = np.memmap(percorso / _FILE_VETTORI, dtype=np.int8, mode="r+", shape=(righe, dimensioni))
                scale_file = np.memmap(percorso / _FILE_SCALE, dtype=np.float32, mode="r+", shape=(righe,))
                impronte_file = np.memmap(percorso / _FILE_IMPRONTE, dtype=np.uint64, mode="r+", shape=(righe,))
                for i in vecchi:
                    posizione = int(da_embeddare[i][3])
                    mappa[posizione] = valori[i]
                    scale_file[posizione] = scale[i]
                    impronte_file[posizione] = np.uint64(da_embeddare[i][2])
                mappa.flush()
                scale_file.flush()
                impronte_file.flush()
                del mappa, scale_file, impronte_file
                esito.ricalcolati += len(vecchi)
            if nuovi:
                with (percorso / _FILE_VETTORI).open("ab") as f_v, (percorso / _FILE_SCALE).open("ab") as f_s, (
                    percorso / _FILE_IDS
                ).open("ab") as f_i, (percorso / _FILE_IMPRONTE).open("ab") as f_h:
                    valori[nuovi].tofile(f_v)
                    scale[nuovi].astype(np.float32).tofile(f_s)
                    np.asarray([da_embeddare[i][0] for i in nuovi], dtype=np.int64).tofile(f_i)
                    np.asarray([da_embeddare[i][2] for i in nuovi], dtype=np.uint64).tofile(f_h)
                for i in nuovi:
                    esistenti[da_embeddare[i][0]] = righe
                    righe += 1
                esito.nuovi += len(nuovi)
            meta["righe"] = righe
            meta["aggiornato"] = _adesso()
            _scrivi_meta(percorso, meta)
            da_embeddare.clear()

        ultimo = 0
        while True:
            pagina = conn.execute(
                """
                SELECT c.id AS chunk_id, c.chunk_text, a.article_number, a.article_title,
                       d.titolo, d.numero, d.data_atto
                FROM normative_chunks c
                JOIN normative_documents d ON d.id = c.document_id
                LEFT JOIN normative_articles a ON a.id = c.article_id
                WHERE c.id > ?
                ORDER BY c.id
                LIMIT 2000
                """,
                (ultimo,),
            ).fetchall()
            if not pagina:
                break
            for riga in pagina:
                chunk_id = int(riga["chunk_id"])
                ultimo = chunk_id
                ids_db.add(chunk_id)
                testo = testo_documento(_titolo_chunk(riga), riga["chunk_text"] or "")
                impronta = impronta_testo(testo)
                posizione = esistenti.get(chunk_id)
                if posizione is not None and posizione < len(impronte) and int(impronte[posizione]) == impronta:
                    esito.invariati += 1
                    continue
                if massimo is not None and esito.nuovi + esito.ricalcolati + len(da_embeddare) >= massimo:
                    esito.interrotto_al_massimo = True
                    break
                da_embeddare.append((chunk_id, testo, impronta, posizione))
                if len(da_embeddare) >= max(1, int(batch)):
                    scarica()
                    fatti = esito.nuovi + esito.ricalcolati
                    if progresso is not None:
                        progresso(esito.invariati + fatti, totale, time.monotonic() - inizio)
            if esito.interrotto_al_massimo:
                break
        scarica()

        if not esito.interrotto_al_massimo and righe:
            ids_file = np.memmap(percorso / _FILE_IDS, dtype=np.int64, mode="r+", shape=(righe,))
            eliminati = [i for i, valore in enumerate(ids_file) if valore >= 0 and int(valore) not in ids_db]
            for posizione in eliminati:
                ids_file[posizione] = -1
            ids_file.flush()
            del ids_file
            esito.eliminati = len(eliminati)
        meta["righe"] = righe
        meta["chunk_totali"] = totale
        meta["aggiornato"] = _adesso()
        _scrivi_meta(percorso, meta)
    finally:
        conn.row_factory = precedente
    esito.righe = righe
    esito.secondi = time.monotonic() - inizio
    return esito


# ---------------------------------------------------------------------------------------------- #
# Riga di comando                                                                                 #
# ---------------------------------------------------------------------------------------------- #

def _barra(fatti: int, totale: int, secondi: float) -> None:
    larghezza = 30
    quota = (fatti / totale) if totale else 1.0
    pieni = int(larghezza * min(1.0, quota))
    velocita = fatti / secondi if secondi > 0 else 0.0
    resto = (totale - fatti) / velocita if velocita > 0 else 0.0
    print(
        f"\r[{'#' * pieni}{'.' * (larghezza - pieni)}] {fatti}/{totale} {quota * 100:5.1f}% "
        f"{velocita:6.1f} chunk/s  ~{resto / 60:5.1f} min",
        end="",
        flush=True,
    )


def main(argv: list[str] | None = None) -> int:
    import argparse

    from .embedding import OllamaEmbedder

    parser = argparse.ArgumentParser(
        prog="python -m lex.ricerca_giuridica.indice_vettoriale", description="Indice vettoriale dei chunk Normattiva."
    )
    parser.add_argument("comando", choices=["costruisci", "aggiorna", "info"])
    parser.add_argument("--db", help="database normattiva.sqlite")
    parser.add_argument("--out", required=True, help="cartella dell'indice vettoriale")
    parser.add_argument("--modello", default="", help="modello Ollama (default: LEX_EMBED_MODEL o embeddinggemma:300m)")
    parser.add_argument("--url", default="", help="URL di Ollama")
    parser.add_argument("--batch", type=int, default=32)
    parser.add_argument("--massimo", type=int, default=None, help="si ferma dopo N chunk (prova o costruzione a tappe)")
    parser.add_argument("--ricomincia", action="store_true", help="cancella l'indice e ricostruisce (solo costruisci)")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.WARNING, format="%(message)s")

    if args.comando == "info":
        indice = IndiceVettoriale.apri(args.out)
        if indice is None:
            print(f"Nessun indice vettoriale in {args.out}")
            return 1
        print(json.dumps(indice.meta, ensure_ascii=False, indent=2))
        attive = int((np.fromfile(Path(args.out) / _FILE_IDS, dtype=np.int64, count=indice.righe) >= 0).sum()) if indice.righe else 0
        print(f"righe attive: {attive} su {indice.righe}")
        return 0

    if not args.db or not Path(args.db).exists():
        print("Database Normattiva non trovato: indica --db <normattiva.sqlite>")
        return 2
    embedder = OllamaEmbedder(modello=args.modello, url=args.url)
    try:
        embedder.embed(["prova"])
    except Exception as exc:
        print(f"Ollama non raggiungibile su {embedder.url} con il modello {embedder.modello}: {exc}")
        return 3
    conn = sqlite3.connect(args.db)
    try:
        esito = costruisci_indice(
            conn,
            args.out,
            embedder,
            batch=args.batch,
            massimo=args.massimo,
            ricomincia=bool(args.ricomincia and args.comando == "costruisci"),
            progresso=_barra,
        )
    except IndiceIncompatibile as exc:
        print(f"\n{exc}")
        return 4
    except KeyboardInterrupt:
        print("\nInterrotto: rilancia lo stesso comando per riprendere dall'ultimo blocco salvato.")
        return 130
    finally:
        conn.close()
    print()
    print(json.dumps(esito.to_dict(), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "EsitoCostruzione",
    "FORMATO",
    "IndiceIncompatibile",
    "IndiceVettoriale",
    "costruisci_indice",
    "impronta_testo",
    "main",
    "quantizza",
]
