"""Ricevute dei depositi telematici lette dall'archivio PEC del software (pec_audit.sqlite, sola lettura).

Caso reale dell'08/11/2026: le ricevute di alcuni depositi non sono più nella casella PEC (cancellate per lo spazio
della casella Aruba), ma il software le aveva già archiviate con il messaggio originale completo. Il controllo dei
depositi le cerca quindi anche qui, non solo via IMAP negli ultimi giorni.

Le PEC dell'archivio passano per le stesse funzioni delle PEC lette via IMAP (``ricevuta_da_intestazioni``,
``testo_messaggio``, ``mittenti_interni``): stessi controlli sul gestore, sulle intestazioni ripetute e sul
collegamento per identificativo in ``pct/ricevute_deposito_pct.py``. Di ogni messaggio si leggono solo le
intestazioni; il testo completo solo per gli esiti del Ministero piccoli, mai le RdAC con la busta.

Velocità (misurata l'08/11/2026 sulla copia dello studio: 1.948 PEC, 643 MB dal 1° luglio): una query SQL su
``original_mime`` carica il messaggio intero, quindi si sceglie prima per oggetto con le intestazioni già salvate
in ``metadata_json`` (solo un filtro: decide sempre l'intestazione originale) e si apre il messaggio con la
lettura incrementale di SQLite (``blobopen``), solo i primi 64 KB.

Provenienza (revisione di sicurezza dell'08/11/2026): si leggono solo le PEC scaricate dalla casella dello studio
(``imap_uid`` presente) nelle cartelle in arrivo e cestino, e di un solo studio (``tenant_id``). La firma del gestore
non si verifica, per decisione dell'avvocato, come per le PEC lette via IMAP.
"""

from __future__ import annotations

import email as _email_lib
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterable, Mapping

from pct.ricevute_deposito_pct import (
    mittenti_interni,
    normalizza_message_id,
    ricevuta_da_intestazioni,
    serve_testo,
    testo_messaggio,
)

logger = logging.getLogger(__name__)

# Le stesse parole cercate nell'oggetto dalla ricerca IMAP (pct/polling_depositi.py::_cerca_ricevute_imap).
PAROLE_OGGETTO = ("DEPOSITO", "TELEMATIC", "ACCETTAZIONE", "CONSEGNA", "ESITO")
INTESTAZIONI_BYTES = 64 * 1024
ESITO_BYTES_MAX = 2 * 1024 * 1024
ESITI_DA_LEGGERE_MAX = 500
GIORNI_MASSIMI = 180
# Cartelle della casella in cui arrivano le ricevute; il cestino resta perché una ricevuta cestinata è ancora una prova.
CARTELLE_RICEVUTE = "('INBOX', 'CESTINO', 'TRASH')"


def percorso_archivio_pec(config: Mapping[str, Any]) -> Path:
    """L'archivio PEC dello studio, accanto alla casella email (come ``web/services/pec_pipeline_runtime.py``)."""
    esplicito = str(config.get("PEC_AUDIT_DB") or "").strip()
    if esplicito:
        return Path(esplicito)
    return Path(str(config.get("EMAIL_CASELLA_DB") or "./email/casella.json")).parent / "pec_audit.sqlite"


def _solo_intestazioni(grezzo: bytes) -> bytes:
    for separatore in (b"\r\n\r\n", b"\n\n"):
        fine = grezzo.find(separatore)
        if fine >= 0:
            return grezzo[: fine + len(separatore)]
    return grezzo


def _leggi(conn: sqlite3.Connection, riga_id: int, massimo: int) -> bytes:
    """I primi byte del messaggio originale senza caricarlo tutto (lettura incrementale del BLOB)."""
    with conn.blobopen("pec_messages", "original_mime", riga_id, readonly=True) as blob:
        return blob.read(massimo)


