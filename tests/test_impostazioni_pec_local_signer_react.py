from pathlib import Path

from tests.test_web_bootstrap import _cfg_web, _write_studio_config
from web.app import create_app


def _app(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))
    app.config["API_KEY"] = "react-test-key"
    return app


def test_react_pec_test_usa_local_signer_ma_composizione_usa_canale_pec_dedicato():
    actions = Path("frontend/src/features/impostazioni/components/SettingsActions.tsx").read_text(encoding="utf-8")
    local_signer = Path("frontend/src/features/impostazioni/localSigner.ts").read_text(encoding="utf-8")
    guard = Path("web/static/js/react-pec-local-signer-guard.js").read_text(encoding="utf-8")
    shell = Path("web/templates/react_shell.html").read_text(encoding="utf-8")
    compose = Path("frontend/src/components/EmailPecPage.tsx").read_text(encoding="utf-8")

    assert "testPecSmtpViaLocalSigner" in actions
    assert "onTest('pec-smtp'" not in actions
    assert 'onTest("pec-smtp"' not in actions
    assert "/pec/smtp/test" in local_signer
    assert "/impostazioni/pec/local-smtp-payload" in local_signer
    assert "viene inviata solo al Local Signer" in local_signer
    assert "/api/v1/ui/impostazioni/test/pec-smtp" in guard
    assert "/pec/smtp/test" in guard
    assert "iusentra-local-signer://restart" in guard
    assert "/impostazioni/pec/local-smtp-payload" in guard
    assert "react-pec-local-signer-guard.js" in shell
    assert "/pec/send" not in compose
    assert "submitPecViaLocalSigner" not in compose
    assert "Invio PEC in corso" in compose
    assert "OfficePecLookupPanel" in compose


def test_api_react_pec_smtp_non_esegue_verifica_sul_server(tmp_path: Path):
    app = _app(tmp_path)
    client = app.test_client()

    response = client.post(
        "/api/v1/ui/impostazioni/test/pec-smtp",
        json={
            "indirizzo": "studio@pec.example.it",
            "password": "segreta",
            "smtp_host": "smtp.pec.example.it",
            "smtp_port": 465,
            "use_ssl": True,
        },
        headers={"X-API-Key": "react-test-key"},
    )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["ok"] is False
    assert payload["local_signer_required"] is True
    assert "PC in uso" in payload["message"]
    assert "Local Signer" in payload["message"]
