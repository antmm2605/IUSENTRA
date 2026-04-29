"""Bridge dati per la pagina React Email PEC.

La funzione costruisce payload in sola lettura sopra GestioneEmailRicevute,
riusando la casella locale e i servizi Flask auditati per le azioni operative.
"""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta, timezone
from typing import Any
from urllib.parse import quote

from pct.email_client import CartellaEmail, GestioneEmailRicevute, StatoEmail

MONTHS_SHORT = ["gen", "feb", "mar", "apr", "mag", "giu", "lug", "ago", "set", "ott", "nov", "dic"]


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _enum_value(value: Any) -> str:
    return str(getattr(value, "value", value) or "")


def _safe_text(value: Any, fallback: str = "") -> str:
    text = " ".join(str(value or "").split())
    return text or fallback


def _short_text(value: Any, limit: int = 180) -> str:
    text = _safe_text(value)
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "..."


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    raw = str(value or "").strip()
    if not raw:
        return None
    for sample in (raw.replace("Z", "+00:00"), raw[:19], raw[:10]):
        try:
            parsed = datetime.fromisoformat(sample)
            if parsed.tzinfo:
                parsed = parsed.astimezone().replace(tzinfo=None)
            return parsed
        except ValueError:
            continue
    return None


def _format_time(value: Any) -> str:
    parsed = _parse_datetime(value)
    if not parsed:
        return ""
    today = date.today()
    if parsed.date() == today:
        return parsed.strftime("%H:%M")
    if parsed.date() == today - timedelta(days=1):
        return "ieri"
    if parsed.year == today.year:
        return f"{parsed.day} {MONTHS_SHORT[parsed.month - 1]}"
    return parsed.strftime("%d/%m/%Y")


def _normalise_folder(value: Any) -> str:
    raw = _enum_value(value).upper()
    if raw == CartellaEmail.INVIATI or raw in {"SENT", "SENT ITEMS", "POSTA INVIATA"}:
        return CartellaEmail.INVIATI
    if raw == CartellaEmail.CESTINO or raw in {"TRASH", "DELETED", "DELETED ITEMS", "POSTA ELIMINATA"}:
        return CartellaEmail.CESTINO
    return CartellaEmail.INBOX


def _tone(email_obj: Any) -> str:
    pct = str(getattr(email_obj, "stato_pct", "") or "").upper()
    if any(marker in pct for marker in ("RIFIUT", "ERRORE")):
        return "danger"
    if any(marker in pct for marker in ("WARN", "ANOMALIA")):
        return "warning"
    if pct:
        return "primary"
    if getattr(email_obj, "e_pst", False):
        return "purple"
    if _normalise_folder(getattr(email_obj, "cartella", "")) == CartellaEmail.INVIATI:
        return "success"
    return "neutral"


def _sync_inviati_da_messaggi(gestore: GestioneEmailRicevute, messaggi_db: str) -> None:
    """Allinea le email inviate da GestioneMessaggi, come fa la vista operativa."""
    if not messaggi_db:
        return
    try:
        from pct.messaggi import CanaleMsggio, GestioneMessaggi

        manager = GestioneMessaggi(config=None, db_path=messaggi_db)
        inviati = []
        for msg in manager.tutti(canale=CanaleMsggio.EMAIL):
            stato = _enum_value(getattr(msg, "stato", ""))
            if stato in {"INVIATO", "CONSEGNATO", "LETTO"}:
                inviati.append(msg)
        if inviati:
            gestore.sincronizza_inviati(inviati)
    except Exception:
        return


def _email_row(email_obj: Any) -> dict[str, Any]:
    email_id = str(getattr(email_obj, "id", "") or "")
    folder = _normalise_folder(getattr(email_obj, "cartella", ""))
    timestamp = str(getattr(email_obj, "timestamp", "") or getattr(email_obj, "data", "") or getattr(email_obj, "ricevuta_il", "") or "")
    sender_name = _safe_text(getattr(email_obj, "mittente_nome", ""))
    sender = _safe_text(getattr(email_obj, "mittente", ""))
    recipients = _safe_text(getattr(email_obj, "destinatari", ""))
    subject = _safe_text(getattr(email_obj, "oggetto", ""), "(nessun oggetto)")
    status = _enum_value(getattr(email_obj, "stato", ""))
    encoded_id = quote(email_id, safe="")
    return {
        "id": email_id,
        "folder": folder,
        "status": status,
        "sender": sender,
        "senderName": sender_name,
        "recipients": recipients,
        "subject": subject,
        "preview": _short_text(getattr(email_obj, "anteprima", "") or getattr(email_obj, "corpo_testo", ""), 220),
        "timestamp": timestamp,
        "timeLabel": _format_time(timestamp),
        "unread": status == StatoEmail.NON_LETTA,
        "isPst": bool(getattr(email_obj, "e_pst", False)),
        "pctStatus": _safe_text(getattr(email_obj, "stato_pct", "")),
        "attachmentCount": len(list(getattr(email_obj, "allegati", []) or [])),
        "origin": _safe_text(getattr(email_obj, "origine", "")),
        "detailHref": f"/email/messaggio/{encoded_id}",
        "operationalHref": f"/email/?cartella={folder}&id={encoded_id}",
        "replyHref": f"/email/scrivi?a={quote(sender, safe='')}&oggetto={quote('Re: ' + subject, safe='')}",
        "trashHref": f"/email/{encoded_id}/cestino",
        "restoreHref": f"/email/{encoded_id}/ripristina",
        "deleteHref": f"/email/{encoded_id}/elimina",
        "markReadHref": f"/email/{encoded_id}/segna-letta",
        "markUnreadHref": f"/email/{encoded_id}/segna-non-letta",
        "tone": _tone(email_obj),
    }


