"""Ricostruzione tabellare dai token OCR (griglia da coordinate) → CSV/HTML.

Non richiede motori OCR né OpenCV: lavora sui token già prodotti (testo + bbox).
Le righe si individuano raggruppando i token per banda verticale (centro Y),
le colonne raggruppando i bordi sinistri (X) in cluster. È un'euristica
deterministica e testabile; per griglie con linee disegnate il rilevamento
visivo (OpenCV) resta un miglioramento futuro lato motore.
"""

from __future__ import annotations

import csv
import html
import io
from typing import Any


def _num(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _bbox(token: dict[str, Any]) -> tuple[float, float, float, float]:
    bbox = token.get("bbox") or [0, 0, 0, 0]
    left = _num(bbox[0] if len(bbox) > 0 else 0)
    top = _num(bbox[1] if len(bbox) > 1 else 0)
    width = _num(bbox[2] if len(bbox) > 2 else 0)
    height = _num(bbox[3] if len(bbox) > 3 else 0)
    return left, top, width, height


def _cluster(values: list[float], tolerance: float) -> list[float]:
    """Raggruppa valori vicini entro `tolerance` e ritorna i centri ordinati."""

    if not values:
        return []
    ordered = sorted(values)
    centers: list[float] = []
    bucket = [ordered[0]]
    for value in ordered[1:]:
        if value - bucket[-1] <= tolerance:
            bucket.append(value)
        else:
            centers.append(sum(bucket) / len(bucket))
            bucket = [value]
    centers.append(sum(bucket) / len(bucket))
    return centers


def _nearest(centers: list[float], value: float) -> int:
    best_index = 0
    best_dist = None
    for index, center in enumerate(centers):
        dist = abs(center - value)
        if best_dist is None or dist < best_dist:
            best_dist = dist
            best_index = index
    return best_index


def reconstruct_table(tokens: list[dict[str, Any]], *, page: int | None = None) -> dict[str, Any] | None:
    """Ricostruisce una tabella da una lista di token (di una pagina).

    Ritorna ``{"rows": [[cell, ...], ...], "n_rows", "n_cols", "page"}`` oppure
    ``None`` se non c'è abbastanza struttura (meno di 2 righe o 2 colonne).
    """

    usable = [t for t in tokens or [] if str(t.get("token") or "").strip()]
    if len(usable) < 4:
        return None

    boxes = [_bbox(t) for t in usable]
    heights = [h for _, _, _, h in boxes if h > 0]
    widths = [w for _, _, w, _ in boxes if w > 0]
    row_tol = (sum(heights) / len(heights) * 0.6) if heights else 6.0
    # Soglia di gap colonna: separa le colonne (gap ampio) ma unisce le parole
    # della stessa cella (gap stretto). Basata sulla larghezza media dei token.
    col_gap = (sum(widths) / len(widths) * 0.8) if widths else 12.0

    row_centers = _cluster([top + height / 2 for (_, top, _, height) in boxes], row_tol)
    # Colonne come "bande occupate": fondo gli intervalli [left, left+width] dei
    # token quando distano meno di col_gap (così le celle multi-parola restano unite).
    intervals = sorted((left, left + max(width, 1.0)) for (left, _, width, _) in boxes)
    bands: list[list[float]] = []
    for left, right in intervals:
        if bands and left - bands[-1][1] <= col_gap:
            bands[-1][1] = max(bands[-1][1], right)
        else:
            bands.append([left, right])
    if len(row_centers) < 2 or len(bands) < 2:
        return None

    band_centers = [(band[0] + band[1]) / 2 for band in bands]

    def _col_of(left: float, width: float) -> int:
        center = left + width / 2
        for index, (band_left, band_right) in enumerate(bands):
            if band_left - col_gap <= center <= band_right + col_gap:
                return index
        return _nearest(band_centers, center)

    grid: dict[tuple[int, int], list[tuple[float, str]]] = {}
    for token, (left, top, width, height) in zip(usable, boxes):
        r = _nearest(row_centers, top + height / 2)
        c = _col_of(left, width)
        grid.setdefault((r, c), []).append((left, str(token.get("token") or "")))

    rows: list[list[str]] = []
    for r in range(len(row_centers)):
        row: list[str] = []
        for c in range(len(bands)):
            cell_tokens = sorted(grid.get((r, c), []), key=lambda item: item[0])
            row.append(" ".join(text for _, text in cell_tokens).strip())
        rows.append(row)

    # Scarta righe completamente vuote (rumore di clustering).
    rows = [row for row in rows if any(cell for cell in row)]
    if len(rows) < 2:
        return None
    return {"rows": rows, "n_rows": len(rows), "n_cols": len(bands), "page": page}


def reconstruct_tables(tokens: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Ricostruisce una tabella per pagina (euristica conservativa)."""

    by_page: dict[int, list[dict[str, Any]]] = {}
    for token in tokens or []:
        try:
            page = int(token.get("page", 1))
        except (TypeError, ValueError):
            page = 1
        by_page.setdefault(page, []).append(token)
    tables: list[dict[str, Any]] = []
    for page in sorted(by_page):
        table = reconstruct_table(by_page[page], page=page)
        if table:
            tables.append(table)
    return tables


def table_to_csv(table: dict[str, Any]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    for row in table.get("rows") or []:
        writer.writerow(row)
    return buffer.getvalue()


def table_to_html(table: dict[str, Any]) -> str:
    rows = table.get("rows") or []
    parts = ['<table border="1">']
    for index, row in enumerate(rows):
        tag = "th" if index == 0 else "td"
        cells = "".join(f"<{tag}>{html.escape(str(cell))}</{tag}>" for cell in row)
        parts.append(f"<tr>{cells}</tr>")
    parts.append("</table>")
    return "".join(parts)


__all__ = [
    "reconstruct_table",
    "reconstruct_tables",
    "table_to_csv",
    "table_to_html",
]
