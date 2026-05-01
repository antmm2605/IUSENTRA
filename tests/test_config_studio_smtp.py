import errno
import socket
import ssl

from pct.config_studio import (
    ConfigSMTP,
    _SMTP_SSLv4,
    _msg_errore_rete,
    test_smtp_email as _test_smtp_email,
    test_smtp_imap as _test_smtp_imap,
)


def test_msg_errore_timeout_server_hosted(monkeypatch):
    monkeypatch.setenv("PCT_PUBLIC_OUTBOUND_IP", "116.203.45.57")
    err = socket.timeout("timed out")
    msg = _msg_errore_rete(err, "Errore SMTP email [1.2.3.4:587]")
    assert "porta 25" in msg
    assert "se stai già usando 587/465" in msg
    assert "server cloud o dedicati" in msg
    assert "116.203.45.57" in msg
    assert "Railway" not in msg
    assert "relay SMTP autorizzato compatibile con hosting server" in msg


def test_msg_errore_timeout_errno_etimedout():
    err = OSError(errno.ETIMEDOUT, "timed out")
    msg = _msg_errore_rete(err, "Errore SMTP email")
    assert "timeout di rete" in msg
    assert "whitelist" in msg
    assert "Railway" not in msg


def test_test_smtp_email_porta_25_filtrata():
    cfg = ConfigSMTP(host="smtp.example.com", port=25, username="", password="", use_tls=True)
    out = _test_smtp_email(cfg)
    assert out["ok"] is False
    assert "Porta 25 non consigliata" in out["messaggio"]
    assert "Railway" not in out["messaggio"]


def test_smtp_sslv4_recupera_il_context_da_python_moderno_e_legacy():
    ctx = ssl.create_default_context()

    smtp_moderno = object.__new__(_SMTP_SSLv4)
    smtp_moderno.context = ctx
    assert smtp_moderno._ssl_context() is ctx

    smtp_legacy = object.__new__(_SMTP_SSLv4)
    smtp_legacy._context = ctx
    assert smtp_legacy._ssl_context() is ctx

    smtp_default = object.__new__(_SMTP_SSLv4)
    ctx_default = smtp_default._ssl_context()
    assert isinstance(ctx_default, ssl.SSLContext)


def test_test_smtp_imap_richiede_host_username_e_password():
    out = _test_smtp_imap(ConfigSMTP(imap_host="", username="", password=""))
    assert out["ok"] is False
    assert "Host IMAP non configurato" in out["messaggio"]

    out_user = _test_smtp_imap(ConfigSMTP(imap_host="imap.example.it", username="", password=""))
    assert out_user["ok"] is False
    assert "Username email ordinaria non configurato" in out_user["messaggio"]
