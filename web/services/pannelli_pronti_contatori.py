"""Contatori di revisione dei pannelli pronti preparati da soli, fuori dalle richieste web.

Fino alla 2.490 i trigger ``pannelli_rev_*`` si installavano solo al rilascio (``scripts/pannelli_pronti_prepara.py``
nel deploy). Le tabelle nate dopo il rilascio restavano senza contatori: le tabelle delle notifiche
(``notification_*`` di ``studio.db``, create dal repository della matrice probatoria al primo uso) non avevano
trigger, quindi una notifica nuova non cambiava l'impronta del fascicolo e il quadro restava quello di prima.

Qui la stessa preparazione governata (``pct.pannelli_pronti.preparazione.prepara_database``: piano dei trigger,
backup verificato solo quando il piano cambia, transazione) gira da sola:
- all'avvio dello scheduler, con il primo giro del lavoro dei pannelli pronti (``avvia_se_serve``);
- poi al più ogni ``INTERVALLO_SECONDI`` per database, così anche una tabella creata più tardi riceve i contatori.

Il controllo a piano invariato è una lettura dello schema in sola lettura: non scrive nulla. Base: art. 20 CAD
(integrità: nessuna scrittura senza copia verificata del database).
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Iterable

logger = logging.getLogger(__name__)
INTERVALLO_SECONDI = 600.0
# Il backup verificato è una copia intera del database (``studio.db`` dello studio supera i 14 GB): si fa solo se
# dopo la copia restano almeno 25 GB liberi; altrimenti si rinvia e lo dice il registro dell'applicazione.
MARGINE_DISCO_BYTE = 25 * 1024**3
_ULTIMO_CONTROLLO: dict[str, float] = {}


def cartella_backup(studio_db: str, slug: str = "") -> Path:
    """``<dati>/backup/pannelli-pronti/<studio>``: la stessa cartella persistente usata dal rilascio."""
    percorso = Path(studio_db).resolve()
    parti = percorso.parts
    radice = Path(*parti[: parti.index("tenants")]) if "tenants" in parti else percorso.parent
    return radice / "backup" / "pannelli-pronti" / (slug or percorso.parent.name)


def spazio_sufficiente(percorso: str, destinazione: Path) -> bool:
    import shutil

    cartella = destinazione
    while not cartella.exists() and cartella != cartella.parent:
        cartella = cartella.parent
    occupato = sum(Path(percorso + suffisso).stat().st_size for suffisso in ("", "-wal") if Path(percorso + suffisso).exists())
    return shutil.disk_usage(cartella).free - occupato >= MARGINE_DISCO_BYTE


def tieni_ultimo_backup(destinazione: Path, percorso: str, firma_corrente: str) -> list[str]:
    """Dopo un backup verificato riuscito, le copie dei piani precedenti dello stesso database si tolgono."""
    import shutil

    if not destinazione.is_dir():
        return []
    radice = Path(percorso).stem
    tolte = []
    for voce in destinazione.iterdir():
        if voce.is_dir() and voce.name.startswith(f"{radice}-") and voce.name != f"{radice}-{firma_corrente[:16]}" \
                and (destinazione / f"{radice}-{firma_corrente[:16]}" / "manifest.json").is_file():
            shutil.rmtree(voce, ignore_errors=True)
            tolte.append(voce.name)
    return tolte


def database_dello_studio(data_paths: dict[str, Any]) -> list[tuple[str, tuple[str, ...], bool]]:
    """(percorso, tabelle senza fascicolo, solo tabelle condivise) come nella preparazione del rilascio."""
    from web.services.pannelli_pronti_fonti import TABELLE_PEC, TABELLE_REGISTRO, TABELLE_STUDIO, percorso_pec
    from web.services.registro_letture_runtime import percorso_registro

    voci = [
        (str(data_paths.get("STUDIO_DB") or ""), TABELLE_STUDIO, False),
        (str(percorso_registro(data_paths) or ""), TABELLE_REGISTRO, False),
        (percorso_pec(data_paths), TABELLE_PEC, True),
    ]
    return [voce for voce in voci if voce[0]]


def prepara_contatori(data_paths: dict[str, Any], *, slug: str = "", forza: bool = False,
                      adesso: float | None = None) -> list[dict[str, object]]:
    """Installa o riallinea i trigger dei database dello studio quando il piano è cambiato. Mai eccezioni."""
    from pct.pannelli_pronti.preparazione import da_preparare, prepara_database

    momento = time.monotonic() if adesso is None else adesso
    esiti: list[dict[str, object]] = []
    studio_db = str(data_paths.get("STUDIO_DB") or "")
    if not studio_db:
        return esiti
    for percorso, tabelle, condivise in database_dello_studio(data_paths):
        if not forza and momento - _ULTIMO_CONTROLLO.get(percorso, float("-inf")) < INTERVALLO_SECONDI:
            continue
        _ULTIMO_CONTROLLO[percorso] = momento
        destinazione = cartella_backup(studio_db, slug)
        try:
            if not Path(percorso).is_file() or not da_preparare(percorso, tabelle, sole_tabelle_condivise=condivise):
                continue
            if not spazio_sufficiente(percorso, destinazione):
                logger.warning("Contatori dei pannelli rinviati su %s: spazio su disco insufficiente per il backup",
                               percorso)
                esiti.append({"database": percorso, "rinviato": "spazio su disco insufficiente per il backup"})
                continue
            esito = prepara_database(percorso, tabelle_senza_fascicolo=tabelle, applica=True,
                                     backup_dir=destinazione, sole_tabelle_condivise=condivise)
            if esito.get("cambiato") and esito.get("firma"):
                esito["backup_tolti"] = tieni_ultimo_backup(destinazione, percorso, str(esito["firma"]))
        except Exception as exc:  # il quadro resta calcolato come prima: si riprova al prossimo intervallo
            logger.warning("Contatori dei pannelli non preparati su %s: %s", percorso, exc)
            esito = {"database": percorso, "errore": str(exc)}
        if esito.get("cambiato"):
            logger.info("Contatori dei pannelli preparati su %s: %s trigger", percorso, esito.get("trigger"))
        esiti.append(esito)
    return esiti


def prepara_tutti(studi: Iterable[tuple[Any, dict[str, Any]]], *, forza: bool = False) -> list[dict[str, object]]:
    esiti: list[dict[str, object]] = []
    for owner, data_paths in studi:
        esiti.extend(prepara_contatori(data_paths, slug=str(getattr(owner, "slug", "") or ""), forza=forza))
    return esiti


__all__ = ["INTERVALLO_SECONDI", "MARGINE_DISCO_BYTE", "cartella_backup", "spazio_sufficiente", "tieni_ultimo_backup", "database_dello_studio", "prepara_contatori", "prepara_tutti"]
