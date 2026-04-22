from __future__ import annotations

import re
import sqlite3
import uuid
from pathlib import Path
from typing import Any

SCHEMA_GIURISPRUDENZA_CORPUS = (
    Path(__file__).resolve().parent / "sql" / "20260414_giurisprudenza_corpus.sql"
)


def _clean_spaces(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _normalize_url(value: Any) -> str:
    text = _clean_spaces(value)
    return text if text.startswith(("http://", "https://")) else ""


def _bool_int(value: Any) -> int:
    return 1 if bool(value) else 0


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _derive_uuid(payload: dict[str, Any]) -> str:
    ecli = _clean_spaces(payload.get("ecli"))
    if ecli:
        return ecli
    provided = _clean_spaces(payload.get("uuid_interno"))
    if provided:
        return provided
    parts = [
        _clean_spaces(payload.get("fonte_codice")),
        _clean_spaces(payload.get("organo_giudicante")),
        _clean_spaces(payload.get("sezione")),
        _clean_spaces(payload.get("numero_sentenza")),
        _clean_spaces(payload.get("anno_sentenza")),
        _clean_spaces(payload.get("data_deposito")),
        _clean_spaces(payload.get("titolo")),
    ]
    stable = "|".join(part for part in parts if part)
    return stable or uuid.uuid4().hex


def _escape_fts_query(value: Any) -> str:
    sanitized = re.sub(r"[^0-9A-Za-zÀ-ÿ]+", " ", _clean_spaces(value))
    words = [token.strip() for token in sanitized.split()]
    cleaned = [token for token in words if token]
    if not cleaned:
        return '""'
    if len(cleaned) == 1:
        return f'"{cleaned[0]}"'
    return " ".join(cleaned[:-1] + [f"{cleaned[-1]}*"])


def derive_corpus_db_path(storage_path: str) -> str:
    target = Path(storage_path)
    stem = target.stem or "giurisprudenza"
    return str(target.with_name(f"{stem}_corpus.db"))


class GestioneCorpusGiurisprudenza:
    def __init__(self, db_path: str, schema_path: Path | None = None):
        self.db_path = str(db_path)
        self.schema_path = Path(schema_path or SCHEMA_GIURISPRUDENZA_CORPUS)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        return conn

    def _ensure_schema(self) -> None:
        schema_sql = self.schema_path.read_text(encoding="utf-8")
        with self._connect() as conn:
            conn.executescript(schema_sql)
            conn.commit()

    def storage_stats(self) -> dict[str, Any]:
        tables = (
            "fonti_giurisprudenza",
            "sentenze",
            "documenti_sentenza",
            "massime",
            "principi_diritto",
            "norme",
            "sentenza_norme",
            "sentenza_precedenti",
            "verifiche_fonti",
        )
        counts: dict[str, int] = {}
        with self._connect() as conn:
            for table_name in tables:
                counts[table_name] = int(
                    conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
                )
        counts["db_path"] = self.db_path
        return counts

    def _upsert_fonte(self, conn: sqlite3.Connection, payload: dict[str, Any]) -> int:
        codice = _clean_spaces(payload.get("codice") or payload.get("fonte_codice") or "manuale_interno")
        current = conn.execute(
            "SELECT id FROM fonti_giurisprudenza WHERE codice = ?",
            (codice,),
        ).fetchone()
        values = (
            codice,
            _clean_spaces(payload.get("nome") or payload.get("fonte_nome") or codice.replace("_", " ").title()),
            _clean_spaces(payload.get("tipo_fonte") or "altra"),
            _clean_spaces(payload.get("ente")),
            _normalize_url(payload.get("url_home")),
            _normalize_url(payload.get("url_ricerca")),
            _normalize_url(payload.get("url_feed")),
            _clean_spaces(payload.get("paese") or "IT"),
            _bool_int(payload.get("attiva", True)),
            _clean_spaces(payload.get("note")),
        )
        if current:
            conn.execute(
                """
                UPDATE fonti_giurisprudenza
                SET nome = ?, tipo_fonte = ?, ente = ?, url_home = ?, url_ricerca = ?,
                    url_feed = ?, paese = ?, attiva = ?, note = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                values[1:] + (int(current["id"]),),
            )
            return int(current["id"])
        cursor = conn.execute(
            """
            INSERT INTO fonti_giurisprudenza (
                codice, nome, tipo_fonte, ente, url_home, url_ricerca, url_feed,
                paese, attiva, note
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            values,
        )
        return int(cursor.lastrowid)

    def salva_sentenza(self, payload: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(payload or {})
        normalized["uuid_interno"] = _derive_uuid(normalized)
        fonte_payload = dict(normalized.get("fonte") or {})
        with self._connect() as conn:
            fonte_id = self._upsert_fonte(
                conn,
                {
                    "codice": fonte_payload.get("codice") or normalized.get("fonte_codice"),
                    "nome": fonte_payload.get("nome") or normalized.get("fonte_nome"),
                    "tipo_fonte": fonte_payload.get("tipo_fonte") or normalized.get("tipo_fonte") or "altra",
                    "ente": fonte_payload.get("ente") or normalized.get("organo_giudicante"),
                    "url_home": fonte_payload.get("url_home") or normalized.get("url_pagina_ufficiale"),
                    "url_ricerca": fonte_payload.get("url_ricerca"),
                    "url_feed": fonte_payload.get("url_feed"),
                    "paese": fonte_payload.get("paese") or "IT",
                    "attiva": fonte_payload.get("attiva", True),
                    "note": fonte_payload.get("note"),
                },
            )
            ecli = _clean_spaces(normalized.get("ecli")) or None
            current = conn.execute(
                "SELECT id FROM sentenze WHERE uuid_interno = ?",
                (normalized["uuid_interno"],),
            ).fetchone()
            if not current and ecli:
                current = conn.execute(
                    "SELECT id FROM sentenze WHERE ecli = ?",
                    (ecli,),
                ).fetchone()
            numero = _clean_spaces(normalized.get("numero_sentenza"))
            if not numero:
                numero = _clean_spaces(normalized.get("numero_provvedimento"))
            anno = _to_int(normalized.get("anno_sentenza"))
            if not anno and "/" in numero:
                tail = numero.split("/")[-1].strip()
                anno = _to_int(tail if len(tail) == 4 else f"20{tail}", 0)
            base_values = (
                fonte_id,
                normalized["uuid_interno"],
                ecli,
                numero,
                anno or None,
                _clean_spaces(normalized.get("numero_ruolo")),
                _clean_spaces(normalized.get("numero_registro")),
                _clean_spaces(normalized.get("organo_giudicante")) or "Organo non indicato",
                _clean_spaces(normalized.get("sezione")),
                _clean_spaces(normalized.get("collegio")),
                _clean_spaces(normalized.get("relatore")),
                _clean_spaces(normalized.get("presidente")),
                _clean_spaces(normalized.get("data_decisione")),
                _clean_spaces(normalized.get("data_deposito")),
                _clean_spaces(normalized.get("data_pubblicazione")),
                _clean_spaces(normalized.get("area_diritto")),
                _clean_spaces(normalized.get("materia_principale")),
                _clean_spaces(normalized.get("sottomateria_principale")),
                _clean_spaces(normalized.get("rito")),
                _clean_spaces(normalized.get("grado_giudizio")),
                _clean_spaces(normalized.get("tipo_provvedimento") or "provvedimento"),
                _clean_spaces(normalized.get("titolo")),
                _clean_spaces(normalized.get("oggetto")),
                _clean_spaces(normalized.get("abstract")),
                _clean_spaces(normalized.get("principio_sintetico")),
                _clean_spaces(normalized.get("massima_ufficiale")),
                _clean_spaces(normalized.get("testo_integrale")),
                _clean_spaces(normalized.get("esito")),
                _clean_spaces(normalized.get("orientamento") or "non_classificato"),
                _to_int(normalized.get("rilevanza"), 0),
                _bool_int(normalized.get("precedente_guida")),
                _bool_int(normalized.get("sezioni_unite")),
                _bool_int(normalized.get("nomofilattica")),
                _clean_spaces(normalized.get("stato_verifica") or "da_verificare"),
                _bool_int(normalized.get("fonte_ufficiale_confermata")),
                _bool_int(normalized.get("pdf_ufficiale_presente")),
                _bool_int(normalized.get("testo_integrale_presente") or normalized.get("testo_integrale")),
                _normalize_url(normalized.get("url_pagina_ufficiale")),
                _normalize_url(normalized.get("url_pdf_ufficiale")),
                _normalize_url(normalized.get("url_html_ufficiale")),
                _clean_spaces(normalized.get("hash_contenuto")),
                _clean_spaces(normalized.get("hash_pdf")),
            )
            if current:
                sentenza_id = int(current["id"])
                conn.execute(
                    """
                    UPDATE sentenze
                    SET fonte_id = ?, uuid_interno = ?, ecli = ?, numero_sentenza = ?, anno_sentenza = ?,
                        numero_ruolo = ?, numero_registro = ?, organo_giudicante = ?, sezione = ?, collegio = ?,
                        relatore = ?, presidente = ?, data_decisione = ?, data_deposito = ?, data_pubblicazione = ?,
                        area_diritto = ?, materia_principale = ?, sottomateria_principale = ?, rito = ?, grado_giudizio = ?,
                        tipo_provvedimento = ?, titolo = ?, oggetto = ?, abstract = ?, principio_sintetico = ?,
                        massima_ufficiale = ?, testo_integrale = ?, esito = ?, orientamento = ?, rilevanza = ?,
                        precedente_guida = ?, sezioni_unite = ?, nomofilattica = ?, stato_verifica = ?,
                        fonte_ufficiale_confermata = ?, pdf_ufficiale_presente = ?, testo_integrale_presente = ?,
                        url_pagina_ufficiale = ?, url_pdf_ufficiale = ?, url_html_ufficiale = ?, hash_contenuto = ?,
                        hash_pdf = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    base_values + (sentenza_id,),
                )
            else:
                cursor = conn.execute(
                    """
                    INSERT INTO sentenze (
                        fonte_id, uuid_interno, ecli, numero_sentenza, anno_sentenza, numero_ruolo, numero_registro,
                        organo_giudicante, sezione, collegio, relatore, presidente, data_decisione, data_deposito,
                        data_pubblicazione, area_diritto, materia_principale, sottomateria_principale, rito,
                        grado_giudizio, tipo_provvedimento, titolo, oggetto, abstract, principio_sintetico,
                        massima_ufficiale, testo_integrale, esito, orientamento, rilevanza, precedente_guida,
                        sezioni_unite, nomofilattica, stato_verifica, fonte_ufficiale_confermata,
                        pdf_ufficiale_presente, testo_integrale_presente, url_pagina_ufficiale, url_pdf_ufficiale,
                        url_html_ufficiale, hash_contenuto, hash_pdf
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    base_values,
                )
                sentenza_id = int(cursor.lastrowid)
            self._replace_documenti(conn, sentenza_id, normalized.get("documenti") or [])
            self._replace_massime(conn, sentenza_id, normalized.get("massime") or [])
            self._replace_principi(conn, sentenza_id, normalized.get("principi_diritto") or [])
            self._replace_norme(conn, sentenza_id, normalized.get("norme") or [])
            self._replace_precedenti(conn, sentenza_id, normalized.get("precedenti") or [])
            self._replace_verifiche(conn, sentenza_id, fonte_id, normalized.get("verifiche") or [])
            conn.commit()
        return self.get_sentenza(sentenza_id) or {}

    def _replace_documenti(self, conn: sqlite3.Connection, sentenza_id: int, rows: list[Any]) -> None:
        conn.execute("DELETE FROM documenti_sentenza WHERE sentenza_id = ?", (sentenza_id,))
        for row in rows:
            item = {"titolo": row} if isinstance(row, str) else dict(row or {})
            conn.execute(
                """
                INSERT INTO documenti_sentenza (
                    sentenza_id, tipo_documento, titolo, nome_file, mime_type, url_origine, path_locale,
                    dimensione_bytes, sha256, testo_estratto, testo_estratto_chars, pages, lingua,
                    ufficiale, scaricato, valido
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    sentenza_id,
                    _clean_spaces(item.get("tipo_documento") or "altro"),
                    _clean_spaces(item.get("titolo")),
                    _clean_spaces(item.get("nome_file")),
                    _clean_spaces(item.get("mime_type")),
                    _normalize_url(item.get("url_origine")),
                    _clean_spaces(item.get("path_locale")),
                    _to_int(item.get("dimensione_bytes"), 0) or None,
                    _clean_spaces(item.get("sha256")),
                    _clean_spaces(item.get("testo_estratto")),
                    _to_int(item.get("testo_estratto_chars"), 0),
                    _to_int(item.get("pages"), 0) or None,
                    _clean_spaces(item.get("lingua") or "it"),
                    _bool_int(item.get("ufficiale", True)),
                    _bool_int(item.get("scaricato")),
                    _bool_int(item.get("valido", True)),
                ),
            )

    def _replace_massime(self, conn: sqlite3.Connection, sentenza_id: int, rows: list[Any]) -> None:
        conn.execute("DELETE FROM massime WHERE sentenza_id = ?", (sentenza_id,))
        for index, row in enumerate(rows):
            item = {"testo": row} if isinstance(row, str) else dict(row or {})
            testo = _clean_spaces(item.get("testo"))
            if not testo:
                continue
            conn.execute(
                """
                INSERT INTO massime (
                    sentenza_id, testo, sintetica, ufficiale, fonte_massima, numero_massima, anno_massima,
                    stato_verifica, principale
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    sentenza_id,
                    testo,
                    _clean_spaces(item.get("sintetica")),
                    _bool_int(item.get("ufficiale")),
                    _clean_spaces(item.get("fonte_massima")),
                    _clean_spaces(item.get("numero_massima")),
                    _to_int(item.get("anno_massima"), 0) or None,
                    _clean_spaces(item.get("stato_verifica") or "da_verificare"),
                    _bool_int(item.get("principale", index == 0)),
                ),
            )

    def _replace_principi(self, conn: sqlite3.Connection, sentenza_id: int, rows: list[Any]) -> None:
        conn.execute("DELETE FROM principi_diritto WHERE sentenza_id = ?", (sentenza_id,))
        for index, row in enumerate(rows):
            item = {"testo": row} if isinstance(row, str) else dict(row or {})
            testo = _clean_spaces(item.get("testo"))
            if not testo:
                continue
            conn.execute(
                """
                INSERT INTO principi_diritto (
                    sentenza_id, testo, formulazione_breve, ufficiale, estratto_da_testo,
                    livello_affidabilita, tema, sotto_tema, favorevole_tesi_attorea,
                    favorevole_tesi_convenuta, principale
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    sentenza_id,
                    testo,
                    _clean_spaces(item.get("formulazione_breve")),
                    _bool_int(item.get("ufficiale")),
                    _bool_int(item.get("estratto_da_testo")),
                    max(0, min(_to_int(item.get("livello_affidabilita"), 50), 100)),
                    _clean_spaces(item.get("tema")),
                    _clean_spaces(item.get("sotto_tema")),
                    _to_int(item.get("favorevole_tesi_attorea"), 0) if item.get("favorevole_tesi_attorea") is not None else None,
                    _to_int(item.get("favorevole_tesi_convenuta"), 0) if item.get("favorevole_tesi_convenuta") is not None else None,
                    _bool_int(item.get("principale", index == 0)),
                ),
            )

    def _replace_norme(self, conn: sqlite3.Connection, sentenza_id: int, rows: list[Any]) -> None:
        conn.execute("DELETE FROM sentenza_norme WHERE sentenza_id = ?", (sentenza_id,))
        for row in rows:
            item = {"testo_riferimento": row} if isinstance(row, str) else dict(row or {})
            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO norme (
                    tipo_norma, sigla, articolo, comma, lettera, rubrica, testo_riferimento,
                    ecli_normativo, url_ufficiale
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    _clean_spaces(item.get("tipo_norma") or "norma"),
                    _clean_spaces(item.get("sigla")),
                    _clean_spaces(item.get("articolo")),
                    _clean_spaces(item.get("comma")),
                    _clean_spaces(item.get("lettera")),
                    _clean_spaces(item.get("rubrica")),
                    _clean_spaces(item.get("testo_riferimento") or item.get("riferimento") or item.get("sigla")),
                    _clean_spaces(item.get("ecli_normativo")),
                    _normalize_url(item.get("url_ufficiale")),
                ),
            )
            if cursor.lastrowid:
                norma_id = int(cursor.lastrowid)
            else:
                norma_id = int(
                    conn.execute(
                        """
                        SELECT id FROM norme
                        WHERE COALESCE(tipo_norma, '') = ?
                          AND COALESCE(sigla, '') = ?
                          AND COALESCE(articolo, '') = ?
                          AND COALESCE(comma, '') = ?
                          AND COALESCE(lettera, '') = ?
                        """,
                        (
                            _clean_spaces(item.get("tipo_norma") or "norma"),
                            _clean_spaces(item.get("sigla")),
                            _clean_spaces(item.get("articolo")),
                            _clean_spaces(item.get("comma")),
                            _clean_spaces(item.get("lettera")),
                        ),
                    ).fetchone()["id"]
                )
            conn.execute(
                """
                INSERT INTO sentenza_norme (
                    sentenza_id, norma_id, tipo_richiamo, primaria, note
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    sentenza_id,
                    norma_id,
                    _clean_spaces(item.get("tipo_richiamo") or "citata"),
                    _bool_int(item.get("primaria")),
                    _clean_spaces(item.get("note")),
                ),
            )

    def _replace_precedenti(self, conn: sqlite3.Connection, sentenza_id: int, rows: list[Any]) -> None:
        conn.execute("DELETE FROM sentenza_precedenti WHERE sentenza_id = ?", (sentenza_id,))
        for row in rows:
            item = {"riferimento_testuale": row} if isinstance(row, str) else dict(row or {})
            riferimento = _clean_spaces(item.get("riferimento_testuale") or item.get("riferimento"))
            if not riferimento:
                continue
            conn.execute(
                """
                INSERT INTO sentenza_precedenti (
                    sentenza_id, riferimento_testuale, organo_giudicante, sezione, numero_sentenza,
                    anno_sentenza, data_sentenza, ecli, tipo_relazione, verificata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    sentenza_id,
                    riferimento,
                    _clean_spaces(item.get("organo_giudicante")),
                    _clean_spaces(item.get("sezione")),
                    _clean_spaces(item.get("numero_sentenza")),
                    _to_int(item.get("anno_sentenza"), 0) or None,
                    _clean_spaces(item.get("data_sentenza")),
                    _clean_spaces(item.get("ecli")),
                    _clean_spaces(item.get("tipo_relazione") or "citata"),
                    _bool_int(item.get("verificata")),
                ),
            )

    def _replace_verifiche(
        self,
        conn: sqlite3.Connection,
        sentenza_id: int,
        fonte_id: int,
        rows: list[Any],
    ) -> None:
        conn.execute("DELETE FROM verifiche_fonti WHERE sentenza_id = ?", (sentenza_id,))
        for row in rows:
            item = {"tipo_verifica": row} if isinstance(row, str) else dict(row or {})
            tipo = _clean_spaces(item.get("tipo_verifica"))
            if not tipo:
                continue
            conn.execute(
                """
                INSERT INTO verifiche_fonti (
                    sentenza_id, fonte_id, tipo_verifica, esito, dettaglio, checked_at, checked_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    sentenza_id,
                    fonte_id,
                    tipo,
                    _clean_spaces(item.get("esito") or "warning"),
                    _clean_spaces(item.get("dettaglio")),
                    _clean_spaces(item.get("checked_at")),
                    _clean_spaces(item.get("checked_by") or "system"),
                ),
            )

    def get_sentenza(self, sentenza_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT s.*, f.codice AS fonte_codice, f.nome AS fonte_nome, f.tipo_fonte, f.url_home
                FROM sentenze s
                JOIN fonti_giurisprudenza f ON f.id = s.fonte_id
                WHERE s.id = ?
                """,
                (int(sentenza_id),),
            ).fetchone()
            if not row:
                return None
            record = dict(row)
            record["documenti"] = [dict(item) for item in conn.execute(
                "SELECT * FROM documenti_sentenza WHERE sentenza_id = ? ORDER BY id",
                (int(sentenza_id),),
            ).fetchall()]
            record["massime"] = [dict(item) for item in conn.execute(
                "SELECT * FROM massime WHERE sentenza_id = ? ORDER BY principale DESC, id",
                (int(sentenza_id),),
            ).fetchall()]
            record["principi_diritto"] = [dict(item) for item in conn.execute(
                "SELECT * FROM principi_diritto WHERE sentenza_id = ? ORDER BY principale DESC, id",
                (int(sentenza_id),),
            ).fetchall()]
            record["norme"] = [dict(item) for item in conn.execute(
                """
                SELECT n.*, sn.tipo_richiamo, sn.primaria, sn.note
                FROM sentenza_norme sn
                JOIN norme n ON n.id = sn.norma_id
                WHERE sn.sentenza_id = ?
                ORDER BY sn.primaria DESC, sn.id
                """,
                (int(sentenza_id),),
            ).fetchall()]
            record["precedenti"] = [dict(item) for item in conn.execute(
                "SELECT * FROM sentenza_precedenti WHERE sentenza_id = ? ORDER BY id",
                (int(sentenza_id),),
            ).fetchall()]
            record["verifiche"] = [dict(item) for item in conn.execute(
                "SELECT * FROM verifiche_fonti WHERE sentenza_id = ? ORDER BY id",
                (int(sentenza_id),),
            ).fetchall()]
            return record

    def cerca_sentenze(
        self,
        *,
        q: str = "",
        organo_giudicante: str = "",
        materia_principale: str = "",
        stato_verifica: str = "",
        solo_con_pdf: bool = False,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        params: list[Any] = []
        if _clean_spaces(q):
            sql = """
                SELECT s.id, s.organo_giudicante, s.sezione, s.numero_sentenza, s.anno_sentenza,
                       s.data_deposito, s.titolo, s.massima_ufficiale, s.principio_sintetico,
                       s.stato_verifica, s.url_pagina_ufficiale, s.url_pdf_ufficiale,
                       s.pdf_ufficiale_presente, s.fonte_ufficiale_confermata, s.ecli,
                       s.precedente_guida, s.sezioni_unite, s.nomofilattica, s.rilevanza
                FROM sentenze s
                JOIN sentenze_fts fts ON fts.rowid = s.id
                WHERE sentenze_fts MATCH ?
            """
            params.append(_escape_fts_query(q))
        else:
            sql = """
                SELECT s.id, s.organo_giudicante, s.sezione, s.numero_sentenza, s.anno_sentenza,
                       s.data_deposito, s.titolo, s.massima_ufficiale, s.principio_sintetico,
                       s.stato_verifica, s.url_pagina_ufficiale, s.url_pdf_ufficiale,
                       s.pdf_ufficiale_presente, s.fonte_ufficiale_confermata, s.ecli,
                       s.precedente_guida, s.sezioni_unite, s.nomofilattica, s.rilevanza
                FROM sentenze s
                WHERE 1 = 1
            """
        if _clean_spaces(organo_giudicante):
            sql += " AND s.organo_giudicante = ?"
            params.append(_clean_spaces(organo_giudicante))
        if _clean_spaces(materia_principale):
            sql += " AND s.materia_principale = ?"
            params.append(_clean_spaces(materia_principale))
        if _clean_spaces(stato_verifica):
            sql += " AND s.stato_verifica = ?"
            params.append(_clean_spaces(stato_verifica))
        if solo_con_pdf:
            sql += " AND s.pdf_ufficiale_presente = 1"
        sql += """
            ORDER BY
                CASE s.stato_verifica
                    WHEN 'verificata' THEN 3
                    WHEN 'parzialmente_verificata' THEN 2
                    ELSE 0
                END DESC,
                s.pdf_ufficiale_presente DESC,
                s.fonte_ufficiale_confermata DESC,
                CASE WHEN COALESCE(s.ecli, '') <> '' THEN 1 ELSE 0 END DESC,
                s.precedente_guida DESC,
                s.sezioni_unite DESC,
                s.nomofilattica DESC,
                COALESCE(s.rilevanza, 0) DESC,
                COALESCE(s.data_deposito, '') DESC,
                COALESCE(s.data_pubblicazione, '') DESC,
                COALESCE(s.anno_sentenza, 0) DESC,
                s.id DESC
            LIMIT ?
        """
        params.append(max(1, int(limit)))
        with self._connect() as conn:
            return [dict(row) for row in conn.execute(sql, tuple(params)).fetchall()]

    def can_cite_sentenza(self, record: dict[str, Any] | None) -> bool:
        if not record:
            return False
        stato = _clean_spaces(record.get("stato_verifica"))
        if stato not in {"verificata", "parzialmente_verificata"}:
            return False
        official_url = _normalize_url(record.get("url_pagina_ufficiale") or record.get("url_html_ufficiale"))
        pdf_url = _normalize_url(record.get("url_pdf_ufficiale"))
        ecli = _clean_spaces(record.get("ecli"))
        organo = _clean_spaces(record.get("organo_giudicante"))
        numero = _clean_spaces(record.get("numero_sentenza"))
        anno = _to_int(record.get("anno_sentenza"), 0)
        return bool(official_url or pdf_url or ecli or (organo and numero and anno))

    def can_offer_pdf(self, record: dict[str, Any] | None) -> bool:
        if not record:
            return False
        if not bool(record.get("pdf_ufficiale_presente")):
            return False
        for document in list(record.get("documenti") or []):
            if _clean_spaces(document.get("tipo_documento")) != "pdf_ufficiale":
                continue
            if not bool(document.get("valido", 1)):
                continue
            if _normalize_url(document.get("url_origine")) or _clean_spaces(document.get("path_locale")):
                return True
        return False


__all__ = [
    "GestioneCorpusGiurisprudenza",
    "SCHEMA_GIURISPRUDENZA_CORPUS",
    "derive_corpus_db_path",
]
