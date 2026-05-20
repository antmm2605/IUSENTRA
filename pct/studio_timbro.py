"""Configurazione e rendering del timbro/intestazione dello studio.

Il timbro e' tenant-aware perche' il chiamante passa sempre il percorso dati
risolto per lo studio corrente. I dati vengono normalizzati qui e poi usati da
renderer Jinja, compilatore atti, PDF e API React senza hardcoding.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from html import escape
import json
import os
from pathlib import Path
import sqlite3
from typing import Any

from pct.postgres_runtime_support import PostgresRepositoryBackend, resolve_runtime_postgres_dsn


SCHEMA_STUDIO_TIMBRO = Path(__file__).with_name("sql") / "20260512_studio_timbro.sql"
POSTGRES_SCHEMA_STUDIO_TIMBRO = Path(__file__).with_name("sql") / "20260512_studio_timbro_postgres.sql"

DEFAULT_LAYOUT: dict[str, Any] = {
    "posizione": "top_left",
    "allineamento": "left",
    "margine_alto_mm": 18,
    "margine_sinistro_mm": 18,
    "margine_basso_mm": 10,
    "larghezza_blocco_mm": 82,
    "interlinea": 1.22,
    "font_per_riga": ["Helvetica-Bold", "Helvetica", "Helvetica", "Helvetica", "Helvetica", "Helvetica"],
    "dimensione_per_riga": [13, 10, 9, 9, 9, 9],
    "grassetto_per_riga": [True, False, False, False, False, False],
    "corsivo_per_riga": [False, False, False, False, False, False],
}

DEFAULT_FLAGS: dict[str, bool] = {
    "applica_a_tutti_i_modelli": True,
    "applica_solo_prima_pagina": False,
    "applica_tutte_le_pagine": True,
    "mostra_su_atti_interni": True,
    "mostra_su_stragiudiziali": True,
    "mostra_su_depositabili": True,
}

TEXT_FIELDS = (
    "studio_nome",
    "studio_sottotitolo",
    "professionista_nome",
    "qualifiche_professionali",
    "indirizzo_riga",
    "cap_citta_provincia",
    "telefono",
    "fax",
    "codice_fiscale",
    "partita_iva",
    "pec",
    "email",
    "sito_web",
    "foro",
)


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _as_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "si", "yes", "on"}


def _as_int(value: Any, default: int, *, min_value: int = 0, max_value: int = 72) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(min_value, min(max_value, parsed))


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value in (None, ""):
        return []
    return [value]


def _style_at(values: list[Any], index: int, default: Any) -> Any:
    return values[index] if index < len(values) and values[index] not in (None, "") else default


def _studio_section(config_studio: Any) -> Any:
    return getattr(config_studio, "studio", None) if config_studio is not None else None


def _pec_section(config_studio: Any) -> Any:
    return getattr(config_studio, "pec", None) if config_studio is not None else None


def default_timbro_payload(
    *,
    config_studio: Any = None,
    app_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Crea default dinamici dai dati studio gia configurati, senza dati personali hardcoded."""
    app_config = app_config or {}
    studio = _studio_section(config_studio)
    pec = _pec_section(config_studio)
    citta = _clean(getattr(studio, "city", "") if studio else app_config.get("PCT_STUDIO_CITY", ""))
    provincia = _clean(getattr(studio, "province", "") if studio else app_config.get("PCT_STUDIO_PROVINCE", ""))
    cap_citta = " ".join(part for part in [citta, f"({provincia})" if provincia else ""] if part).strip()
    ordine = _clean(getattr(studio, "ordine_avvocati", "") if studio else app_config.get("STUDIO_ORDINE_AVVOCATI", ""))
    numero_albo = _clean(
        getattr(studio, "numero_iscrizione_albo", "")
        if studio
        else app_config.get("STUDIO_NUMERO_ISCRIZIONE_ALBO", "")
    )
    qualifiche = " - ".join(part for part in [ordine, f"n. {numero_albo}" if numero_albo else ""] if part)
    payload = {
        "studio_nome": _clean(getattr(studio, "nome", "") if studio else app_config.get("STUDIO_NOME", ""))
        or _clean(app_config.get("STUDIO_NOME", "")),
        "studio_sottotitolo": "",
        "professionista_nome": _clean(getattr(studio, "avvocato", "") if studio else app_config.get("STUDIO_AVVOCATO", "")),
        "qualifiche_professionali": qualifiche,
        "indirizzo_riga": _clean(getattr(studio, "indirizzo", "") if studio else app_config.get("STUDIO_INDIRIZZO", "")),
        "cap_citta_provincia": cap_citta,
        "telefono": _clean(getattr(studio, "telefono", "") if studio else app_config.get("PCT_STUDIO_TELEFONO", "")),
        "fax": "",
        "codice_fiscale": _clean(getattr(studio, "cf", "") if studio else app_config.get("STUDIO_CF", "")),
        "partita_iva": _clean(getattr(studio, "piva", "") if studio else app_config.get("STUDIO_PIVA", "")),
        "pec": _clean(getattr(pec, "indirizzo", "") if pec else app_config.get("PCT_STUDIO_PEC", "")),
        "email": _clean(getattr(studio, "email", "") if studio else app_config.get("SMTP_FROM", "")),
        "sito_web": _clean(getattr(studio, "sito_web", "") if studio else app_config.get("PCT_STUDIO_SITO", "")),
        "foro": ordine,
        "righe_extra": [],
        "layout": dict(DEFAULT_LAYOUT),
        **DEFAULT_FLAGS,
    }
    return normalize_timbro_payload(payload)


