"""Bridge dati per le pagine Messaggi della shell React app-v2.

Normalizza lo storico e il form multicanale senza creare una seconda source of
truth. Le scritture restano sul servizio operativo ``/messaggi/nuovo``.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping
from datetime import date, datetime, timedelta, timezone
from typing import Any

from pct.messaggi import CanaleMsggio, StatoMessaggio

MONTHS_SHORT = ["gen", "feb", "mar", "apr", "mag", "giu", "lug", "ago", "set", "ott", "nov", "dic"]


def _enum_value(value: Any) -> str:
    return str(getattr(value, "value", value) or "")


def _text(value: Any, fallback: str = "") -> str:
    return " ".join(str(value or fallback).split())


def _short(value: Any, limit: int = 140) -> str:
    text = _text(value)
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "..."


def _safe(label: str, func: Callable[[], Any], fallback: Any) -> Any:
    try:
        return func()
    except Exception:
        return fallback


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value.astimezone().replace(tzinfo=None) if value.tzinfo else value
    raw = str(value or "").strip()
    if not raw:
        return None
    for sample in (raw.replace("Z", "+00:00"), raw[:19], raw[:10]):
        try:
            parsed = datetime.fromisoformat(sample)
            return parsed.astimezone().replace(tzinfo=None) if parsed.tzinfo else parsed
        except ValueError:
            continue
    return None


def _format_date_time(value: Any) -> str:
    parsed = _parse_datetime(value)
    if not parsed:
        return ""
    today = date.today()
    if parsed.date() == today:
        return parsed.strftime("oggi %H:%M")
    if parsed.date() == today - timedelta(days=1):
        return parsed.strftime("ieri %H:%M")
    if parsed.date() == today + timedelta(days=1):
        return parsed.strftime("domani %H:%M")
    if parsed.year == today.year:
        return f"{parsed.day} {MONTHS_SHORT[parsed.month - 1]} {parsed.strftime('%H:%M')}"
    return parsed.strftime("%d/%m/%Y %H:%M")


def _initials(value: Any) -> str:
    parts = [part for part in str(value or "").replace("@", " ").replace(".", " ").split() if part]
    if not parts:
        return ""
    return "".join(part[0] for part in parts[:2]).upper()


def _status_label(value: str) -> str:
    return {
        StatoMessaggio.IN_CODA.value: "In attesa",
        StatoMessaggio.INVIATO.value: "Inviato",
        StatoMessaggio.CONSEGNATO.value: "Consegnato",
        StatoMessaggio.LETTO.value: "Letto",
        StatoMessaggio.FALLITO.value: "Errore",
        StatoMessaggio.ANNULLATO.value: "Annullato",
    }.get(value, value.replace("_", " ").title())


def _status_tone(value: str) -> str:
    return {
        StatoMessaggio.IN_CODA.value: "warning",
        StatoMessaggio.INVIATO.value: "primary",
        StatoMessaggio.CONSEGNATO.value: "success",
        StatoMessaggio.LETTO.value: "info",
        StatoMessaggio.FALLITO.value: "danger",
        StatoMessaggio.ANNULLATO.value: "neutral",
    }.get(value, "neutral")


def _channel_label(value: str) -> str:
    return {"EMAIL": "Email", "SMS": "SMS", "WHATSAPP": "WhatsApp"}.get(value, value)


def _client_lookup(clienti: list[Any]) -> dict[str, Any]:
    return {str(getattr(cliente, "id", "") or ""): cliente for cliente in clienti if str(getattr(cliente, "id", "") or "")}


def _fiscal_id(cliente: Any) -> str:
    return _text(
        getattr(cliente, "identificativo_fiscale", "")
        or getattr(cliente, "codice_fiscale", "")
        or getattr(cliente, "partita_iva", "")
    )


def _client_options(clienti: list[Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for cliente in clienti:
        item_id = _text(getattr(cliente, "id", ""))
        if not item_id:
            continue
        recapiti = getattr(cliente, "recapiti", None)
        rows.append({
            "id": item_id,
            "label": _text(getattr(cliente, "nome_completo", "")) or "Cliente senza nome",
            "fiscalId": _fiscal_id(cliente),
            "email": _text(getattr(recapiti, "email", "")),
            "phone": _text(getattr(recapiti, "cellulare", "") or getattr(recapiti, "telefono", "")),
        })
    return rows


def _message_item(message: Any, clienti_by_id: dict[str, Any]) -> dict[str, Any]:
    canale = _enum_value(getattr(message, "canale", "EMAIL")) or "EMAIL"
    stato = _enum_value(getattr(message, "stato", StatoMessaggio.IN_CODA.value))
    id_cliente = _text(getattr(message, "id_cliente", ""))
    cliente = clienti_by_id.get(id_cliente)
    client_label = _text(getattr(cliente, "nome_completo", "")) if cliente else ""
    destination = _text(getattr(message, "email_destinatario", "") or getattr(message, "telefono_destinatario", ""))
    recipient_name = _text(getattr(message, "nome_destinatario", ""))
    recipient = recipient_name or client_label or destination or "Destinatario non indicato"
    subject = _text(getattr(message, "oggetto", ""))
    body = _text(getattr(message, "corpo", ""))
    sid = _text(getattr(message, "sid_esterno", ""))
    manual_whatsapp = canale == CanaleMsggio.WHATSAPP.value and sid.startswith("https://wa.me")
    item_id = _text(getattr(message, "id", ""))
    return {
        "id": item_id,
        "channel": canale,
        "channelLabel": _channel_label(canale),
        "recipientName": recipient_name,
        "recipient": recipient,
        "destination": destination,
        "subject": subject,
        "body": body,
        "preview": _short(subject or body or "Messaggio senza testo", 150),
        "status": stato,
        "statusLabel": _status_label(stato),
        "tone": _status_tone(stato),
        "createdAt": _text(getattr(message, "creato_il", "")),
        "createdLabel": _format_date_time(getattr(message, "creato_il", "")),
        "sentLabel": _format_date_time(getattr(message, "inviato_il", "")),
        "automationLabel": _text(getattr(message, "tipo_automazione", "")).replace("_", " ").title(),
        "clientLabel": client_label,
        "clientHref": f"/clienti/{id_cliente}/cartella" if id_cliente else "",
        "detailHref": f"/messaggi/{item_id}",
        "whatsappLink": sid if sid.startswith("https://wa.me") else "",
        "error": _text(getattr(message, "errore", "")),
        "note": _text(getattr(message, "note", "")),
        "initials": _initials(recipient),
        "manualWhatsapp": manual_whatsapp,
    }


def _summary(items: list[dict[str, Any]]) -> dict[str, int]:
    statuses = Counter(str(item.get("status") or "") for item in items)
    channels = Counter(str(item.get("channel") or "") for item in items)
    week_ago = datetime.now() - timedelta(days=7)
    recent = 0
    for item in items:
        created = _parse_datetime(item.get("createdAt"))
        if created and created >= week_ago:
            recent += 1
    return {
        "total": len(items),
        "sent": int(statuses.get(StatoMessaggio.INVIATO.value, 0)),
        "queued": int(statuses.get(StatoMessaggio.IN_CODA.value, 0)),
        "delivered": int(statuses.get(StatoMessaggio.CONSEGNATO.value, 0)),
        "read": int(statuses.get(StatoMessaggio.LETTO.value, 0)),
        "failed": int(statuses.get(StatoMessaggio.FALLITO.value, 0)),
        "cancelled": int(statuses.get(StatoMessaggio.ANNULLATO.value, 0)),
        "email": int(channels.get(CanaleMsggio.EMAIL.value, 0)),
        "sms": int(channels.get(CanaleMsggio.SMS.value, 0)),
        "whatsapp": int(channels.get(CanaleMsggio.WHATSAPP.value, 0)),
        "recent": recent,
        "manualWhatsapp": sum(1 for item in items if item.get("manualWhatsapp")),
    }


def _facet_rows(items: list[dict[str, Any]], key: str, labels: Mapping[str, str], all_label: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = [{"value": "", "label": all_label, "count": len(items)}]
    for value, label in labels.items():
        rows.append({"value": value, "label": label, "count": sum(1 for item in items if item.get(key) == value)})
    return rows


def _channel_info(config: Mapping[str, Any], summary: dict[str, int]) -> list[dict[str, Any]]:
    twilio_ready = bool(config.get("TWILIO_SID") and config.get("TWILIO_TOKEN"))
    smtp_ready = bool(config.get("SMTP_HOST") or config.get("MAIL_SERVER") or config.get("MAIL_HOST"))
    return [
        {
            "value": "EMAIL",
            "label": "Email",
            "subtitle": "Invio via SMTP configurato nelle impostazioni.",
            "tone": "primary",
            "count": summary.get("email", 0),
            "available": True,
            "configured": smtp_ready,
            "destinationPlaceholder": "cliente@esempio.it",
            "destinationHelp": "Indirizzo email del destinatario.",
            "subjectVisible": True,
        },
        {
            "value": "SMS",
            "label": "SMS",
            "subtitle": "Invio tramite Twilio SMS quando configurato.",
            "tone": "success",
            "count": summary.get("sms", 0),
            "available": True,
            "configured": twilio_ready,
            "destinationPlaceholder": "+39 333 1234567",
            "destinationHelp": "Numero in formato E.164, ad esempio +39 333 1234567.",
            "subjectVisible": False,
            "maxLength": 160,
        },
        {
            "value": "WHATSAPP",
            "label": "WhatsApp",
            "subtitle": "API Twilio se presente, altrimenti link WhatsApp Web precompilato.",
            "tone": "success",
            "count": summary.get("whatsapp", 0),
            "available": True,
            "configured": twilio_ready,
            "destinationPlaceholder": "+39 333 1234567",
            "destinationHelp": "Numero in formato E.164. Senza Twilio viene creato un link WhatsApp Web.",
            "subjectVisible": False,
        },
    ]


def _filter_items(items: list[dict[str, Any]], query: Mapping[str, Any]) -> list[dict[str, Any]]:
    q = _text(query.get("q", "")).lower()
    canale = _text(query.get("canale") or query.get("channel")).upper()
    stato = _text(query.get("stato") or query.get("status")).upper()
    rows = items
    if canale:
        rows = [item for item in rows if item.get("channel") == canale]
    if stato:
        rows = [item for item in rows if item.get("status") == stato]
    if q:
        rows = [
            item
            for item in rows
            if q in " ".join(
                str(item.get(key, ""))
                for key in ("recipient", "destination", "subject", "body", "clientLabel", "statusLabel")
            ).lower()
        ]
    return rows


def _templates() -> list[dict[str, str]]:
    return [
        {
            "id": "aggiornamento-pratica",
            "label": "Aggiornamento pratica",
            "channel": "ALL",
            "subject": "Aggiornamento sulla pratica",
            "body": "Gentile {nome},\n\nla informiamo che la Sua pratica è stata aggiornata. Restiamo a disposizione per ogni chiarimento.\n\nCordiali saluti",
        },
        {
            "id": "richiesta-documenti",
            "label": "Richiesta documenti",
            "channel": "ALL",
            "subject": "Richiesta documentazione",
            "body": "Gentile {nome},\n\nper proseguire abbiamo necessità della seguente documentazione:\n- documento di identità\n- codice fiscale\n- documenti relativi alla pratica\n\nPuò inviarli rispondendo a questo messaggio.",
        },
        {
            "id": "promemoria-appuntamento",
            "label": "Promemoria appuntamento",
            "channel": "ALL",
            "subject": "Promemoria appuntamento",
            "body": "Gentile {nome},\n\nle ricordiamo l’appuntamento presso lo Studio. Per modifiche o conferme può rispondere a questo messaggio.\n\nGrazie",
        },
    ]


def _sort_key(item: dict[str, Any]) -> str:
    return str(item.get("createdAt") or "")


def build_react_messaggi_payload(
    *,
    get_messaggi: Callable[[], Any],
    get_clienti: Callable[[], Any],
    query: Mapping[str, Any] | None = None,
    config: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    query = query or {}
    config = config or {}
    clienti = _safe("clienti", lambda: get_clienti().tutti(), [])
    clienti_by_id = _client_lookup(clienti)
    messages = _safe("messaggi", lambda: get_messaggi().tutti(), [])
    items = [_message_item(message, clienti_by_id) for message in messages]
    items.sort(key=_sort_key, reverse=True)
    summary = _summary(items)
    filtered = _filter_items(items, query)
    return {
        "source": "repository_reali",
        "generated_at": _iso_now(),
        "contracts": {"mock_fallback": False, "read_only": False, "writes": "operational_routes"},
        "summary": summary,
        "items": filtered,
        "facets": {
            "channels": _facet_rows(items, "channel", {"EMAIL": "Email", "SMS": "SMS", "WHATSAPP": "WhatsApp"}, "Tutti i canali"),
            "statuses": _facet_rows(items, "status", {item.value: _status_label(item.value) for item in StatoMessaggio}, "Tutti gli stati"),
        },
        "filters": {
            "q": _text(query.get("q", "")),
            "channel": _text(query.get("canale") or query.get("channel")).upper(),
            "status": _text(query.get("stato") or query.get("status")).upper(),
        },
        "actions": {
            "newMessage": "/messaggi/nuovo",
            "sendEndpoint": "/messaggi/nuovo",
            "settings": "/impostazioni",
            "emailSettings": "/email/impostazioni",
        },
        "channelInfo": _channel_info(config, summary),
        "lex": [
            "Controlla i messaggi in errore prima di inviare nuove comunicazioni sullo stesso canale.",
            "Per WhatsApp senza Twilio verifica che l'utente apra il link Web: il messaggio resta tracciato come invio manuale.",
            "Collega sempre il cliente quando il messaggio riguarda un fascicolo o un conferimento.",
        ],
    }


def build_react_messaggi_nuovo_payload(
    *,
    get_clienti: Callable[[], Any],
    query: Mapping[str, Any] | None = None,
    config: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    query = query or {}
    config = config or {}
    clienti = _safe("clienti", lambda: get_clienti().tutti(), [])
    requested_channel = _text(query.get("canale") or query.get("channel") or "EMAIL").upper()
    if requested_channel not in {"EMAIL", "SMS", "WHATSAPP"}:
        requested_channel = "EMAIL"
    id_cliente = _text(query.get("id_cliente") or query.get("idCliente"))
    summary = {"email": 0, "sms": 0, "whatsapp": 0}
    return {
        "source": "repository_reali",
        "generated_at": _iso_now(),
        "contracts": {"mock_fallback": False, "read_only": False, "writes": "operational_routes"},
        "channelInfo": _channel_info(config, summary),
        "clientOptions": _client_options(clienti),
        "templates": _templates(),
        "query": {
            "channel": requested_channel,
            "idCliente": id_cliente,
            "fromCliente": _text(query.get("from_cliente") or query.get("fromCliente")),
        },
        "actions": {
            "messagesList": "/messaggi",
            "sendEndpoint": "/messaggi/nuovo",
            "clientFolder": f"/clienti/{id_cliente}/cartella" if id_cliente else "",
        },
        "insights": [
            "La scrittura resta sul servizio operativo per riusare SMTP, Twilio e alternativa WhatsApp Web già testati.",
            "Il destinatario viene precompilato dal cliente selezionato in base al canale.",
            "Per SMS mantieni il testo compatto; per email usa l'oggetto per rendere tracciabile la comunicazione.",
        ],
    }
