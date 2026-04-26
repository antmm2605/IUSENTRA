"""Gestione asset del Sito Studio Builder."""

from __future__ import annotations

import mimetypes
import os
from html import escape
from datetime import datetime
from pathlib import Path
from typing import Any

from flask import current_app, url_for
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from pct.studio_site import clean_text
from web.services.studio_site_runtime import (
    ALLOWED_SITE_IMAGE_EXTENSIONS,
    site_assets_dir,
    studio_site_repository,
)


DEFAULT_MAX_IMAGE_MB = 5


def _max_image_bytes() -> int:
    raw = os.environ.get("IUSENTRA_AI_IMAGE_MAX_SIZE_MB") or current_app.config.get("SITE_STUDIO_IMAGE_MAX_SIZE_MB")
    try:
        value = float(raw or DEFAULT_MAX_IMAGE_MB)
    except Exception:
        value = DEFAULT_MAX_IMAGE_MB
    return int(max(value, 1) * 1024 * 1024)


def _asset_url(site: dict[str, Any], filename: str) -> str:
    return url_for(
        "studio_site_public.asset",
        public_slug=str(site.get("public_slug") or ""),
        filename=filename,
    )


def _safe_asset_filename(prefix: str, original_filename: str) -> str:
    original = secure_filename(original_filename or "immagine.png")
    extension = Path(original).suffix.lower()
    if extension not in ALLOWED_SITE_IMAGE_EXTENSIONS:
        raise ValueError("Formato immagine non supportato. Usa PNG, JPG, WEBP, SVG o ICO.")
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
    stem = secure_filename(Path(original).stem) or "asset"
    return f"{clean_text(prefix) or 'asset'}-{timestamp}-{stem}{extension}"


def save_builder_asset(site: dict[str, Any], file_storage: FileStorage, *, payload: dict[str, Any]) -> dict[str, Any]:
    if file_storage is None or not getattr(file_storage, "filename", ""):
        raise ValueError("Seleziona un'immagine da caricare.")
    filename = _safe_asset_filename("asset", file_storage.filename or "")
    target_dir = site_assets_dir(str(site.get("public_slug") or ""))
    target_path = (target_dir / filename).resolve()
    file_storage.save(str(target_path))
    size_bytes = target_path.stat().st_size if target_path.exists() else 0
    if size_bytes > _max_image_bytes():
        target_path.unlink(missing_ok=True)
        raise ValueError("Immagine troppo grande per il sito pubblico.")
    title = clean_text(payload.get("title")) or clean_text(Path(file_storage.filename or "").stem)
    alt_text = clean_text(payload.get("alt_text"))
    if not alt_text:
        raise ValueError("Inserisci un testo alternativo: e' obbligatorio per le immagini pubbliche.")
    asset_payload = {
        "filename": filename,
        "original_filename": file_storage.filename or filename,
        "url": _asset_url(site, filename),
        "title": title,
        "alt_text": alt_text,
        "caption": clean_text(payload.get("caption")),
        "category": clean_text(payload.get("category")) or "generale",
        "size_bytes": size_bytes,
        "mime_type": file_storage.mimetype or mimetypes.guess_type(filename)[0] or "",
        "width": 0,
        "height": 0,
    }
    return studio_site_repository().create_asset(int(site["id"]), asset_payload)


def create_generated_svg_asset(
    site: dict[str, Any],
    *,
    title: str,
    alt_text: str,
    caption: str = "",
    category: str = "redazione_ai",
) -> dict[str, Any]:
    safe_title = clean_text(title) or "Immagine articolo"
    safe_alt = clean_text(alt_text) or safe_title
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
    filename = f"ai-{timestamp}.svg"
    target_dir = site_assets_dir(str(site.get("public_slug") or ""))
    target_path = (target_dir / filename).resolve()
    svg_title = escape(safe_title[:54])
    svg_alt = escape(safe_alt)
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="675" viewBox="0 0 1200 675" role="img" aria-label="{svg_alt}">
  <defs>
    <linearGradient id="g" x1="0" x2="1" y1="0" y2="1">
      <stop offset="0" stop-color="#0f172a"/>
      <stop offset="0.62" stop-color="#1d4ed8"/>
      <stop offset="1" stop-color="#b8860b"/>
    </linearGradient>
  </defs>
  <rect width="1200" height="675" fill="url(#g)"/>
  <circle cx="1030" cy="110" r="150" fill="rgba(255,255,255,.12)"/>
  <circle cx="140" cy="590" r="190" fill="rgba(255,255,255,.10)"/>
  <rect x="120" y="145" width="960" height="385" rx="34" fill="rgba(255,255,255,.12)" stroke="rgba(255,255,255,.35)"/>
  <text x="170" y="300" fill="#ffffff" font-family="Georgia, serif" font-size="54" font-weight="700">{svg_title}</text>
  <text x="170" y="365" fill="rgba(255,255,255,.86)" font-family="Arial, sans-serif" font-size="28">Approfondimento dello studio legale</text>
  <path d="M170 432h280" stroke="#facc15" stroke-width="8" stroke-linecap="round"/>
</svg>"""
    target_path.write_text(svg, encoding="utf-8")
    return studio_site_repository().create_asset(
        int(site["id"]),
        {
            "filename": filename,
            "original_filename": filename,
            "url": _asset_url(site, filename),
            "title": safe_title,
            "alt_text": safe_alt,
            "caption": caption,
            "category": category,
            "size_bytes": target_path.stat().st_size,
            "mime_type": "image/svg+xml",
            "width": 1200,
            "height": 675,
        },
    )


def delete_builder_asset(site: dict[str, Any], asset_id: int) -> None:
    repo = studio_site_repository()
    asset = repo.get_asset(int(site["id"]), int(asset_id))
    if asset is None:
        raise ValueError("Immagine non trovata.")
    filename = clean_text(asset.get("filename"))
    if filename:
        target_dir = site_assets_dir(str(site.get("public_slug") or ""))
        target_path = (target_dir / Path(filename).name).resolve()
        if target_dir in target_path.parents or target_path.parent == target_dir:
            target_path.unlink(missing_ok=True)
    repo.delete_asset(int(site["id"]), int(asset_id))
