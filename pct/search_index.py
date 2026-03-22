"""
Indice di ricerca full-text con SQLite FTS5.

Funzionalità:
  - Indicizzazione veloce di clienti, fascicoli, agenda, scadenziario
  - Full-text search con ranking BM25 nativo SQLite
  - Aggiornamento incrementale (insert/delete/update)
  - Ricerca globale unificata con risultati raggruppati per tipo
  - Snippet contestuale nel risultato

L'indice è un file SQLite separato dal DB dati (solo cache di ricerca).
Se l'indice viene cancellato può essere ricostruito in qualsiasi momento.
"""

import sqlite3
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime


# ------------------------------------------------------------------ Risultato

@dataclass
class RisultatoRicerca:
    tipo: str          # "fascicolo" | "cliente" | "appuntamento" | "scadenza"
    id: str
    titolo: str
    sottotitolo: str
    url: str           # route Flask relativa
    icona: str         # Bootstrap Icon class
    rank: float = 0.0
    snippet: str = ""


# ------------------------------------------------------------------ Indice

class IndiceRicerca:
    """
    Gestisce un indice SQLite FTS5 per la ricerca full-text.

    Schema:
        documenti(rowid, tipo, entity_id, titolo, corpo, meta)
        → FTS5 su (titolo, corpo)
    """

    CREATE_FTS = """
        CREATE VIRTUAL TABLE IF NOT EXISTS documenti USING fts5(
            tipo UNINDEXED,
            entity_id UNINDEXED,
            titolo,
            corpo,
            meta UNINDEXED,
            tokenize = 'unicode61 remove_diacritics 1'
        );
    """

    def __init__(self, index_path: str = "./search_index.db"):
        self.path = Path(index_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self):
        with self._conn:
            self._conn.execute(self.CREATE_FTS)
            # Tabella metadati per tracciare l'ultima indicizzazione
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS meta_indice (
                    chiave TEXT PRIMARY KEY,
                    valore TEXT
                )
            """)
            # Cache OCR: keyed by sha256 per evitare di ripetere l'OCR sullo stesso file
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS ocr_cache (
                    hash_sha256 TEXT PRIMARY KEY,
                    testo       TEXT,
                    elaborato_il TEXT
                )
            """)

    # ---- indicizzazione

    def indicizza(
        self,
        tipo: str,
        entity_id: str,
        titolo: str,
        corpo: str,
        meta: dict = None,
    ):
        """Aggiunge o aggiorna un documento nell'indice."""
        # Rimuovi il vecchio record se esiste
        self.rimuovi(tipo, entity_id)
        meta_json = json.dumps(meta or {}, ensure_ascii=False)
        with self._conn:
            self._conn.execute(
                "INSERT INTO documenti(tipo, entity_id, titolo, corpo, meta) VALUES(?,?,?,?,?)",
                (tipo, entity_id, titolo or "", corpo or "", meta_json),
            )

    def rimuovi(self, tipo: str, entity_id: str):
        """Rimuove un documento dall'indice."""
        with self._conn:
            self._conn.execute(
                "DELETE FROM documenti WHERE tipo=? AND entity_id=?",
                (tipo, entity_id),
            )

    def indicizza_documento(
        self,
        id_fasc: str,
        id_doc: str,
        nome: str,
        testo: str,
        tipo_doc: str = "",
    ):
        """
        Indicizza il contenuto OCR di un documento allegato a un fascicolo.

        entity_id = "{id_fasc}:{id_doc}" per garantire unicità globale.
        """
        if not testo or not testo.strip():
            return
        self.indicizza(
            tipo="documento",
            entity_id=f"{id_fasc}:{id_doc}",
            titolo=nome,
            corpo=testo,
            meta={"id_fasc": id_fasc, "id_doc": id_doc, "tipo_doc": tipo_doc},
        )

    # ---- OCR cache

    def get_ocr_cache(self, hash_sha256: str) -> Optional[str]:
        """Restituisce il testo OCR dalla cache, o None se non presente."""
        row = self._conn.execute(
            "SELECT testo FROM ocr_cache WHERE hash_sha256=?", (hash_sha256,)
        ).fetchone()
        return row["testo"] if row else None

    def set_ocr_cache(self, hash_sha256: str, testo: str):
        """Salva il risultato OCR in cache."""
        with self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO ocr_cache(hash_sha256, testo, elaborato_il) VALUES(?,?,?)",
                (hash_sha256, testo, datetime.now().isoformat()),
            )

    def ricostruisci(
        self,
        clienti=None,
        fascicoli=None,
        appuntamenti=None,
        scadenze=None,
        documenti_ocr=None,
    ):
        """
        Ricostruisce l'indice completo dai dati forniti.

        Args:
            clienti, fascicoli, appuntamenti, scadenze: liste di oggetti/dict
            documenti_ocr: lista di tuple (id_fasc, id_doc, nome, testo, tipo_doc)
                           con il testo già estratto via OCR/cache
        """
        # Svuota solo il testo indicizzato (non la cache OCR)
        with self._conn:
            self._conn.execute("DELETE FROM documenti")

        if clienti:
            for c in clienti:
                self._indicizza_cliente(c)
        if fascicoli:
            for f in fascicoli:
                self._indicizza_fascicolo(f)
        if appuntamenti:
            for a in appuntamenti:
                self._indicizza_appuntamento(a)
        if scadenze:
            for s in scadenze:
                self._indicizza_scadenza(s)
        if documenti_ocr:
            for id_fasc, id_doc, nome, testo, tipo_doc in documenti_ocr:
                self.indicizza_documento(id_fasc, id_doc, nome, testo, tipo_doc)

        with self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO meta_indice VALUES('ultimo_rebuild', ?)",
                (datetime.now().isoformat(),)
            )

    # ---- helper indicizzazione per tipo

    def _indicizza_cliente(self, c):
        """Indicizza un oggetto Cliente (o dict)."""
        if hasattr(c, 'to_dict'):
            d = c.to_dict()
        else:
            d = c
        titolo = d.get("nome_completo") or (
            f"{d.get('cognome','')} {d.get('nome','')}".strip()
            or d.get("ragione_sociale", "")
        )
        corpo_parts = [
            d.get("codice_fiscale", ""),
            d.get("partita_iva", ""),
            d.get("email", ""),
            d.get("telefono", ""),
            d.get("note", ""),
        ]
        indirizzo = d.get("indirizzo") or {}
        if isinstance(indirizzo, dict):
            corpo_parts.append(indirizzo.get("citta", ""))
            corpo_parts.append(indirizzo.get("indirizzo", ""))
        corpo = " ".join(p for p in corpo_parts if p)
        self.indicizza(
            tipo="cliente",
            entity_id=d["id"],
            titolo=titolo,
            corpo=corpo,
            meta={"tipo_cliente": d.get("tipo", ""), "stato": d.get("stato", "")},
        )

    def _indicizza_fascicolo(self, f):
        if hasattr(f, 'to_dict'):
            d = f.to_dict()
        else:
            d = f
        titolo = f"{d.get('numero', '')} — {d.get('titolo', '')}"
        corpo_parts = [
            d.get("nome_cliente", ""),
            d.get("controparte", ""),
            d.get("tribunale", ""),
            d.get("giudice", ""),
            d.get("oggetto", ""),
            d.get("note", ""),
            d.get("numero_rg", ""),
            d.get("avvocato_referente", ""),
        ]
        corpo = " ".join(p for p in corpo_parts if p)
        self.indicizza(
            tipo="fascicolo",
            entity_id=d["id"],
            titolo=titolo,
            corpo=corpo,
            meta={
                "tipo": d.get("tipo", ""),
                "stato": d.get("stato", ""),
                "numero": d.get("numero", ""),
            },
        )

    def _indicizza_appuntamento(self, a):
        if hasattr(a, 'to_dict'):
            d = a.to_dict()
        else:
            d = a
        titolo = d.get("titolo", "")
        corpo_parts = [
            d.get("descrizione", ""),
            d.get("luogo", ""),
            d.get("partecipanti", ""),
            d.get("note", ""),
        ]
        corpo = " ".join(p for p in corpo_parts if p)
        self.indicizza(
            tipo="appuntamento",
            entity_id=d["id"],
            titolo=titolo,
            corpo=corpo,
            meta={
                "tipo": d.get("tipo", ""),
                "data_ora": d.get("data_ora", ""),
                "stato": d.get("stato", ""),
            },
        )

    def _indicizza_scadenza(self, s):
        if hasattr(s, 'to_dict'):
            d = s.to_dict()
        else:
            d = s
        titolo = d.get("titolo", "")
        corpo = " ".join(filter(None, [
            d.get("descrizione", ""),
            d.get("note", ""),
            d.get("tipo", ""),
        ]))
        self.indicizza(
            tipo="scadenza",
            entity_id=d["id"],
            titolo=titolo,
            corpo=corpo,
            meta={
                "data_scadenza": d.get("data_scadenza", ""),
                "priorita": d.get("priorita", ""),
                "stato": d.get("stato", ""),
            },
        )

    # ---- ricerca

    def cerca(
        self,
        query: str,
        tipi: Optional[List[str]] = None,
        limit: int = 20,
    ) -> List[RisultatoRicerca]:
        """
        Esegue una ricerca full-text.

        Args:
            query: testo da cercare (supporta FTS5 syntax: AND, OR, NOT, prefix*)
            tipi: lista di tipi da includere (None = tutti)
            limit: max risultati
        Returns:
            Lista di RisultatoRicerca ordinata per rilevanza.
        """
        if not query or not query.strip():
            return []

        # Normalizza query: aggiungi * per prefix match sull'ultima parola
        q = query.strip()
        # Semplice escape per FTS5
        q_fts = self._escape_fts(q)

        tipo_filter = ""
        params: list = [q_fts]
        if tipi:
            placeholders = ",".join("?" * len(tipi))
            tipo_filter = f"AND tipo IN ({placeholders})"
            params.extend(tipi)
        params.append(limit)

        sql = f"""
            SELECT tipo, entity_id, titolo, meta,
                   snippet(documenti, 3, '<mark>', '</mark>', '…', 12) AS snip,
                   bm25(documenti) AS rank
            FROM documenti
            WHERE documenti MATCH ?
            {tipo_filter}
            ORDER BY rank
            LIMIT ?
        """
        try:
            rows = self._conn.execute(sql, params).fetchall()
        except sqlite3.OperationalError:
            # Query syntax error: tenta ricerca semplice senza FTS syntax
            q_simple = " ".join(w + "*" for w in q.split() if w)
            params[0] = q_simple
            try:
                rows = self._conn.execute(sql, params).fetchall()
            except sqlite3.OperationalError:
                return []

        risultati = []
        for row in rows:
            meta = json.loads(row["meta"] or "{}")
            r = RisultatoRicerca(
                tipo=row["tipo"],
                id=row["entity_id"],
                titolo=row["titolo"],
                sottotitolo=self._sottotitolo(row["tipo"], meta),
                url=self._url(row["tipo"], row["entity_id"]),
                icona=self._icona(row["tipo"]),
                rank=row["rank"],
                snippet=row["snip"] or "",
            )
            risultati.append(r)
        return risultati

    def cerca_globale(self, query: str, limit: int = 15) -> Dict[str, List[RisultatoRicerca]]:
        """Ricerca su tutti i tipi, raggruppa per tipo."""
        tutti = self.cerca(query, limit=limit)
        raggruppati: Dict[str, List[RisultatoRicerca]] = {}
        for r in tutti:
            raggruppati.setdefault(r.tipo, []).append(r)
        return raggruppati

    # ---- statistiche

    def statistiche(self) -> Dict[str, Any]:
        cur = self._conn.execute(
            "SELECT tipo, COUNT(*) as n FROM documenti GROUP BY tipo"
        )
        counts = {row["tipo"]: row["n"] for row in cur.fetchall()}
        meta = self._conn.execute(
            "SELECT valore FROM meta_indice WHERE chiave='ultimo_rebuild'"
        ).fetchone()
        return {
            "totale": sum(counts.values()),
            "per_tipo": counts,
            "ultimo_rebuild": meta["valore"] if meta else None,
        }

    def ottimizza(self):
        """Ottimizza l'indice FTS5 (merge segments)."""
        with self._conn:
            self._conn.execute("INSERT INTO documenti(documenti) VALUES('optimize')")

    # ---- helper privati

    @staticmethod
    def _escape_fts(q: str) -> str:
        """Costruisce una query FTS5 sicura con prefix match."""
        # Rimuovi caratteri speciali FTS5 e aggiungi * all'ultima parola
        words = [w.strip('"\'()') for w in q.split() if w.strip('"\'()')]
        if not words:
            return '""'
        # Prefix match sull'ultima parola per autocomplete
        result = " ".join(words[:-1] + [words[-1] + "*"])
        return result

    @staticmethod
    def _sottotitolo(tipo: str, meta: dict) -> str:
        if tipo == "fascicolo":
            stato = meta.get("stato", "")
            tp = meta.get("tipo", "").replace("_", " ")
            return f"{tp} — {stato}" if tp else stato
        if tipo == "cliente":
            return meta.get("tipo_cliente", "").replace("_", " ")
        if tipo == "appuntamento":
            data = meta.get("data_ora", "")[:10]
            return f"{meta.get('tipo','').replace('_',' ')} — {data}"
        if tipo == "scadenza":
            ds = meta.get("data_scadenza", "")
            p = meta.get("priorita", "")
            return f"{ds} — {p}" if ds else p
        if tipo == "documento":
            td = meta.get("tipo_doc", "").replace("_", " ")
            return f"Documento — {td}" if td else "Documento"
        return ""

    @staticmethod
    def _url(tipo: str, entity_id: str) -> str:
        if tipo == "documento":
            # entity_id = "id_fasc:id_doc"
            id_fasc = entity_id.split(":")[0]
            return f"/fascicoli/{id_fasc}"
        routes = {
            "fascicolo": f"/fascicoli/{entity_id}",
            "cliente": f"/clienti/{entity_id}",
            "appuntamento": f"/agenda/appuntamento/{entity_id}",
            "scadenza": f"/scadenziario/{entity_id}",
        }
        return routes.get(tipo, "/")

    @staticmethod
    def _icona(tipo: str) -> str:
        icone = {
            "fascicolo": "bi-folder2-open",
            "cliente": "bi-person",
            "appuntamento": "bi-calendar-event",
            "scadenza": "bi-alarm",
            "documento": "bi-file-text",
        }
        return icone.get(tipo, "bi-search")
