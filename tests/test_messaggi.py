"""Test per il sistema di messaggistica multicanale."""

import pytest
from unittest.mock import MagicMock, patch

from pct.messaggi import (
    GestioneMessaggi,
    Messaggio,
    CanaleMsggio,
    StatoMessaggio,
    TipoAutomazione,
    ConfigMessaggistica,
    ConfigEmail,
    ConfigTwilio,
    TEMPLATES,
)


@pytest.fixture
def cfg():
    return ConfigMessaggistica(
        email=ConfigEmail(
            smtp_host="smtp.example.com",
            smtp_port=587,
            username="user@example.com",
            password="secret",
            mittente_email="user@example.com",
            mittente_nome="Studio Test",
        ),
        twilio=ConfigTwilio(
            account_sid="ACtest",
            auth_token="token",
            numero_sms="+39123456789",
            numero_whatsapp="whatsapp:+39123456789",
        ),
        studio_nome="Studio Test",
    )


@pytest.fixture
def gm(tmp_path, cfg):
    return GestioneMessaggi(config=cfg, db_path=str(tmp_path / "messaggi.json"))


# ------------------------------------------------------------------ Template

def test_templates_definiti():
    """Tutti i tipi di automazione hanno un template."""
    for tipo in [
        TipoAutomazione.REMINDER_APPUNTAMENTO,
        TipoAutomazione.AVVISO_SCADENZA,
        TipoAutomazione.AGGIORNAMENTO_FASCICOLO,
        TipoAutomazione.BENVENUTO_CLIENTE,
        TipoAutomazione.RICHIESTA_DOCUMENTI,
        TipoAutomazione.SOLLECITO_PARCELLA,
    ]:
        assert tipo.value in TEMPLATES
        t = TEMPLATES[tipo.value]
        assert "oggetto" in t
        assert "sms" in t
        assert "email_html" in t


# ------------------------------------------------------------------ Email (mock SMTP)

def test_invia_email_mock(gm):
    """Invia email mocckando il server SMTP."""
    with patch("smtplib.SMTP") as mock_smtp:
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp.return_value.__exit__ = MagicMock(return_value=False)
        msg = gm.invia_email(
            destinatario="cliente@example.com",
            oggetto="Test",
            corpo_testo="Testo di prova",
        )
    assert msg.canale == CanaleMsggio.EMAIL
    assert msg.email_destinatario == "cliente@example.com"
    assert msg.stato in (StatoMessaggio.INVIATO, StatoMessaggio.FALLITO)


def test_invia_email_imposta_message_id_per_deduplica_inviati(gm):
    sent = {}

    class FakeSMTP:
        def __init__(self, *args, **kwargs):
            sent["init"] = (args, kwargs)

        def starttls(self, context=None):
            sent["starttls"] = context

        def login(self, username, password):
            sent["login"] = (username, password)

        def send_message(self, mime, *args, **kwargs):
            sent["mime"] = mime
            sent["send_args"] = (args, kwargs)

        def quit(self):
            sent["quit"] = True

    with patch("pct.messaggi._SMTPv4", FakeSMTP):
        msg = gm.invia_email(
            destinatario="cliente@example.com",
            oggetto="Test",
            corpo_testo="Testo di prova",
        )

    assert msg.stato == StatoMessaggio.INVIATO
    assert msg.sid_esterno.startswith("<")
    assert msg.sid_esterno.endswith(">")
    assert sent["mime"]["Message-ID"] == msg.sid_esterno


def test_email_salvata_in_db(tmp_path, cfg):
    """Un messaggio email è persistito nel DB."""
    db = str(tmp_path / "msg.json")
    gm1 = GestioneMessaggi(config=cfg, db_path=db)
    with patch("smtplib.SMTP"):
        gm1.invia_email("a@b.com", "Subj", "Body")
    gm2 = GestioneMessaggi(config=cfg, db_path=db)
    assert len(gm2.tutti()) == 1


def test_email_senza_smtp_fallisce(gm):
    """Email fallisce senza un server SMTP raggiungibile."""
    with patch("smtplib.SMTP", side_effect=ConnectionRefusedError("no server")):
        msg = gm.invia_email("a@b.com", "Subj", "Body")
    assert msg.stato == StatoMessaggio.FALLITO
    assert msg.errore != ""


def test_registra_email_inviata_da_canale_esterno(gm):
    msg = gm.registra_email_inviata(
        destinatario="cliente@example.com",
        oggetto="PEC locale",
        corpo_testo="Testo",
        message_id="<local-pec@example.test>",
        note="Invio confermato dal Local Signer.",
    )

    assert msg.stato == StatoMessaggio.INVIATO
    assert msg.sid_esterno == "<local-pec@example.test>"
    assert msg.inviato_il
    assert gm.get(msg.id).note == "Invio confermato dal Local Signer."


