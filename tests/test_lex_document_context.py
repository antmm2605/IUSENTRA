from __future__ import annotations

import base64

from tools.lex_document_context import build_attachment_prompt_block, parse_attachment_payloads


def test_parse_attachment_payloads_supporta_testo_base64():
    payload = [
        {
            "name": "memo.txt",
            "mime_type": "text/plain",
            "content_base64": "data:text/plain;base64,"
            + base64.b64encode("Promemoria per il deposito telematico di domani".encode("utf-8")).decode("ascii"),
        }
    ]

    attachments, errors = parse_attachment_payloads(payload)

    assert errors == []
    assert attachments[0]["name"] == "memo.txt"
    assert attachments[0]["mime_type"] == "text/plain"
    assert "Promemoria" in attachments[0]["text_excerpt"]


def test_parse_attachment_payloads_html_rimuove_script_e_style():
    html = "<html><body><main>Contenuto utile</main><script>alert('x')</script><style>.x{}</style></body></html>"
    payload = [
        {
            "name": "pagina.html",
            "mime_type": "text/html",
            "content_base64": base64.b64encode(html.encode("utf-8")).decode("ascii"),
        }
    ]

    attachments, errors = parse_attachment_payloads(payload)

    assert errors == []
    assert "Contenuto utile" in attachments[0]["text_excerpt"]
    assert "alert" not in attachments[0]["text_excerpt"]


def test_build_attachment_prompt_block_contiene_metadati_documento():
    block = build_attachment_prompt_block(
        [
            {
                "name": "memo.txt",
                "mime_type": "text/plain",
                "page_count": 1,
                "text_excerpt": "Controllare procura, allegati firmati e busta telematica.",
                "truncated": False,
            }
        ]
    )

    assert "DOCUMENTI CARICATI DALL'UTENTE" in block
    assert "memo.txt" in block
    assert "pagine 1" in block
    assert "busta telematica" in block
