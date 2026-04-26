from __future__ import annotations

import io
import re
from datetime import datetime
from typing import Any

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover - fallback difensivo
    ZoneInfo = None  # type: ignore[assignment]

CM_TO_PT = 28.35
VISIBLE_SIGNATURE_MODE_LATERALE = "laterale"
VISIBLE_SIGNATURE_MODE_BASSO_SINISTRA = "basso_sinistra"
VISIBLE_SIGNATURE_MODE_BASSO_DESTRA = "basso_destra"
VISIBLE_SIGNATURE_MODES = {
    VISIBLE_SIGNATURE_MODE_LATERALE,
    VISIBLE_SIGNATURE_MODE_BASSO_SINISTRA,
    VISIBLE_SIGNATURE_MODE_BASSO_DESTRA,
}
VISIBLE_SIGNATURE_PREFIX = "Firmato digitalmente da"
VISIBLE_SIGNATURE_DATE_LABEL = "Data e ora firma:"
VISIBLE_SIGNATURE_METADATA_KEY = "/HACSSignatureStamp"
ITALY_TIMEZONE = ZoneInfo("Europe/Rome") if ZoneInfo else None


def normalize_visible_signature_mode(value: Any) -> str:
    mode = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        VISIBLE_SIGNATURE_MODE_LATERALE: {
            "laterale",
            "side",
            "verticale",
            "margine",
            "margine_destro",
            "laterale_dx",
        },
        VISIBLE_SIGNATURE_MODE_BASSO_SINISTRA: {
            "basso_sinistra",
            "bottom_left",
            "left",
            "sinistra",
            "sx",
            "basso_sx",
        },
        VISIBLE_SIGNATURE_MODE_BASSO_DESTRA: {
            "basso_destra",
            "bottom_right",
            "right",
            "destra",
            "dx",
            "basso_dx",
        },
    }
    for normalized, values in aliases.items():
        if mode in values:
            return normalized
    return VISIBLE_SIGNATURE_MODE_LATERALE


def compute_visible_signature_layout(
    *,
    width: float,
    height: float,
    mode: str,
    margin: float = CM_TO_PT,
) -> dict[str, float | str | int]:
    """Calcola coordinate sicure per la firma visibile su pagine di qualsiasi formato."""
    page_width = max(float(width or 0), 1.0)
    page_height = max(float(height or 0), 1.0)
    shortest_side = max(min(page_width, page_height), 1.0)
    safe_margin = min(max(float(margin or CM_TO_PT), 12.0), max(shortest_side / 4, 12.0))
    resolved_mode = normalize_visible_signature_mode(mode)
    available_width = max(page_width - (safe_margin * 2), 1.0)
    available_height = max(page_height - (safe_margin * 2), 1.0)

    if resolved_mode in {VISIBLE_SIGNATURE_MODE_BASSO_SINISTRA, VISIBLE_SIGNATURE_MODE_BASSO_DESTRA}:
        box_width = min(440.0, available_width)
        box_height = min(102.0, available_height)
        x = safe_margin
        if resolved_mode == VISIBLE_SIGNATURE_MODE_BASSO_DESTRA:
            x = max(safe_margin, page_width - box_width - safe_margin)
        y = safe_margin
        return {
            "x": x,
            "y": y,
            "box_width": box_width,
            "box_height": box_height,
            "align": "left" if resolved_mode == VISIBLE_SIGNATURE_MODE_BASSO_SINISTRA else "right",
            "rotation": 0,
            "mode": resolved_mode,
        }

    side_width = min(max(CM_TO_PT * 1.85, min(42.0, available_width)), available_width)
    side_height = available_height
    return {
        "x": max(safe_margin, page_width - side_width - safe_margin),
        "y": safe_margin,
        "box_width": side_width,
        "box_height": side_height,
        "align": "left",
        "rotation": 90,
        "mode": VISIBLE_SIGNATURE_MODE_LATERALE,
    }