def _studio_dell_archivio(conn: sqlite3.Connection, studio: str) -> str:
    """Lo studio da leggere: quello indicato, o l'unico presente nel file; con più studi e nessuna indicazione, nessuno."""
    if studio:
        return studio
    presenti = [riga[0] for riga in conn.execute("SELECT DISTINCT tenant_id FROM pec_messages LIMIT 2").fetchall()]
    return presenti[0] if len(presenti) == 1 else ""


def ricevute_da_archivio(percorso: str | Path, *, dal: datetime, studio: str = "") -> list[dict]:
    """Le PEC di ritorno archiviate dal giorno indicato, nello stesso formato della ricerca IMAP.

    Solo PEC scaricate dalla casella (con numero IMAP) nelle cartelle in arrivo e cestino, e di un solo studio.
    """
    percorso = Path(percorso)
    if not percorso.is_file():
        return []
    dal = max(dal, datetime.now(dal.tzinfo) - timedelta(days=GIORNI_MASSIMI))
    risultati: list[dict] = []
    da_leggere: list[tuple[str, dict]] = []
    try:
        conn = sqlite3.connect(f"file:{percorso}?mode=ro", uri=True, timeout=10)
    except sqlite3.Error as exc:
        logger.warning("Archivio PEC non leggibile per le ricevute dei depositi: %s", exc)
        return []
    try:
        filtro = " OR ".join("metadata_json LIKE ?" for _ in PAROLE_OGGETTO)
        # Con lo studio indicato la ricerca resta sugli indici del presidio (che contengono anche metadata_json):
        # senza, SQLite scorre ogni riga attraverso il messaggio originale che la precede.
        studio = _studio_dell_archivio(conn, studio)
        if not studio:
            logger.warning("Archivio PEC con più studi e nessuno indicato: ricevute dei depositi non lette dall'archivio.")
            return []
        righe = conn.execute(
            "SELECT rowid, mime_size FROM pec_messages WHERE tenant_id = ? AND received_at >= ? "
            f"AND upper(folder) IN {CARTELLE_RICEVUTE} AND imap_uid <> '' AND ({filtro}) ORDER BY received_at",
            (studio, dal.strftime("%Y-%m-%d"), *(f"%{parola}%" for parola in PAROLE_OGGETTO)),
        ).fetchall()
        for riga_id, dimensione in righe:
            try:
                msg = _email_lib.message_from_bytes(_solo_intestazioni(_leggi(conn, riga_id, INTESTAZIONI_BYTES)))
                ricevuta = ricevuta_da_intestazioni(msg)
            except Exception:
                continue
            oggetto = str(ricevuta.get("subject") or "").upper()
            if not any(parola in oggetto for parola in PAROLE_OGGETTO):
                continue
            ricevuta["fonte"] = "archivio_pec"
            risultati.append(ricevuta)
            if serve_testo(ricevuta) and int(dimensione or 0) <= ESITO_BYTES_MAX:
                da_leggere.append((riga_id, ricevuta))
        for riga_id, ricevuta in da_leggere[:ESITI_DA_LEGGERE_MAX]:
            try:
                completo = _email_lib.message_from_bytes(_leggi(conn, riga_id, ESITO_BYTES_MAX))
                ricevuta["testo"] = testo_messaggio(completo)
                ricevuta["mittenti_interni"] = mittenti_interni(completo)
            except Exception:
                continue
    except sqlite3.Error as exc:
        logger.warning("Archivio PEC: lettura delle ricevute dei depositi interrotta: %s", exc)
    finally:
        conn.close()
    return risultati


def unisci_ricevute(*elenchi: Iterable[dict]) -> list[dict]:
    """Casella e archivio insieme; la stessa PEC (stesso Message-ID) conta una volta, la prima trovata."""
    viste: set[str] = set()
    unite: list[dict] = []
    for elenco in elenchi:
        for ricevuta in elenco or []:
            chiave = normalizza_message_id(ricevuta.get("message_id"))
            if chiave and chiave in viste:
                continue
            if chiave:
                viste.add(chiave)
            unite.append(ricevuta)
    return unite
