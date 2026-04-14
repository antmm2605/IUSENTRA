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
VISIBLE_SIGNATURE_MODE_BASSO_DESTRA = "basso_destra"
VISIBLE_SIGNATURE_MODES = {
    VISIBLE_SIGNATURE_MODE_LATERALE,
    VISIBLE_SIGNATURE_MODE_BASSO_DESTRA,
}
VISIBLE_SIGNATURE_PREFIX = "Firmato digitalmente da"
VISIBLE_SIGNATURE_DATE_LABEL = "Data e ora firma:"
VISIBLE_SIGNATURE_METADATA_KEY = "/HACSSignatureStamp"
ITALY_TIMEZONE = ZoneInfo("Europe/Rome") if ZoneInfo else None


def normalize_visible_signature_mode(value: Any) -> str:
    mode = str(value or "").strip().lower()
    if mode in VISIBLE_SIGNATURE_MODES:
        return mode
    return VISIBLE_SIGNATURE_MODE_LATERALE


def resolve_visible_signature_place(*, city: str = "", address: str = "") -> str:
    city_value = str(city or "").strip()
    if city_value:
        return city_value[:48]

    address_value = str(address or "").strip()
    if not address_value:
        return ""

    parts = [part.strip() for part in re.split(r"[;,|-]", address_value) if part.strip()]
    if not parts:
        return ""

    candidate = re.sub(r"^\d{5}\s+", "", parts[-1]).strip()
    if not candidate:
        return ""
    return candidate[:48]


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
        )

    try:
        reader = PdfReader(io.BytesIO(pdf_data))
        writer = PdfWriter()
        page_count = len(reader.pages)
        if page_count == 0:
            return pdf_data

        last_page_index = page_count - 1
        signer_name = str(intestatario or "").strip()
        signature_place = str(luogo or "").strip()

        for index, page in enumerate(reader.pages):
            if index == last_page_index:
                width = float(page.mediabox.width)
                height = float(page.mediabox.height)

                overlay_buffer = io.BytesIO()
                overlay = canvas.Canvas(overlay_buffer, pagesize=(width, height))

                muted = Color(0.23, 0.23, 0.23)
                _clear_visible_signature_zones(
                    overlay,
                    width=width,
                    height=height,
                )
                if resolved_mode == VISIBLE_SIGNATURE_MODE_BASSO_DESTRA:
                    _draw_visible_signature_bottom_right_text(
                        overlay,
                        width=width,
                        height=height,
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

            writer.add_page(page)

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
        box_width = 280 if resolved_mode == VISIBLE_SIGNATURE_MODE_BASSO_DESTRA else 236
        box_height = 72 if resolved_mode == VISIBLE_SIGNATURE_MODE_BASSO_DESTRA else 92
        page_width = 595.0
        try:
            page_ref, _ = writer.find_page_for_modification(dest_page)
            media_box = page_ref.get_object().get("/MediaBox")
            if media_box and len(media_box) >= 4:
                page_width = float(media_box[2]) - float(media_box[0])
        except Exception:
            page_width = 595.0

        x_margin = int(CM_TO_PT)
        y_margin = int(CM_TO_PT)
        x = max(x_margin, int(page_width - box_width - x_margin))
        y = y_margin
        style = TextStampStyle(
            stamp_text=stamp_text,
            border_width=1,
            border_color=(0.12, 0.31, 0.55),
            text_box_style=TextBoxStyle(
                font_size=11 if resolved_mode == VISIBLE_SIGNATURE_MODE_BASSO_DESTRA else 10,
                leading=13 if resolved_mode == VISIBLE_SIGNATURE_MODE_BASSO_DESTRA else 11,
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


def _draw_visible_signature_side_mark(
    overlay,
    *,
    width: float,
    height: float,
    color,
    intestatario: str = "",
    data_firma: Any = None,
    luogo: str = "",
    issuer: str = "",
) -> None:
    right_margin = CM_TO_PT
    bottom_margin = CM_TO_PT
    side_text = _build_visible_signature_side_text(
        intestatario=intestatario,
        data_firma=data_firma,
        luogo=luogo,
        issuer=issuer,
    )
    overlay.setFillColor(color)
    overlay.setFont("Helvetica", 10)
    overlay.saveState()
    overlay.translate(width - right_margin, bottom_margin)
    overlay.rotate(90)
    overlay.drawString(0, 0, side_text)
    overlay.restoreState()
    _draw_visible_signature_seal(
        overlay,
        anchor_x=width - right_margin + 1.5,
        anchor_y=bottom_margin - 3,
    )


def _clear_visible_signature_zones(
    overlay,
    *,
    width: float,
    height: float,
) -> None:
    try:
        from reportlab.lib.colors import Color
    except Exception:
        return

    white = Color(1, 1, 1)
    right_margin = CM_TO_PT

    side_strip_width = CM_TO_PT * 2.05
    side_strip_x = max(width - side_strip_width, 0)
    side_strip_y = max((CM_TO_PT * 0.45) - 4, 0)
    side_strip_height = max(height - side_strip_y - (CM_TO_PT * 0.35), 0)

    bottom_block_width = 360
    bottom_block_height = 86
    bottom_block_x = max(width - right_margin - bottom_block_width, CM_TO_PT * 1.2)
    bottom_block_y = max((CM_TO_PT * 0.55) - 4, 0)

    overlay.saveState()
    overlay.setFillColor(white)
    overlay.setStrokeColor(white)
    overlay.rect(
        side_strip_x,
        side_strip_y,
        side_strip_width,
        side_strip_height,
        stroke=0,
        fill=1,
    )
    overlay.rect(
        bottom_block_x,
        bottom_block_y,
        bottom_block_width,
        bottom_block_height,
        stroke=0,
        fill=1,
    )
    overlay.restoreState()


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
    del height
    right_margin = CM_TO_PT
    bottom_margin = CM_TO_PT
    font_name = "Helvetica"
    font_size = 11
    line_one, line_two = _build_visible_signature_bottom_lines(
        intestatario=intestatario,
        data_firma=data_firma,
        luogo=luogo,
    )

    overlay.saveState()
    overlay.setFillColor(color)
    overlay.setFont(font_name, font_size)
    baseline_y = bottom_margin + 14
    if line_two:
        overlay.drawRightString(width - right_margin, baseline_y + 14, line_one)
        overlay.drawRightString(width - right_margin, baseline_y, line_two)
    else:
        overlay.drawRightString(width - right_margin, baseline_y + 7, line_one)
    overlay.restoreState()

    line_one_width = overlay.stringWidth(line_one, font_name, font_size)
    line_two_width = overlay.stringWidth(line_two, font_name, font_size) if line_two else 0
    text_width = max(line_one_width, line_two_width)
    seal_anchor_x = max(width - right_margin - text_width - 18, right_margin + 10)
    seal_anchor_y = bottom_margin + 8
    _draw_visible_signature_seal(
        overlay,
        anchor_x=seal_anchor_x,
        anchor_y=seal_anchor_y,
        scale=1.05,
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
