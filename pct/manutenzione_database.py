"""Misura e recupera lo spazio sprecato dentro gli `studio.db`.

SQLite non restituisce mai da solo lo spazio di una riga cancellata o
accorciata: le pagine liberate finiscono in una lista interna al file, che
resta grande com'era. Dopo la 2.328.0, che ha tolto la copia doppia dei
documenti da `dati_json`, quelle pagine sono tante e nessuno le ha ancora
reclamate.

`analizza` legge e basta. `compatta` esegue un VACUUM vero, e va usato
sapendo che per tutta la durata il database resta bloccato in scrittura.

La logica sta qui, non nella rotta: la console e la riga di comando devono
fare esattamente la stessa cosa.
"""

from __future__ import annotations

import shutil
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pct.manutenzione_dati_json import archivi_degli_studi

#: Quanto spazio libero serve, in proporzione al file, per osare un VACUUM.
#: SQLite costruisce il database nuovo accanto a quello vecchio prima di
#: sostituirlo: senza questo margine si riempie il disco a meta' lavoro.
MARGINE_DISCO = 1.2

#: Sotto questa percentuale di pagine libere il VACUUM costa piu' di quanto rende.
SOGLIA_UTILE_PERCENTO = 10.0


def _mb(byte: int) -> float:
    return round(byte / 1048576, 2)


def _gb(byte: int) -> float:
    return round(byte / 1073741824, 2)


def _etichetta(byte: int) -> str:
    """Una misura leggibile: «0.0 GiB» non dice niente a chi legge."""
    byte = int(byte or 0)
    for soglia, divisore, unita in (
        (1073741824, 1073741824, "GiB"),
        (1048576, 1048576, "MB"),
        (1024, 1024, "KB"),
    ):
        if byte >= soglia:
            return f"{round(byte / divisore, 2)} {unita}"
    return f"{byte} byte"


@dataclass
class EsitoDatabase:
    """Quanto pesa un `studio.db` e quanto se ne potrebbe recuperare."""

    studio: str
    percorso: str
    byte_su_disco: int = 0
    byte_liberabili: int = 0
    pagine: int = 0
    pagine_libere: int = 0
    dimensione_pagina: int = 0
    byte_dopo: int = 0
    compattato: bool = False
    saltato: str = ""
    errore: str = ""

    @property
    def percento_libero(self) -> float:
        if not self.pagine:
            return 0.0
        return round(100 * self.pagine_libere / self.pagine, 1)

    @property
    def vale_la_pena(self) -> bool:
        return self.percento_libero >= SOGLIA_UTILE_PERCENTO

    def come_dizionario(self) -> dict[str, Any]:
        return {
            "studio": self.studio,
            "percorso": self.percorso,
            "su_disco": _etichetta(self.byte_su_disco),
            "liberabili": _etichetta(self.byte_liberabili),
            "dopo": _etichetta(self.byte_dopo) if self.byte_dopo else "",
            "recuperati": _etichetta(self.byte_su_disco - self.byte_dopo) if self.byte_dopo else "",
            "gb_su_disco": _gb(self.byte_su_disco),
            "mb_su_disco": _mb(self.byte_su_disco),
            "gb_liberabili": _gb(self.byte_liberabili),
            "mb_liberabili": _mb(self.byte_liberabili),
            "percento_libero": self.percento_libero,
            "vale_la_pena": self.vale_la_pena,
            "pagine": self.pagine,
            "pagine_libere": self.pagine_libere,
            "dimensione_pagina": self.dimensione_pagina,
            "gb_dopo": _gb(self.byte_dopo) if self.byte_dopo else 0.0,
            "gb_recuperati": _gb(self.byte_su_disco - self.byte_dopo) if self.byte_dopo else 0.0,
            "compattato": self.compattato,
            "saltato": self.saltato,
            "errore": self.errore,
        }


