from __future__ import annotations

import json
from pathlib import Path

from flask import Flask

from web.blueprints.api_v1_react import (
    _PUBLIC_JSON_RESERVED_DETAIL,
    _jsonify_public_payload,
    _pdf_import_public_result,
    _public_json_payload,
)
from web.services.server_maintenance_surface import (
    _safe_tenant_storage_key,
    _tenant_context_from_record,
)
from scripts.audit_quickorganizer_import import _public_output


def test_tenant_context_rifiuta_storage_key_con_traversal(tmp_path: Path) -> None:
    tenants_root = tmp_path / "tenants"
    tenants_root.mkdir()
    (tenants_root / "tenant-valido").mkdir()

    context = _tenant_context_from_record(
        tmp_path,
        {
            "id": "studio-1",
            "storage_key": "tenant-valido",
            "slug": "tenant-valido",
            "registry_key": "studio-1",
            "active": True,
        },
    )
    assert context is not None
    assert Path(context["root"]).name == "tenant-valido"

    for unsafe in ("../tenant-valido", "..\\tenant-valido", "/tenant-valido", "C:\\tenant-valido", "tenant..valido"):
        assert _safe_tenant_storage_key(unsafe) == ""
        assert _tenant_context_from_record(tmp_path, {"id": "studio-x", "storage_key": unsafe}) is None


def test_payload_pubblico_non_espone_traceback_o_path_server() -> None:
    raw_payload = {
        "ok": False,
        "message": "Messaggio operativo leggibile",
        "traceback": 'Traceback (most recent call last):\n  File "/opt/iusentra/app.py", line 1',
        "nested": {
            "last_error": "C:\\repo\\segreto\\app.py, line 9",
            "nota": "Contenuto ordinario",
        },
        "items": [{"stack": "RuntimeError: dettaglio interno"}],
    }

    sanitized = _public_json_payload(raw_payload)
    rendered = json.dumps(sanitized, ensure_ascii=False)

    assert sanitized["message"] == "Messaggio operativo leggibile"
    assert sanitized["traceback"] == _PUBLIC_JSON_RESERVED_DETAIL
    assert sanitized["nested"]["last_error"] == _PUBLIC_JSON_RESERVED_DETAIL
    assert sanitized["items"][0]["stack"] == _PUBLIC_JSON_RESERVED_DETAIL
    assert "Traceback" not in rendered
    assert "/opt/iusentra" not in rendered
    assert "C:\\repo" not in rendered


def test_jsonify_pubblico_sanifica_prima_della_risposta() -> None:
    app = Flask(__name__)
    with app.app_context():
        response, status = _jsonify_public_payload(
            {
                "ok": False,
                "exception": "ValueError: dettaglio interno",
                "message": "Errore gestito",
            },
            400,
        )

    assert status == 400
    body = response.get_data(as_text=True)
    assert "ValueError" not in body
    assert _PUBLIC_JSON_RESERVED_DETAIL in body


def test_import_pdf_non_rimanda_eccezione_come_messaggio_pubblico() -> None:
    public_result = _pdf_import_public_result(
        {
            "ok": False,
            "message": 'Agenda non aggiornata: Traceback (most recent call last): File "/opt/iusentra/app.py"',
            "items": [{"message": "voce ordinaria"}],
        }
    )

    rendered = json.dumps(public_result, ensure_ascii=False)
    assert public_result["message"] == "Importazione PDF non completata."
    assert "Traceback" not in rendered
    assert "/opt/iusentra" not in rendered


def test_audit_quickorganizer_output_pubblico_redige_dati_privati() -> None:
    public_result = _public_output(
        {
            "ok": True,
            "tenantRoot": "C:\\Users\\studio\\tenant-riservato",
            "importId": "import-segreto",
            "sourceName": "QuickOrganizer-Studio-Montagnese.zip",
            "stageSummary": {"sourceName": "QuickOrganizer-Studio-Montagnese.zip", "records": 12},
            "storage": {
                "studioDbExists": True,
                "studioDbPath": "C:\\Users\\studio\\tenant-riservato\\studio.db",
                "tables": {"fascicoli": 2, "clienti": 1},
            },
            "before": {"fascicoli": 1},
            "after": {"fascicoli": 2},
            "audit": {
                "ok": True,
                "errors": [{"cliente": "Rossi Mario", "path": "C:\\riservato\\fascicolo.pdf"}],
            },
        }
    )

    rendered = json.dumps(public_result, ensure_ascii=False)
    assert public_result["ok"] is True
    assert public_result["storage"]["tables"]["fascicoli"] == 2
    assert public_result["audit"]["errors"] == {"count": 1}
    assert "QuickOrganizer-Studio-Montagnese.zip" not in rendered
    assert "tenant-riservato" not in rendered
    assert "Rossi Mario" not in rendered