def _facet(value: str, label: str, count: int) -> dict[str, Any]:
    return {"value": value, "label": label, "count": int(count or 0)}


def build_react_email_payload(
    *,
    db_path: str,
    messaggi_db: str = "",
    folder: str = CartellaEmail.INBOX,
    query: str = "",
    stato: str = "",
    solo_pst: bool = False,
    con_allegati: bool = False,
    stato_pct: str = "",
    origine: str = "",
    data_da: str = "",
    data_a: str = "",
) -> dict[str, Any]:
    gestore = GestioneEmailRicevute(db_path=db_path)
    _sync_inviati_da_messaggi(gestore, messaggi_db)

    folder_valida = _normalise_folder(folder)
    emails = gestore.tutte(
        cartella=folder_valida,
        solo_non_lette=stato == StatoEmail.NON_LETTA,
        q=query,
        stato_lettura=stato if stato in {StatoEmail.NON_LETTA, StatoEmail.LETTA} else "",
        solo_pst=solo_pst,
        con_allegati=con_allegati,
        stato_pct=stato_pct,
        origine=origine,
        data_da=data_da,
        data_a=data_a,
    )
    all_emails = list(gestore._carica().values())  # noqa: SLF001 - bridge read-only su repository operativa
    stats = gestore.statistiche()
    rows = [_email_row(email_obj) for email_obj in emails]
    pct_counts = Counter(str(getattr(email_obj, "stato_pct", "") or "") for email_obj in all_emails if getattr(email_obj, "stato_pct", ""))

    attachments_total = sum(len(list(getattr(email_obj, "allegati", []) or [])) for email_obj in all_emails)
    auto_linked = sum(1 for email_obj in all_emails if bool(getattr(email_obj, "auto_registrata", False)))
    warning_total = sum(
        1
        for email_obj in all_emails
        if any(marker in str(getattr(email_obj, "stato_pct", "") or "").upper() for marker in ("RIFIUT", "ERRORE", "WARN"))
    )

    return {
        "source": "repository_reali",
        "generatedAt": _iso_now(),
        "contracts": {"mock_fallback": False, "read_only": True},
        "summary": {
            "total": stats.get("totale", len(all_emails)),
            "filtered": len(rows),
            "inbox": stats.get("inbox", 0),
            "unread": stats.get("non_lette", 0),
            "sent": stats.get("inviati", 0),
            "trash": stats.get("cestino", 0),
            "pst": stats.get("pst", 0),
            "attachments": attachments_total,
            "autoLinked": auto_linked,
            "warnings": warning_total,
        },
        "items": rows,
        "facets": {
            "folders": [
                _facet(CartellaEmail.INBOX, "In arrivo", int(stats.get("inbox", 0))),
                _facet(CartellaEmail.INVIATI, "Inviati", int(stats.get("inviati", 0))),
                _facet(CartellaEmail.CESTINO, "Cestino", int(stats.get("cestino", 0))),
            ],
            "statuses": [
                _facet("tutti", "Tutte", len(all_emails)),
                _facet(StatoEmail.NON_LETTA, "Non lette", int(stats.get("non_lette", 0))),
                _facet(StatoEmail.LETTA, "Lette", sum(1 for email_obj in all_emails if getattr(email_obj, "stato", "") == StatoEmail.LETTA)),
                _facet(StatoEmail.CESTINO, "Nel cestino", int(stats.get("cestino", 0))),
            ],
            "pctStatuses": [
                _facet("", "Tutti gli esiti", int(stats.get("pst", 0))),
                *[_facet(value, value, count) for value, count in sorted(pct_counts.items())],
            ],
        },
        "actions": {
            "compose": "/email/scrivi",
            "settings": "/email/impostazioni",
            "sync": "/email/sincronizza",
            "autoEsiti": "/email/auto-esiti",
            "operationalInbox": "/email/",
            "localPecTest": "/email/impostazioni",
            "lex": "/lex?context=email-pec",
        },
    }
