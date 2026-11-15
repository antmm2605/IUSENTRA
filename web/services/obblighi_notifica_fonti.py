"""Impronta delle sole fonti da cui dipendono gli obblighi di un fascicolo."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path

from flask import g, has_request_context

from pct.ora_italiana import oggi_roma
from pct.pannelli_pronti.impronta import revisioni_database
from web.services.registro_letture_runtime import percorso_registro, tenant_corrente

VERSIONE = "obblighi-notifica-fonti:v1"


def _apri(percorso: str) -> sqlite3.Connection:
    return sqlite3.connect(Path(percorso).resolve().as_uri() + "?mode=ro", uri=True, timeout=1)


def riferimento_corrente(fascicolo_id: str) -> str | None:
    """Legge i contatori SQL del solo fascicolo per la consultazione ordinaria."""
    if not has_request_context() or not fascicolo_id:
        return None
    percorsi = g.get("data_paths") or {}
    studio = percorsi.get("STUDIO_DB")
    if not studio:
        return None
    try:
        revisioni = [
            revisioni_database(p, fascicolo_id)
            for p in (studio, percorso_registro(percorsi))
        ]
        if any(r is None for r in revisioni):
            return None
        valori = [VERSIONE, oggi_roma().isoformat(), *(r[:2] for r in revisioni if r is not None)]
        return json.dumps(valori, separators=(",", ":"))
    except (OSError, TypeError, ValueError, sqlite3.Error):
        return None


def impronta(fascicolo_id: str) -> str | None:
    """Legge le fonti SQL correnti senza consultare atti, eseguire OCR o calcolare scadenze."""
    if not has_request_context() or not fascicolo_id:
        return None
    percorsi = g.get("data_paths") or {}
    studio = percorsi.get("STUDIO_DB")
    if not studio:
        return None
    tenant = tenant_corrente()
    parametri = (tenant, fascicolo_id)
    try:
        with closing(_apri(studio)) as db:
            db.execute("BEGIN")
            fascicolo = db.execute(
                """SELECT tipo, stato, numero_rg, anno_rg, tribunale, controparte,
                          json_extract(dati_json, '$.ufficio_giudiziario'),
                          json_extract(dati_json, '$.avvocato_controparte'), documenti_json
                     FROM fascicoli WHERE id=?""",
                (fascicolo_id,),
            ).fetchone()
            if fascicolo is None:
                return None
            catalogo = db.execute(
                """SELECT document_id, document_label, status, updated_at
                     FROM document_catalog_assignments WHERE tenant_id=? AND fascicolo_id=?
                      AND status NOT IN ('superseded', 'rejected')
                    ORDER BY updated_at DESC, document_label, document_id""",
                parametri,
            ).fetchall()
            testi = db.execute(
                """SELECT d.id, d.sha256, d.original_filename, d.updated_at, d.current_version_id, t.text
                     FROM fascicolo_documenti_ai d LEFT JOIN fascicolo_documenti_ai_testi t
                       ON (t.tenant_id,t.fascicolo_id,t.document_id,t.version_id) =
                          (d.tenant_id,d.fascicolo_id,d.id,d.current_version_id)
                    WHERE d.tenant_id=? AND d.fascicolo_id=? AND d.status='ready'
                    ORDER BY d.updated_at DESC, d.id""",
                parametri,
            ).fetchall()
            verifiche = db.execute(
                """SELECT documento_id, dati_json, revisione FROM notifiche_verifiche
                    WHERE tenant_id=? AND fascicolo_id=? ORDER BY documento_id""",
                parametri,
            ).fetchall()
        with closing(_apri(percorso_registro(percorsi))) as db:
            db.execute("BEGIN")
            fatti = db.execute(
                """SELECT tipo, oggetto_id, sha256, categoria, campo, valore, contesto,
                          posizione, verifica, prove_json, letto_il, valore_letto, etichetta,
                          origine, confidenza, motore, versione_motore
                     FROM letture_fatti WHERE tenant_id=? AND fascicolo_id=?
                      AND verifica IN ('verificata','plausibile','corretta')
                      AND (categoria IN ('data','ruolo','parte','prova_notifica')
                           OR campo IN ('impronta_testo_atto','riscontro_notifica_pec_storica'))
                    ORDER BY posizione, letto_il, id""",
                parametri,
            ).fetchall()
            oggetti = db.execute(
                """SELECT tipo, oggetto_id, sha256, sha256_archivio, presente
                     FROM letture_oggetti WHERE tenant_id=? AND fascicolo_id=?
                    ORDER BY tipo, oggetto_id""",
                parametri,
            ).fetchall()
        # L'indice OCR conserva il testo delle scansioni che non è ancora nella
        # tabella dei testi. Legge una sola volta le sole impronte di questa pratica.
        cache_ocr = _cache_ocr(percorsi.get("SEARCH_INDEX"), fascicolo[-1])
        fonti = [VERSIONE, oggi_roma().isoformat(), fascicolo, catalogo, testi, verifiche, fatti, oggetti, cache_ocr]
        return hashlib.sha256(json.dumps(fonti, ensure_ascii=False).encode("utf-8")).hexdigest()
    except (OSError, TypeError, ValueError, sqlite3.Error):
        return None


def _cache_ocr(percorso: str | None, documenti_json: str) -> list[tuple]:
    if not percorso or not Path(percorso).is_file():
        return []
    impronte = sorted({d["hash_sha256"] for d in json.loads(documenti_json or "[]") if d.get("hash_sha256")})
    if not impronte:
        return []
    with closing(_apri(percorso)) as db:
        return db.execute(
            """SELECT hash_sha256, testo FROM ocr_cache
                WHERE hash_sha256 IN (SELECT value FROM json_each(?)) ORDER BY hash_sha256""",
            (json.dumps(impronte),),
        ).fetchall()
