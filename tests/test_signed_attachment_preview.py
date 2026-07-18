from io import BytesIO
import zipfile

from web.services.signed_attachment_preview import build_attachment_preview_payload


def _zip_bytes(entries: list[tuple[str, bytes]]) -> bytes:
    output = BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in entries:
            archive.writestr(name, data)
    return output.getvalue()


def test_zip_preview_rifiuta_percorso_non_sicuro():
    payload = build_attachment_preview_payload(
        nome_file="decreto.pdf.zip",
        data=_zip_bytes([("../decreto.pdf", b"%PDF-1.4\n")]),
        mime_salvato="application/zip",
    )

    assert payload.unavailable_reason == "L'archivio ZIP contiene un percorso non sicuro."


def test_zip_preview_rifiuta_compressione_anomala():
    payload = build_attachment_preview_payload(
        nome_file="decreto.pdf.zip",
        data=_zip_bytes([("decreto.pdf", b"0" * (1024 * 1024))]),
        mime_salvato="application/zip",
    )

    assert "compressione anomala" in payload.unavailable_reason
