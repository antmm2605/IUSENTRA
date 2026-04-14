from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any, Iterable


SCHEMA_TEMPLATE_REPOSITORY = Path(__file__).with_name("sql") / "20260414_template_repository.sql"


def _clean_spaces(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value is None:
        return []
    return [value]


def _template_value(template: Any, key: str) -> Any:
    if isinstance(template, dict):
        return template.get(key)
    return getattr(template, key, None)


def _query_terms(question: str) -> list[str]:
    seen: set[str] = set()
    terms: list[str] = []
    for raw in _clean_spaces(question).lower().replace("/", " ").replace("-", " ").split():
        token = "".join(ch for ch in raw if ch.isalnum())
        if len(token) < 3 or token in seen:
            continue
        seen.add(token)
        terms.append(token)
    return terms


def derive_template_repository_db_path(template_db_path: str) -> str:
    target = Path(template_db_path).resolve()
    return str(target.with_name("template_repository.db"))


def derive_template_repository_json_path(template_db_path: str) -> str:
    target = Path(template_db_path).resolve()
    return str(target.with_name("template_repository.json"))


def build_template_search_text(template: dict[str, Any]) -> str:
    parts: list[str] = []
    scalar_fields = (
        "titolo",
        "codice",
        "categoria",
        "collezione",
        "area",
        "branca",
        "sottobranca",
        "microtema",
        "fase",
        "rito",
        "grado",
        "canale_telematico",
        "profilo_deposito",
        "descrizione",
        "note",
        "corpo",
    )
    for key in scalar_fields:
        text = _clean_spaces(template.get(key))
        if text:
            parts.append(text)
    for item in template.get("parole_chiave", []):
        text = _clean_spaces(item)
        if text:
            parts.append(text)
    for item in template.get("varianti", []):
        text = _clean_spaces(item)
        if text:
            parts.append(text)
    for item in template.get("allegati_obbligatori", []):
        text = _clean_spaces(item.get("nome") if isinstance(item, dict) else item)
        if text:
            parts.append(text)
    for item in template.get("controlli_conformita", []):
        text = _clean_spaces(item.get("testo") if isinstance(item, dict) else item)
        if text:
            parts.append(text)
    for item in template.get("campi_guidati", []):
        if not isinstance(item, dict):
            continue
        for key in ("name", "label", "type", "section", "placeholder", "help_text"):
            text = _clean_spaces(item.get(key))
            if text:
                parts.append(text)
    for item in template.get("bindings", []):
        if not isinstance(item, dict):
            continue
        for key in ("binding_type", "binding_value", "label"):
            text = _clean_spaces(item.get(key))
            if text:
                parts.append(text)
    return "\n".join(parts).strip()


def normalize_template_repository_item(template: Any) -> dict[str, Any]:
    fields: list[dict[str, Any]] = []
    for idx, field in enumerate(_as_list(_template_value(template, "campi_guidati")), start=1):
        if not isinstance(field, dict):
            continue
        fields.append(
            {
                "ordine": idx,
                "field_name": _clean_spaces(field.get("name")),
                "label": _clean_spaces(field.get("label")),
                "field_type": _clean_spaces(field.get("type")),
                "section_name": _clean_spaces(field.get("section")),
                "placeholder": _clean_spaces(field.get("placeholder")),
                "help_text": _clean_spaces(field.get("help_text")),
                "rows_count": int(field.get("rows") or 0),
            }
        )

    attachments = [
        {
            "ordine": idx,
            "attachment_name": _clean_spaces(item),
            "required": True,
        }
        for idx, item in enumerate(_as_list(_template_value(template, "allegati_obbligatori")), start=1)
        if _clean_spaces(item)
    ]

    checks = [
        {
            "ordine": idx,
            "check_text": _clean_spaces(item),
            "severity": "warning",
        }
        for idx, item in enumerate(_as_list(_template_value(template, "controlli_conformita")), start=1)
        if _clean_spaces(item)
    ]

    keywords = [
        _clean_spaces(item)
        for item in _as_list(_template_value(template, "parole_chiave"))
        if _clean_spaces(item)
    ]
    variants = [
        _clean_spaces(item)
        for item in _as_list(_template_value(template, "varianti"))
        if _clean_spaces(item)
    ]
    compiler_code = _clean_spaces(_template_value(template, "link_compilatore_code"))
    bindings = (
        [
            {
                "ordine": 1,
                "binding_type": "compiler_code",
                "binding_value": compiler_code,
                "label": "Compilatore atti",
            }
        ]
        if compiler_code
        else []
    )
    normalized = {
        "template_id": _clean_spaces(_template_value(template, "id")),
        "codice": _clean_spaces(_template_value(template, "codice")),
        "titolo": _clean_spaces(_template_value(template, "titolo")),
        "categoria": _clean_spaces(_template_value(template, "categoria")),
        "collezione": _clean_spaces(_template_value(template, "collezione")),
        "area": _clean_spaces(_template_value(template, "area")),
        "branca": _clean_spaces(_template_value(template, "branca")),
        "sottobranca": _clean_spaces(_template_value(template, "sottobranca")),
        "microtema": _clean_spaces(_template_value(template, "microtema")),
        "fase": _clean_spaces(_template_value(template, "fase")),
        "rito": _clean_spaces(_template_value(template, "rito")),
        "grado": _clean_spaces(_template_value(template, "grado")),
        "canale_telematico": _clean_spaces(_template_value(template, "canale_telematico")),
        "profilo_deposito": _clean_spaces(_template_value(template, "profilo_deposito")),
        "builtin": bool(_template_value(template, "builtin")),
        "ordine": int(_template_value(template, "ordine") or 9999),
        "descrizione": _clean_spaces(_template_value(template, "descrizione")),
        "note": _clean_spaces(_template_value(template, "note")),
        "corpo": str(_template_value(template, "corpo") or ""),
        "parole_chiave": keywords,
        "varianti": variants,
        "campi_guidati": fields,
        "allegati_obbligatori": attachments,
        "controlli_conformita": checks,
        "bindings": bindings,
    }
    normalized["search_text"] = build_template_search_text(normalized)
    return normalized


def _payload_signature(items: list[dict[str, Any]]) -> str:
    encoded = json.dumps(items, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


class GestioneTemplateRepository:
    def __init__(
        self,
        db_path: str,
        *,
        json_path: str | None = None,
        schema_path: Path | None = None,
    ):
        self.db_path = str(db_path)
        self.json_path = str(json_path) if json_path else ""
        self.schema_path = Path(schema_path or SCHEMA_TEMPLATE_REPOSITORY)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        if self.json_path:
            Path(self.json_path).parent.mkdir(parents=True, exist_ok=True)
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

    def _get_meta(self, key: str) -> str:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT meta_value FROM template_repository_meta WHERE meta_key = ?",
                (_clean_spaces(key),),
            ).fetchone()
        return _clean_spaces(row["meta_value"]) if row else ""

    def _set_meta(self, conn: sqlite3.Connection, key: str, value: str) -> None:
        conn.execute(
            """
            INSERT INTO template_repository_meta(meta_key, meta_value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(meta_key) DO UPDATE SET
                meta_value = excluded.meta_value,
                updated_at = CURRENT_TIMESTAMP
            """,
            (_clean_spaces(key), _clean_spaces(value)),
        )

    def storage_stats(self) -> dict[str, Any]:
        tables = (
            "template_repository",
            "template_blocks",
            "template_fields",
            "template_checks",
            "template_bindings",
            "template_required_attachments",
            "template_keywords",
            "template_variants",
        )
        counts: dict[str, Any] = {"db_path": self.db_path, "json_path": self.json_path}
        with self._connect() as conn:
            for table_name in tables:
                counts[table_name] = int(
                    conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
                )
        counts["source_signature"] = self._get_meta("source_signature")
        return counts

    def synchronize_templates(self, templates: Iterable[Any], *, export_json: bool = True) -> dict[str, Any]:
        normalized = [normalize_template_repository_item(template) for template in templates]
        signature = _payload_signature(normalized)
        current_signature = self._get_meta("source_signature")
        current_count = int(self.storage_stats().get("template_repository", 0))
        if signature == current_signature and current_count == len(normalized):
            if export_json and self.json_path and not Path(self.json_path).exists():
                self.export_repository_json(self.json_path)
            return self.storage_stats()
        self.rebuild_from_payload(normalized, source_label="repo_builtin_templates")
        if export_json and self.json_path:
            self.export_repository_json(self.json_path)
        return self.storage_stats()

    def rebuild_from_payload(self, templates: list[dict[str, Any]], *, source_label: str = "template_repository") -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM template_blocks")
            conn.execute("DELETE FROM template_fields")
            conn.execute("DELETE FROM template_checks")
            conn.execute("DELETE FROM template_bindings")
            conn.execute("DELETE FROM template_required_attachments")
            conn.execute("DELETE FROM template_keywords")
            conn.execute("DELETE FROM template_variants")
            conn.execute("DELETE FROM template_repository")
            for template in templates:
                self._insert_template(conn, template)
            self._set_meta(conn, "source_signature", _payload_signature(templates))
            self._set_meta(conn, "source_label", source_label)
            conn.commit()

    def _insert_template(self, conn: sqlite3.Connection, template: dict[str, Any]) -> None:
        conn.execute(
            """
            INSERT INTO template_repository (
                template_id, codice, titolo, categoria, collezione, area, branca,
                sottobranca, microtema, fase, rito, grado, canale_telematico,
                profilo_deposito, builtin, ordine, descrizione, note, search_text
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                template.get("template_id"),
                template.get("codice"),
                template.get("titolo"),
                template.get("categoria"),
                template.get("collezione"),
                template.get("area"),
                template.get("branca"),
                template.get("sottobranca"),
                template.get("microtema"),
                template.get("fase"),
                template.get("rito"),
                template.get("grado"),
                template.get("canale_telematico"),
                template.get("profilo_deposito"),
                1 if template.get("builtin") else 0,
                template.get("ordine") or 9999,
                template.get("descrizione"),
                template.get("note"),
                template.get("search_text"),
            ),
        )
        conn.execute(
            """
            INSERT INTO template_blocks (
                template_id, block_key, block_type, content, ordine
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                template.get("template_id"),
                "corpo",
                "body",
                template.get("corpo") or "",
                1,
            ),
        )
        for order, item in enumerate(template.get("parole_chiave") or [], start=1):
            conn.execute(
                "INSERT INTO template_keywords (template_id, keyword, ordine) VALUES (?, ?, ?)",
                (template.get("template_id"), _clean_spaces(item), order),
            )
        for order, item in enumerate(template.get("varianti") or [], start=1):
            conn.execute(
                "INSERT INTO template_variants (template_id, variante, ordine) VALUES (?, ?, ?)",
                (template.get("template_id"), _clean_spaces(item), order),
            )
        for item in template.get("campi_guidati") or []:
            conn.execute(
                """
                INSERT INTO template_fields (
                    template_id, field_name, label, field_type, section_name,
                    placeholder, help_text, rows_count, ordine
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    template.get("template_id"),
                    item.get("field_name"),
                    item.get("label"),
                    item.get("field_type"),
                    item.get("section_name"),
                    item.get("placeholder"),
                    item.get("help_text"),
                    int(item.get("rows_count") or 0),
                    int(item.get("ordine") or 0),
                ),
            )
        for item in template.get("controlli_conformita") or []:
            conn.execute(
                "INSERT INTO template_checks (template_id, check_text, severity, ordine) VALUES (?, ?, ?, ?)",
                (
                    template.get("template_id"),
                    item.get("check_text"),
                    item.get("severity") or "warning",
                    int(item.get("ordine") or 0),
                ),
            )
        for item in template.get("bindings") or []:
            conn.execute(
                """
                INSERT INTO template_bindings (template_id, binding_type, binding_value, label, ordine)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    template.get("template_id"),
                    item.get("binding_type"),
                    item.get("binding_value"),
                    item.get("label"),
                    int(item.get("ordine") or 0),
                ),
            )
        for item in template.get("allegati_obbligatori") or []:
            conn.execute(
                """
                INSERT INTO template_required_attachments (
                    template_id, attachment_name, required, ordine
                ) VALUES (?, ?, ?, ?)
                """,
                (
                    template.get("template_id"),
                    item.get("attachment_name"),
                    1 if item.get("required", True) else 0,
                    int(item.get("ordine") or 0),
                ),
            )

    def load_repository_payload(self) -> dict[str, Any]:
        templates = [self.get_template(row["template_id"]) for row in self.list_templates()]
        templates = [row for row in templates if row]
        return {
            "source": self._get_meta("source_label") or "template_repository",
            "count": len(templates),
            "templates": templates,
        }

    def export_repository_json(self, path: str | None = None) -> str:
        target = Path(path or self.json_path)
        if not str(target):
            raise ValueError("Percorso export JSON repository non configurato.")
        payload = self.load_repository_payload()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(target)

    def import_repository_json(self, path: str) -> dict[str, Any]:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        self.rebuild_from_payload(
            list(payload.get("templates") or []),
            source_label=_clean_spaces(payload.get("source")) or "template_repository_json",
        )
        return self.storage_stats()

    def list_templates(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            return [
                dict(row)
                for row in conn.execute(
                    """
                    SELECT *
                    FROM template_repository
                    ORDER BY builtin DESC, ordine ASC, titolo ASC
                    """
                ).fetchall()
            ]

    def get_template(self, template_id: str) -> dict[str, Any] | None:
        template_key = _clean_spaces(template_id)
        if not template_key:
            return None
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM template_repository WHERE template_id = ?",
                (template_key,),
            ).fetchone()
            if not row:
                return None
            payload = dict(row)
            payload["template_blocks"] = [
                dict(item)
                for item in conn.execute(
                    """
                    SELECT block_key, block_type, content, ordine
                    FROM template_blocks
                    WHERE template_id = ?
                    ORDER BY ordine
                    """,
                    (template_key,),
                ).fetchall()
            ]
            payload["corpo"] = next(
                (item.get("content") for item in payload["template_blocks"] if item.get("block_key") == "corpo"),
                "",
            )
            payload["campi_guidati"] = [
                {
                    "ordine": item["ordine"],
                    "name": item["field_name"],
                    "label": item["label"],
                    "type": item["field_type"],
                    "section": item["section_name"],
                    "placeholder": item["placeholder"],
                    "help_text": item["help_text"],
                    "rows": item["rows_count"],
                }
                for item in conn.execute(
                    """
                    SELECT field_name, label, field_type, section_name, placeholder, help_text, rows_count, ordine
                    FROM template_fields
                    WHERE template_id = ?
                    ORDER BY ordine
                    """,
                    (template_key,),
                ).fetchall()
            ]
            payload["controlli_conformita"] = [
                {
                    "ordine": item["ordine"],
                    "testo": item["check_text"],
                    "severity": item["severity"],
                }
                for item in conn.execute(
                    """
                    SELECT check_text, severity, ordine
                    FROM template_checks
                    WHERE template_id = ?
                    ORDER BY ordine
                    """,
                    (template_key,),
                ).fetchall()
            ]
            payload["allegati_obbligatori"] = [
                {
                    "ordine": item["ordine"],
                    "nome": item["attachment_name"],
                    "required": bool(item["required"]),
                }
                for item in conn.execute(
                    """
                    SELECT attachment_name, required, ordine
                    FROM template_required_attachments
                    WHERE template_id = ?
                    ORDER BY ordine
                    """,
                    (template_key,),
                ).fetchall()
            ]
            payload["bindings"] = [
                {
                    "ordine": item["ordine"],
                    "binding_type": item["binding_type"],
                    "binding_value": item["binding_value"],
                    "label": item["label"],
                }
                for item in conn.execute(
                    """
                    SELECT binding_type, binding_value, label, ordine
                    FROM template_bindings
                    WHERE template_id = ?
                    ORDER BY ordine
                    """,
                    (template_key,),
                ).fetchall()
            ]
            payload["parole_chiave"] = [
                item["keyword"]
                for item in conn.execute(
                    "SELECT keyword FROM template_keywords WHERE template_id = ? ORDER BY ordine",
                    (template_key,),
                ).fetchall()
            ]
            payload["varianti"] = [
                item["variante"]
                for item in conn.execute(
                    "SELECT variante FROM template_variants WHERE template_id = ? ORDER BY ordine",
                    (template_key,),
                ).fetchall()
            ]
            return payload

    def _candidate_pool(
        self,
        *,
        area: str = "",
        fase: str = "",
        rito: str = "",
        canale: str = "",
    ) -> list[dict[str, Any]]:
        rows = [self.get_template(row["template_id"]) for row in self.list_templates()]
        rows = [row for row in rows if row]

        def _matches(value: str, probe: str) -> bool:
            left = _clean_spaces(value).lower()
            right = _clean_spaces(probe).lower()
            if not right:
                return True
            return right in left or left == right

        filtered = [
            row
            for row in rows
            if _matches(row.get("area", ""), area)
            and _matches(row.get("fase", ""), fase)
            and _matches(row.get("rito", ""), rito)
            and _matches(row.get("canale_telematico", ""), canale)
        ]
        return filtered or rows

    def _score_template(self, question: str, template: dict[str, Any]) -> tuple[int, list[str]]:
        query = _clean_spaces(question).lower()
        terms = _query_terms(question)
        search_text = _clean_spaces(template.get("search_text")).lower()
        title = _clean_spaces(template.get("titolo")).lower()
        metadata = " ".join(
            _clean_spaces(template.get(key)).lower()
            for key in (
                "categoria",
                "collezione",
                "area",
                "branca",
                "sottobranca",
                "microtema",
                "fase",
                "rito",
                "grado",
                "canale_telematico",
                "profilo_deposito",
            )
        )
        score = 0
        reasons: list[str] = []
        if query and query in title:
            score += 45
            reasons.append("titolo")
        if query and query in search_text and "contenuto" not in reasons:
            score += 18
            reasons.append("contenuto")
        for term in terms:
            if term in title:
                score += 12
                if "titolo" not in reasons:
                    reasons.append("titolo")
            if term in metadata:
                score += 6
                if "metadati" not in reasons:
                    reasons.append("metadati")
            if term in search_text:
                score += 3
        if template.get("bindings"):
            score += 4
            if "compilatore" not in reasons:
                reasons.append("compilatore")
        if template.get("builtin"):
            score += 1
        ordine = int(template.get("ordine") or 9999)
        score += max(0, 15 - min(ordine, 15))
        return score, reasons

    def select_best_templates(
        self,
        question: str,
        *,
        area: str = "",
        fase: str = "",
        rito: str = "",
        canale: str = "",
        limit: int = 3,
    ) -> dict[str, Any]:
        candidates = self._candidate_pool(area=area, fase=fase, rito=rito, canale=canale)
        scored: list[tuple[int, int, str, dict[str, Any]]] = []
        for row in candidates:
            score, reasons = self._score_template(question, row)
            decorated = dict(row)
            decorated["match_score"] = score
            decorated["match_reasons"] = list(dict.fromkeys(reasons))
            scored.append((score, 1 if row.get("bindings") else 0, row.get("titolo") or "", decorated))
        scored.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)
        selected = [item[3] for item in scored[: max(1, int(limit))] if item[0] > 0]
        if not selected and scored:
            selected = [item[3] for item in scored[: max(1, int(limit))]]
        best = selected[0] if selected else None
        alternatives = selected[1:] if len(selected) > 1 else []
        return {
            "question": _clean_spaces(question),
            "filters": {
                "area": _clean_spaces(area),
                "fase": _clean_spaces(fase),
                "rito": _clean_spaces(rito),
                "canale": _clean_spaces(canale),
            },
            "best_template": best,
            "alternatives": alternatives,
            "selected_count": len(selected),
        }


__all__ = [
    "GestioneTemplateRepository",
    "SCHEMA_TEMPLATE_REPOSITORY",
    "build_template_search_text",
    "derive_template_repository_db_path",
    "derive_template_repository_json_path",
    "normalize_template_repository_item",
]
