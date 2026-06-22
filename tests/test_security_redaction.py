from __future__ import annotations

import base64

from web.services.security_redaction import redact_exception_details


def test_redaction_preserva_content_base64_anche_se_sembra_marker_tecnico():
    encoded = "sqliteAA"
    assert base64.b64decode(encoded, validate=True)

    payload = {
        "message": r"C:\Users\antmm\traceback.txt",
        "local_pec": {
            "payload": {
                "attachments": [
                    {
                        "filename": "Atto.enc",
                        "content_base64": encoded,
                    }
                ]
            }
        },
    }

    cleaned = redact_exception_details(payload)

    assert cleaned["message"] == "Operazione non completata."
    assert cleaned["local_pec"]["payload"]["attachments"][0]["content_base64"] == encoded
