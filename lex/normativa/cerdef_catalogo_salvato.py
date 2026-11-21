"""Proiezione riutilizzabile dell'indice pubblico CeRDEF."""
from __future__ import annotations

from functools import lru_cache
import gzip
import html
import json
import logging
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import Lock, Thread

from lex.normativa.cerdef_biblioteca import ID_BASE, _catalogue, fonti_catalogo
from lex.retrieval.normativa_catalog import wal_revision

_LOG = logging.getLogger(__name__)
_LOCK = Lock()
_IN_CORSO: set[Path] = set()


def _revisione(fonti):
    revisione = []
    for base, indice, database in fonti:
        registro = indice.stat()
        archivio = database.stat()
        revisione.append((base, str(indice), registro.st_dev, registro.st_ino, registro.st_size, registro.st_mtime_ns,
                          wal_revision(Path(str(indice) + "-wal"))))
        revisione.append((str(database), archivio.st_dev, archivio.st_ino))
        if base != ID_BASE:
            revisione.append((archivio.st_size, archivio.st_mtime_ns, wal_revision(Path(str(database) + "-wal"))))
        # Nel database generale l'associazione document_id+SHA è stabilita
        # dall'indice CeRDEF. Le scritture del crawler su altri atti non la
        # modificano. La consultazione del singolo atto mantiene il controllo SHA.
    return json.dumps(revisione, separators=(",", ":"))


@lru_cache(maxsize=2)
def _leggi(percorso, revisione, _mtime_ns):
    with gzip.open(percorso, "rt", encoding="utf-8") as file:
        payload = json.load(file)
    return payload["atti"] if payload["revisione"] == revisione else None


def _riscontro(percorso, revisione):
    try:
        return _leggi(percorso, revisione, percorso.stat().st_mtime_ns)
    except (OSError, EOFError, ValueError, KeyError):
        return None


def _ricostruisci(percorso, fonti, revisione, carica):
    file_temporaneo = None
    try:
        atti = [atto for base, indice, database in fonti for atto in carica(base, source=(indice, database))]
        if _revisione(fonti) != revisione:
            return
        percorso.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(dir=percorso.parent, prefix=".cerdef-", delete=False) as file:
            file_temporaneo = Path(file.name)
        with gzip.open(file_temporaneo, "wt", encoding="utf-8", compresslevel=3) as file:
            json.dump({"revisione": revisione, "atti": atti}, file, ensure_ascii=False, separators=(",", ":"))
        os.replace(file_temporaneo, percorso)
    finally:
        if file_temporaneo:
            file_temporaneo.unlink(missing_ok=True)


def _aggiorna(percorso, fonti, revisione, carica):
    try:
        if os.name != "posix":
            _ricostruisci(percorso, fonti, revisione, carica)
            return
        import fcntl

        percorso.parent.mkdir(parents=True, exist_ok=True)
        with percorso.with_suffix(".lock").open("ab") as lockfile:
            try:
                fcntl.flock(lockfile, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return
            if _riscontro(percorso, revisione) is None:
                _ricostruisci(percorso, fonti, revisione, carica)
    except Exception:
        _LOG.exception("Aggiornamento del catalogo storico CeRDEF non riuscito")
    finally:
        with _LOCK:
            _IN_CORSO.discard(percorso)


def catalogo_cerdef_salvato(data_dir, basi, *, prepara=False):
    """Il thread HTTP consulta una proiezione della stessa revisione delle fonti."""
    fonti = tuple((base, *source) for base in basi if (source := fonti_catalogo(base)) is not None)
    if not fonti:
        return []
    edizioni = "-".join(str(base // 10**12) for base in basi)
    percorso = Path(data_dir) / "search" / f"cerdef-catalogo-v3-{edizioni}.json.gz"
    revisione = _revisione(fonti)
    atti = _riscontro(percorso, revisione)
    if atti is not None:
        return atti
    if prepara:
        _ricostruisci(percorso, fonti, revisione, _catalogue)
        return _riscontro(percorso, revisione)
    with _LOCK:
        if percorso not in _IN_CORSO:
            _IN_CORSO.add(percorso)
            try:
                Thread(target=_aggiorna, args=(percorso, fonti, revisione, _catalogue),
                       name="catalogo-storico-cerdef", daemon=True).start()
            except RuntimeError:
                _IN_CORSO.discard(percorso)
                raise
    return None


# Campi che l'elenco di «Codici e leggi» usa davvero (scelta, ricerca, materie, data dell'edizione).
# urn, xml_entry e data_pubblicazione servono solo all'apertura del testo, che li rilegge dall'archivio:
# toglierli porta il catalogo vigente da 6,6 a 4,7 MB prima della compressione.
CAMPI_ELENCO = ("id", "key", "label", "title", "category", "articles", "materia", "tipo", "numero",
                "data_atto", "updated_at")


def voce_elenco(atto):
    """Voce leggera del catalogo, con i titoli decodificati («&agrave;» → «à»)."""
    voce = {campo: atto.get(campo) for campo in CAMPI_ELENCO if campo in atto}
    for campo in ("title", "label"):
        if isinstance(voce.get(campo), str) and "&" in voce[campo]:
            voce[campo] = html.unescape(voce[campo])
    if "materia" in atto:
        # La materia si ricalcola con le regole correnti: la proiezione salvata può essere di una versione precedente.
        from lex.normativa.materie import materia

        voce["materia"] = materia(str(atto.get("key") or ""), str(atto.get("urn") or ""), voce.get("title") or "")
    return voce


def elenco_leggero(atti):
    return [voce_elenco(atto) for atto in atti]
