"""Runtime helpers for browser-local PEC delivery through Local Signer.

The hosted Flask process must not become the default SMTP sender for PEC:
many providers reject datacenter IPs and, more importantly, the operational
channel for the lawyer's workstation is the Local Signer running on the PC.
"""

from __future__ import annotations

import base64
import mimetypes
import os
import tempfile
from pathlib import Path
from typing import Any

from pct.path_security import UnsafeRuntimePath, resolve_runtime_path


LOCAL_SIGNER_BASE_URL = "http://127.0.0.1:27272"


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on", "si"}


def pec_server_send_enabled() -> bool:
    """Return True only when server-side real PEC delivery is explicitly enabled."""

    return _truthy(os.getenv("PEC_SEND_ENABLED") or os.getenv("PCT_PEC_SERVER_SEND_ENABLED"))


def build_local_pec_payload(
    *,
    pec_cfg: Any,
    destinatario: str,
    oggetto: str,
    corpo: str,
    attachment_path: str,
    attachment_name: str | None = None,
) -> dict[str, Any]:
    """Build a Local Signer `/pec/send` payload without exposing any saved password."""

    try:
        path = resolve_runtime_path(attachment_path, extra_roots=(tempfile.gettempdir(), Path.cwd())).resolve(strict=True)
    except (OSError, RuntimeError, ValueError, UnsafeRuntimePath) as exc:
        raise ValueError("Allegato PEC non disponibile nell'area autorizzata.") from exc
    if not path.is_file():
        raise ValueError("Allegato PEC non disponibile.")
    # lgtm[py/path-injection] Allegato risolto con resolve_runtime_path e radici runtime consentite.
    content = base64.b64encode(path.read_bytes()).decode("ascii")
    filename = attachment_name or path.name
    mime_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    smtp_port = int(getattr(pec_cfg, "smtp_port", 465) or 465)
    use_ssl = bool(getattr(pec_cfg, "use_ssl", smtp_port == 465))
    indirizzo = str(getattr(pec_cfg, "indirizzo", "") or "").strip()
    smtp_host = str(getattr(pec_cfg, "smtp_host", "") or "").strip()

    return {
        "endpoint": f"{LOCAL_SIGNER_BASE_URL}/pec/send",
        "requires_password": True,
        "channel": "local_signer",
        "messaggio": (
            "Invio PEC reale da completare dal PC locale tramite Local Signer. "
            "La password viene richiesta nel browser e inviata solo al servizio locale."
        ),
        "payload": {
            "indirizzo": indirizzo,
            "username": indirizzo,
            "from": indirizzo,
            "smtp_host": smtp_host,
            "smtp_port": smtp_port,
            "use_ssl": use_ssl,
            "to": destinatario,
            "subject": oggetto,
            "body": corpo,
            "attachments": [
                {
                    "filename": filename,
                    "content_base64": content,
                    "mime_type": mime_type,
                }
            ],
        },
    }


def deposito_pec_subject(
    *,
    tipo_atto: str,
    numero_rg: str | None,
    anno_rg: int | str | None,
    tribunale: str,
) -> str:
    """Compose the official PCT PEC subject without coupling routes to wording."""

    if numero_rg and anno_rg:
        return f"DEPOSITO TELEMATICO - {tipo_atto} - RG {numero_rg}/{anno_rg}"
    return f"DEPOSITO TELEMATICO - {tipo_atto} - {tribunale}"


def deposito_pec_body() -> str:
    """Return the standard body used for local PEC delivery of a deposit envelope."""

    return (
        "Deposito telematico tramite IUSENTRA.\n"
        "Si allega la busta telematica per il deposito.\n\n"
        "Invio eseguito dal PC locale tramite Local Signer."
    )


def local_pec_required_response(
    *,
    pec_cfg: Any,
    pec_dest: str,
    tipo_atto: str,
    id_deposito: str,
    timestamp: str,
    oggetto_pec: str,
    attachment_path: str,
    validation: Any,
) -> dict[str, Any]:
    """Build the JSON contract used by browsers to complete PEC locally."""

    return {
        "ok": False,
        "requires_local_pec": True,
        "id_deposito": id_deposito,
        "pec_dest": pec_dest,
        "tipo_atto": tipo_atto,
        "timestamp": timestamp,
        "local_pec": build_local_pec_payload(
            pec_cfg=pec_cfg,
            destinatario=pec_dest,
            oggetto=oggetto_pec,
            corpo=deposito_pec_body(),
            attachment_path=attachment_path,
            attachment_name=f"Busta_{id_deposito}.enc",
        ),
        "validation": validation.to_dict() if hasattr(validation, "to_dict") else validation,
        "messaggio": (
            "Invio PEC reale da completare dal PC locale tramite Local Signer. "
            "Il server cloud non tenta l'SMTP."
        ),
    }


def local_pec_confirmation_result(message_id: str) -> dict[str, Any]:
    """Normalize the successful local-send acknowledgement for deposit routes."""

    cleaned = str(message_id or "").strip()
    if not cleaned:
        raise ValueError("Message-ID dell'invio PEC locale mancante.")
    return {
        "inviato": True,
        "message_id": cleaned,
        "local": True,
        "canale": "local_signer",
    }