# ------------------------------------------------------------------ SMS/WA (mock Twilio)

def _mock_twilio(gm):
    """Restituisce un context manager che mocka il client Twilio."""
    mock_twilio = MagicMock()
    mock_twilio.messages.create.return_value = MagicMock(sid="SMtest123")
    return patch.object(gm, "_twilio_client", return_value=mock_twilio)


def test_invia_sms_mock(gm):
    with _mock_twilio(gm):
        msg = gm.invia_sms(telefono="+39333123456", testo="Ciao")
    assert msg.canale == CanaleMsggio.SMS
    assert msg.stato == StatoMessaggio.INVIATO
    assert msg.sid_esterno == "SMtest123"


def test_invia_whatsapp_mock(gm):
    with _mock_twilio(gm):
        msg = gm.invia_whatsapp(telefono="+39333123456", testo="Ciao WA")
    assert msg.canale == CanaleMsggio.WHATSAPP
    assert msg.stato == StatoMessaggio.INVIATO


def test_sms_senza_twilio_fallisce(gm):
    with patch.object(gm, "_twilio_client", side_effect=Exception("Twilio error")):
        msg = gm.invia_sms(telefono="+39333123456", testo="Test")
    assert msg.stato == StatoMessaggio.FALLITO


# ------------------------------------------------------------------ Template invio

def test_invia_da_template_reminder(gm):
    with patch("smtplib.SMTP"):
        msgs = gm.invia_da_template(
            tipo=TipoAutomazione.REMINDER_APPUNTAMENTO,
            canali=[CanaleMsggio.EMAIL],
            destinatario_email="test@example.com",
            variabili={
                "nome": "Mario Rossi",
                "data": "2024-03-15",
                "ora": "10:00",
                "tipo": "Udienza",
                "luogo": "Aula 3",
                "studio": "Studio Test",
                "telefono_studio": "+0212345678",
                "email_studio": "info@studio.it",
            },
        )
    assert len(msgs) == 1
    assert msgs[0].canale == CanaleMsggio.EMAIL


def test_template_sms_non_richiede_oggetto(gm):
    with _mock_twilio(gm):
        msgs = gm.invia_da_template(
            tipo=TipoAutomazione.AVVISO_SCADENZA,
            canali=[CanaleMsggio.SMS],
            destinatario_telefono="+39333123456",
            variabili={
                "nome": "Luigi",
                "scadenza": "2024-04-01",
                "tipo_atto": "Memoria",
                "numero_fascicolo": "2024/001",
                "studio": "Studio",
                "telefono_studio": "+02123",
            },
        )
    assert len(msgs) == 1
    assert msgs[0].canale == CanaleMsggio.SMS


# ------------------------------------------------------------------ Query

def test_tutti_filtra_per_canale(gm):
    with patch("smtplib.SMTP"):
        gm.invia_email("a@b.com", "S", "T")
    with _mock_twilio(gm):
        gm.invia_sms("+39333123456", "sms")
    email_msgs = gm.tutti(canale=CanaleMsggio.EMAIL)
    sms_msgs = gm.tutti(canale=CanaleMsggio.SMS)
    assert all(m.canale == CanaleMsggio.EMAIL for m in email_msgs)
    assert all(m.canale == CanaleMsggio.SMS for m in sms_msgs)


def test_per_cliente(gm):
    with patch("smtplib.SMTP"):
        gm.invia_email("a@b.com", "S1", "T1", id_cliente="CLI001")
        gm.invia_email("c@d.com", "S2", "T2", id_cliente="CLI002")
    assert len(gm.per_cliente("CLI001")) == 1
    assert len(gm.per_cliente("CLI002")) == 1
    assert len(gm.per_cliente("NONEXISTENT")) == 0


def test_elimina_messaggio(gm):
    with patch("smtplib.SMTP"):
        msg = gm.invia_email("a@b.com", "S", "T")
    gm.elimina(msg.id)
    assert gm.get(msg.id) is None


def test_elimina_inesistente_errore(gm):
    with pytest.raises(ValueError):
        gm.elimina("nonexistent-id")


def test_statistiche(gm):
    with patch("smtplib.SMTP"):
        gm.invia_email("a@b.com", "S1", "T1")
    with _mock_twilio(gm):
        gm.invia_sms("+39333123456", "sms")
    stats = gm.statistiche()
    assert stats["totale"] == 2
    assert stats["per_canale"]["EMAIL"] >= 1
    assert stats["per_canale"]["SMS"] >= 1


# ------------------------------------------------------------------ Validazione

def test_valida_email():
    assert GestioneMessaggi.valida_email("test@example.com")
    assert not GestioneMessaggi.valida_email("not-an-email")


def test_valida_telefono():
    assert GestioneMessaggi.valida_telefono("+39333123456")
    assert not GestioneMessaggi.valida_telefono("0333123456")