def _peso_su_disco(db: Path) -> int:
    """Il file piu' i suoi compagni: senza WAL il conto e' falso."""
    totale = 0
    for nome in (db.name, f"{db.name}-wal", f"{db.name}-shm", f"{db.name}-journal"):
        candidato = db.parent / nome
        try:
            if candidato.exists():
                totale += candidato.stat().st_size
        except OSError:
            continue
    return totale


def analizza(db: Path) -> EsitoDatabase:
    """Legge le pagine libere. Apre in sola lettura e non modifica nulla."""
    db = Path(db)
    esito = EsitoDatabase(studio=db.parent.name, percorso=str(db))
    try:
        esito.byte_su_disco = _peso_su_disco(db)
        with sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=10) as conn:
            leggi = lambda nome: int(conn.execute(f"PRAGMA {nome}").fetchone()[0])  # noqa: E731
            esito.pagine = leggi("page_count")
            esito.pagine_libere = leggi("freelist_count")
            esito.dimensione_pagina = leggi("page_size")
        esito.byte_liberabili = esito.pagine_libere * esito.dimensione_pagina
    except Exception as exc:
        esito.errore = str(exc)
    return esito


def compatta(db: Path) -> EsitoDatabase:
    """Esegue VACUUM su un singolo archivio.

    Si ferma da sola quando non conviene o quando il disco non ha il margine
    che SQLite richiede: meglio non fare niente che riempire il disco a meta'
    di un VACUUM.
    """
    esito = analizza(db)
    if esito.errore:
        return esito
    if not esito.vale_la_pena:
        esito.saltato = (
            f"Solo il {esito.percento_libero}% delle pagine e' libero: "
            f"sotto il {SOGLIA_UTILE_PERCENTO}% il VACUUM costa piu' di quanto rende."
        )
        return esito
    try:
        libero = shutil.disk_usage(Path(db).parent).free
    except OSError as exc:
        esito.errore = str(exc)
        return esito
    richiesto = int(esito.byte_su_disco * MARGINE_DISCO)
    if libero < richiesto:
        esito.saltato = (
            f"Servono {_etichetta(richiesto)} liberi sul disco per lavorare in sicurezza, "
            f"ce ne sono {_etichetta(libero)}."
        )
        return esito
    try:
        with sqlite3.connect(str(db), timeout=60) as conn:
            conn.execute("VACUUM")
        esito.byte_dopo = _peso_su_disco(Path(db))
        esito.compattato = True
    except Exception as exc:
        esito.errore = str(exc)
    return esito


def esamina_tutti(data_root: Path, *, compattare: bool = False) -> dict[str, Any]:
    archivi = archivi_degli_studi(Path(data_root))
    if not archivi:
        return {
            "ok": False,
            "messaggio": f"Nessuno studio.db trovato sotto {data_root}.",
            "studi": [],
        }
    esiti = [(compatta(db) if compattare else analizza(db)) for db in archivi]
    liberabili = sum(e.byte_liberabili for e in esiti)
    recuperati = sum((e.byte_su_disco - e.byte_dopo) for e in esiti if e.byte_dopo)
    errori = [e.errore for e in esiti if e.errore]
    saltati = [f"{e.studio}: {e.saltato}" for e in esiti if e.saltato]
    if compattare:
        messaggio = f"Recuperati {_etichetta(recuperati)} su {len(esiti)} archivi."
        if saltati:
            messaggio += f" Saltati {len(saltati)}."
    else:
        messaggio = (
            f"{_etichetta(liberabili)} recuperabili con un VACUUM. Nessuna modifica eseguita."
        )
    return {
        "ok": not errori,
        "compattazione_eseguita": bool(compattare),
        "gb_liberabili": _gb(liberabili),
        "gb_recuperati": _gb(recuperati),
        "liberabili": _etichetta(liberabili),
        "recuperati": _etichetta(recuperati),
        "errori": errori,
        "saltati": saltati,
        "studi": [e.come_dizionario() for e in esiti],
        "messaggio": messaggio,
    }
