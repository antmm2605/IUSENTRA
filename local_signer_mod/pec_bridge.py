from __future__ import annotations

import base64
import mimetypes
import smtplib
import socket
import ssl
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from typing import Any


DEFAULT_TIMEOUT_SECONDS = 25
MAX_ATTACHMENT_BYTES = 100 * 1024 * 1024


class PecBridgeValidationError(ValueError):
    """Errore di validazione del payload PEC locale."""


def _text(value: Any) -> str:
    return str(value or "").strip()


def _coerce_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on", "si"}


def _coerce_int(value: Any, default: int, *, minimum: int = 1, maximum: int = 65535) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(min(parsed, maximum), minimum)


def _payload_config(payload: dict[str, Any]) -> dict[str, Any]:
    host = _text(payload.get("smtp_host") or payload.get("host"))
    port = _coerce_int(payload.get("smtp_port") or payload.get("port"), 465)
    use_ssl = _coerce_bool(payload.get("use_ssl"), port == 465)
    username = _text(payload.get("username") or payload.get("indirizzo") or payload.get("from"))
    sender = _text(payload.get("from") or payload.get("mittente") or username)
    password = _text(payload.get("password"))
    timeout = _coerce_int(
        payload.get("timeout") or payload.get("timeout_seconds"),
        DEFAULT_TIMEOUT_SECONDS,
        minimum=5,
        maximum=120,
    )
    if not host:
        raise PecBridgeValidationError("Host SMTP PEC mancante.")
    if not username:
        raise PecBridgeValidationError("Indirizzo o username PEC mancante.")
    if not sender:
        raise PecBridgeValidationError("Mittente PEC mancante.")
    if not password:
        raise PecBridgeValidationError(
            "Password PEC mancante. Inseriscila nel campo password: resta sul PC e non viene salvata dal server."
        )
    return {
        "host": host,
        "port": port,
        "use_ssl": use_ssl,
        "use_tls": _coerce_bool(payload.get("use_tls"), not use_ssl),
        "username": username,
        "password": password,
        "sender": sender,
        "timeout": timeout,
    }


def _connect_and_login(
    config: dict[str, Any],
    *,
    smtp_factory: Any = smtplib.SMTP,
    smtp_ssl_factory: Any = smtplib.SMTP_SSL,
) -> Any:
    context = ssl.create_default_context()
    if config["use_ssl"]:
        client = smtp_ssl_factory(
            config["host"],
            config["port"],
            timeout=config["timeout"],
            context=context,
        )
    else:
        client = smtp_factory(config["host"], config["port"], timeout=config["timeout"])
    try:
        client.ehlo()
        if not config["use_ssl"] and config["use_tls"]:
            client.starttls(context=context)
            client.ehlo()
        client.login(config["username"], config["password"])
        return client
    except Exception:
        _close_smtp(client)
        raise


def _close_smtp(client: Any) -> None:
    try:
        client.quit()
    except Exception:
        try:
            client.close()
        except Exception:
            pass


def _human_error(error: Exception, *, host: str = "", port: int | None = None) -> str:
    endpoint = f" verso {host}:{port}" if host and port else ""
    if isinstance(error, PecBridgeValidationError):
        return str(error)
    if isinstance(error, smtplib.SMTPAuthenticationError):
        return "Autenticazione SMTP PEC non riuscita. Verifica indirizzo, username e password."
    if isinstance(error, (socket.timeout, TimeoutError)):
        return (
            "Timeout SMTP PEC locale"
            f"{endpoint}: il provider non ha risposto entro il tempo limite da questo PC."
        )
    if isinstance(error, socket.gaierror):
        return f"Host SMTP PEC non risolto{endpoint}. Verifica il nome del server."
    if isinstance(error, ConnectionRefusedError):
        return f"Connessione SMTP PEC rifiutata{endpoint}. Verifica porta e SSL/TLS."
    if isinstance(error, ssl.SSLError):
        return f"Errore TLS/SSL SMTP PEC{endpoint}. Verifica porta, SSL/TLS e certificati del provider."
    if isinstance(error, smtplib.SMTPException):
        return f"Errore SMTP PEC locale{endpoint}: {error}"
    if isinstance(error, OSError):
        return f"Errore di rete SMTP PEC locale{endpoint}: {error}"
    return f"Errore SMTP PEC locale{endpoint}: {error}"


