import errno
import socket
import ssl

from pct.config_studio import ConfigSMTP, _SMTP_SSLv4, _msg_errore_rete, test_smtp_email as _test_smtp_email


def test_msg_errore_timeout_cloud_friendly():
    err = socket.timeout("timed out")
    msg = _msg_errore_rete(err, "Errore SMTP email [1.2.3.4:587]")
    assert "porta 25" in msg
    assert "se stai già usando 587/465" in msg
    assert "relay cloud-friendly" in msg


def test_msg_errore_timeout_errno_etimedout():
    err = OSError(errno.ETIMEDOUT, "timed out")
    msg = _msg_errore_rete(err, "Errore SMTP email")
    assert "timeout di rete" in msg
    assert "whitelist" in msg


def test_test_smtp_email_porta_25_bloccata():
    cfg = ConfigSMTP(host="smtp.example.com", port=25, username="", password="", use_tls=True)
    out = _test_smtp_email(cfg)
    assert out["ok"] is False
    assert "Porta 25 bloccata" in out["messaggio"]


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
