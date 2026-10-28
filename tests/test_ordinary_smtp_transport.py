import pytest
from web.services.ordinary_smtp_transport import ordinary_smtp_uses_local_signer

@pytest.mark.parametrize('host', ['smtp.gmail.com', 'SMTP.GMAIL.COM.', 'smtp.googlemail.com'])
def test_gmail_preserves_existing_transport(host):
    assert ordinary_smtp_uses_local_signer(host) is False

@pytest.mark.parametrize('host', ['smtp.tiscali.it', '213.205.33.13', 'smtp.gmail.com.attacker.example', 'smtp.other.example', ''])
def test_other_providers_require_local_signer(host):
    assert ordinary_smtp_uses_local_signer(host) is True

@pytest.mark.parametrize('host', ['smtp.tiscali.it', 'smtp.gmail.com'])
def test_settings_select_transport_without_sending_email(tmp_path, monkeypatch, host):
    from tests.test_impostazioni_pec_local_signer_react import _app
    import pct.config_studio as config
    calls = []
    def fake_test(value):
        calls.append(value.host)
        return {'ok': True, 'message': 'connection verified'}
    monkeypatch.setattr(config, 'test_smtp_email', fake_test)
    response = _app(tmp_path).test_client().post(
        '/api/v1/ui/impostazioni/test/smtp',
        json={'host': host}, headers={'X-API-Key': 'react-test-key'})
    assert response.status_code == 200
    payload = response.get_json()
    if host == 'smtp.gmail.com':
        assert calls == [host]
        assert payload['ok'] is True
    else:
        assert calls == []
        assert payload['local_signer_required'] is True
        assert payload['ok'] is False


@pytest.mark.parametrize("port,starttls,expected", [(465,True,{"use_ssl":True,"use_tls":False}), (465,False,{"use_ssl":True,"use_tls":False}), (587,True,{"use_ssl":False,"use_tls":True})])
def test_submission_465_richiede_tls_implicito(port,starttls,expected):
    from web.services.ordinary_smtp_transport import ordinary_smtp_tls_options
    assert ordinary_smtp_tls_options(port,starttls)==expected
