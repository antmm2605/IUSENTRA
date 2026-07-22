"""Renderer raster governati per il lettore documenti interno."""

from __future__ import annotations

import base64
from html import escape
import io
import warnings

from web.services.signed_attachment_preview import AttachmentPreviewPayload, _preview_shell, attachment_mimetype


MAX_RASTER_FRAME_PIXELS = 16_000_000
MAX_RASTER_SOURCE_DIMENSION = 16_384
MAX_RASTER_THUMBNAIL_DIMENSION = 1_600
MAX_RASTER_PREVIEW_OUTPUT_BYTES = 8 * 1024 * 1024
RASTER_PREVIEW_SHELL_RESERVE_BYTES = 64 * 1024
MAX_TIFF_PREVIEW_FRAMES = 24
MAX_TIFF_FRAME_PIXELS = MAX_RASTER_FRAME_PIXELS
MAX_TIFF_TOTAL_PIXELS = 48_000_000
MAX_TIFF_SOURCE_DIMENSION = MAX_RASTER_SOURCE_DIMENSION
MAX_TIFF_THUMBNAIL_DIMENSION = MAX_RASTER_THUMBNAIL_DIMENSION
MAX_TIFF_PREVIEW_OUTPUT_BYTES = MAX_RASTER_PREVIEW_OUTPUT_BYTES
TIFF_PREVIEW_SHELL_RESERVE_BYTES = RASTER_PREVIEW_SHELL_RESERVE_BYTES


def _image_data_uri(data: bytes, mimetype: str) -> str:
    return f"data:{mimetype};base64,{base64.b64encode(data).decode('ascii')}"


class _RasterPreviewRejected(ValueError):
    """Interrompe l'anteprima prima di decodificare contenuti raster non sicuri."""


class _TiffPreviewRejected(_RasterPreviewRejected):
    """Interrompe l'anteprima prima di decodificare contenuti TIFF non sicuri."""


def _validate_raster_frame(
    *,
    width: int,
    height: int,
    max_pixels: int,
    max_dimension: int,
    format_label: str,
) -> int:
    if width <= 0 or height <= 0 or width > max_dimension or height > max_dimension:
        raise _RasterPreviewRejected(
            f"L'immagine {format_label} ha dimensioni non sicure per l'anteprima interna. "
            "Scarica l'originale per verificarla."
        )
    frame_pixels = width * height
    if frame_pixels > max_pixels:
        raise _RasterPreviewRejected(
            f"L'immagine {format_label} supera il limite di sicurezza per la decompressione. "
            "Scarica l'originale per verificarla."
        )
    return frame_pixels


def _raster_thumbnail_bytes(
    *,
    image: object,
    pillow_image: object,
    max_dimension: int,
) -> bytes:
    from PIL import ImageOps  # type: ignore

    page = ImageOps.exif_transpose(image.copy())
    resampling = getattr(getattr(pillow_image, "Resampling", pillow_image), "LANCZOS")
    page.thumbnail((max_dimension, max_dimension), resampling)
    if "A" in page.getbands() or "transparency" in page.info:
        rgba = page.convert("RGBA")
        background = pillow_image.new("RGB", rgba.size, color=(255, 255, 255))
        background.paste(rgba, mask=rgba.getchannel("A"))
        page = background
    elif page.mode not in {"L", "RGB"}:
        page = page.convert("RGB")
    out = io.BytesIO()
    page.save(out, format="JPEG", quality=88)
    return out.getvalue()


def _is_pillow_decompression_bomb(exc: BaseException) -> bool:
    try:
        from PIL import Image  # type: ignore

        return isinstance(exc, (Image.DecompressionBombError, Image.DecompressionBombWarning))
    except Exception:
        return False


def _tiff_unavailable(
    *,
    nome_file: str,
    data: bytes,
    signed: bool,
    reason: str,
) -> AttachmentPreviewPayload:
    return AttachmentPreviewPayload(
        data=data,
        mimetype="image/tiff",
        download_name=nome_file,
        extracted_from_signature=signed,
        unavailable_reason=reason,
    )


