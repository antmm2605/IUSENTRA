"""Vista preferita dell'elenco documenti del fascicolo.

Ogni studio guarda i documenti a modo suo: chi lavora sulle scadenze parte dai
«Da firmare», chi controlla la catalogazione dai «Senza sezione», chi segue il
deposito dall'ultimo caricato. Rifare la scelta a ogni fascicolo e' lavoro
ripetuto, e quando i fascicoli sono molti diventa lavoro perso.

La preferenza vale per lo studio ed e' esplicita: si salva quando l'avvocato lo
chiede, non si registra da sola mentre naviga. Non e' un filtro di sicurezza —
non nasconde documenti a nessuno — ma solo l'ordine in cui compaiono.

Le chiavi ammesse sono quelle dichiarate dal frontend: un valore fuori catalogo
viene riportato al predefinito invece di essere salvato, cosi' una vista non
puo' «sparire» per un dato corrotto.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from pct.document_intelligence.sezioni import SEZIONI_DOCUMENTO

SEZIONE = "fascicolo_documenti_vista"
SORGENTE = "react_fascicolo_documenti"

# Ordinamenti dichiarati in frontend/src/components/fascicoloDocumenti/documentListOrdering.ts
ORDINAMENTI = {
    "data_documento_desc",
    "data_documento_asc",
    "caricamento_desc",
    "caricamento_asc",
    "nome_asc",
}
ORDINAMENTO_PREDEFINITO = "data_documento_desc"

# Sezioni dichiarate in FascicoliPage.tsx (documentListSectionOptions).
# Le stesse sezioni del catalogo documentale, piu' «tutte».
SEZIONI = {"tutte", *SEZIONI_DOCUMENTO}
SEZIONE_PREDEFINITA = "tutte"

STATI = {"tutti", "da_firmare", "da_verificare"}
STATO_PREDEFINITO = "tutti"


def preferenze_predefinite() -> dict[str, Any]:
    return {"sort": ORDINAMENTO_PREDEFINITO, "section": SEZIONE_PREDEFINITA, "status": STATO_PREDEFINITO}


def _scelta(valore: Any, ammessi: set[str], predefinito: str) -> str:
    testo = str(valore or "").strip()
    return testo if testo in ammessi else predefinito


def normalizza(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    """Preferenze ripulite: ogni campo o e' una scelta valida o e' il predefinito."""
    origine = dict(payload or {})
    if isinstance(origine.get("preferences"), Mapping):
        origine = dict(origine["preferences"])
    return {
        "sort": _scelta(origine.get("sort"), ORDINAMENTI, ORDINAMENTO_PREDEFINITO),
        "section": _scelta(origine.get("section"), SEZIONI, SEZIONE_PREDEFINITA),
        "status": _scelta(origine.get("status"), STATI, STATO_PREDEFINITO),
    }


def _percorso(ancora: str | Path) -> Path:
    return Path(ancora).resolve().parent / "ui_preferences.db"


def _prepara(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS ui_preferences (
            scope TEXT PRIMARY KEY,
            updated_at TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT 'react_fascicoli',
            dati_json TEXT NOT NULL DEFAULT '{}'
        );
        CREATE INDEX IF NOT EXISTS idx_ui_preferences_updated ON ui_preferences(updated_at);
        """
    )


def carica(ancora: str | Path) -> dict[str, Any]:
    """Vista salvata, o i predefiniti quando lo studio non ne ha ancora una."""
    percorso = _percorso(ancora)
    riga = None
    if percorso.exists():
        try:
            with sqlite3.connect(str(percorso), timeout=2.0) as conn:
                conn.execute("PRAGMA busy_timeout=2000")
                _prepara(conn)
                riga = conn.execute(
                    "SELECT updated_at, dati_json FROM ui_preferences WHERE scope = ?", (SEZIONE,)
                ).fetchone()
        except sqlite3.Error:
            riga = None
    if not riga:
        return {"ok": True, "configured": False, "updatedAt": "", "preferences": preferenze_predefinite()}
    try:
        salvato = json.loads(riga[1] or "{}")
    except json.JSONDecodeError:
        salvato = {}
    if not isinstance(salvato, dict):
        salvato = {}
    return {
        "ok": True,
        "configured": True,
        "updatedAt": str(salvato.get("updatedAt") or riga[0] or ""),
        "preferences": normalizza(salvato),
    }


def salva(ancora: str | Path, payload: Mapping[str, Any] | None) -> dict[str, Any]:
    preferenze = normalizza(payload)
    momento = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    percorso = _percorso(ancora)
    percorso.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(percorso), timeout=5.0) as conn:
        conn.execute("PRAGMA busy_timeout=5000")
        _prepara(conn)
        conn.execute(
            """
            INSERT INTO ui_preferences (scope, updated_at, source, dati_json)
            VALUES (?,?,?,?)
            ON CONFLICT(scope) DO UPDATE SET
                updated_at = excluded.updated_at,
                source = excluded.source,
                dati_json = excluded.dati_json
            """,
            (
                SEZIONE,
                momento,
                SORGENTE,
                json.dumps({"preferences": preferenze, "updatedAt": momento}, ensure_ascii=False, separators=(",", ":")),
            ),
        )
    return {
        "ok": True,
        "configured": True,
        "updatedAt": momento,
        "preferences": preferenze,
        "message": "Vista dei documenti salvata per questo studio.",
    }


def dimentica(ancora: str | Path) -> dict[str, Any]:
    """Torna alla vista predefinita cancellando la preferenza salvata."""
    percorso = _percorso(ancora)
    if percorso.exists():
        with sqlite3.connect(str(percorso), timeout=5.0) as conn:
            conn.execute("PRAGMA busy_timeout=5000")
            _prepara(conn)
            conn.execute("DELETE FROM ui_preferences WHERE scope = ?", (SEZIONE,))
    return {
        "ok": True,
        "configured": False,
        "updatedAt": "",
        "preferences": preferenze_predefinite(),
        "message": "Vista dei documenti riportata ai valori predefiniti.",
    }
