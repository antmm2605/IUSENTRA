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
from collections import deque
from collections.abc import Callable, Iterable, Iterator
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from .embedding import PREFISSO_DOCUMENTO, PREFISSO_DOMANDA, Embedder, IstanzeOllamaDiverse, normalizza_righe, testo_documento
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

        from .costruzione_iniziale import disponibile
        if not disponibile(self.meta):
            raise IndiceIncompatibile("Prima costruzione o riconvalida finale dell'indice non terminata")
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


def richieste_contemporanee(embedder: Any) -> int:
    """Richieste di embedding da tenere in volo insieme (attributo ``paralleli`` dell'embedder, minimo 1)."""

    try:
        return max(1, int(getattr(embedder, "paralleli", 1) or 1))
    except (TypeError, ValueError):
        return 1


def embed_in_flusso(embedder: Any, lotti: Iterable[list[Any]], testo: Callable[[Any], str]) -> Iterator[tuple[list[Any], np.ndarray]]:
    """Calcola gli embedding dei lotti tenendo sempre ``paralleli`` richieste in volo.

    I risultati escono nell'ordine dei lotti. A differenza della divisione di un batch in parti
    che si aspettano a vicenda, appena un lotto termina ne parte un altro: la GPU di Ollama non
    resta ferma mentre si scrive su disco o si aspetta la richiesta piu' lenta.
    """

    in_volo = richieste_contemporanee(embedder)
    if in_volo <= 1:
        for lotto in lotti:
            yield lotto, embedder.embed([testo(voce) for voce in lotto])
        return
    singolo = getattr(embedder, "embed_singolo", None) or embedder.embed
    esecutore = ThreadPoolExecutor(max_workers=in_volo, thread_name_prefix="embed")
    coda: deque[tuple[list[Any], Future]] = deque()
    try:
        for lotto in lotti:
            coda.append((lotto, esecutore.submit(singolo, [testo(voce) for voce in lotto])))
            if len(coda) >= in_volo:
                primo, futuro = coda.popleft()
                yield primo, futuro.result()
        while coda:
            primo, futuro = coda.popleft()
            yield primo, futuro.result()
    finally:
        esecutore.shutdown(wait=False, cancel_futures=True)