def normalize_timbro_payload(payload: dict[str, Any] | None, *, defaults: dict[str, Any] | None = None) -> dict[str, Any]:
    defaults = normalize_timbro_payload(defaults, defaults={}) if defaults else {}
    raw = dict(payload or {})
    result: dict[str, Any] = {}
    for field_name in TEXT_FIELDS:
        result[field_name] = _clean(raw.get(field_name, defaults.get(field_name, "")))
    result["righe_extra"] = [_clean(item) for item in _as_list(raw.get("righe_extra", defaults.get("righe_extra", []))) if _clean(item)]
    layout_raw = raw.get("layout", defaults.get("layout", {}))
    layout_raw = layout_raw if isinstance(layout_raw, dict) else {}
    flat_layout_aliases = {
        "layout_posizione": "posizione",
        "layout_allineamento": "allineamento",
        "margine_top_mm": "margine_alto_mm",
        "margine_left_mm": "margine_sinistro_mm",
        "margine_bottom_after_timbro_mm": "margine_basso_mm",
        "larghezza_blocco_mm": "larghezza_blocco_mm",
        "line_spacing": "interlinea",
        "font_family": "font_per_riga",
    }
    for raw_key, layout_key in flat_layout_aliases.items():
        if raw.get(raw_key) not in (None, ""):
            layout_raw[layout_key] = raw[raw_key]
    layout = dict(DEFAULT_LAYOUT)
    layout.update({key: value for key, value in layout_raw.items() if key in DEFAULT_LAYOUT})
    layout["posizione"] = "top_left"
    layout["allineamento"] = "left"
    layout["margine_alto_mm"] = _as_int(layout.get("margine_alto_mm"), DEFAULT_LAYOUT["margine_alto_mm"], min_value=0, max_value=60)
    layout["margine_sinistro_mm"] = _as_int(layout.get("margine_sinistro_mm"), DEFAULT_LAYOUT["margine_sinistro_mm"], min_value=0, max_value=60)
    layout["margine_basso_mm"] = _as_int(layout.get("margine_basso_mm"), DEFAULT_LAYOUT["margine_basso_mm"], min_value=0, max_value=60)
    layout["larghezza_blocco_mm"] = _as_int(layout.get("larghezza_blocco_mm"), DEFAULT_LAYOUT["larghezza_blocco_mm"], min_value=40, max_value=140)
    try:
        line_spacing = float(layout.get("interlinea", DEFAULT_LAYOUT["interlinea"]))
    except (TypeError, ValueError):
        line_spacing = DEFAULT_LAYOUT["interlinea"]
    layout["interlinea"] = max(1.0, min(1.8, line_spacing))
    layout["font_per_riga"] = [_clean(item) or "Helvetica" for item in _as_list(layout.get("font_per_riga"))]
    layout["dimensione_per_riga"] = [
        _as_int(item, 9, min_value=7, max_value=18) for item in _as_list(layout.get("dimensione_per_riga"))
    ]
    layout["grassetto_per_riga"] = [_as_bool(item) for item in _as_list(layout.get("grassetto_per_riga"))]
    layout["corsivo_per_riga"] = [_as_bool(item) for item in _as_list(layout.get("corsivo_per_riga"))]
    result["layout"] = layout
    result["layout_posizione"] = layout["posizione"]
    result["layout_allineamento"] = layout["allineamento"]
    result["margine_top_mm"] = layout["margine_alto_mm"]
    result["margine_left_mm"] = layout["margine_sinistro_mm"]
    result["margine_bottom_after_timbro_mm"] = layout["margine_basso_mm"]
    result["larghezza_blocco_mm"] = layout["larghezza_blocco_mm"]
    result["line_spacing"] = layout["interlinea"]
    result["font_family"] = _clean(_style_at(_as_list(layout.get("font_per_riga")), 0, "Helvetica")) or "Helvetica"
    result["font_size_studio_nome"] = _as_int(_style_at(_as_list(layout.get("dimensione_per_riga")), 0, 13), 13, min_value=7, max_value=18)
    result["font_size_righe"] = _as_int(_style_at(_as_list(layout.get("dimensione_per_riga")), 1, 9), 9, min_value=7, max_value=18)
    for key, default in DEFAULT_FLAGS.items():
        result[key] = _as_bool(raw.get(key, defaults.get(key, default)), default)
    return result


