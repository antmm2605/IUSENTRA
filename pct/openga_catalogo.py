"""Catalogo OpenGA di soli metadati con provenienza e conteggi SQL dichiarati.

Separato dalle massime: non restituisce principi, motivazioni o testo delle decisioni.
"""

from __future__ import annotations

import csv
import hashlib
import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from pct.sync import FileLock
from scripts.precedenti.openga import categoria, ripulisci

VERSIONE = "openga-metadati-v1"
RICERCA_UFFICIALE = "https://www.giustizia-amministrativa.it/dcsnprr"
CAMPI = (
    "CODICE_SEDE",
    "NOME_SEDE",
    "TIPO_PROVVEDIMENTO",
    "NUMERO_PROVVEDIMENTO",
    "ANNO_PUBBLICAZIONE",
    "NUMERO_RICORSO",
    "OGGETTO_RICORSO",
    "ESITO_PROVVEDIMENTO",
    "FLG_DEFINISCE",
)


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _clean(value):
    return " ".join(str(value or "").split())


class CatalogoOpenGA:
    def __init__(self, db):
        self.path = Path(db)

    def _connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        c = sqlite3.connect(self.path)
        c.row_factory = sqlite3.Row
        c.executescript("""
          CREATE TABLE IF NOT EXISTS risorse (
            id TEXT PRIMARY KEY, dataset_id TEXT NOT NULL, url TEXT NOT NULL,
            revisione TEXT NOT NULL, sha256 TEXT NOT NULL, licenza TEXT NOT NULL,
            aggiornamento_fonte TEXT, importato_utc TEXT NOT NULL,
            righe_file INTEGER NOT NULL, righe_valide INTEGER NOT NULL);
          CREATE TABLE IF NOT EXISTS righe (
            id INTEGER PRIMARY KEY AUTOINCREMENT, risorsa TEXT NOT NULL,
            revisione TEXT NOT NULL, row_sha TEXT NOT NULL, decisione TEXT NOT NULL,
            relazione TEXT NOT NULL, sede TEXT NOT NULL, nome_sede TEXT NOT NULL,
            tipo TEXT NOT NULL, numero TEXT NOT NULL, anno INTEGER NOT NULL,
            ricorso TEXT NOT NULL, oggetto TEXT NOT NULL, esito_originale TEXT NOT NULL,
            categoria TEXT NOT NULL, definisce TEXT NOT NULL,
            UNIQUE(risorsa,revisione,row_sha));
          CREATE INDEX IF NOT EXISTS righe_revisione ON righe(risorsa,revisione);
          CREATE VIEW IF NOT EXISTS attive AS SELECT r.* FROM righe r JOIN risorse s
            ON s.id=r.risorsa AND s.revisione=r.revisione;
          CREATE VIRTUAL TABLE IF NOT EXISTS oggetti_fts USING fts5(oggetto,nome_sede,content='righe',content_rowid='id');
          CREATE TRIGGER IF NOT EXISTS righe_ai AFTER INSERT ON righe BEGIN
            INSERT INTO oggetti_fts(rowid,oggetto,nome_sede) VALUES(new.id,new.oggetto,new.nome_sede);
          END;
          CREATE VIEW IF NOT EXISTS normative_chunks AS SELECT id,id AS document_id,
            id AS article_id,oggetto AS chunk_text FROM attive WHERE oggetto!='';
          CREATE VIEW IF NOT EXISTS normative_documents AS SELECT id,
            nome_sede || ' ' || tipo || ' ' || numero || '/' || anno AS titolo,
            '' AS numero,'' AS data_atto FROM attive;
          CREATE VIEW IF NOT EXISTS normative_articles AS SELECT id,'' AS article_number,
            'Oggetto del ricorso, soli metadati' AS article_title FROM attive;

        """)
        return c

    def importa(self, csv_path, manifest):
        path = Path(csv_path)
        resource = manifest["resource"]
        url = str(resource.get("url") or "")
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.hostname != "openga.giustizia-amministrativa.it":
            raise ValueError("Risorsa OpenGA non ufficiale")
        license_id = resource.get("license_id")
        if license_id != "cc-by-04":
            raise ValueError("Licenza della singola risorsa non verificata")
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if digest != manifest.get("download_sha256"):
            raise ValueError("Impronta del file diversa dalla risorsa acquisita")
        rid = str(resource["id"])
        revision = digest + ":" + VERSIONE
        now = datetime.now(timezone.utc).isoformat()
        with FileLock(str(self.path)), closing(self._connect()) as c:
            current = c.execute("SELECT * FROM risorse WHERE id=?", (rid,)).fetchone()
            if current and current["revisione"] == revision:
                return {
                    "stato": "invariata",
                    "righe_file": current["righe_file"],
                    "righe_valide": current["righe_valide"],
                    "nuove_righe": 0,
                }
            backup = None
            if current:
                backup = str(self.path) + "." + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f") + ".bak"
                with sqlite3.connect(backup) as b:
                    c.backup(b)
            count = valid = 0
            with path.open(encoding="utf-8-sig", newline="") as stream, c:
                reader = csv.DictReader(stream)
                if not set(CAMPI).issubset(reader.fieldnames or []):
                    raise ValueError("CSV privo di campi obbligatori")
                for raw in reader:
                    count += 1
                    row = {key: _clean(raw.get(key)) for key in CAMPI}
                    if not all(row[k] for k in ("CODICE_SEDE", "TIPO_PROVVEDIMENTO", "NUMERO_PROVVEDIMENTO")):
                        continue
                    if not row["ANNO_PUBBLICAZIONE"].isdigit():
                        continue
                    year = int(row["ANNO_PUBBLICAZIONE"])
                    if not 1900 <= year <= 2100:
                        continue
                    decision = "|".join(
                        row[k]
                        for k in ("CODICE_SEDE", "TIPO_PROVVEDIMENTO", "ANNO_PUBBLICAZIONE", "NUMERO_PROVVEDIMENTO")
                    )
                    relation = decision + "|" + (row["NUMERO_RICORSO"] or "[ricorso non indicato]")
                    raw_sha = _sha(json.dumps(raw, sort_keys=True, ensure_ascii=False).encode())
                    c.execute(
                        """INSERT OR IGNORE INTO righe
                      (risorsa,revisione,row_sha,decisione,relazione,sede,nome_sede,tipo,
                       numero,anno,ricorso,oggetto,esito_originale,categoria,definisce)
                      VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (
                            rid,
                            revision,
                            raw_sha,
                            decision,
                            relation,
                            row["CODICE_SEDE"],
                            row["NOME_SEDE"],
                            row["TIPO_PROVVEDIMENTO"],
                            row["NUMERO_PROVVEDIMENTO"],
                            year,
                            row["NUMERO_RICORSO"],
                            ripulisci(row["OGGETTO_RICORSO"]),
                            row["ESITO_PROVVEDIMENTO"],
                            categoria(row["ESITO_PROVVEDIMENTO"]) if row["ESITO_PROVVEDIMENTO"] else "mancante",
                            row["FLG_DEFINISCE"],
                        ),
                    )
                    valid += 1
                if not count or not valid:
                    raise ValueError("Risorsa vuota o senza righe valide: aggiornamento non applicato")
                c.execute(
                    """INSERT INTO risorse VALUES(?,?,?,?,?,?,?,?,?,?)
                  ON CONFLICT(id) DO UPDATE SET dataset_id=excluded.dataset_id,url=excluded.url,
                  revisione=excluded.revisione,sha256=excluded.sha256,licenza=excluded.licenza,
                  aggiornamento_fonte=excluded.aggiornamento_fonte,importato_utc=excluded.importato_utc,
                  righe_file=excluded.righe_file,righe_valide=excluded.righe_valide""",
                    (
                        rid,
                        manifest["package_id"],
                        url,
                        revision,
                        digest,
                        license_id,
                        resource.get("last_modified"),
                        now,
                        count,
                        valid,
                    ),
                )
            return {
                "stato": "importata",
                "righe_file": count,
                "righe_valide": valid,
                "righe_scartate": count - valid,
                "backup": backup,
                "solo_metadati": True,
            }

    def riepilogo(self, *, sede="", dal=1900, al=2100):
        """Popolazione SQL completa, mai percentuali sui soli vicini semantici top-k."""
        if not self.path.is_file():
            raise ValueError("Catalogo OpenGA assente: nessuna copertura dimostrata")
        if int(dal) > int(al):
            raise ValueError("Intervallo temporale non valido")
        uri = self.path.resolve().as_uri() + "?mode=ro"
        with closing(sqlite3.connect(uri, uri=True)) as c:
            where = "anno BETWEEN ? AND ?"
            params = [int(dal), int(al)]
            if sede:
                where += " AND sede=?"
                params.append(sede)
            total = c.execute(
                "SELECT count(*),count(DISTINCT decisione),min(anno),max(anno) FROM attive WHERE " + where, params
            ).fetchone()
            sql = (
                """SELECT CASE WHEN count(DISTINCT upper(esito_originale))>1 THEN 'esiti multipli da verificare'
                     ELSE max(categoria) END AS categoria,relazione
                     FROM attive WHERE """
                + where
                + """ AND definisce='D' GROUP BY relazione"""
            )
            rows = c.execute("SELECT categoria,count(*) FROM (" + sql + ") GROUP BY categoria", params).fetchall()
            counts = {r[0]: r[1] for r in rows}
            denominator = sum(counts.values())
            provenance = [
                {
                    "resource_id": row[0],
                    "url": row[1],
                    "sha256": row[2],
                    "licenza": row[3],
                    "aggiornamento_fonte": row[4],
                }
                for row in c.execute(
                    "SELECT id,url,sha256,licenza,aggiornamento_fonte FROM risorse WHERE id IN (SELECT risorsa FROM attive WHERE "
                    + where
                    + ")",
                    params,
                )
            ]
            return {
                "evidence_scope": "metadata_only",
                "sede": sede or "tutte le sedi importate",
                "dal": dal,
                "al": al,
                "anni_presenti": [total[2], total[3]],
                "risorse": provenance,
                "righe_attive": total[0],
                "provvedimenti_distinti": total[1],
                "denominatore_relazioni_definite": denominator,
                "esiti_per_relazione_definita": counts,
                "percentuali_su_relazioni_definite": {k: round(v * 100 / denominator, 2) for k, v in counts.items()}
                if denominator
                else {},
                "ricerca_ufficiale": RICERCA_UFFICIALE,
                "limite": "Solo dati importati; relazioni provvedimento-ricorso, non probabilita di successo. Nessuna motivazione o principio disponibile.",
            }

    def costruisci_indice(self, *, embedder=None):
        """Indice distinto dei soli oggetti: nessuna massima e nessuna attivazione."""
        from lex.ricerca_giuridica.embedding import OllamaEmbedder
        from lex.ricerca_giuridica.indice_vettoriale import costruisci_indice

        folder = self.path.with_name(self.path.name + ".vettori-oggetti")
        folder.mkdir(parents=True, exist_ok=True)
        with FileLock(str(folder / "costruzione")):
            report = folder / "scope.json"
            temp = report.with_suffix(".tmp")
            state = {"scope": "metadata_only", "catalogo": str(self.path.resolve()), "completo": False}
            temp.write_text(json.dumps(state))
            temp.replace(report)
            with closing(sqlite3.connect(self.path.resolve().as_uri() + "?mode=ro", uri=True)) as c:
                result = costruisci_indice(c, folder, embedder or OllamaEmbedder())
            state.update(completo=not result.interrotto_al_massimo, esito=result.to_dict())
            temp.write_text(json.dumps(state, indent=2))
            temp.replace(report)
            return state

    def cerca(self, q, *, sede="", dal=1900, al=2100, limit=20, semantica=False, embedder=None, canale="ibrido"):
        """Schede strutturate metadata_only; mai percentuali da un insieme top-k."""
        from pct.giurisprudenza_corpus import _fts_or_query
        from pct.giurisprudenza_semantica import fondi

        if canale not in {"ibrido", "vettoriale"}:
            raise ValueError("Canale di ricerca non valido")
        if canale == "vettoriale" and not semantica:
            raise ValueError("Il canale vettoriale richiede semantica=True")
        if not self.path.is_file():
            raise ValueError("Catalogo OpenGA assente")
        limit = min(100, max(1, int(limit)))
        query = _clean(q)
        if not query:
            return []
        where = "r.anno BETWEEN ? AND ?"
        filters = [int(dal), int(al)]
        if sede:
            if isinstance(sede, (list, tuple)):
                where += " AND r.sede IN (" + ",".join("?" for _ in sede) + ")"
                filters.extend(sede)
            else:
                where += " AND r.sede=?"
                filters.append(sede)
        with closing(sqlite3.connect(self.path.resolve().as_uri() + "?mode=ro", uri=True)) as c:
            c.row_factory = sqlite3.Row
            lexical = c.execute(
                """SELECT r.*,bm25(oggetti_fts) AS score FROM oggetti_fts
              JOIN attive r ON r.id=oggetti_fts.rowid WHERE oggetti_fts MATCH ? AND """
                + where
                + " ORDER BY score LIMIT 200",
                [_fts_or_query(query), *filters],
            ).fetchall()
            if canale == "vettoriale":
                lexical = []
            records = {int(r["id"]): dict(r) for r in lexical}
            vectors = []
            if semantica:
                from lex.ricerca_giuridica.embedding import EmbedderDomande, OllamaEmbedder
                from lex.ricerca_giuridica.indice_vettoriale import IndiceVettoriale

                folder = self.path.with_name(self.path.name + ".vettori-oggetti")
                report = folder / "scope.json"
                if canale == "vettoriale" and not report.is_file():
                    raise ValueError("Indice semantico assente")
                if report.is_file():
                    stamp = report.read_bytes()
                    scope = json.loads(stamp)
                    if scope.get("scope") != "metadata_only" or scope.get("catalogo") != str(self.path.resolve()):
                        raise ValueError("Indice oggetti di un altro archivio o perimetro")
                    if canale == "vettoriale" and not scope.get("completo"):
                        raise ValueError("Indice semantico non completo")
                    if scope.get("completo"):
                        index = IndiceVettoriale.apri(folder)
                        if index is None:
                            raise ValueError("Indice oggetti assente o non leggibile")
                        engine = embedder or OllamaEmbedder(timeout=4, tentativi=1)
                        ok, reason = index.verifica_modello(engine.modello, engine.versione())
                        if not ok:
                            raise ValueError(reason)
                        # Il filtro deve precedere il top-k: filtrare solo dopo
                        # elimina vicini pertinenti fuori dai primi 500 globali.
                        allowed = None
                        if sede or int(dal) != 1900 or int(al) != 2100:
                            allowed = {int(row[0]) for row in c.execute("SELECT r.id FROM attive r WHERE " + where, filters)}
                        for row_id, score in index.cerca(EmbedderDomande(engine).vettore(query), k=500, ids_ammessi=allowed):
                            row = c.execute(
                                "SELECT r.* FROM attive r WHERE r.id=? AND " + where, [row_id, *filters]
                            ).fetchone()
                            if row is not None:
                                records[int(row_id)] = dict(row)
                                vectors.append(int(row_id))
                        if stamp != report.read_bytes():
                            if canale == "vettoriale":
                                raise ValueError("Indice modificato durante la ricerca")
                            vectors = []
            lexical_ids = [int(r["id"]) for r in lexical]
            ordered = vectors if canale == "vettoriale" else fondi(lexical_ids, vectors, limit=400)
            # Un oggetto semanticamente molto vicino non deve sparire solo perche
            # altri oggetti ricevono due punteggi deboli, uno da ciascun canale.
            quota = limit // 2
            selected = set(lexical_ids[:quota] + vectors[:quota])
            for row_id in ordered:
                if len(selected) >= limit:
                    break
                selected.add(row_id)
            if canale != "vettoriale":
                ordered = [row_id for row_id in ordered if row_id in selected]
            seen = set()
            results = []
            for row_id in ordered:
                row = records[row_id]
                key = (row["relazione"], row["esito_originale"], row["oggetto"])
                if key in seen:
                    continue
                seen.add(key)
                resource = c.execute("SELECT url,sha256 FROM risorse WHERE id=?", (row["risorsa"],)).fetchone()
                results.append(
                    {
                        "evidence_scope": "metadata_only",
                        "stato_verifica": "parzialmente_verificata",
                        "fonte_codice": "openga",
                        "fonte_ufficiale_confermata": True,
                        "organo_giudicante": row["nome_sede"],
                        "numero_sentenza": row["numero"],
                        "tipo_provvedimento": row["tipo"],
                        "decisione_id": row["decisione"],
                        "relazione_id": row["relazione"],
                        "anno_sentenza": row["anno"],
                        "numero_ricorso": row["ricorso"],
                        "oggetto": row["oggetto"],
                        "esito": row["esito_originale"],
                        "testo_integrale_presente": False,
                        "massima_ufficiale": "",
                        "principio_sintetico": "",
                        "url_pagina_ufficiale": resource[0],
                        "resource_id": row["risorsa"],
                        "resource_sha256": resource[1],
                        "official_search_url": RICERCA_UFFICIALE,
                        "official_search_is_document": False,
                    }
                )
                if len(results) >= limit:
                    break
            return results

    def cerca_canali(self, q, *, sede="", dal=1900, al=2100, limit=10, embedder=None):
        """Conserva la lista lessicale e restituisce suggerimenti semantici separati.

        Il limite vale per ciascun canale. Non equivale a un ranking unico top-k:
        nessun risultato lessicale viene espulso per far posto ai vettori.
        Un errore semantico resta esplicito e non elimina i risultati lessicali.
        """
        limit = min(100, max(1, int(limit)))
        lexical = self.cerca(q, sede=sede, dal=dal, al=al, limit=limit, semantica=False)
        folder = self.path.with_name(self.path.name + ".vettori-oggetti")
        error = None
        semantic = []
        variants = []
        ambiti = []
        try:
            scope = json.loads((folder / "scope.json").read_text())
            if not scope.get("completo"):
                raise ValueError("Indice semantico non completo")
            candidates = self.cerca(
                q,
                sede=sede,
                dal=dal,
                al=al,
                limit=min(100, limit * 2),
                semantica=True,
                embedder=embedder,
                canale="vettoriale",
            )

            def identity(row):
                return (row["relazione_id"], row["oggetto"], row["esito"])

            from pct.openga_query import sedi_menzionate, varianti_query
            from pct.giurisprudenza_semantica import fondi

            with closing(sqlite3.connect(self.path.resolve().as_uri() + "?mode=ro", uri=True)) as connection:
                sedi = [r[0] for r in connection.execute("SELECT DISTINCT nome_sede FROM attive")]
            variants = varianti_query(q, sedi)
            by_id = {identity(row): row for row in candidates}
            ordered = [identity(row) for row in candidates]
            for variant in variants:
                extra = self.cerca(
                    variant["query"], sede=sede, dal=dal, al=al, limit=min(100, limit * 2), semantica=False
                )
                by_id.update({identity(row): row for row in extra})
                ordered = fondi(ordered, [identity(row) for row in extra], limit=100)
            # Il riferimento geografico guida ulteriori candidati, senza filtrare
            # la lista originale: il tribunale citato puo essere quello del giudizio precedente.
            ambiti = [] if sede else sedi_menzionate(q, sedi)
            contestuali = []
            for ambito in ambiti:
                extra = self.cerca(
                    variants[-1]["query"] if variants else q,
                    sede=ambito,
                    dal=dal,
                    al=al,
                    limit=min(100, limit * 2),
                    semantica=False,
                )
                by_id.update({identity(row): row for row in extra})
                contestuali.extend(identity(row) for row in extra)
            if contestuali:
                ordered = fondi(ordered, contestuali, limit=100)
            candidates = [by_id[key] for key in ordered]
            present = {identity(row) for row in lexical}
            for row in candidates:
                key = identity(row)
                if key not in present:
                    semantic.append(row)
                    present.add(key)
                if len(semantic) >= limit:
                    break
        except (OSError, ValueError, RuntimeError) as exc:
            error = str(exc)
        return {
            "modalita": "canali_separati_v1",
            "limite_per_canale": limit,
            "lessicali": lexical,
            "semantici_aggiuntivi": semantic,
            "errore_semantico": error,
            "evidence_scope": "metadata_only",
            "varianti_query": variants,
            "ambiti_geografici_suggeriti": ambiti,
            "criterio_suggerimenti": "vettori_e_contesto_lessicale" if variants or ambiti else "vettori",
        }

    def cerca_fusa(self, q, *, sede="", dal=1900, al=2100, limit=10, embedder=None, traccia=False, riformulatore=None, reranker=None):
        """Lista unica sperimentale: filtri espliciti prima del recupero e RRF.

        Il catalogo e il modello restano quelli originali; nessuna costruzione.
        Numero atteso, split del banco e anno non richiesto non sono input.
        """
        import re
        from pct.openga_query import sede_richiesta, varianti_query, query_sostanziale, sedi_menzionate

        limit = min(100, max(1, int(limit)))
        with closing(sqlite3.connect(self.path.resolve().as_uri() + "?mode=ro", uri=True)) as c:
            sedi = dict(c.execute("SELECT DISTINCT sede,nome_sede FROM attive"))
        requested = [] if sede else sede_richiesta(q, sedi)
        scope = sede or tuple(requested)
        lexical = self.cerca(q, sede=scope, dal=dal, al=al, limit=100)
        channels = [(2.0, lexical)]
        error = None
        variants = varianti_query(q, list(sedi.values()))
        compact = query_sostanziale(q, list(sedi.values()))
        if compact and compact not in {str(q), *[v["query"] for v in variants]}:
            variants.append({"query": compact, "motivi": ["compressione_senza_nuove_parole"]})
        rewrite_info = None
        if riformulatore is not None:
            try:
                rewrite_info = riformulatore(str(q))
                from pct.openga_riformulazione import valida
                for text in list(rewrite_info.get("queries") or [])[:2]:
                    if valida(str(q), text) and text not in {str(q), *[v["query"] for v in variants]}:
                        variants.append({"query": text, "motivi": ["riformulazione_locale_validata"]})
            except Exception as exc:
                rewrite_info = {"errore": str(exc), "queries": []}
        try:
            vectors = self.cerca(q, sede=scope, dal=dal, al=al, limit=100,
                                 semantica=True, canale="vettoriale", embedder=embedder)
            channels.append((1.0, vectors))
            for variant in variants:
                extra = self.cerca(variant["query"], sede=scope, dal=dal, al=al,
                                   limit=100, semantica=True, canale="vettoriale", embedder=embedder)
                channels.append((1.0, extra))
            # Le varianti verranno fuse con massimo per canale, non sommate:
            # molte parafrasi non aumentano artificialmente il consenso.
        except (OSError, ValueError, RuntimeError) as exc:
            error = str(exc)
        alt_lexical = []
        for variant in variants:
            alt_lexical.append(self.cerca(variant["query"], sede=scope, dal=dal, al=al, limit=100))
        contextual = []
        if not scope:
            names = sedi_menzionate(q, list(sedi.values()))
            contextual = [code for code, title in sedi.items() if title in names]
            if contextual:
                alt_lexical.append(self.cerca(q, sede=tuple(contextual), dal=dal, al=al, limit=100))
                if not error:
                    try:
                        channels.append((1.0, self.cerca(q, sede=tuple(contextual), dal=dal, al=al,
                                          limit=100, semantica=True, canale="vettoriale", embedder=embedder)))
                    except (OSError, ValueError, RuntimeError) as exc:
                        error = str(exc)
        scores, records, order, vector_scores, alternate_scores = {}, {}, {}, {}, {}
        for channel_no, (weight, rows) in enumerate(channels):
            for rank, row in enumerate(rows, 1):
                key = (row["relazione_id"], row["oggetto"], row["esito"])
                records[key] = row
                order.setdefault(key, len(order))
                if channel_no == 0:
                    scores[key] = weight / (60 + rank)
                else:
                    vector_scores[key] = max(vector_scores.get(key, 0.0), 1.0 / (60 + rank))
        for rows in alt_lexical:
            for rank, row in enumerate(rows, 1):
                key = (row["relazione_id"], row["oggetto"], row["esito"])
                records[key] = row
                order.setdefault(key, len(order))
                alternate_scores[key] = max(alternate_scores.get(key, 0.0), 1.0 / (60 + rank))
        for key in records:
            scores[key] = scores.get(key, 0.0) + vector_scores.get(key, 0.0) + alternate_scores.get(key, 0.0)
        # Ancore esplicite nel quesito: il riferimento a un procedimento/data
        # non puo essere sostituito da un altro solo semanticamente simile.
        numbers = {str(int(n)) for n in re.findall(r"\b\d+\b", str(q))}
        if numbers and not error:
            for key, row in records.items():
                source = {str(int(n)) for n in re.findall(r"\b\d+\b", row["oggetto"])}
                scores[key] += .02 * len(numbers & source) / len(numbers)
        codes = {code.lower() for code in re.findall(r"\b[a-zA-Z]++[0-9]++[a-zA-Z0-9]*+\b", str(q))}
        if codes and not error:
            for key, row in records.items():
                found = {code.lower() for code in re.findall(r"\b[a-zA-Z]++[0-9]++[a-zA-Z0-9]*+\b", row["oggetto"])}
                scores[key] += .04 * len(codes & found) / len(codes)
        ranked = [records[key] for key in sorted(scores, key=lambda key: (-scores[key], order[key]))]
        # Presidio generale dei primi tre lessicali, non dei casi attesi.
        protected = lexical[:min(3, limit)]
        keys = {(row["relazione_id"], row["oggetto"], row["esito"]) for row in protected}
        ranked = protected + [row for row in ranked if (row["relazione_id"], row["oggetto"], row["esito"]) not in keys]
        rerank_info = None
        rerank_error = None
        if error:
            ranked = list(lexical)
        if reranker is not None and not error:
            try:
                import math
                pool = ranked[:100]
                values = list(reranker(str(q), pool))
                if len(values) != len(pool) or not all(math.isfinite(float(v)) for v in values):
                    raise ValueError("Punteggi del confronto non validi")
                ordered = [pool[i] for i in sorted(range(len(pool)), key=lambda i: (-float(values[i]), i))]
                tail = ranked[len(pool):]
                ranked = protected + [row for row in ordered if (row["relazione_id"], row["oggetto"], row["esito"]) not in keys]
                from pct.openga_reranker import diversifica_descrizioni
                ranked = diversifica_descrizioni(str(q), ranked, len(protected)) + tail
                rerank_info = {"statistiche": getattr(reranker, "last_stats", {}), "punteggi": values}
            except Exception as exc:
                rerank_error = str(exc)
                ranked = list(lexical)
        return {"modalita": "lista_unica_dismax_sede_v2", "risultati": ranked[:limit],
                "errore_semantico": error, "sedi_esplicite": requested, "sedi_contestuali_non_vincolanti": contextual,
                "varianti_query": variants, "riformulazione": rewrite_info, "rerank": rerank_info, "errore_reranker": rerank_error, "evidence_scope": "metadata_only",
                **({"traccia_canali": [{"peso": weight, "righe": rows} for weight, rows in channels], "traccia_alt_lessicali": alt_lexical, "candidati_ordinati": ranked} if traccia else {})}
