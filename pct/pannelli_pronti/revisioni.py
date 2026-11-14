"""Contatori di revisione delle fonti dei pannelli, aggiornati da trigger SQL.

Ogni tabella con una colonna del fascicolo (``fascicolo_id``, ``id_fascicolo``; per ``fascicoli`` la chiave ``id``)
incrementa il contatore del fascicolo toccato nella stessa transazione della scrittura: non serve fidarsi di
``modificato_il`` o ``updated_at``, che non tutti i percorsi aggiornano. Le tabelle senza fascicolo lette dai
pannelli incrementano un contatore per tabella. L'impronta legge i contatori con una query per chiave primaria.

I trigger si installano solo con la preparazione governata (``scripts/pannelli_pronti_prepara.py``), mai in una
richiesta web: senza trigger installati l'impronta non esiste e i pannelli si calcolano come prima.
"""

from __future__ import annotations

import hashlib
import re
from typing import Iterable

VERSIONE_SCHEMA = 1
TABELLA_FASCICOLI = "pannelli_revisioni"
TABELLA_TABELLE = "pannelli_revisioni_tabelle"
TABELLA_SCHEMA = "pannelli_revisioni_schema"
PREFISSO_TRIGGER = "pannelli_rev_"
COLONNE_FASCICOLO = ("fascicolo_id", "id_fascicolo")

# Tabelle derivate o di servizio: proiezioni ricalcolabili, code di consegna, indici di ricerca, cache. Una loro
# scrittura non cambia i dati che un pannello mostra (le loro fonti hanno già i propri trigger).
_ESCLUSE_ESATTE = frozenset({
    "transactional_outbox", "operational_live_revisions", "operational_live_tenant_revisions",
    "operational_live_tenant_meta", "sqlite_sequence", "_meta",
    # registro delle letture: la vista dell'utente si ricompone a ogni apertura del pannello «Letture»;
    # la cache della Lettura e la coda degli eventi sono derivate dalle tabelle dei fatti e degli oggetti.
    "letture_viste", "letture_payload_cache",
})
_ESCLUSE_PREFISSI = (
    "fascicoli_list_", "pannelli_", "search_", "sqlite_", "calendar_query_", "email_mailbox_query_",
    "receipt_archive_query_", "controllo_",
)


