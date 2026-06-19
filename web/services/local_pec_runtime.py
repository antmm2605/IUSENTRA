"""Runtime helpers for browser-local PEC delivery through Local Signer.

The hosted Flask process must not become the default SMTP sender for PEC:
many providers reject datacenter IPs and, more importantly, the operational
channel for the lawyer's workstation is the Local Signer running on the PC.
"""

from __future__ import annotations

import base64
import mimetypes
import tempfile
from pathlib import Path
from typing import Any

from pct.path_security import UnsafeRuntimePath, resolve_runtime_path


LOCAL_SIGNER_BASE_URL = "http://127.0.0.1:27272"


def build_local_pec_payload(
    *,
    pec_cfg: Any,
    destinatario: str,
    oggetto: str,
    corpo: str,
    attachment_path: str,
    attachment_name: str | None = None,
    include_attachment_content: bool = True,
) -> dict[str, Any]:
    """Build a Local Signer `/pec/send` payload without exposing any saved password."""

    try:
        path = resolve_runtime_path(attachment_path, extra_roots=(tempfile.gettempdir(), Path.cwd())).resolve(strict=True)
    except (OSError, RuntimeError, ValueError, UnsafeRuntimePath) as exc:
        raise ValueError("Allegato PEC non disponibile nell'area autorizzata.") from exc
    if not path.is_file():
        raise ValueError("Allegato PEC non disponibile.")
    # lgtm[py/path-injection] Allegato risolto con resolve_runtime_path e radici runtime consentite.
    filename = attachment_name or path.name
    mime_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    attachment = {
        "filename": filename,
        "mime_type": mime_type,
        "size_bytes": path.stat().st_size,
    }
    if include_attachment_content:
        attachment["content_base64"] = base64.b64encode(path.read_bytes()).decode("ascii")
    smtp_port = int(getattr(pec_cfg, "smtp_port", 465) or 465)
    use_ssl = bool(getattr(pec_cfg, "use_ssl", smtp_port == 465))
    use_tls = bool(getattr(pec_cfg, "use_tls", not use_ssl))
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
            "use_tls": use_tls,
            "to": destinatario,
            "subject": oggetto,
            "body": corpo,
            "attachments": [attachment],
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


def deposito_pec_body(documenti: list[str] | tuple[str, ...] | None = None) -> str:
    """Return the standard body used for local PEC delivery of a deposit envelope."""

    elenco = [str(item or "").strip() for item in (documenti or []) if str(item or "").strip()]
    files = ""
    if elenco:
        files = "\n\nIl file Atto.enc contiene i seguenti documenti:\n" + "\n".join(f"- {nome}" for nome in elenco)
    return (
        "Egregio sig. Cancelliere,\n\n"
        "Allego alla presente il file crittografato Atto.enc per il deposito telematico."
        f"{files}"
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
    documenti: list[str] | tuple[str, ...] | None = None,
    corpo_pec: str | None = None,
    busta_audit: dict[str, Any] | None = None,
    include_attachment_content: bool = True,
) -> dict[str, Any]:
    """Build the JSON contract used by browsers to complete PEC locally."""

    corpo_pec_finale = str(corpo_pec or "").strip() or deposito_pec_body(documenti)
    documenti_busta = [str(item or "").strip() for item in (documenti or []) if str(item or "").strip()]
    return {
        "ok": False,
        "requires_local_pec": True,
        "package_ready": True,
        "id_deposito": id_deposito,
        "pec_dest": pec_dest,
        "tipo_atto": tipo_atto,
        "timestamp": timestamp,
        "oggetto_pec": oggetto_pec,
        "corpo_pec": corpo_pec_finale,
        "documenti_busta": documenti_busta,
        "local_pec": build_local_pec_payload(
            pec_cfg=pec_cfg,
            destinatario=pec_dest,
            oggetto=oggetto_pec,
            corpo=corpo_pec_finale,
            attachment_path=attachment_path,
            attachment_name="Atto.enc",
            include_attachment_content=include_attachment_content,
        ),
        "validation": validation.to_dict() if hasattr(validation, "to_dict") else validation,
        "busta_audit": busta_audit or {},
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
