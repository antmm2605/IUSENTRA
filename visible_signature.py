from __future__ import annotations

import io
import re
from datetime import datetime
from typing import Any

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
    issuer_value = str(issuer or "").strip()
    date_value = format_visible_signature_datetime(data_firma)
    place_value = str(luogo or "").strip()

    if signer_name:
        segments.append(f"Firmato da: {signer_name}")
    if issuer_value:
        segments.append(f"Emesso da: {issuer_value.upper()}")
    if date_value:
        segments.append(f"Data e ora firma: {date_value}")
    if place_value:
        segments.append(f"Luogo firma: {place_value.upper()}")
    return "  ".join(segments)


def _build_visible_signature_bottom_lines(
    *,
    intestatario: str = "",
    data_firma: Any = None,
    luogo: str = "",
) -> tuple[str, str]:
    signer_name = str(intestatario or "").strip().upper()
    place_value = str(luogo or "").strip()
    date_value = format_visible_signature_datetime(data_firma)

    first_line = VISIBLE_SIGNATURE_PREFIX
    if signer_name:
        first_line = f"{first_line} {signer_name}"

    second_parts = []
    if place_value:
        second_parts.append(place_value)
    if date_value:
        second_parts.append(date_value)
    second_line = " - ".join(part for part in second_parts if part).strip()
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
    overlay.setFillColor(color)
    overlay.setFont("Helvetica", 10)
    overlay.saveState()
    overlay.translate(width - right_margin, bottom_margin)
    overlay.rotate(90)
    overlay.drawString(
        0,
        0,
        _build_visible_signature_side_text(
            intestatario=intestatario,
            data_firma=data_firma,
            luogo=luogo,
            issuer=issuer,
        ),
    )
    overlay.restoreState()
    _draw_visible_signature_seal(
        overlay,
        anchor_x=width - right_margin + 1.5,
        anchor_y=bottom_margin - 3,
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
    del height
    right_margin = CM_TO_PT
    bottom_margin = CM_TO_PT
    line_one, line_two = _build_visible_signature_bottom_lines(
        intestatario=intestatario,
        data_firma=data_firma,
        luogo=luogo,
    )

    overlay.saveState()
    overlay.setFillColor(color)
    overlay.setFont("Helvetica", 11)
    baseline_y = bottom_margin + 14
    if line_two:
        overlay.drawRightString(width - right_margin, baseline_y + 14, line_one)
        overlay.drawRightString(width - right_margin, baseline_y, line_two)
    else:
        overlay.drawRightString(width - right_margin, baseline_y + 7, line_one)
    overlay.restoreState()


def _draw_visible_signature_seal(
    overlay,
    *,
    anchor_x: float,
    anchor_y: float,
) -> None:
    try:
        from reportlab.lib.colors import Color
    except Exception:
        return

    center_x = anchor_x
    center_y = anchor_y
    outline = Color(0.55, 0.55, 0.55)
    fill = Color(0.92, 0.92, 0.92)

    overlay.saveState()
    overlay.setStrokeColor(outline)
    overlay.setFillColor(fill)
    overlay.circle(center_x, center_y, 7.5, stroke=1, fill=1)
    overlay.setFillColor(Color(0.97, 0.97, 0.97))
    overlay.circle(center_x, center_y, 4.4, stroke=1, fill=1)
    overlay.setFillColor(outline)
    overlay.setLineWidth(0.8)
    overlay.circle(center_x, center_y, 1.6, stroke=1, fill=0)
    overlay.line(center_x - 4.5, center_y - 7.8, center_x - 1.6, center_y - 13)
    overlay.line(center_x + 4.5, center_y - 7.8, center_x + 1.6, center_y - 13)
    overlay.restoreState()