@dataclass
class StudioTimbro:
    payload: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_payload(cls, payload: dict[str, Any] | None, *, defaults: dict[str, Any] | None = None) -> "StudioTimbro":
        return cls(normalize_timbro_payload(payload, defaults=defaults))

    def to_payload(self) -> dict[str, Any]:
        return normalize_timbro_payload(self.payload)

    @property
    def enabled(self) -> bool:
        return bool(self.payload.get("applica_a_tutti_i_modelli", True) and self.to_lines())

    def to_lines(self) -> list[dict[str, Any]]:
        payload = self.to_payload()
        raw_lines: list[tuple[str, str]] = []
        studio_nome = _clean(payload.get("studio_nome"))
        if studio_nome:
            first_line = studio_nome.upper()
            if not first_line.startswith("STUDIO"):
                first_line = f"STUDIO LEGALE {first_line}".upper()
            raw_lines.append((first_line, "studio_nome"))
        for key in ("studio_sottotitolo", "professionista_nome", "qualifiche_professionali"):
            value = _clean(payload.get(key))
            if value:
                raw_lines.append((value, key))
        address_parts = [_clean(payload.get("indirizzo_riga")), _clean(payload.get("cap_citta_provincia"))]
        if any(address_parts):
            raw_lines.append((" - ".join(part for part in address_parts if part), "indirizzo"))
        fiscal = []
        if payload.get("codice_fiscale"):
            fiscal.append(f"C.F. {payload['codice_fiscale']}")
        if payload.get("partita_iva"):
            fiscal.append(f"P. IVA {payload['partita_iva']}")
        if fiscal:
            raw_lines.append((" - ".join(fiscal), "fiscale"))
        contacts = []
        if payload.get("telefono"):
            contacts.append(f"Tel. {payload['telefono']}")
        if payload.get("fax"):
            contacts.append(f"Fax {payload['fax']}")
        if payload.get("pec"):
            contacts.append(f"PEC {payload['pec']}")
        if payload.get("email"):
            contacts.append(f"Email {payload['email']}")
        if payload.get("sito_web"):
            contacts.append(payload["sito_web"])
        if contacts:
            raw_lines.append((" - ".join(contacts), "recapiti"))
        for line in payload.get("righe_extra") or []:
            if _clean(line):
                raw_lines.append((_clean(line), "righe_extra"))

        layout = payload["layout"]
        fonts = _as_list(layout.get("font_per_riga"))
        sizes = _as_list(layout.get("dimensione_per_riga"))
        bold = _as_list(layout.get("grassetto_per_riga"))
        italic = _as_list(layout.get("corsivo_per_riga"))
        lines: list[dict[str, Any]] = []
        for index, (text, source) in enumerate(raw_lines):
            lines.append(
                {
                    "text": text,
                    "source": source,
                    "align": "left",
                    "font": _clean(_style_at(fonts, index, "Helvetica")) or "Helvetica",
                    "size": _as_int(_style_at(sizes, index, 9), 9, min_value=7, max_value=18),
                    "bold": _as_bool(_style_at(bold, index, index == 0), index == 0),
                    "italic": _as_bool(_style_at(italic, index, False), False),
                }
            )
        return lines

    def to_text(self) -> str:
        return "\n".join(line["text"] for line in self.to_lines()).strip()

    def to_html(self) -> str:
        lines = self.to_lines()
        if not lines:
            return ""
        html_lines = []
        for line in lines:
            weight = "700" if line.get("bold") else "400"
            style = (
                "text-align: left;"
                f"font-size:{int(line.get('size') or 9)}pt;"
                f"font-weight:{weight};"
                f"font-style:{'italic' if line.get('italic') else 'normal'};"
                f"line-height:{float(self.payload.get('layout', {}).get('interlinea', 1.22)):.2f};"
                "margin:0;"
            )
            html_lines.append(f'<p style="{style}">{escape(line["text"])}</p>')
        return (
            '<div class="iusentra-studio-timbro" data-studio-timbro="true" '
            'style="text-align: left;margin:0 0 1.1rem 0;max-width:82mm;">'
            + "".join(html_lines)
            + "</div>"
        )

    def to_docx_header(self) -> dict[str, Any]:
        placement = self.to_stamp_placement()
        return {
            "position": "top_left",
            "alignment": "left",
            "repeat_on_each_page": True,
            "align_within_box": placement["align_within_box"],
            "lines": self.to_lines(),
            "scope": self.scope_payload(),
            "placement": placement,
        }

    def to_stamp_placement(self) -> dict[str, Any]:
        payload = self.to_payload()
        layout = payload.get("layout") if isinstance(payload.get("layout"), dict) else {}
        line_count = max(1, len(self.to_lines()))
        font_size = _as_int(_style_at(_as_list(layout.get("dimensione_per_riga")), 0, 11), 11, min_value=7, max_value=18)
        box_height = max(18, int(line_count * font_size * float(layout.get("interlinea", 1.22)) * 0.36) + 6)
        return {
            "position": "top_left",
            "repeat_on_each_page": True,
            "align_within_box": "center",
            "line_align": "left",
            "margin_top_mm": int(payload.get("margine_top_mm") or layout.get("margine_alto_mm") or DEFAULT_LAYOUT["margine_alto_mm"]),
            "margin_left_mm": int(payload.get("margine_left_mm") or layout.get("margine_sinistro_mm") or DEFAULT_LAYOUT["margine_sinistro_mm"]),
            "box_width_mm": int(payload.get("larghezza_blocco_mm") or layout.get("larghezza_blocco_mm") or DEFAULT_LAYOUT["larghezza_blocco_mm"]),
            "box_height_mm": box_height,
            "bottom_gap_mm": int(payload.get("margine_bottom_after_timbro_mm") or layout.get("margine_basso_mm") or DEFAULT_LAYOUT["margine_basso_mm"]),
            "avoid_overlap": True,
        }

    def to_pdf_flowable(self, styles: Any = None) -> list[Any]:
        try:
            from reportlab.lib.enums import TA_LEFT
            from reportlab.platypus import Paragraph, Spacer
            from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
            from reportlab.lib.units import mm
        except ImportError:
            return []
        base_styles = styles or getSampleStyleSheet()
        flowables: list[Any] = []
        for index, line in enumerate(self.to_lines()):
            font = "Helvetica-Bold" if line.get("bold") else "Helvetica"
            style = ParagraphStyle(
                f"studio_timbro_{index}",
                parent=base_styles["Normal"],
                fontName=font,
                fontSize=int(line.get("size") or 9),
                leading=max(8, int((int(line.get("size") or 9)) * float(self.payload.get("layout", {}).get("interlinea", 1.22)))),
                alignment=TA_LEFT,
                spaceAfter=1,
            )
            flowables.append(Paragraph(escape(line["text"]), style))
        if flowables:
            flowables.append(Spacer(1, int(self.payload.get("layout", {}).get("margine_basso_mm", 10)) * mm))
        return flowables

    def scope_payload(self) -> dict[str, Any]:
        payload = self.to_payload()
        return {key: payload[key] for key in DEFAULT_FLAGS}


