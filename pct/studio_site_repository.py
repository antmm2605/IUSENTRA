from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from pct.postgres_runtime_support import PostgresRepositoryBackend
from pct.studio_site import (
    booking_slots_for_date,
    clean_text,
    default_article_seed,
    default_office_seed,
    default_page_seed,
    default_professional_seed,
    default_service_seed,
    normalize_page_slug,
    parse_blocks,
    slugify,
    truthy,
)


SCHEMA_STUDIO_SITE_SQL = Path(__file__).with_name("sql") / "20260422_studio_site.sql"
POSTGRES_SCHEMA_STUDIO_SITE_SQL = Path(__file__).with_name("sql") / "20260422_studio_site_postgres.sql"


def _json_dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _json_load(value: Any, default: Any) -> Any:
    if isinstance(value, (list, dict)):
        return value
    text = str(value or "").strip()
    if not text:
        return default
    try:
        return json.loads(text)
    except Exception:
        return default


class StudioSiteRepository:
    def __init__(
        self,
        db_path: str,
        *,
        postgres_dsn: str = "",
        postgres_schema_path: Path | None = None,
    ) -> None:
        self.db_path = str(db_path or "").strip()
        self.postgres_dsn = str(postgres_dsn or "").strip()
        self.postgres_schema_path = Path(postgres_schema_path or POSTGRES_SCHEMA_STUDIO_SITE_SQL)
        self.backend_kind = "postgresql" if self.postgres_dsn else "sqlite"
        self._postgres_backend = (
            PostgresRepositoryBackend(self.postgres_dsn, self.postgres_schema_path)
            if self.postgres_dsn
            else None
        )
        self._ensure_schema()

    def _connect(self):
        if self._postgres_backend is not None:
            return self._postgres_backend.connection()
        target = Path(self.db_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(target))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _ensure_schema(self) -> None:
        schema = (
            self.postgres_schema_path.read_text(encoding="utf-8")
            if self._postgres_backend is not None
            else SCHEMA_STUDIO_SITE_SQL.read_text(encoding="utf-8")
        )
        with self._connect() as conn:
            conn.executescript(schema)
            conn.commit()

    def _row_to_dict(self, row: Any, *, json_fields: tuple[str, ...] = ()) -> dict[str, Any] | None:
        if row is None:
            return None
        if isinstance(row, dict):
            payload = dict(row)
        elif hasattr(row, "keys"):
            payload = {key: row[key] for key in row.keys()}
        else:
            return None
        for field in json_fields:
            payload[field] = _json_load(payload.get(field), [])
        for key in (
            "show_in_menu",
            "is_home",
            "is_visible",
            "is_primary",
            "is_active",
            "privacy_accepted",
            "show_legal_tools",
            "show_applications",
            "show_legal_news",
            "is_published",
        ):
            if key in payload:
                payload[key] = bool(payload[key])
        return payload

    def _insert_returning_id(self, conn: Any, sql: str, params: tuple[Any, ...]) -> int:
        statement = str(sql or "").strip().rstrip(";")
        if self._postgres_backend is not None:
            row = conn.execute(f"{statement} RETURNING id", params).fetchone()
            if row is None:
                raise RuntimeError("Inserimento senza id restituito.")
            if isinstance(row, dict):
                return int(row.get("id") or next(iter(row.values()), 0) or 0)
            return int((row or [0])[0] or 0)
        cursor = conn.execute(statement, params)
        return int(cursor.lastrowid)

    def _unique_site_slug(self, requested_slug: str, *, exclude_site_id: int | None = None) -> str:
        base = slugify(requested_slug)
        with self._connect() as conn:
            candidate = base
            suffix = 2
            while True:
                if exclude_site_id:
                    row = conn.execute(
                        "SELECT id FROM site_studio WHERE public_slug = ? AND id <> ? LIMIT 1",
                        (candidate, int(exclude_site_id)),
                    ).fetchone()
                else:
                    row = conn.execute(
                        "SELECT id FROM site_studio WHERE public_slug = ? LIMIT 1",
                        (candidate,),
                    ).fetchone()
                if not row:
                    return candidate
                candidate = f"{base}-{suffix}"
                suffix += 1

    def _unique_content_slug(
        self,
        table: str,
        site_id: int,
        requested_slug: str,
        *,
        exclude_id: int | None = None,
        is_page: bool = False,
        is_home: bool = False,
    ) -> str:
        base = normalize_page_slug(requested_slug, is_home=is_home) if is_page else slugify(requested_slug)
        with self._connect() as conn:
            candidate = base
            suffix = 2
            while True:
                if exclude_id:
                    row = conn.execute(
                        f"SELECT id FROM {table} WHERE site_id = ? AND slug = ? AND id <> ? LIMIT 1",
                        (int(site_id), candidate, int(exclude_id)),
                    ).fetchone()
                else:
                    row = conn.execute(
                        f"SELECT id FROM {table} WHERE site_id = ? AND slug = ? LIMIT 1",
                        (int(site_id), candidate),
                    ).fetchone()
                if not row:
                    return candidate
                candidate = f"{base}-{suffix}"
                suffix += 1

    def _seed_site_defaults(
        self,
        site_id: int,
        *,
        public_slug: str,
        page_seed: list[dict[str, Any]] | None = None,
        professional_seed: dict[str, Any] | None = None,
        office_seed: dict[str, Any] | None = None,
        article_seed: list[dict[str, Any]] | None = None,
    ) -> None:
        pages = self.list_pages(site_id)
        if not pages:
            for row in page_seed or []:
                self.save_page(site_id, row)
        if not self.list_services(site_id):
            for row in default_service_seed():
                self.save_service(site_id, row)
        if not self.list_articles(site_id):
            for row in article_seed or []:
                self.save_article(site_id, row)
        if professional_seed and not self.list_professionals(site_id):
            self.save_professional(site_id, professional_seed)
        if office_seed and not self.list_offices(site_id):
            office = self.save_office(site_id, office_seed)
            self.save_booking_rule(
                site_id,
                {
                    "office_id": office["id"],
                    "weekday": 1,
                    "start_time": "09:30",
                    "end_time": "12:30",
                    "slot_minutes": 30,
                    "max_requests_per_slot": 1,
                    "is_active": True,
                },
            )
            self.save_booking_rule(
                site_id,
                {
                    "office_id": office["id"],
                    "weekday": 3,
                    "start_time": "15:00",
                    "end_time": "18:00",
                    "slot_minutes": 30,
                    "max_requests_per_slot": 1,
                    "is_active": True,
                },
            )

    def get_site_by_id(self, site_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM site_studio WHERE id = ? LIMIT 1", (int(site_id),)).fetchone()
        return self._row_to_dict(row)

    def get_site_by_tenant_slug(self, tenant_slug: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM site_studio WHERE tenant_slug = ? LIMIT 1",
                (clean_text(tenant_slug).lower(),),
            ).fetchone()
        return self._row_to_dict(row)

    def get_site_by_public_slug(self, public_slug: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM site_studio WHERE public_slug = ? LIMIT 1",
                (slugify(public_slug),),
            ).fetchone()
        return self._row_to_dict(row)

    def list_sites(
        self,
        *,
        query: str = "",
        published_only: bool = False,
        active_only: bool = False,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        clauses = ["1 = 1"]
        params: list[Any] = []
        if published_only:
            clauses.append("is_published = 1")
        if active_only:
            clauses.append("is_active = 1")
        if query:
            token = f"%{clean_text(query).lower()}%"
            clauses.append(
                "("
                "LOWER(tenant_slug) LIKE ? OR LOWER(studio_nome) LIKE ? OR LOWER(site_name) LIKE ? OR LOWER(public_slug) LIKE ?"
                ")"
            )
            params.extend([token, token, token, token])
        params.append(int(limit or 200))
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT * FROM site_studio
                WHERE {' AND '.join(clauses)}
                ORDER BY is_published DESC, updated_at DESC, site_name ASC
                LIMIT ?
                """,
                tuple(params),
            ).fetchall()
        return [self._row_to_dict(row) or {} for row in rows]

    def ensure_site(
        self,
        tenant_slug: str,
        *,
        defaults: dict[str, Any],
        page_seed: list[dict[str, Any]] | None = None,
        professional_seed: dict[str, Any] | None = None,
        office_seed: dict[str, Any] | None = None,
        article_seed: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        existing = self.get_site_by_tenant_slug(tenant_slug)
        if existing:
            self._seed_site_defaults(
                int(existing["id"]),
                public_slug=str(existing.get("public_slug") or ""),
                page_seed=page_seed,
                professional_seed=professional_seed,
                office_seed=office_seed,
                article_seed=article_seed,
            )
            return self.get_site_by_id(int(existing["id"])) or existing

        public_slug = self._unique_site_slug(str(defaults.get("public_slug") or tenant_slug))
        with self._connect() as conn:
            site_id = self._insert_returning_id(
                conn,
                """
                INSERT INTO site_studio (
                    tenant_slug, studio_nome, site_name, public_slug, site_title, site_description,
                    hero_claim, logo_url, favicon_url, primary_color, secondary_color, accent_color,
                    contact_email, contact_phone, whatsapp_number, address, city, province, zip_code,
                    footer_text, facebook_url, instagram_url, linkedin_url,
                    show_legal_tools, show_applications, show_legal_news, is_published, is_active, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (
                    clean_text(defaults.get("tenant_slug") or tenant_slug).lower(),
                    clean_text(defaults.get("studio_nome")),
                    clean_text(defaults.get("site_name")),
                    public_slug,
                    clean_text(defaults.get("site_title")),
                    clean_text(defaults.get("site_description")),
                    clean_text(defaults.get("hero_claim")),
                    clean_text(defaults.get("logo_url")),
                    clean_text(defaults.get("favicon_url")),
                    clean_text(defaults.get("primary_color")),
                    clean_text(defaults.get("secondary_color")),
                    clean_text(defaults.get("accent_color")),
                    clean_text(defaults.get("contact_email")),
                    clean_text(defaults.get("contact_phone")),
                    clean_text(defaults.get("whatsapp_number")),
                    clean_text(defaults.get("address")),
                    clean_text(defaults.get("city")),
                    clean_text(defaults.get("province")),
                    clean_text(defaults.get("zip_code")),
                    clean_text(defaults.get("footer_text")),
                    clean_text(defaults.get("facebook_url")),
                    clean_text(defaults.get("instagram_url")),
                    clean_text(defaults.get("linkedin_url")),
                    1 if truthy(defaults.get("show_legal_tools")) else 0,
                    1 if truthy(defaults.get("show_applications")) else 0,
                    1 if truthy(defaults.get("show_legal_news")) else 0,
                    1 if truthy(defaults.get("is_published")) else 0,
                    0 if defaults.get("is_active") is False else 1,
                ),
            )
            conn.commit()
        self._seed_site_defaults(
            site_id,
            public_slug=public_slug,
            page_seed=page_seed,
            professional_seed=professional_seed,
            office_seed=office_seed,
            article_seed=article_seed,
        )
        return self.get_site_by_id(site_id) or {}

    def save_site(self, site_id: int, payload: dict[str, Any]) -> dict[str, Any] | None:
        current = self.get_site_by_id(site_id)
        if current is None:
            return None
        public_slug = self._unique_site_slug(
            str(payload.get("public_slug") or current.get("public_slug") or ""),
            exclude_site_id=site_id,
        )
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE site_studio
                SET studio_nome = ?, site_name = ?, public_slug = ?, site_title = ?, site_description = ?,
                    hero_claim = ?, logo_url = ?, favicon_url = ?, primary_color = ?, secondary_color = ?,
                    accent_color = ?, contact_email = ?, contact_phone = ?, whatsapp_number = ?, address = ?,
                    city = ?, province = ?, zip_code = ?, footer_text = ?, facebook_url = ?, instagram_url = ?,
                    linkedin_url = ?, show_legal_tools = ?, show_applications = ?, show_legal_news = ?,
                    is_published = ?, is_active = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    clean_text(payload.get("studio_nome") or current.get("studio_nome")),
                    clean_text(payload.get("site_name") or current.get("site_name")),
                    public_slug,
                    clean_text(payload.get("site_title") or current.get("site_title")),
                    clean_text(payload.get("site_description") or current.get("site_description")),
                    clean_text(payload.get("hero_claim") or current.get("hero_claim")),
                    clean_text(payload.get("logo_url") or current.get("logo_url")),
                    clean_text(payload.get("favicon_url") or current.get("favicon_url")),
                    clean_text(payload.get("primary_color") or current.get("primary_color")),
                    clean_text(payload.get("secondary_color") or current.get("secondary_color")),
                    clean_text(payload.get("accent_color") or current.get("accent_color")),
                    clean_text(payload.get("contact_email") or current.get("contact_email")),
                    clean_text(payload.get("contact_phone") or current.get("contact_phone")),
                    clean_text(payload.get("whatsapp_number") or current.get("whatsapp_number")),
                    clean_text(payload.get("address") or current.get("address")),
                    clean_text(payload.get("city") or current.get("city")),
                    clean_text(payload.get("province") or current.get("province")),
                    clean_text(payload.get("zip_code") or current.get("zip_code")),
                    clean_text(payload.get("footer_text") or current.get("footer_text")),
                    clean_text(payload.get("facebook_url") or current.get("facebook_url")),
                    clean_text(payload.get("instagram_url") or current.get("instagram_url")),
                    clean_text(payload.get("linkedin_url") or current.get("linkedin_url")),
                    1 if truthy(payload.get("show_legal_tools", current.get("show_legal_tools"))) else 0,
                    1 if truthy(payload.get("show_applications", current.get("show_applications"))) else 0,
                    1 if truthy(payload.get("show_legal_news", current.get("show_legal_news"))) else 0,
                    1 if truthy(payload.get("is_published", current.get("is_published"))) else 0,
                    0 if payload.get("is_active", current.get("is_active")) is False else 1,
                    int(site_id),
                ),
            )
            conn.commit()
        return self.get_site_by_id(site_id)

    def _list_rows(
        self,
        table: str,
        *,
        site_id: int,
        where: str = "",
        params: tuple[Any, ...] = (),
        order_by: str = "id ASC",
        json_fields: tuple[str, ...] = (),
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        sql = f"SELECT * FROM {table} WHERE site_id = ?"
        query_params: list[Any] = [int(site_id)]
        if where:
            sql += f" AND {where}"
            query_params.extend(params)
        sql += f" ORDER BY {order_by}"
        if limit:
            sql += " LIMIT ?"
            query_params.append(int(limit))
        with self._connect() as conn:
            rows = conn.execute(sql, tuple(query_params)).fetchall()
        return [self._row_to_dict(row, json_fields=json_fields) or {} for row in rows]

    def _get_row(
        self,
        table: str,
        *,
        site_id: int,
        row_id: int | None = None,
        slug: str = "",
        published_only: bool = False,
        json_fields: tuple[str, ...] = (),
    ) -> dict[str, Any] | None:
        clauses = ["site_id = ?"]
        params: list[Any] = [int(site_id)]
        if row_id is not None:
            clauses.append("id = ?")
            params.append(int(row_id))
        if slug:
            clauses.append("slug = ?")
            params.append(clean_text(slug))
        if published_only:
            clauses.append("status = 'published'")
        with self._connect() as conn:
            row = conn.execute(
                f"SELECT * FROM {table} WHERE {' AND '.join(clauses)} LIMIT 1",
                tuple(params),
            ).fetchone()
        return self._row_to_dict(row, json_fields=json_fields)

    def _delete_row(self, table: str, *, site_id: int, row_id: int) -> None:
        with self._connect() as conn:
            conn.execute(
                f"DELETE FROM {table} WHERE site_id = ? AND id = ?",
                (int(site_id), int(row_id)),
            )
            conn.commit()

    def list_pages(self, site_id: int, *, published_only: bool = False) -> list[dict[str, Any]]:
        return self._list_rows(
            "site_page",
            site_id=site_id,
            where="status = 'published'" if published_only else "",
            order_by="sort_order ASC, title ASC",
            json_fields=("body_json",),
        )

    def get_page(self, site_id: int, page_id: int) -> dict[str, Any] | None:
        return self._get_row("site_page", site_id=site_id, row_id=page_id, json_fields=("body_json",))

    def get_page_by_slug(self, site_id: int, slug: str, *, published_only: bool = False) -> dict[str, Any] | None:
        return self._get_row(
            "site_page",
            site_id=site_id,
            slug=slug,
            published_only=published_only,
            json_fields=("body_json",),
        )

    def save_page(self, site_id: int, payload: dict[str, Any], *, page_id: int | None = None) -> dict[str, Any]:
        current = self.get_page(site_id, page_id) if page_id else None
        is_home = truthy(payload.get("is_home", current.get("is_home") if current else False))
        slug = self._unique_content_slug(
            "site_page",
            site_id,
            str(payload.get("slug") or payload.get("title") or (current.get("slug") if current else "")),
            exclude_id=page_id,
            is_page=True,
            is_home=is_home,
        )
        body = parse_blocks(payload.get("body_json") if "body_json" in payload else (current.get("body_json") if current else []))
        with self._connect() as conn:
            if is_home:
                if page_id:
                    conn.execute(
                        "UPDATE site_page SET is_home = 0 WHERE site_id = ? AND id <> ?",
                        (int(site_id), int(page_id)),
                    )
                else:
                    conn.execute("UPDATE site_page SET is_home = 0 WHERE site_id = ?", (int(site_id),))
            if current:
                conn.execute(
                    """
                    UPDATE site_page
                    SET title = ?, slug = ?, excerpt = ?, body_json = ?, status = ?, show_in_menu = ?,
                        sort_order = ?, is_home = ?, seo_title = ?, seo_description = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ? AND site_id = ?
                    """,
                    (
                        clean_text(payload.get("title") or current.get("title")),
                        slug,
                        clean_text(payload.get("excerpt") or current.get("excerpt")),
                        _json_dump(body),
                        clean_text(payload.get("status") or current.get("status") or "draft"),
                        1 if truthy(payload.get("show_in_menu", current.get("show_in_menu"))) else 0,
                        int(payload.get("sort_order") or current.get("sort_order") or 0),
                        1 if is_home else 0,
                        clean_text(payload.get("seo_title") or current.get("seo_title")),
                        clean_text(payload.get("seo_description") or current.get("seo_description")),
                        int(page_id),
                        int(site_id),
                    ),
                )
                conn.commit()
                target_id = int(page_id)
            else:
                target_id = self._insert_returning_id(
                    conn,
                    """
                    INSERT INTO site_page (
                        site_id, title, slug, excerpt, body_json, status, show_in_menu,
                        sort_order, is_home, seo_title, seo_description, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """,
                    (
                        int(site_id),
                        clean_text(payload.get("title")),
                        slug,
                        clean_text(payload.get("excerpt")),
                        _json_dump(body),
                        clean_text(payload.get("status") or "draft"),
                        1 if truthy(payload.get("show_in_menu", True)) else 0,
                        int(payload.get("sort_order") or 0),
                        1 if is_home else 0,
                        clean_text(payload.get("seo_title")),
                        clean_text(payload.get("seo_description")),
                    ),
                )
                conn.commit()
        return self.get_page(site_id, target_id) or {}

    def delete_page(self, site_id: int, page_id: int) -> None:
        self._delete_row("site_page", site_id=site_id, row_id=page_id)

    def list_articles(self, site_id: int, *, published_only: bool = False, limit: int | None = None) -> list[dict[str, Any]]:
        return self._list_rows(
            "site_article",
            site_id=site_id,
            where="status = 'published'" if published_only else "",
            order_by="COALESCE(NULLIF(published_at, ''), created_at) DESC, id DESC",
            json_fields=("body_json",),
            limit=limit,
        )

    def get_article(self, site_id: int, article_id: int) -> dict[str, Any] | None:
        return self._get_row("site_article", site_id=site_id, row_id=article_id, json_fields=("body_json",))

    def get_article_by_slug(self, site_id: int, slug: str, *, published_only: bool = False) -> dict[str, Any] | None:
        return self._get_row(
            "site_article",
            site_id=site_id,
            slug=slug,
            published_only=published_only,
            json_fields=("body_json",),
        )

    def save_article(self, site_id: int, payload: dict[str, Any], *, article_id: int | None = None) -> dict[str, Any]:
        current = self.get_article(site_id, article_id) if article_id else None
        slug = self._unique_content_slug(
            "site_article",
            site_id,
            str(payload.get("slug") or payload.get("title") or (current.get("slug") if current else "")),
            exclude_id=article_id,
        )
        body = parse_blocks(payload.get("body_json") if "body_json" in payload else (current.get("body_json") if current else []))
        with self._connect() as conn:
            if current:
                conn.execute(
                    """
                    UPDATE site_article
                    SET title = ?, slug = ?, excerpt = ?, cover_url = ?, category = ?, tags_csv = ?,
                        author_name = ?, body_json = ?, status = ?, published_at = ?, seo_title = ?,
                        seo_description = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ? AND site_id = ?
                    """,
                    (
                        clean_text(payload.get("title") or current.get("title")),
                        slug,
                        clean_text(payload.get("excerpt") or current.get("excerpt")),
                        clean_text(payload.get("cover_url") or current.get("cover_url")),
                        clean_text(payload.get("category") or current.get("category")),
                        clean_text(payload.get("tags_csv") or current.get("tags_csv")),
                        clean_text(payload.get("author_name") or current.get("author_name")),
                        _json_dump(body),
                        clean_text(payload.get("status") or current.get("status") or "draft"),
                        clean_text(payload.get("published_at") or current.get("published_at")),
                        clean_text(payload.get("seo_title") or current.get("seo_title")),
                        clean_text(payload.get("seo_description") or current.get("seo_description")),
                        int(article_id),
                        int(site_id),
                    ),
                )
                conn.commit()
                target_id = int(article_id)
            else:
                target_id = self._insert_returning_id(
                    conn,
                    """
                    INSERT INTO site_article (
                        site_id, title, slug, excerpt, cover_url, category, tags_csv, author_name,
                        body_json, status, published_at, seo_title, seo_description, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """,
                    (
                        int(site_id),
                        clean_text(payload.get("title")),
                        slug,
                        clean_text(payload.get("excerpt")),
                        clean_text(payload.get("cover_url")),
                        clean_text(payload.get("category")),
                        clean_text(payload.get("tags_csv")),
                        clean_text(payload.get("author_name")),
                        _json_dump(body),
                        clean_text(payload.get("status") or "draft"),
                        clean_text(payload.get("published_at")),
                        clean_text(payload.get("seo_title")),
                        clean_text(payload.get("seo_description")),
                    ),
                )
                conn.commit()
        return self.get_article(site_id, target_id) or {}

    def delete_article(self, site_id: int, article_id: int) -> None:
        self._delete_row("site_article", site_id=site_id, row_id=article_id)

    def list_services(self, site_id: int) -> list[dict[str, Any]]:
        return self._list_rows("site_service", site_id=site_id, order_by="sort_order ASC, title ASC")

    def get_service(self, site_id: int, service_id: int) -> dict[str, Any] | None:
        return self._get_row("site_service", site_id=site_id, row_id=service_id)

    def save_service(self, site_id: int, payload: dict[str, Any], *, service_id: int | None = None) -> dict[str, Any]:
        current = self.get_service(site_id, service_id) if service_id else None
        slug = self._unique_content_slug(
            "site_service",
            site_id,
            str(payload.get("slug") or payload.get("title") or (current.get("slug") if current else "")),
            exclude_id=service_id,
        )
        with self._connect() as conn:
            if current:
                conn.execute(
                    """
                    UPDATE site_service
                    SET title = ?, slug = ?, short_description = ?, long_description = ?, icon = ?,
                        sort_order = ?, is_visible = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ? AND site_id = ?
                    """,
                    (
                        clean_text(payload.get("title") or current.get("title")),
                        slug,
                        clean_text(payload.get("short_description") or current.get("short_description")),
                        clean_text(payload.get("long_description") or current.get("long_description")),
                        clean_text(payload.get("icon") or current.get("icon")),
                        int(payload.get("sort_order") or current.get("sort_order") or 0),
                        1 if truthy(payload.get("is_visible", current.get("is_visible"))) else 0,
                        int(service_id),
                        int(site_id),
                    ),
                )
                conn.commit()
                target_id = int(service_id)
            else:
                target_id = self._insert_returning_id(
                    conn,
                    """
                    INSERT INTO site_service (
                        site_id, title, slug, short_description, long_description, icon,
                        sort_order, is_visible, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """,
                    (
                        int(site_id),
                        clean_text(payload.get("title")),
                        slug,
                        clean_text(payload.get("short_description")),
                        clean_text(payload.get("long_description")),
                        clean_text(payload.get("icon")),
                        int(payload.get("sort_order") or 0),
                        1 if truthy(payload.get("is_visible", True)) else 0,
                    ),
                )
                conn.commit()
        return self.get_service(site_id, target_id) or {}

    def delete_service(self, site_id: int, service_id: int) -> None:
        self._delete_row("site_service", site_id=site_id, row_id=service_id)

    def list_professionals(self, site_id: int) -> list[dict[str, Any]]:
        return self._list_rows("site_professional", site_id=site_id, order_by="sort_order ASC, full_name ASC")

    def get_professional(self, site_id: int, professional_id: int) -> dict[str, Any] | None:
        return self._get_row("site_professional", site_id=site_id, row_id=professional_id)

    def save_professional(
        self,
        site_id: int,
        payload: dict[str, Any],
        *,
        professional_id: int | None = None,
    ) -> dict[str, Any]:
        current = self.get_professional(site_id, professional_id) if professional_id else None
        with self._connect() as conn:
            if current:
                conn.execute(
                    """
                    UPDATE site_professional
                    SET full_name = ?, role_title = ?, bio = ?, photo_url = ?, email = ?, phone = ?,
                        sort_order = ?, is_visible = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ? AND site_id = ?
                    """,
                    (
                        clean_text(payload.get("full_name") or current.get("full_name")),
                        clean_text(payload.get("role_title") or current.get("role_title")),
                        clean_text(payload.get("bio") or current.get("bio")),
                        clean_text(payload.get("photo_url") or current.get("photo_url")),
                        clean_text(payload.get("email") or current.get("email")),
                        clean_text(payload.get("phone") or current.get("phone")),
                        int(payload.get("sort_order") or current.get("sort_order") or 0),
                        1 if truthy(payload.get("is_visible", current.get("is_visible"))) else 0,
                        int(professional_id),
                        int(site_id),
                    ),
                )
                conn.commit()
                target_id = int(professional_id)
            else:
                target_id = self._insert_returning_id(
                    conn,
                    """
                    INSERT INTO site_professional (
                        site_id, full_name, role_title, bio, photo_url, email, phone,
                        sort_order, is_visible, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """,
                    (
                        int(site_id),
                        clean_text(payload.get("full_name")),
                        clean_text(payload.get("role_title")),
                        clean_text(payload.get("bio")),
                        clean_text(payload.get("photo_url")),
                        clean_text(payload.get("email")),
                        clean_text(payload.get("phone")),
                        int(payload.get("sort_order") or 0),
                        1 if truthy(payload.get("is_visible", True)) else 0,
                    ),
                )
                conn.commit()
        return self.get_professional(site_id, target_id) or {}

    def delete_professional(self, site_id: int, professional_id: int) -> None:
        self._delete_row("site_professional", site_id=site_id, row_id=professional_id)

    def list_offices(self, site_id: int) -> list[dict[str, Any]]:
        return self._list_rows("site_office", site_id=site_id, order_by="is_primary DESC, name ASC")

    def get_office(self, site_id: int, office_id: int) -> dict[str, Any] | None:
        return self._get_row("site_office", site_id=site_id, row_id=office_id)

    def save_office(self, site_id: int, payload: dict[str, Any], *, office_id: int | None = None) -> dict[str, Any]:
        current = self.get_office(site_id, office_id) if office_id else None
        is_primary = truthy(payload.get("is_primary", current.get("is_primary") if current else False))
        with self._connect() as conn:
            if is_primary:
                if office_id:
                    conn.execute("UPDATE site_office SET is_primary = 0 WHERE site_id = ? AND id <> ?", (int(site_id), int(office_id)))
                else:
                    conn.execute("UPDATE site_office SET is_primary = 0 WHERE site_id = ?", (int(site_id),))
            if current:
                conn.execute(
                    """
                    UPDATE site_office
                    SET name = ?, address = ?, city = ?, province = ?, zip_code = ?, lat = ?, lng = ?,
                        phone = ?, email = ?, opening_hours = ?, map_url = ?, is_primary = ?, is_visible = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ? AND site_id = ?
                    """,
                    (
                        clean_text(payload.get("name") or current.get("name")),
                        clean_text(payload.get("address") or current.get("address")),
                        clean_text(payload.get("city") or current.get("city")),
                        clean_text(payload.get("province") or current.get("province")),
                        clean_text(payload.get("zip_code") or current.get("zip_code")),
                        clean_text(payload.get("lat") or current.get("lat")),
                        clean_text(payload.get("lng") or current.get("lng")),
                        clean_text(payload.get("phone") or current.get("phone")),
                        clean_text(payload.get("email") or current.get("email")),
                        clean_text(payload.get("opening_hours") or current.get("opening_hours")),
                        clean_text(payload.get("map_url") or current.get("map_url")),
                        1 if is_primary else 0,
                        1 if truthy(payload.get("is_visible", current.get("is_visible"))) else 0,
                        int(office_id),
                        int(site_id),
                    ),
                )
                conn.commit()
                target_id = int(office_id)
            else:
                target_id = self._insert_returning_id(
                    conn,
                    """
                    INSERT INTO site_office (
                        site_id, name, address, city, province, zip_code, lat, lng, phone, email,
                        opening_hours, map_url, is_primary, is_visible, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """,
                    (
                        int(site_id),
                        clean_text(payload.get("name")),
                        clean_text(payload.get("address")),
                        clean_text(payload.get("city")),
                        clean_text(payload.get("province")),
                        clean_text(payload.get("zip_code")),
                        clean_text(payload.get("lat")),
                        clean_text(payload.get("lng")),
                        clean_text(payload.get("phone")),
                        clean_text(payload.get("email")),
                        clean_text(payload.get("opening_hours")),
                        clean_text(payload.get("map_url")),
                        1 if is_primary else 0,
                        1 if truthy(payload.get("is_visible", True)) else 0,
                    ),
                )
                conn.commit()
        return self.get_office(site_id, target_id) or {}

    def delete_office(self, site_id: int, office_id: int) -> None:
        self._delete_row("site_office", site_id=site_id, row_id=office_id)

    def list_booking_rules(self, site_id: int, *, active_only: bool = False) -> list[dict[str, Any]]:
        return self._list_rows(
            "site_booking_rule",
            site_id=site_id,
            where="is_active = 1" if active_only else "",
            order_by="weekday ASC, start_time ASC",
        )

    def get_booking_rule(self, site_id: int, rule_id: int) -> dict[str, Any] | None:
        return self._get_row("site_booking_rule", site_id=site_id, row_id=rule_id)

    def save_booking_rule(self, site_id: int, payload: dict[str, Any], *, rule_id: int | None = None) -> dict[str, Any]:
        current = self.get_booking_rule(site_id, rule_id) if rule_id else None
        with self._connect() as conn:
            if current:
                conn.execute(
                    """
                    UPDATE site_booking_rule
                    SET office_id = ?, weekday = ?, start_time = ?, end_time = ?, slot_minutes = ?,
                        max_requests_per_slot = ?, is_active = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ? AND site_id = ?
                    """,
                    (
                        int(payload.get("office_id") or current.get("office_id") or 0),
                        int(payload.get("weekday") or current.get("weekday") or 0),
                        clean_text(payload.get("start_time") or current.get("start_time")),
                        clean_text(payload.get("end_time") or current.get("end_time")),
                        int(payload.get("slot_minutes") or current.get("slot_minutes") or 30),
                        int(payload.get("max_requests_per_slot") or current.get("max_requests_per_slot") or 1),
                        1 if truthy(payload.get("is_active", current.get("is_active"))) else 0,
                        int(rule_id),
                        int(site_id),
                    ),
                )
                conn.commit()
                target_id = int(rule_id)
            else:
                target_id = self._insert_returning_id(
                    conn,
                    """
                    INSERT INTO site_booking_rule (
                        site_id, office_id, weekday, start_time, end_time, slot_minutes,
                        max_requests_per_slot, is_active, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """,
                    (
                        int(site_id),
                        int(payload.get("office_id") or 0),
                        int(payload.get("weekday") or 0),
                        clean_text(payload.get("start_time")),
                        clean_text(payload.get("end_time")),
                        int(payload.get("slot_minutes") or 30),
                        int(payload.get("max_requests_per_slot") or 1),
                        1 if truthy(payload.get("is_active", True)) else 0,
                    ),
                )
                conn.commit()
        return self.get_booking_rule(site_id, target_id) or {}

    def delete_booking_rule(self, site_id: int, rule_id: int) -> None:
        self._delete_row("site_booking_rule", site_id=site_id, row_id=rule_id)

    def list_booking_requests(
        self,
        site_id: int,
        *,
        status: str = "",
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        where = "status = ?" if status else ""
        params = (clean_text(status).lower(),) if status else ()
        return self._list_rows(
            "site_booking_request",
            site_id=site_id,
            where=where,
            params=params,
            order_by="created_at DESC, id DESC",
            limit=limit,
        )

    def get_booking_request(self, site_id: int, booking_request_id: int) -> dict[str, Any] | None:
        return self._get_row("site_booking_request", site_id=site_id, row_id=booking_request_id)

    def available_slots(self, site_id: int, requested_date_iso: str, *, office_id: int | None = None) -> list[dict[str, Any]]:
        return booking_slots_for_date(
            self.list_booking_rules(site_id, active_only=True),
            self.list_booking_requests(site_id, limit=1000),
            requested_date_iso=requested_date_iso,
            office_id=office_id,
        )

    def create_booking_request(self, site_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        with self._connect() as conn:
            request_id = self._insert_returning_id(
                conn,
                """
                INSERT INTO site_booking_request (
                    site_id, office_id, customer_name, customer_email, customer_phone,
                    requested_date, requested_time, subject, notes, privacy_accepted, status,
                    agenda_event_id, reviewed_by, reviewed_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (
                    int(site_id),
                    int(payload.get("office_id")) if payload.get("office_id") not in (None, "") else None,
                    clean_text(payload.get("customer_name")),
                    clean_text(payload.get("customer_email")),
                    clean_text(payload.get("customer_phone")),
                    clean_text(payload.get("requested_date")),
                    clean_text(payload.get("requested_time")),
                    clean_text(payload.get("subject")),
                    clean_text(payload.get("notes")),
                    1 if truthy(payload.get("privacy_accepted")) else 0,
                    clean_text(payload.get("status") or "pending"),
                    clean_text(payload.get("agenda_event_id")),
                    clean_text(payload.get("reviewed_by")),
                    clean_text(payload.get("reviewed_at")),
                ),
            )
            conn.commit()
        return self.get_booking_request(site_id, request_id) or {}

    def update_booking_request(self, site_id: int, booking_request_id: int, **updates: Any) -> dict[str, Any] | None:
        current = self.get_booking_request(site_id, booking_request_id)
        if current is None:
            return None
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE site_booking_request
                SET office_id = ?, customer_name = ?, customer_email = ?, customer_phone = ?,
                    requested_date = ?, requested_time = ?, subject = ?, notes = ?, privacy_accepted = ?,
                    status = ?, agenda_event_id = ?, reviewed_by = ?, reviewed_at = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND site_id = ?
                """,
                (
                    int(updates.get("office_id")) if updates.get("office_id") not in (None, "") else (int(current.get("office_id")) if current.get("office_id") not in (None, "") else None),
                    clean_text(updates.get("customer_name") or current.get("customer_name")),
                    clean_text(updates.get("customer_email") or current.get("customer_email")),
                    clean_text(updates.get("customer_phone") or current.get("customer_phone")),
                    clean_text(updates.get("requested_date") or current.get("requested_date")),
                    clean_text(updates.get("requested_time") or current.get("requested_time")),
                    clean_text(updates.get("subject") or current.get("subject")),
                    clean_text(updates.get("notes") or current.get("notes")),
                    1 if truthy(updates.get("privacy_accepted", current.get("privacy_accepted"))) else 0,
                    clean_text(updates.get("status") or current.get("status")),
                    clean_text(updates.get("agenda_event_id") or current.get("agenda_event_id")),
                    clean_text(updates.get("reviewed_by") or current.get("reviewed_by")),
                    clean_text(updates.get("reviewed_at") or current.get("reviewed_at")),
                    int(booking_request_id),
                    int(site_id),
                ),
            )
            conn.commit()
        return self.get_booking_request(site_id, booking_request_id)

    def list_contact_submissions(self, site_id: int, *, limit: int = 200) -> list[dict[str, Any]]:
        return self._list_rows(
            "site_contact_submission",
            site_id=site_id,
            order_by="created_at DESC, id DESC",
            limit=limit,
        )

    def create_contact_submission(self, site_id: int, payload: dict[str, Any]) -> dict[str, Any] | None:
        with self._connect() as conn:
            submission_id = self._insert_returning_id(
                conn,
                """
                INSERT INTO site_contact_submission (
                    site_id, full_name, email, phone, subject, message, privacy_accepted
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(site_id),
                    clean_text(payload.get("full_name")),
                    clean_text(payload.get("email")),
                    clean_text(payload.get("phone")),
                    clean_text(payload.get("subject")),
                    clean_text(payload.get("message")),
                    1 if truthy(payload.get("privacy_accepted")) else 0,
                ),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM site_contact_submission WHERE id = ? AND site_id = ? LIMIT 1",
                (int(submission_id), int(site_id)),
            ).fetchone()
        return self._row_to_dict(row)

    def site_stats(self, site_id: int) -> dict[str, Any]:
        tables = {
            "pages": "site_page",
            "articles": "site_article",
            "services": "site_service",
            "professionals": "site_professional",
            "offices": "site_office",
            "booking_requests": "site_booking_request",
            "contact_submissions": "site_contact_submission",
        }
        counts: dict[str, Any] = {}
        with self._connect() as conn:
            for key, table in tables.items():
                row = conn.execute(f"SELECT COUNT(*) AS total FROM {table} WHERE site_id = ?", (int(site_id),)).fetchone()
                if isinstance(row, dict):
                    counts[key] = int(row.get("total") or 0)
                else:
                    counts[key] = int((row or [0])[0] or 0)
            pending = conn.execute(
                "SELECT COUNT(*) AS total FROM site_booking_request WHERE site_id = ? AND status = 'pending'",
                (int(site_id),),
            ).fetchone()
        counts["pending_booking_requests"] = int((pending.get("total") if isinstance(pending, dict) else (pending or [0])[0]) or 0)
        return counts

    def platform_stats(self) -> dict[str, Any]:
        with self._connect() as conn:
            site_count = conn.execute("SELECT COUNT(*) AS total FROM site_studio").fetchone()
            published_count = conn.execute("SELECT COUNT(*) AS total FROM site_studio WHERE is_published = 1").fetchone()
            booking_count = conn.execute("SELECT COUNT(*) AS total FROM site_booking_request WHERE status = 'pending'").fetchone()
            contact_count = conn.execute("SELECT COUNT(*) AS total FROM site_contact_submission").fetchone()
        return {
            "sites": int((site_count.get("total") if isinstance(site_count, dict) else (site_count or [0])[0]) or 0),
            "published": int((published_count.get("total") if isinstance(published_count, dict) else (published_count or [0])[0]) or 0),
            "pending_bookings": int((booking_count.get("total") if isinstance(booking_count, dict) else (booking_count or [0])[0]) or 0),
            "contacts": int((contact_count.get("total") if isinstance(contact_count, dict) else (contact_count or [0])[0]) or 0),
        }

    def bootstrap_site_from_profile(
        self,
        *,
        tenant_slug: str,
        defaults: dict[str, Any],
        profile: Any,
    ) -> dict[str, Any]:
        existing = self.get_site_by_tenant_slug(tenant_slug)
        if existing is not None:
            public_slug = clean_text(existing.get("public_slug")) or clean_text(defaults.get("public_slug")) or slugify(defaults.get("site_name"))
        else:
            requested_public_slug = clean_text(defaults.get("public_slug")) or slugify(defaults.get("site_name"))
            public_slug = self._unique_site_slug(requested_public_slug)
        seeded_defaults = dict(defaults)
        seeded_defaults["public_slug"] = public_slug
        return self.ensure_site(
            tenant_slug,
            defaults=seeded_defaults,
            page_seed=default_page_seed(profile, public_slug),
            professional_seed=default_professional_seed(profile),
            office_seed=default_office_seed(profile),
            article_seed=default_article_seed(profile),
        )