def test_pec_smtp_local(
    payload: dict[str, Any],
    *,
    smtp_factory: Any = smtplib.SMTP,
    smtp_ssl_factory: Any = smtplib.SMTP_SSL,
) -> dict[str, Any]:
    config: dict[str, Any] = {}
    client = None
    try:
        config = _payload_config(payload)
        client = _connect_and_login(
            config,
            smtp_factory=smtp_factory,
            smtp_ssl_factory=smtp_ssl_factory,
        )
        return {
            "ok": True,
            "canale": "locale",
            "messaggio": "Connessione SMTP PEC riuscita.",
            "endpoint": f"{config['host']}:{config['port']}",
        }
    except Exception as exc:
        return {
            "ok": False,
            "canale": "locale",
            "messaggio": _human_error(
                exc,
                host=str(config.get("host") or ""),
                port=config.get("port"),
            ),
        }
    finally:
        if client is not None:
            _close_smtp(client)


def _recipients(value: Any) -> list[str]:
    if isinstance(value, str):
        return [chunk.strip() for chunk in value.replace(";", ",").split(",") if chunk.strip()]
    if isinstance(value, (list, tuple, set)):
        return [_text(item) for item in value if _text(item)]
    return []


def _attachment_parts(item: dict[str, Any]) -> tuple[str, bytes, str]:
    filename = _text(item.get("filename") or item.get("nome") or item.get("name"))
    encoded = _text(item.get("content_base64") or item.get("base64") or item.get("contenuto_base64"))
    if not filename:
        raise PecBridgeValidationError("Nome allegato mancante.")
    if not encoded:
        raise PecBridgeValidationError(f"Contenuto base64 mancante per l'allegato {filename}.")
    try:
        content = base64.b64decode(encoded, validate=True)
    except Exception as exc:
        raise PecBridgeValidationError(f"Allegato {filename} non e' base64 valido.") from exc
    mime_type = _text(item.get("mime_type") or item.get("content_type")) or (
        mimetypes.guess_type(filename)[0] or "application/octet-stream"
    )
    return filename, content, mime_type


def _build_message(payload: dict[str, Any], config: dict[str, Any]) -> tuple[EmailMessage, list[str]]:
    to_recipients = _recipients(payload.get("to") or payload.get("destinatari") or payload.get("destinatario"))
    cc_recipients = _recipients(payload.get("cc"))
    bcc_recipients = _recipients(payload.get("bcc"))
    if not to_recipients and not cc_recipients and not bcc_recipients:
        raise PecBridgeValidationError("Destinatario PEC mancante.")

    subject = _text(payload.get("subject") or payload.get("oggetto")) or "Messaggio PEC IUSENTRA"
    body = _text(payload.get("body") or payload.get("corpo")) or "Invio generato da IUSENTRA."

    msg = EmailMessage()
    msg["From"] = config["sender"]
    if to_recipients:
        msg["To"] = ", ".join(to_recipients)
    if cc_recipients:
        msg["Cc"] = ", ".join(cc_recipients)
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid()
    msg.set_content(body)

    total_attachment_bytes = 0
    for item in payload.get("attachments") or payload.get("allegati") or []:
        if not isinstance(item, dict):
            raise PecBridgeValidationError("Formato allegato non valido.")
        filename, content, mime_type = _attachment_parts(item)
        total_attachment_bytes += len(content)
        if total_attachment_bytes > MAX_ATTACHMENT_BYTES:
            raise PecBridgeValidationError("Allegati troppo grandi per il ponte PEC locale.")
        maintype, _, subtype = mime_type.partition("/")
        if not maintype or not subtype:
            maintype, subtype = "application", "octet-stream"
        msg.add_attachment(content, maintype=maintype, subtype=subtype, filename=filename)

    return msg, [*to_recipients, *cc_recipients, *bcc_recipients]


def send_pec_local(
    payload: dict[str, Any],
    *,
    smtp_factory: Any = smtplib.SMTP,
    smtp_ssl_factory: Any = smtplib.SMTP_SSL,
) -> dict[str, Any]:
    config: dict[str, Any] = {}
    client = None
    try:
        config = _payload_config(payload)
        message, recipients = _build_message(payload, config)
        client = _connect_and_login(
            config,
            smtp_factory=smtp_factory,
            smtp_ssl_factory=smtp_ssl_factory,
        )
        client.send_message(message, from_addr=config["sender"], to_addrs=recipients)
        return {
            "ok": True,
            "inviato": True,
            "canale": "locale",
            "message_id": message["Message-ID"],
            "destinatari": recipients,
            "messaggio": "PEC inviata dal PC locale tramite Local Signer.",
        }
    except Exception as exc:
        return {
            "ok": False,
            "inviato": False,
            "canale": "locale",
            "messaggio": _human_error(
                exc,
                host=str(config.get("host") or ""),
                port=config.get("port"),
            ),
        }
    finally:
        if client is not None:
            _close_smtp(client)