class StudioTimbroRepository:
    def __init__(self, db_path: str, *, postgres_dsn: str = "") -> None:
        self.db_path = str(db_path or "./config/studio_timbro.db")
        self.postgres_dsn = resolve_runtime_postgres_dsn(postgres_dsn)
        self._postgres = (
            PostgresRepositoryBackend(self.postgres_dsn, POSTGRES_SCHEMA_STUDIO_TIMBRO)
            if self.postgres_dsn
            else None
        )
        self._ensure_schema()

    def _connect(self):
        if self._postgres:
            return self._postgres.connection()
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        if self._postgres:
            return
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(SCHEMA_STUDIO_TIMBRO.read_text(encoding="utf-8"))
            conn.commit()

    def load_payload(self, *, profile_id: str = "default", defaults: dict[str, Any] | None = None) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload_json FROM studio_timbro WHERE profile_id = ?",
                (profile_id,),
            ).fetchone()
        if not row:
            return normalize_timbro_payload(defaults or {})
        try:
            raw = json.loads(row["payload_json"])
        except Exception:
            raw = {}
        return normalize_timbro_payload(raw, defaults=defaults)

    def load(self, *, profile_id: str = "default", defaults: dict[str, Any] | None = None) -> StudioTimbro:
        return StudioTimbro.from_payload(self.load_payload(profile_id=profile_id, defaults=defaults))

    def save_payload(self, payload: dict[str, Any], *, profile_id: str = "default", defaults: dict[str, Any] | None = None) -> dict[str, Any]:
        normalized = normalize_timbro_payload(payload, defaults=defaults)
        encoded = json.dumps(normalized, ensure_ascii=False, sort_keys=True)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO studio_timbro(profile_id, payload_json, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(profile_id) DO UPDATE SET
                    payload_json = excluded.payload_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (profile_id, encoded),
            )
            conn.commit()
        return normalized