def costruisci_indice(
    conn: sqlite3.Connection,
    cartella: str | Path,
    embedder: Embedder,
    *,
    batch: int = 32,
    massimo: int | None = None,
    ricomincia: bool = False,
    prima_costruzione: bool = False,
    riconvalida_finale: bool = False,
    tempo_massimo_s: float | None = None,
    progresso: Callable[[int, int, float], None] | None = None,
) -> EsitoCostruzione:
    """Costruisce o aggiorna l'indice: solo chunk nuovi o con testo cambiato (ripresa automatica).

    ``progresso(completati, totale, chunk_al_secondo)``: la velocita' conta solo i chunk calcolati
    in questa sessione, non quelli gia' presenti nell'indice.
    """

    inizio = time.monotonic()
    if riconvalida_finale and (prima_costruzione or ricomincia):
        raise ValueError("La riconvalida finale è distinta dalla prima costruzione")
    if riconvalida_finale and (batch != 1 or richieste_contemporanee(embedder) != 1):
        raise ValueError("La riconvalida finale richiede batch=1 e una richiesta per volta")
    if tempo_massimo_s is not None and (
        not 0 < tempo_massimo_s <= 60 or batch != 1 or richieste_contemporanee(embedder) != 1
    ):
        raise ValueError("I lotti a tempo richiedono batch=1, una richiesta per volta e un limite fra 0 e 60 secondi")
    percorso = Path(cartella)
    percorso.mkdir(parents=True, exist_ok=True)
    esito = EsitoCostruzione()
    versione = ""
    try:
        versione = str(embedder.versione() or "")
    except IstanzeOllamaDiverse:
        raise
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
    if righe < int(meta.get("righe", 0)):
        meta.pop("riconvalida_iniziale", None)
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
        initial = None
        validation = None
        validation_version = None
        if prima_costruzione:
            from . import costruzione_iniziale
            initial = costruzione_iniziale.prepara(conn, meta, righe=righe, ids=esistenti)
            _scrivi_meta(percorso, meta)
        elif riconvalida_finale:
            from . import riconvalida_iniziale
            validation, validation_version = riconvalida_iniziale.prepara(conn, meta)
            _scrivi_meta(percorso, meta)
        meta["limite_tempo_raggiunto"] = False

        def scrivi(lotto: list[tuple[int, str, int, int | None]], matrice: np.ndarray) -> None:
            nonlocal righe, dimensioni
            if not lotto:
                return
            if dimensioni == 0:
                dimensioni = int(matrice.shape[1])
                meta["dimensioni"] = dimensioni
            if matrice.shape[1] != dimensioni:
                raise IndiceIncompatibile(f"il modello restituisce {matrice.shape[1]} dimensioni, l'indice {dimensioni}")
            valori, scale = quantizza(matrice)
            nuovi = [i for i, voce in enumerate(lotto) if voce[3] is None]
            vecchi = [i for i, voce in enumerate(lotto) if voce[3] is not None]
            if vecchi:
                mappa = np.memmap(percorso / _FILE_VETTORI, dtype=np.int8, mode="r+", shape=(righe, dimensioni))
                scale_file = np.memmap(percorso / _FILE_SCALE, dtype=np.float32, mode="r+", shape=(righe,))
                impronte_file = np.memmap(percorso / _FILE_IMPRONTE, dtype=np.uint64, mode="r+", shape=(righe,))
                for i in vecchi:
                    posizione = int(lotto[i][3])
                    mappa[posizione] = valori[i]
                    scale_file[posizione] = scale[i]
                    impronte_file[posizione] = np.uint64(lotto[i][2])
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
                    np.asarray([lotto[i][0] for i in nuovi], dtype=np.int64).tofile(f_i)
                    np.asarray([lotto[i][2] for i in nuovi], dtype=np.uint64).tofile(f_h)
                for i in nuovi:
                    esistenti[lotto[i][0]] = righe
                    righe += 1
                esito.nuovi += len(nuovi)
            meta["righe"] = righe
            meta["aggiornato"] = _adesso()
            if initial is not None:
                costruzione_iniziale.conferma_lotto(meta, lotto)
            _scrivi_meta(percorso, meta)

        # Con N richieste in volo, ogni richiesta porta batch/N chunk: --batch resta il lavoro in corso.
        in_volo = richieste_contemporanee(embedder)
        passo = max(1, -(-max(1, int(batch)) // in_volo))
        avvio_lavoro: list[float] = []

        def lotti() -> Iterator[list[tuple[int, str, int, int | None]]]:
            ultimo = int((initial or validation or {}).get("ultimo_id", 0))
            if validation is not None and validation["fase"] != "impronte":
                return
            prodotti = 0
            esaminati = 0
            lotto: list[tuple[int, str, int, int | None]] = []
            while True:
                pagina = conn.execute(
                    """
                    SELECT c.id AS chunk_id, c.chunk_text, a.article_number, a.article_title,
                           d.titolo, d.numero, d.data_atto
                    FROM normative_chunks c
                    JOIN normative_documents d ON d.id = c.document_id
                    LEFT JOIN normative_articles a ON a.id = c.article_id
                    WHERE c.id > ? AND (? IS NULL OR c.id<=?)
                    ORDER BY c.id
                    LIMIT 2000
                    """,
                    (ultimo, initial["massimo_id"] if initial is not None else None,
                     initial["massimo_id"] if initial is not None else None),
                ).fetchall()
                if not pagina:
                    if validation is not None:
                        validation["fase"] = "pulizia"
                    break
                for riga in pagina:
                    if tempo_massimo_s is not None and time.monotonic() - inizio >= tempo_massimo_s:
                        esito.interrotto_al_massimo = True
                        meta["limite_tempo_raggiunto"] = True
                        break
                    if validation is not None and esaminati >= 2000:
                        esito.interrotto_al_massimo = True
                        break
                    chunk_id = int(riga["chunk_id"])
                    ultimo = chunk_id
                    ids_db.add(chunk_id)
                    testo = testo_documento(_titolo_chunk(riga), riga["chunk_text"] or "")
                    impronta = impronta_testo(testo)
                    esaminati += 1
                    posizione = esistenti.get(chunk_id)
                    if posizione is not None and posizione < len(impronte) and int(impronte[posizione]) == impronta:
                        esito.invariati += 1
                        if validation is not None:
                            validation["ultimo_id"] = chunk_id
                        continue
                    if massimo is not None and prodotti >= massimo:
                        esito.interrotto_al_massimo = True
                        break
                    lotto.append((chunk_id, testo, impronta, posizione))
                    prodotti += 1
                    if len(lotto) >= passo:
                        if not avvio_lavoro:
                            avvio_lavoro.append(time.monotonic())
                        yield lotto
                        if validation is not None:
                            validation["ultimo_id"] = chunk_id
                        lotto = []
                if esito.interrotto_al_massimo:
                    break
            if lotto:
                if not avvio_lavoro:
                    avvio_lavoro.append(time.monotonic())
                yield lotto
                if validation is not None:
                    validation["ultimo_id"] = lotto[-1][0]

        for lotto, matrice in embed_in_flusso(embedder, lotti(), lambda voce: voce[1]):
            scrivi(lotto, matrice)
            if progresso is not None:
                fatti = esito.nuovi + esito.ricalcolati
                secondi = time.monotonic() - (avvio_lavoro[0] if avvio_lavoro else inizio)
                # velocita' solo sul lavoro di questa sessione: i chunk gia' presenti (ripresa) non contano
                velocita = fatti / secondi if secondi > 0 else 0.0
                progresso(esito.invariati + fatti, totale, velocita)

        if validation is not None and validation["fase"] == "pulizia":
            # Rimozioni a posizioni riprendibili, senza enumerare il corpus SQL.
            start = int(validation["posizione_pulizia"])
            stop = min(righe, start + 2000)
            if righe and start < stop:
                ids_file = np.memmap(percorso / _FILE_IDS, dtype=np.int64, mode="r+", shape=(righe,))
                selected = [int(value) for value in ids_file[start:stop] if value >= 0]
                present = set()
                for offset in range(0, len(selected), 500):
                    part = selected[offset:offset + 500]
                    present.update(int(row[0]) for row in conn.execute(
                        "SELECT c.id FROM normative_chunks c JOIN normative_documents d ON d.id=c.document_id WHERE c.id IN ("
                        + ",".join("?" for _ in part) + ")", part))
                for position in range(start, stop):
                    if ids_file[position] >= 0 and int(ids_file[position]) not in present:
                        ids_file[position] = -1
                        esito.eliminati += 1
                ids_file.flush()
                del ids_file
            validation["posizione_pulizia"] = stop
            validation["completa"] = stop >= righe
            esito.interrotto_al_massimo = not validation["completa"]
        elif not esito.interrotto_al_massimo and righe and initial is None and validation is None:
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
        if initial is not None:
            costruzione_iniziale.concludi(conn, meta, interrotto=esito.interrotto_al_massimo)
        elif validation is not None:
            if not riconvalida_iniziale.concludi(conn, meta, validation, validation_version):
                esito.interrotto_al_massimo = True
        elif not esito.interrotto_al_massimo and "riconvalida_finale_richiesta" in meta:
            meta["riconvalida_finale_richiesta"] = False
        _scrivi_meta(percorso, meta)
    finally:
        conn.row_factory = precedente
    esito.righe = righe
    esito.secondi = time.monotonic() - inizio
    return esito


# ---------------------------------------------------------------------------------------------- #
# Riga di comando                                                                                 #
# ---------------------------------------------------------------------------------------------- #

def _barra(fatti: int, totale: int, velocita: float) -> None:
    larghezza = 30
    quota = (fatti / totale) if totale else 1.0
    pieni = int(larghezza * min(1.0, quota))
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
    parser.add_argument("--paralleli", type=int, default=0, help="richieste Ollama contemporanee (0 = LEX_EMBED_PARALLELI o 1)")
    parser.add_argument("--massimo", type=int, default=None, help="si ferma dopo N chunk (prova o costruzione a tappe)")
    parser.add_argument("--prima-costruzione", action="store_true", help="prima costruzione a checkpoint su un indice nuovo separato")
    parser.add_argument("--riconvalida-finale", action="store_true", help="riconvalida del candidato a lotti riprendibili di massimo 2000 righe")
    parser.add_argument("--tempo-massimo-s", type=float, default=None, help="budget lotto, massimo 60 s; richiede --batch 1")
    parser.add_argument("--ricomincia", action="store_true", help="cancella l'indice e ricostruisce (solo costruisci)")
    parser.add_argument(
        "--se-disponibile",
        action="store_true",
        help="aggiornamento notturno: se Ollama o il modello non rispondono esce con successo (0) senza fare nulla",
    )
    parser.add_argument(
        "--solo-esistente",
        action="store_true",
        help="aggiornamento notturno: non crea un indice nuovo, aggiorna solo quello gia' presente",
    )
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
    if args.solo_esistente and IndiceVettoriale.apri(args.out) is None:
        print(f"Indice vettoriale assente in {args.out}: aggiornamento saltato (si crea con il pacchetto o a mano).")
        return 0
    # costruzione lunga: piu' tentativi e attese piu' lunghe (Ollama puo' ricaricare il modello dopo un errore)
    embedder = OllamaEmbedder(
        modello=args.modello, url=args.url, paralleli=getattr(args, "paralleli", 0) or 0, tentativi=4, attesa_s=2.0
    )
    try:
        embedder.embed(["prova"])
    except Exception as exc:
        print(f"Ollama non raggiungibile su {embedder.url} con il modello {embedder.modello}: {exc}")
        if args.se_disponibile:
            print("Indice vettoriale non aggiornato: la ricerca resta lessicale (FTS) e riprovera' al prossimo giro.")
            return 0
        return 3
    conn = sqlite3.connect(args.db)
    try:
        esito = costruisci_indice(
            conn,
            args.out,
            embedder,
            batch=args.batch,
            massimo=args.massimo,
            prima_costruzione=args.prima_costruzione,
            riconvalida_finale=args.riconvalida_finale,
            tempo_massimo_s=args.tempo_massimo_s,
            ricomincia=bool(args.ricomincia and args.comando == "costruisci"),
            progresso=_barra,
        )
    except IndiceIncompatibile as exc:
        print(f"\n{exc}")
        return 0 if args.se_disponibile else 4
    except KeyboardInterrupt:
        print("\nInterrotto: rilancia lo stesso comando per riprendere dall'ultimo blocco salvato.")
        return 130
    finally:
        conn.close()
    print()
    ridotti = list(getattr(embedder, "testi_ridotti", []) or [])
    if ridotti:
        print(f"Chunk indicizzati con testo accorciato perche' rifiutati da Ollama: {len(ridotti)}")
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