def _normalize_visible_signature_place(value: str = "") -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""

    normalized = re.sub(r"\([^)]*\)", "", raw)
    normalized = re.sub(r"\b\d{5}\b", "", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip(" ,;-")
    if not normalized:
        return ""

    if normalized.upper() == normalized:
        normalized = normalized.title()

    return normalized[:48]


def resolve_visible_signature_place(*, city: str = "", province: str = "", address: str = "") -> str:
    city_value = _normalize_visible_signature_place(city)
    if city_value:
        return city_value

    address_value = str(address or "").strip()
    if not address_value:
        return ""

    parts = [part.strip() for part in re.split(r"[;,|-]", address_value) if part.strip()]
    if not parts:
        return ""

    candidate = re.sub(r"^\d{5}\s+", "", parts[-1]).strip()
    candidate = _normalize_visible_signature_place(candidate)
    if candidate:
        return candidate

    province_value = _normalize_visible_signature_place(province)
    if province_value:
        return province_value
    return ""


def format_visible_signature_datetime(value: Any) -> str:
    if value is None:
        return ""

    if isinstance(value, datetime):
        dt = value
        has_time = True
    else:
        raw = str(value or "").strip()
        if not raw:
            return ""
        has_time = any(token in raw for token in ("T", ":", " "))
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except Exception:
            dt = None
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
                try:
                    dt = datetime.strptime(raw, fmt)
                    has_time = fmt != "%Y-%m-%d"
                    break
                except Exception:
                    dt = None
            if dt is None:
                return ""

    try:
        if getattr(dt, "tzinfo", None) is not None:
            if ITALY_TIMEZONE is not None:
                dt = dt.astimezone(ITALY_TIMEZONE)
            else:
                dt = dt.astimezone()
    except Exception:
        pass

    if has_time:
        return dt.strftime("%d/%m/%Y alle ore %H:%M")
    return dt.strftime("%d/%m/%Y")


def build_visible_signature_text(
    *,
    intestatario: str = "",
    data_firma: Any = None,
    luogo: str = "",
    issuer: str = "",
    serial: str = "",
) -> str:
    signer_name = str(intestatario or "").strip()
    signature_time = format_visible_signature_datetime(data_firma)
    signature_place = str(luogo or "").strip()
    issuer_value = str(issuer or "").strip()
    serial_value = str(serial or "").strip()

    lines: list[str] = [VISIBLE_SIGNATURE_PREFIX]
    if signer_name:
        lines.append(signer_name)
    if signature_time:
        lines.append(f"{VISIBLE_SIGNATURE_DATE_LABEL} {signature_time}")
    if signature_place:
        lines.append(f"Luogo firma: {signature_place}")
    if issuer_value:
        lines.append(f"Emesso da: {issuer_value}")
    if serial_value:
        lines.append(f"Seriale: {serial_value}")
    return "\n".join(line for line in lines if line.strip())


def _normalize_visible_signature_name(
    intestatario: str = "",
    *,
    uppercase: bool = False,
    force_avv_prefix: bool = False,
) -> str:
    value = str(intestatario or "").strip()
    if not value:
        return ""

    normalized = value.upper()
    if force_avv_prefix and not normalized.startswith(("AVV.", "AVV ", "AVVOCATO ", "AVVOCATA ")):
        value = f"Avv. {value}"

    return value.upper() if uppercase else value


def has_visible_signature_stamp(pdf_data: bytes) -> bool:
    if not pdf_data.startswith(b"%PDF"):
        return False
    try:
        return (
            VISIBLE_SIGNATURE_METADATA_KEY.encode("ascii") in pdf_data
            or (
                VISIBLE_SIGNATURE_PREFIX.encode("utf-8") in pdf_data
                and VISIBLE_SIGNATURE_DATE_LABEL.encode("utf-8") in pdf_data
            )
        )
    except Exception:
        return False


def apply_visible_signature_stamp(
    pdf_data: bytes,
    *,
    intestatario: str = "",
    data_firma: Any = None,
    luogo: str = "",
    issuer: str = "",
    serial: str = "",
    mode: str = VISIBLE_SIGNATURE_MODE_LATERALE,
) -> bytes:
    if not pdf_data.startswith(b"%PDF"):
        return pdf_data

    if has_visible_signature_stamp(pdf_data):
        return pdf_data

    stamp_text = build_visible_signature_text(
        intestatario=intestatario,
        data_firma=data_firma,
        luogo=luogo,
        issuer=issuer,
        serial=serial,
    )
    resolved_mode = normalize_visible_signature_mode(mode)
    if not stamp_text:
        return pdf_data

    try:
        from pypdf import PdfReader, PdfWriter
        from reportlab.lib.colors import Color
        from reportlab.pdfgen import canvas
    except Exception:
        return _apply_visible_signature_stamp_fallback(
            pdf_data,
            stamp_text=stamp_text,
            mode=resolved_mode,
        )

    try:
        reader = PdfReader(io.BytesIO(pdf_data))
        writer = PdfWriter(clone_from=io.BytesIO(pdf_data))
        page_count = len(reader.pages)
        if page_count == 0:
            return pdf_data

        last_page_index = page_count - 1
        signer_name = str(intestatario or "").strip()
        signature_place = str(luogo or "").strip()

        for index in range(page_count):
            page = writer.pages[index]
            if index == last_page_index:
                page_box = getattr(page, "cropbox", None) or page.mediabox
                width = float(page_box.width)
                height = float(page_box.height)
                layout = compute_visible_signature_layout(
                    width=width,
                    height=height,
                    mode=resolved_mode,
                )

                overlay_buffer = io.BytesIO()
                overlay = canvas.Canvas(overlay_buffer, pagesize=(width, height))

                muted = Color(0.23, 0.23, 0.23)
                _clear_visible_signature_zones(
                    overlay,
                    width=width,
                    height=height,
                    mode=resolved_mode,
                    layout=layout,
                )
                if resolved_mode in {VISIBLE_SIGNATURE_MODE_BASSO_SINISTRA, VISIBLE_SIGNATURE_MODE_BASSO_DESTRA}:
                    _draw_visible_signature_bottom_text(
                        overlay,
                        width=width,
                        height=height,
                        layout=layout,
                        color=muted,
                        intestatario=signer_name,
                        data_firma=data_firma,
                        luogo=signature_place,
                    )
                else:
                    _draw_visible_signature_side_mark(
                        overlay,
                        width=width,
                        height=height,
                        layout=layout,
                        color=muted,
                        intestatario=signer_name,
                        data_firma=data_firma,
                        luogo=signature_place,
                        issuer=issuer,
                    )

                overlay.save()
                overlay_buffer.seek(0)
                overlay_page = PdfReader(overlay_buffer).pages[0]
                page.merge_page(overlay_page)

        metadata = {}
        try:
            existing_metadata = reader.metadata or {}
            metadata = {
                key: str(value)
                for key, value in existing_metadata.items()
                if key and value is not None
            }
        except Exception:
            metadata = {}
        metadata[VISIBLE_SIGNATURE_METADATA_KEY] = stamp_text
        writer.add_metadata(metadata)

        output_buffer = io.BytesIO()
        writer.write(output_buffer)
        return output_buffer.getvalue()
    except Exception:
        return _apply_visible_signature_stamp_fallback(
            pdf_data,
            stamp_text=stamp_text,
            mode=resolved_mode,
        )


def _apply_visible_signature_stamp_fallback(
    pdf_data: bytes,
    *,
    stamp_text: str,
    mode: str = VISIBLE_SIGNATURE_MODE_LATERALE,
) -> bytes:
    try:
        from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
        from pyhanko.pdf_utils.layout import BoxConstraints
        from pyhanko.pdf_utils.text import TextBoxStyle
        from pyhanko.stamp import TextStamp, TextStampStyle
    except Exception:
        return pdf_data

    try:
        buf_in = io.BytesIO(pdf_data)
        writer = IncrementalPdfFileWriter(buf_in)
        page_count = 1
        try:
            pages = writer.prev.root["/Pages"].get_object()
            page_count = max(int(pages.get("/Count", 1) or 1), 1)
        except Exception:
            page_count = 1

        dest_page = page_count - 1
        resolved_mode = normalize_visible_signature_mode(mode)
        page_width = 595.0
        page_height = 842.0
        try:
            page_ref, _ = writer.find_page_for_modification(dest_page)
            media_box = page_ref.get_object().get("/MediaBox")
            if media_box and len(media_box) >= 4:
                page_width = float(media_box[2]) - float(media_box[0])
                page_height = float(media_box[3]) - float(media_box[1])
        except Exception:
            page_width = 595.0
            page_height = 842.0

        layout = compute_visible_signature_layout(
            width=page_width,
            height=page_height,
            mode=resolved_mode,
        )
        box_width = int(float(layout["box_width"]))
        box_height = int(float(layout["box_height"]))
        x = int(float(layout["x"]))
        y = int(float(layout["y"]))
        style = TextStampStyle(
            stamp_text=stamp_text,
            border_width=1,
            border_color=(0.12, 0.31, 0.55),
            text_box_style=TextBoxStyle(
                font_size=11 if resolved_mode in {VISIBLE_SIGNATURE_MODE_BASSO_SINISTRA, VISIBLE_SIGNATURE_MODE_BASSO_DESTRA} else 9,
                leading=13 if resolved_mode in {VISIBLE_SIGNATURE_MODE_BASSO_SINISTRA, VISIBLE_SIGNATURE_MODE_BASSO_DESTRA} else 11,
                text_color=(0.11, 0.16, 0.24),
            ),
        )
        stamp = TextStamp(writer, style, box=BoxConstraints(width=box_width, height=box_height))
        stamp.apply(dest_page, x, y)

        buf_out = io.BytesIO()
        writer.write(buf_out)
        return buf_out.getvalue()
    except Exception:
        return pdf_data


def prepare_document_for_signature(
    document_data: bytes,
    *,
    intestatario: str = "",
    data_firma: Any = None,
    luogo: str = "",
    issuer: str = "",
    serial: str = "",
    mode: str = VISIBLE_SIGNATURE_MODE_LATERALE,
) -> bytes:
    if not document_data.startswith(b"%PDF"):
        return document_data
    return apply_visible_signature_stamp(
        document_data,
        intestatario=intestatario,
        data_firma=data_firma,
        luogo=luogo,
        issuer=issuer,
        serial=serial,
        mode=mode,
    )


def apply_visible_signature_stamp_from_firme(
    pdf_data: bytes,
    firme: list[dict] | None,
    *,
    city: str = "",
    address: str = "",
    mode: str = VISIBLE_SIGNATURE_MODE_LATERALE,
) -> bytes:
    if not firme:
        return pdf_data

    signature = (firme or [{}])[0] or {}
    return apply_visible_signature_stamp(
        pdf_data,
        intestatario=str(signature.get("intestatario") or signature.get("cn") or "").strip(),
        data_firma=signature.get("data_firma"),
        luogo=resolve_visible_signature_place(city=city, address=address),
        issuer=str(signature.get("emittente_cn") or signature.get("emittente") or "").strip(),
        serial=str(signature.get("seriale") or "").strip(),
        mode=mode,
    )


def _build_visible_signature_location_line(*, luogo: str = "", data_firma: Any = None) -> str:
    luogo_value = str(luogo or "").strip()
    data_value = format_visible_signature_datetime(data_firma)
    if luogo_value and data_value:
        return f"{luogo_value} {data_value}"
    return luogo_value or data_value


def _build_visible_signature_side_text(
    *,
    intestatario: str = "",
    data_firma: Any = None,
    luogo: str = "",
    issuer: str = "",
    serial: str = "",
) -> str:
    segments: list[str] = []
    signer_name = _normalize_visible_signature_name(
        intestatario,
        uppercase=True,
        force_avv_prefix=True,
    )
    date_value = format_visible_signature_datetime(data_firma)
    place_value = str(luogo or "").strip()

    if signer_name:
        segments.append(f"Firmato da: {signer_name}")
    if date_value:
        segments.append(f"Data e ora firma: {date_value}")
    if place_value:
        segments.append(f"Luogo firma: {place_value.upper()}")
    return " | ".join(segment for segment in segments if segment.strip())


def _build_visible_signature_bottom_lines(
    *,
    intestatario: str = "",
    data_firma: Any = None,
    luogo: str = "",
) -> tuple[str, str]:
    signer_name = _normalize_visible_signature_name(
        intestatario,
        uppercase=True,
        force_avv_prefix=True,
    )
    place_value = str(luogo or "").strip()
    date_value = format_visible_signature_datetime(data_firma)
    if date_value:
        date_value = date_value.replace(" alle ore ", " ore ")

    first_line = "Per autentica e sottoscrizione"

    second_line = "Firmato da:"
    if signer_name:
        second_line = f"{second_line} {signer_name}"
    if date_value:
        second_line = f"{second_line} in data {date_value}"
    if place_value:
        second_line = f"{second_line} Luogo: {place_value}"
    return first_line, second_line


def _fit_text_for_width(overlay, text: str, font_name: str, font_size: float, max_width: float) -> str:
    value = str(text or "")
    if not value:
        return ""
    try:
        if overlay.stringWidth(value, font_name, font_size) <= max_width:
            return value
        suffix = "..."
        while value and overlay.stringWidth(value + suffix, font_name, font_size) > max_width:
            value = value[:-1]
        return (value.rstrip() + suffix) if value else suffix
    except Exception:
        max_chars = max(int(max_width / max(font_size * 0.55, 1)), 8)
        return value if len(value) <= max_chars else value[: max_chars - 3].rstrip() + "..."


def _draw_visible_signature_side_mark(
    overlay,
    *,
    width: float,
    height: float,
    color,
    layout: dict[str, float | str | int] | None = None,
    intestatario: str = "",
    data_firma: Any = None,
    luogo: str = "",
    issuer: str = "",
) -> None:
    side_text = _build_visible_signature_side_text(
        intestatario=intestatario,
        data_firma=data_firma,
        luogo=luogo,
        issuer=issuer,
    )
    layout = layout or compute_visible_signature_layout(
        width=width,
        height=height,
        mode=VISIBLE_SIGNATURE_MODE_LATERALE,
    )
    text_length = max(float(layout["box_height"]) - 24.0, 40.0)
    font_name = "Helvetica"
    font_size = 10.0
    while font_size > 7.0 and overlay.stringWidth(side_text, font_name, font_size) > text_length:
        font_size -= 0.5
    side_text = _fit_text_for_width(overlay, side_text, font_name, font_size, text_length)

    overlay.setFillColor(color)
    overlay.setFont(font_name, font_size)
    overlay.saveState()
    translate_x = min(
        max(float(layout["x"]) + float(layout["box_width"]) - 10.0, CM_TO_PT),
        max(width - 10.0, CM_TO_PT),
    )
    translate_y = min(max(float(layout["y"]) + 10.0, 10.0), max(height - 10.0, 10.0))
    overlay.translate(translate_x, translate_y)
    overlay.rotate(90)
    overlay.drawString(0, 0, side_text)
    overlay.restoreState()
    _draw_visible_signature_seal(
        overlay,
        anchor_x=min(max(float(layout["x"]) + float(layout["box_width"]) - 14.0, 16.0), max(width - 16.0, 16.0)),
        anchor_y=min(max(float(layout["y"]) + 16.0, 16.0), max(height - 16.0, 16.0)),
    )


def _clear_visible_signature_zones(
    overlay,
    *,
    width: float,
    height: float,
    mode: str = VISIBLE_SIGNATURE_MODE_LATERALE,
    layout: dict[str, float | str | int] | None = None,
) -> None:
    try:
        from reportlab.lib.colors import Color
    except Exception:
        return

    white = Color(1, 1, 1)
    layout = layout or compute_visible_signature_layout(width=width, height=height, mode=mode)
    pad = 8.0
    block_x = max(float(layout["x"]) - pad, 0.0)
    block_y = max(float(layout["y"]) - pad, 0.0)
    block_width = min(float(layout["box_width"]) + pad * 2, max(width - block_x, 0.0))
    block_height = min(float(layout["box_height"]) + pad * 2, max(height - block_y, 0.0))

    overlay.saveState()
    overlay.setFillColor(white)
    overlay.setStrokeColor(white)
    overlay.rect(
        block_x,
        block_y,
        block_width,
        block_height,
        stroke=0,
        fill=1,
    )
    overlay.restoreState()


def _draw_visible_signature_bottom_text(
    overlay,
    *,
    width: float,
    height: float,
    color,
    layout: dict[str, float | str | int] | None = None,
    intestatario: str = "",
    data_firma: Any = None,
    luogo: str = "",
) -> None:
    layout = layout or compute_visible_signature_layout(
        width=width,
        height=height,
        mode=VISIBLE_SIGNATURE_MODE_BASSO_DESTRA,
    )
    align = str(layout.get("align") or "right")
    font_name = "Helvetica"
    font_size = 11
    line_one, line_two = _build_visible_signature_bottom_lines(
        intestatario=intestatario,
        data_firma=data_firma,
        luogo=luogo,
    )
    max_text_width = max(float(layout["box_width"]) - (42.0 if align == "left" else 8.0), 80.0)
    while font_size > 8 and max(
        overlay.stringWidth(line_one, font_name, font_size),
        overlay.stringWidth(line_two, font_name, font_size) if line_two else 0,
    ) > max_text_width:
        font_size -= 0.5
    line_one = _fit_text_for_width(overlay, line_one, font_name, font_size, max_text_width)
    line_two = _fit_text_for_width(overlay, line_two, font_name, font_size, max_text_width)

    overlay.saveState()
    overlay.setFillColor(color)
    overlay.setFont(font_name, font_size)
    baseline_y = float(layout["y"]) + 14.0
    x_left = float(layout["x"]) + 34.0
    x_right = min(float(layout["x"]) + float(layout["box_width"]), width - CM_TO_PT)
    if align == "left":
        if line_two:
            overlay.drawString(x_left, baseline_y + 14, line_one)
            overlay.drawString(x_left, baseline_y, line_two)
        else:
            overlay.drawString(x_left, baseline_y + 7, line_one)
    else:
        if line_two:
            overlay.drawRightString(x_right, baseline_y + 14, line_one)
            overlay.drawRightString(x_right, baseline_y, line_two)
        else:
            overlay.drawRightString(x_right, baseline_y + 7, line_one)
    overlay.restoreState()

    line_one_width = overlay.stringWidth(line_one, font_name, font_size)
    line_two_width = overlay.stringWidth(line_two, font_name, font_size) if line_two else 0
    text_width = max(line_one_width, line_two_width)
    if align == "left":
        seal_anchor_x = max(float(layout["x"]) + 14.0, 14.0)
    else:
        seal_anchor_x = max(x_right - text_width - 18.0, float(layout["x"]) + 14.0)
    seal_anchor_x = min(seal_anchor_x, max(width - 16.0, 16.0))
    seal_anchor_y = min(max(float(layout["y"]) + 8.0, 16.0), max(height - 16.0, 16.0))
    _draw_visible_signature_seal(
        overlay,
        anchor_x=seal_anchor_x,
        anchor_y=seal_anchor_y,
        scale=1.05,
    )


def _draw_visible_signature_bottom_right_text(
    overlay,
    *,
    width: float,
    height: float,
    color,
    intestatario: str = "",
    data_firma: Any = None,
    luogo: str = "",
) -> None:
    """Wrapper retrocompatibile per test e chiamanti legacy."""
    return _draw_visible_signature_bottom_text(
        overlay,
        width=width,
        height=height,
        layout=compute_visible_signature_layout(
            width=width,
            height=height,
            mode=VISIBLE_SIGNATURE_MODE_BASSO_DESTRA,
        ),
        color=color,
        intestatario=intestatario,
        data_firma=data_firma,
        luogo=luogo,
    )


def _draw_visible_signature_seal(
    overlay,
    *,
    anchor_x: float,
    anchor_y: float,
    scale: float = 1.0,
) -> None:
    try:
        from reportlab.lib.colors import Color
    except Exception:
        return

    center_x = anchor_x
    center_y = anchor_y
    radius = 7.5 * scale
    silver_dark = Color(0.56, 0.58, 0.63)
    silver_light = Color(0.90, 0.91, 0.93)
    ribbon_gray = Color(0.74, 0.75, 0.79)
    green = Color(0.11, 0.57, 0.24)
    white = Color(0.98, 0.98, 0.98)
    red = Color(0.78, 0.16, 0.18)
    gold = Color(0.84, 0.70, 0.29)

    overlay.saveState()

    left_tail = overlay.beginPath()
    left_tail.moveTo(center_x - 1.4 * scale, center_y - 4.6 * scale)
    left_tail.lineTo(center_x - 5.7 * scale, center_y - 12.5 * scale)
    left_tail.lineTo(center_x - 0.5 * scale, center_y - 9.7 * scale)
    left_tail.close()
    overlay.setFillColor(ribbon_gray)
    overlay.setStrokeColor(ribbon_gray)
    overlay.drawPath(left_tail, fill=1, stroke=0)

    right_tail = overlay.beginPath()
    right_tail.moveTo(center_x + 1.4 * scale, center_y - 4.6 * scale)
    right_tail.lineTo(center_x + 5.7 * scale, center_y - 12.5 * scale)
    right_tail.lineTo(center_x + 0.5 * scale, center_y - 9.7 * scale)
    right_tail.close()
    overlay.drawPath(right_tail, fill=1, stroke=0)

    overlay.setStrokeColor(silver_dark)
    overlay.setFillColor(silver_light)
    overlay.circle(center_x, center_y, radius, stroke=1, fill=1)
    overlay.setFillColor(green)
    overlay.circle(center_x, center_y, radius * 0.68, stroke=0, fill=1)
    overlay.setFillColor(white)
    overlay.circle(center_x, center_y, radius * 0.45, stroke=0, fill=1)
    overlay.setFillColor(red)
    overlay.circle(center_x, center_y, radius * 0.26, stroke=0, fill=1)
    overlay.setFillColor(gold)
    overlay.circle(center_x, center_y, radius * 0.08, stroke=0, fill=1)

    overlay.setStrokeColor(silver_dark)
    overlay.setLineWidth(0.55 * scale)
    overlay.circle(center_x, center_y, radius * 0.88, stroke=1, fill=0)
    overlay.circle(center_x, center_y, radius * 0.56, stroke=1, fill=0)
    overlay.restoreState()