def build_studio_timbro(
    *,
    db_path: str,
    config_studio: Any = None,
    app_config: dict[str, Any] | None = None,
    postgres_dsn: str = "",
) -> StudioTimbro:
    defaults = default_timbro_payload(config_studio=config_studio, app_config=app_config)
    return StudioTimbroRepository(db_path, postgres_dsn=postgres_dsn).load(defaults=defaults)


def save_studio_timbro(
    payload: dict[str, Any],
    *,
    db_path: str,
    config_studio: Any = None,
    app_config: dict[str, Any] | None = None,
    postgres_dsn: str = "",
) -> dict[str, Any]:
    defaults = default_timbro_payload(config_studio=config_studio, app_config=app_config)
    return StudioTimbroRepository(db_path, postgres_dsn=postgres_dsn).save_payload(payload, defaults=defaults)


def _payload_to_timbro(value: Any) -> StudioTimbro:
    if isinstance(value, StudioTimbro):
        return value
    if isinstance(value, dict):
        return StudioTimbro.from_payload(value)
    return StudioTimbro.from_payload({})


def inject_timbro_text(content: str, timbro: Any, *, enabled: bool = True) -> str:
    if not enabled:
        return (content or "").strip()
    resolved = _payload_to_timbro(timbro)
    if not resolved.enabled:
        return (content or "").strip()
    text = resolved.to_text()
    body = (content or "").strip()
    if not text:
        return body
    first_line = text.splitlines()[0].strip()
    if body.startswith(first_line):
        return body
    return f"{text}\n\n{body}".strip()


def inject_timbro_html(content: str, timbro: Any, *, enabled: bool = True) -> str:
    if not enabled:
        return content or ""
    resolved = _payload_to_timbro(timbro)
    if not resolved.enabled:
        return content or ""
    stamp = resolved.to_html()
    body = content or ""
    if 'data-studio-timbro="true"' in body:
        return body
    return f"{stamp}\n{body}".strip()


__all__ = [
    "DEFAULT_LAYOUT",
    "StudioTimbro",
    "StudioTimbroRepository",
    "build_studio_timbro",
    "default_timbro_payload",
    "inject_timbro_html",
    "inject_timbro_text",
    "normalize_timbro_payload",
    "save_studio_timbro",
]
