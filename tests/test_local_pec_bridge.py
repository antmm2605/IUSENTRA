from __future__ import annotations

import base64
import socket
from pathlib import Path

from local_signer_mod.pec_bridge import send_pec_local, test_pec_smtp_local as _test_pec_smtp_local
from pct.pst_cifratura import carica_certificato_cifratura, cifra_atto_msg_aes256, crea_certificato_cifratura_test


class _FakeSmtp:
    instances: list["_FakeSmtp"] = []

    def __init__(self, host: str, port: int, timeout: int = 0, context=None):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.context = context
        self.logged_in = None
        self.sent = []
        self.quit_called = False
        _FakeSmtp.instances.append(self)

    def ehlo(self):
        return (250, b"ok")

    def starttls(self, context=None):
        self.context = context
        return (220, b"ready")

    def login(self, username: str, password: str):
        self.logged_in = (username, password)
        return (235, b"ok")

    def send_message(self, message, from_addr=None, to_addrs=None):
        self.sent.append((message, from_addr, to_addrs))
        return {}

    def quit(self):
        self.quit_called = True


def _payload(**extra):
    data = {
        "indirizzo": "studio@example.test",
        "password": "segreta",
        "smtp_host": "smtp.example.test",
        "smtp_port": 465,
        "use_ssl": True,
    }
    data.update(extra)
    return data


def _atto_enc_cms_payload(tmp_path: Path) -> bytes:
    info = crea_certificato_cifratura_test(tmp_path / "certificato-pec-test.cer")
    cert = carica_certificato_cifratura(info.path)
    return cifra_atto_msg_aes256(b"Atto.msg test con IndiceBusta.xml", cert)


def test_smtp_locale_usa_configurazione_e_non_espone_password():
    _FakeSmtp.instances.clear()

    result = _test_pec_smtp_local(_payload(), smtp_ssl_factory=_FakeSmtp)

    assert result["ok"] is True
    assert result["canale"] == "locale"
    assert result["messaggio"] == "Connessione SMTP PEC riuscita."
    assert "segreta" not in str(result)
    assert result["endpoint"] == "smtp.example.test:465"
    assert _FakeSmtp.instances[0].logged_in == ("studio@example.test", "segreta")
    assert _FakeSmtp.instances[0].quit_called is True


def test_smtp_locale_password_mancante_restituisce_messaggio_operativo():
    result = _test_pec_smtp_local(_payload(password=""), smtp_ssl_factory=_FakeSmtp)

    assert result["ok"] is False
    assert "Password PEC mancante" in result["messaggio"]
    assert "non viene salvata dal server" in result["messaggio"]


def test_smtp_locale_timeout_parla_del_pc_locale_senza_railway():
    def _timeout_factory(*args, **kwargs):
        raise socket.timeout("timed out")

    result = _test_pec_smtp_local(_payload(), smtp_ssl_factory=_timeout_factory)

    assert result["ok"] is False
    assert "Timeout SMTP PEC locale" in result["messaggio"]
    assert "questo PC" in result["messaggio"]
    assert "Railway" not in result["messaggio"]
    assert "Brevo" not in result["messaggio"]


def test_invio_pec_locale_invia_allegato_base64():
    _FakeSmtp.instances.clear()
    attachment = base64.b64encode(b"contenuto busta").decode("ascii")

    result = send_pec_local(
        _payload(
            destinatario="tribunale@example.test",
            oggetto="DEPOSITO TELEMATICO - Ricorso",
            corpo="Deposito da IUSENTRA",
            allegati=[
                {
                    "filename": "busta.enc",
                    "content_base64": attachment,
                    "mime_type": "application/octet-stream",
                }
            ],
        ),
        smtp_ssl_factory=_FakeSmtp,
    )

    smtp = _FakeSmtp.instances[0]
    sent_message, from_addr, to_addrs = smtp.sent[0]
    assert result["ok"] is True
    assert result["inviato"] is True
    assert result["message_id"]
    assert from_addr == "studio@example.test"
    assert to_addrs == ["tribunale@example.test"]
    assert sent_message["Subject"] == "DEPOSITO TELEMATICO - Ricorso"
    assert sent_message.is_multipart()


def test_invio_pec_locale_rifiuta_atto_enc_non_cms():
    result = send_pec_local(
        _payload(
            destinatario="tribunale@example.test",
            oggetto="DEPOSITO TELEMATICO - Ricorso",
            corpo="Deposito da IUSENTRA",
            allegati=[
                {
                    "filename": "Atto.enc",
                    "content_base64": base64.b64encode(b"ATTO-ENC-NON-MINISTERIALE").decode("ascii"),
                    "mime_type": "application/octet-stream",
                }
            ],
        ),
        smtp_ssl_factory=_FakeSmtp,
    )

    assert result["ok"] is False
    assert "CMS EnvelopedData ministeriale" in result["messaggio"]


def test_invio_pec_locale_accetta_atto_enc_cms(tmp_path):
    _FakeSmtp.instances.clear()
    result = send_pec_local(
        _payload(
            destinatario="tribunale@example.test",
            oggetto="DEPOSITO TELEMATICO - Ricorso",
            corpo="Deposito da IUSENTRA",
            allegati=[
                {
                    "filename": "Atto.enc",
                    "content_base64": base64.b64encode(_atto_enc_cms_payload(tmp_path)).decode("ascii"),
                    "mime_type": "application/octet-stream",
                }
            ],
        ),
        smtp_ssl_factory=_FakeSmtp,
    )

    assert result["ok"] is True
    sent_message, _, _ = _FakeSmtp.instances[0].sent[0]
    assert any(part.get_filename() == "Atto.enc" for part in sent_message.iter_attachments())