def _render_tiff_preview(nome_file: str, data: bytes, *, signed: bool) -> AttachmentPreviewPayload:
    try:
        from PIL import Image  # type: ignore

        figures: list[str] = []
        decoded_pixels = 0
        estimated_output_bytes = TIFF_PREVIEW_SHELL_RESERVE_BYTES
        truncation_note = ""
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as image:
                for frame_index in range(MAX_TIFF_PREVIEW_FRAMES):
                    try:
                        image.seek(frame_index)
                    except EOFError:
                        break

                    width, height = image.size
                    try:
                        frame_pixels = _validate_raster_frame(
                            width=width,
                            height=height,
                            max_pixels=MAX_TIFF_FRAME_PIXELS,
                            max_dimension=MAX_TIFF_SOURCE_DIMENSION,
                            format_label="TIFF",
                        )
                    except _RasterPreviewRejected as exc:
                        raise _TiffPreviewRejected(str(exc)) from exc
                    if decoded_pixels + frame_pixels > MAX_TIFF_TOTAL_PIXELS:
                        truncation_note = (
                            f"Anteprima limitata a {len(figures)} pagine per mantenere rapido il lettore. "
                            "Scarica l'originale per consultare tutte le pagine."
                        )
                        break
                    decoded_pixels += frame_pixels

                    rendered = _raster_thumbnail_bytes(
                        image=image,
                        pillow_image=Image,
                        max_dimension=MAX_TIFF_THUMBNAIL_DIMENSION,
                    )
                    encoded_bytes = 4 * ((len(rendered) + 2) // 3)
                    projected_output = estimated_output_bytes + encoded_bytes + 512
                    if projected_output > MAX_TIFF_PREVIEW_OUTPUT_BYTES:
                        if not figures:
                            raise _TiffPreviewRejected(
                                "L'anteprima TIFF supera il limite di memoria previsto dal lettore. "
                                "Scarica l'originale per verificarla."
                            )
                        truncation_note = (
                            f"Anteprima limitata a {len(figures)} pagine per mantenere rapido il lettore. "
                            "Scarica l'originale per consultare tutte le pagine."
                        )
                        break
                    estimated_output_bytes = projected_output

                    page_number = frame_index + 1
                    figures.append(
                        "<figure>"
                        f"<figcaption>Pagina {page_number}</figcaption>"
                        f'<img src="{_image_data_uri(rendered, "image/jpeg")}" alt="Pagina {page_number} di {escape(nome_file, quote=True)}">'
                        "</figure>"
                    )
        if figures:
            if len(figures) == MAX_TIFF_PREVIEW_FRAMES and not truncation_note:
                truncation_note = (
                    f"La visualizzazione è limitata a un massimo di {MAX_TIFF_PREVIEW_FRAMES} pagine "
                    "per mantenere rapido il lettore."
                )
            note_html = f'<p class="muted">{escape(truncation_note)}</p>' if truncation_note else ""
            preview_data = _preview_shell(
                title=nome_file,
                subtitle="Immagine TIFF firmata" if signed else "Immagine TIFF",
                body=f'{note_html}<section class="image-reader">{"".join(figures)}</section>',
            )
            if len(preview_data) > MAX_TIFF_PREVIEW_OUTPUT_BYTES:
                raise _TiffPreviewRejected(
                    "L'anteprima TIFF supera il limite di memoria previsto dal lettore. "
                    "Scarica l'originale per verificarla."
                )
            return AttachmentPreviewPayload(
                data=preview_data,
                mimetype="text/html; charset=utf-8",
                download_name=nome_file,
                extracted_from_signature=signed,
            )
    except _TiffPreviewRejected as exc:
        return _tiff_unavailable(nome_file=nome_file, data=data, signed=signed, reason=str(exc))
    except Exception as exc:
        if _is_pillow_decompression_bomb(exc):
            return _tiff_unavailable(
                nome_file=nome_file,
                data=data,
                signed=signed,
                reason=(
                    "L'immagine TIFF supera il limite di sicurezza per la decompressione. "
                    "Scarica l'originale per verificarla."
                ),
            )
    return _tiff_unavailable(
        nome_file=nome_file,
        data=data,
        signed=signed,
        reason=(
            "L'immagine TIFF non può essere convertita in anteprima interna. "
            "Scarica l'originale per verificarla."
        ),
    )


def _raster_unavailable(
    *,
    nome_file: str,
    data: bytes,
    mimetype: str,
    signed: bool,
    reason: str,
) -> AttachmentPreviewPayload:
    return AttachmentPreviewPayload(
        data=data,
        mimetype=mimetype,
        download_name=nome_file,
        extracted_from_signature=signed,
        unavailable_reason=reason,
    )


def _render_static_raster_preview(
    nome_file: str,
    data: bytes,
    *,
    mimetype: str,
    signed: bool,
) -> AttachmentPreviewPayload:
    labels = {"image/jpeg": "JPEG", "image/png": "PNG", "image/gif": "GIF"}
    mime = mimetype if mimetype in labels else "image/jpeg"
    format_label = labels[mime]
    try:
        from PIL import Image  # type: ignore

        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as image:
                image.seek(0)
                detected_mime = {
                    "JPEG": "image/jpeg",
                    "PNG": "image/png",
                    "GIF": "image/gif",
                }.get(str(image.format or "").upper())
                if detected_mime:
                    mime = detected_mime
                    format_label = labels[mime]
                width, height = image.size
                _validate_raster_frame(
                    width=width,
                    height=height,
                    max_pixels=MAX_RASTER_FRAME_PIXELS,
                    max_dimension=MAX_RASTER_SOURCE_DIMENSION,
                    format_label=format_label,
                )

                original_encoded_bytes = 4 * ((len(data) + 2) // 3)
                preserve_original = (
                    mime in {"image/jpeg", "image/png"}
                    and width <= MAX_RASTER_THUMBNAIL_DIMENSION
                    and height <= MAX_RASTER_THUMBNAIL_DIMENSION
                    and RASTER_PREVIEW_SHELL_RESERVE_BYTES + original_encoded_bytes + 512
                    <= MAX_RASTER_PREVIEW_OUTPUT_BYTES
                )
                if preserve_original:
                    image.load()
                    rendered = data
                    rendered_mime = mime
                else:
                    rendered = _raster_thumbnail_bytes(
                        image=image,
                        pillow_image=Image,
                        max_dimension=MAX_RASTER_THUMBNAIL_DIMENSION,
                    )
                    rendered_mime = "image/jpeg"

        note = (
            '<p class="muted">Viene mostrato il primo fotogramma del file GIF.</p>'
            if mime == "image/gif"
            else ""
        )
        preview_data = _preview_shell(
            title=nome_file,
            subtitle="Immagine firmata" if signed else "Immagine",
            body=(
                f'{note}<section class="image-reader"><figure>'
                f'<img src="{_image_data_uri(rendered, rendered_mime)}" alt="{escape(nome_file, quote=True)}">'
                "</figure></section>"
            ),
        )
        if len(preview_data) > MAX_RASTER_PREVIEW_OUTPUT_BYTES:
            raise _RasterPreviewRejected(
                f"L'anteprima {format_label} supera il limite di memoria previsto dal lettore. "
                "Scarica l'originale per verificarla."
            )
        return AttachmentPreviewPayload(
            data=preview_data,
            mimetype="text/html; charset=utf-8",
            download_name=nome_file,
            extracted_from_signature=signed,
        )
    except _RasterPreviewRejected as exc:
        reason = str(exc)
    except Exception as exc:
        if _is_pillow_decompression_bomb(exc):
            reason = (
                f"L'immagine {format_label} supera il limite di sicurezza per la decompressione. "
                "Scarica l'originale per verificarla."
            )
        else:
            reason = (
                f"L'immagine {format_label} non può essere preparata per l'anteprima interna. "
                "Scarica l'originale per verificarla."
            )
    return _raster_unavailable(
        nome_file=nome_file,
        data=data,
        mimetype=mime,
        signed=signed,
        reason=reason,
    )


def render_image_preview(
    nome_file: str,
    data: bytes,
    *,
    mimetype: str,
    signed: bool,
) -> AttachmentPreviewPayload:
    mime = str(mimetype or attachment_mimetype(nome_file)).split(";", 1)[0].strip().lower()
    lower = str(nome_file or "").casefold()
    if mime == "image/tiff" or lower.endswith((".tif", ".tiff")):
        return _render_tiff_preview(nome_file, data, signed=signed)
    if mime not in {"image/jpeg", "image/png", "image/gif"}:
        mime = "image/png" if data.startswith(b"\x89PNG\r\n\x1a\n") else "image/jpeg"
    return _render_static_raster_preview(nome_file, data, mimetype=mime, signed=signed)


__all__ = ["render_image_preview"]