def _nome_sicuro(valore: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", str(valore or "")):
        raise ValueError(f"Nome SQL non ammesso: {valore!r}")
    return str(valore)


def esclusa(tabella: str) -> bool:
    nome = str(tabella or "").lower()
    return nome in _ESCLUSE_ESATTE or nome.startswith(_ESCLUSE_PREFISSI)


def colonna_fascicolo(conn, tabella: str) -> str:
    """La colonna che identifica il fascicolo nella tabella, o stringa vuota."""
    if tabella == "fascicoli":
        return "id"
    colonne = {str(r[1]) for r in conn.execute(f"PRAGMA table_info('{_nome_sicuro(tabella)}')").fetchall()}
    return next((c for c in COLONNE_FASCICOLO if c in colonne), "")


def tabelle_del_fascicolo(conn) -> list[tuple[str, str]]:
    """Le tabelle del database con una colonna del fascicolo, escluse le derivate."""
    righe = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
    risultato = []
    for (nome,) in righe:
        nome = str(nome)
        if esclusa(nome) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", nome):
            continue
        colonna = colonna_fascicolo(conn, nome)
        if colonna:
            risultato.append((nome, colonna))
    return risultato


def _incrementa_fascicolo(espressione: str) -> str:
    return (f"INSERT INTO {TABELLA_FASCICOLI}(fascicolo_id,revisione) VALUES (CAST({espressione} AS TEXT),1) "
            f"ON CONFLICT(fascicolo_id) DO UPDATE SET revisione=revisione+1;")


def _incrementa_tabella(tabella: str) -> str:
    return (f"INSERT INTO {TABELLA_TABELLE}(tabella,revisione) VALUES ('{tabella}',1) "
            f"ON CONFLICT(tabella) DO UPDATE SET revisione=revisione+1;")


def _piano_per_fascicolo(tabella: str, nuovo: str, vecchio: str) -> dict[str, str]:
    base = f"{PREFISSO_TRIGGER}{tabella}"
    return {
        f"{base}_i": f"CREATE TRIGGER {base}_i AFTER INSERT ON {tabella} WHEN {nuovo} IS NOT NULL "
                     f"BEGIN {_incrementa_fascicolo(nuovo)} END",
        f"{base}_un": f"CREATE TRIGGER {base}_un AFTER UPDATE ON {tabella} WHEN {nuovo} IS NOT NULL "
                      f"BEGIN {_incrementa_fascicolo(nuovo)} END",
        f"{base}_uo": f"CREATE TRIGGER {base}_uo AFTER UPDATE ON {tabella} WHEN {vecchio} IS NOT NULL "
                      f"AND NOT COALESCE({vecchio} = {nuovo}, 0) BEGIN {_incrementa_fascicolo(vecchio)} END",
        f"{base}_d": f"CREATE TRIGGER {base}_d AFTER DELETE ON {tabella} WHEN {vecchio} IS NOT NULL "
                     f"BEGIN {_incrementa_fascicolo(vecchio)} END",
    }


def _piano_agenda_storica() -> dict[str, str]:
    """Il legame di Agenda è nel dato SQL dati_json sugli studi già attivi."""
    def fascicolo(riga: str) -> str:
        dato = f"{riga}.dati_json"
        return (f"(CASE WHEN json_valid({dato}) THEN "
                f"NULLIF(TRIM(CAST(json_extract({dato}, '$.id_fascicolo') AS TEXT)), '') END)")

    nuovo, vecchio = fascicolo("NEW"), fascicolo("OLD")
    tabella = _incrementa_tabella("appuntamenti")
    # Le voci senza fascicolo possono essere ritrovate per RG: cambiandole va
    # rivista la proiezione anche quando l'associazione non è ancora registrata.
    return {
        **_piano_per_fascicolo("appuntamenti", nuovo, vecchio),
        "pannelli_rev_appuntamenti_ti":
            f"CREATE TRIGGER pannelli_rev_appuntamenti_ti AFTER INSERT ON appuntamenti WHEN {nuovo} IS NULL BEGIN {tabella} END",
        "pannelli_rev_appuntamenti_tu":
            f"CREATE TRIGGER pannelli_rev_appuntamenti_tu AFTER UPDATE ON appuntamenti "
            f"WHEN {nuovo} IS NULL OR {vecchio} IS NULL BEGIN {tabella} END",
        "pannelli_rev_appuntamenti_td":
            f"CREATE TRIGGER pannelli_rev_appuntamenti_td AFTER DELETE ON appuntamenti WHEN {vecchio} IS NULL BEGIN {tabella} END",
    }


def piano_trigger(conn, tabelle_senza_fascicolo: Iterable[str] = ()) -> dict[str, str]:
    """Nome → istruzione CREATE TRIGGER per tutte le fonti del database."""
    piano: dict[str, str] = {}
    for tabella, colonna in tabelle_del_fascicolo(conn):
        t, c = _nome_sicuro(tabella), _nome_sicuro(colonna)
        nuovo, vecchio = f"NEW.{c}", f"OLD.{c}"
        if t == "practice_audit_events":
            # Solo gli eventi che incidono sulla pratica (per esempio un override economico)
            # entrano nell'impronta. Il Registro consulta direttamente gli eventi.
            consultazione = "'DOC_VIEWED', 'DOC_DOWNLOADED', 'DOC_EIDAS_CHECKED'"
            nuovo = f"(CASE WHEN NEW.event_type NOT IN ({consultazione}) THEN {nuovo} END)"
            vecchio = f"(CASE WHEN OLD.event_type NOT IN ({consultazione}) THEN {vecchio} END)"
        piano.update(_piano_per_fascicolo(t, nuovo, vecchio))
    esistenti = {str(r[0]) for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    for tabella in sorted(set(tabelle_senza_fascicolo)):
        if tabella not in esistenti or colonna_fascicolo(conn, tabella):
            continue
        if tabella == "appuntamenti" and any(
            row[1] == "dati_json" for row in conn.execute("PRAGMA table_info('appuntamenti')")
        ):
            piano.update(_piano_agenda_storica())
            continue
        t = _nome_sicuro(tabella)
        for sigla, azione in (("ti", "INSERT"), ("tu", "UPDATE"), ("td", "DELETE")):
            nome = f"{PREFISSO_TRIGGER}{t}_{sigla}"
            piano[nome] = f"CREATE TRIGGER {nome} AFTER {azione} ON {t} BEGIN {_incrementa_tabella(t)} END"
    return piano


def firma_piano(piano: dict[str, str]) -> str:
    digest = hashlib.sha256(f"v{VERSIONE_SCHEMA}".encode())
    for nome in sorted(piano):
        digest.update(nome.encode() + b"\0" + piano[nome].encode() + b"\n")
    return digest.hexdigest()


def installa_schema(conn) -> None:
    conn.execute(f"CREATE TABLE IF NOT EXISTS {TABELLA_FASCICOLI} ("
                 "fascicolo_id TEXT PRIMARY KEY, revisione INTEGER NOT NULL DEFAULT 0)")
    conn.execute(f"CREATE TABLE IF NOT EXISTS {TABELLA_TABELLE} ("
                 "tabella TEXT PRIMARY KEY, revisione INTEGER NOT NULL DEFAULT 0)")
    conn.execute(f"CREATE TABLE IF NOT EXISTS {TABELLA_SCHEMA} ("
                 "singleton INTEGER PRIMARY KEY CHECK (singleton = 1), firma TEXT NOT NULL, installato_il TEXT NOT NULL)")


def installa(conn, tabelle_senza_fascicolo: Iterable[str] = ()) -> dict[str, int | str | bool]:
    """Installa (o riallinea) i trigger. Idempotente; il chiamante gestisce la transazione e il backup."""
    from datetime import UTC, datetime

    installa_schema(conn)
    piano = piano_trigger(conn, tabelle_senza_fascicolo)
    firma = firma_piano(piano)
    attuale = conn.execute(f"SELECT firma FROM {TABELLA_SCHEMA} WHERE singleton=1").fetchone()
    presenti = {str(r[0]) for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='trigger' AND name LIKE ?", (PREFISSO_TRIGGER + "%",)).fetchall()}
    if attuale is not None and str(attuale[0]) == firma and presenti == set(piano):
        return {"cambiato": False, "trigger": len(piano), "firma": firma}
    for nome in sorted(presenti):
        conn.execute(f"DROP TRIGGER IF EXISTS {_nome_sicuro(nome)}")
    for nome in sorted(piano):
        conn.execute(piano[nome])
    adesso = datetime.now(UTC).isoformat()
    conn.execute(f"INSERT INTO {TABELLA_SCHEMA}(singleton,firma,installato_il) VALUES (1,?,?) "
                 "ON CONFLICT(singleton) DO UPDATE SET firma=excluded.firma, installato_il=excluded.installato_il",
                 (firma, adesso))
    # Le revisioni ripartono con una nuova firma: un payload salvato prima dell'installazione non può coincidere.
    return {"cambiato": True, "trigger": len(piano), "firma": firma}


def stato(conn) -> str:
    """La firma dei trigger installati, o stringa vuota se la preparazione non è stata fatta."""
    try:
        riga = conn.execute(f"SELECT firma FROM {TABELLA_SCHEMA} WHERE singleton=1").fetchone()
    except Exception:
        return ""
    return str(riga[0]) if riga else ""


def leggi(conn, fascicolo_id: str) -> tuple[str, int, tuple[tuple[str, int], ...]]:
    """(firma dei trigger, revisione del fascicolo, revisioni delle tabelle senza fascicolo)."""
    firma = stato(conn)
    if not firma:
        return "", 0, ()
    riga = conn.execute(f"SELECT revisione FROM {TABELLA_FASCICOLI} WHERE fascicolo_id=?",
                        (str(fascicolo_id),)).fetchone()
    tabelle = tuple((str(r[0]), int(r[1])) for r in conn.execute(
        f"SELECT tabella, revisione FROM {TABELLA_TABELLE} ORDER BY tabella").fetchall())
    return firma, int(riga[0]) if riga else 0, tabelle
