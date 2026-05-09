"""Payload e azioni React per la scheda Notifiche nelle impostazioni."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from flask import current_app, g, request


def _text(value: Any, fallback: str = "") -> str:
    return str(value if value is not None else fallback).strip()


def _api_key_valida() -> bool:
    api_key = str(current_app.config.get("API_KEY", "") or "")
    return bool(api_key and request.headers.get("X-API-Key") == api_key)


def _can(permission: str) -> bool:
    if _api_key_valida():
        return True
    user = g.get("utente_corrente")
    checker = getattr(user, "ha_permesso", None)
    return bool(callable(checker) and checker(permission))


def _studio_nome() -> str:
    return _text(current_app.config.get("STUDIO_NOME"), "Studio Legale") or "Studio Legale"


def _log_path() -> Path:
    raw = _text(current_app.config.get("NOTIFICHE_LOG"), "./notifiche/log.json")
    return Path(raw)


def _leggi_log() -> list[dict[str, Any]]:
    path = _log_path()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _scrivi_log(entry: dict[str, Any]) -> None:
    path = _log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = _leggi_log()
    rows.insert(0, entry)
    path.write_text(json.dumps(rows[:200], ensure_ascii=False, indent=2), encoding="utf-8")


def _format_dt(value: Any) -> str:
    raw = _text(value)
    if not raw:
        return ""
    try:
        parsed = datetime.fromisoformat(raw)
        return parsed.strftime("%d/%m/%Y %H:%M")
    except ValueError:
        return raw[:19].replace("T", " ")


def _config_wa(studio_cfg: Any | None = None):
    from pct.notifiche_wa import ConfigWA

    whatsapp = getattr(studio_cfg, "whatsapp", None)
    return ConfigWA(
        twilio_sid=_text(getattr(whatsapp, "twilio_sid", "") or current_app.config.get("TWILIO_SID", "")),
        twilio_token=_text(getattr(whatsapp, "twilio_token", "") or current_app.config.get("TWILIO_TOKEN", "")),
        twilio_numero=_text(getattr(whatsapp, "twilio_numero", "") or current_app.config.get("TWILIO_NUMERO", "")),
        callmebot_key=_text(getattr(whatsapp, "callmebot_key", "") or current_app.config.get("CALLMEBOT_KEY", "")),
    )


def _clienti():
    from web.helpers import get_clienti

    return get_clienti()


def _agenda():
    from web.helpers import get_agenda

    return get_agenda()


def _cliente_payload(cliente: Any) -> dict[str, str]:
    numero = _text(getattr(getattr(cliente, "recapiti", None), "cellulare", ""))
    return {
        "id": _text(getattr(cliente, "id", "")),
        "nome": _text(getattr(cliente, "nome_completo", "")),
        "numero": numero,
        "email": _text(getattr(getattr(cliente, "recapiti", None), "email", "")),
    }


def _domani_payload(clienti_by_id: dict[str, Any]) -> list[dict[str, Any]]:
    domani = date.today() + timedelta(days=1)
    rows: list[dict[str, Any]] = []
    try:
        appointments = _agenda().tutti()
    except Exception as exc:
        current_app.logger.warning("Agenda notifiche React non disponibile: %s", exc)
        return rows
    for item in appointments:
        try:
            data_ora = item.data_ora_dt
        except Exception:
            continue
        if data_ora.date() != domani:
            continue
        cliente = clienti_by_id.get(_text(getattr(item, "id_cliente", "")))
        numero = _text(getattr(getattr(cliente, "recapiti", None), "cellulare", "")) if cliente else ""
        rows.append(
            {
                "id": _text(getattr(item, "id", "")),
                "titolo": _text(getattr(item, "titolo", "")),
                "ora": data_ora.strftime("%H:%M"),
                "luogo": _text(getattr(item, "luogo", "")),
                "cliente": _text(getattr(cliente, "nome_completo", "")) if cliente else _text(getattr(item, "cliente", "")),
                "id_cliente": _text(getattr(item, "id_cliente", "")),
                "numero": numero,
                "inviabile": bool(numero),
            }
        )
    return rows


def _registro_payload() -> list[dict[str, Any]]:
    rows = []
    for index, row in enumerate(_leggi_log()[:30]):
        esito = row.get("esito") if isinstance(row.get("esito"), dict) else {}
        ok = esito.get("ok") if isinstance(esito, dict) else None
        rows.append(
            {
                "id": f"notifica-{index}",
                "quando": _format_dt(row.get("ts")),
                "tipo": _text(row.get("tipo")),
                "cliente": _text(row.get("cliente")),
                "numero": _text(row.get("numero")),
                "stato": "inviata" if ok is True else "link pronto" if ok is None else "da verificare",
            }
        )
    return rows


def build_notifiche_payload(studio_cfg: Any | None = None) -> dict[str, Any]:
    config = _config_wa(studio_cfg)
    try:
        clienti = _clienti().tutti()
    except Exception as exc:
        current_app.logger.warning("Clienti notifiche React non disponibili: %s", exc)
        clienti = []
    clienti_con_numero = [_cliente_payload(cliente) for cliente in clienti if _cliente_payload(cliente)["numero"]]
    clienti_by_id = {_text(getattr(cliente, "id", "")): cliente for cliente in clienti}
    appuntamenti = _domani_payload(clienti_by_id)
    registro = _registro_payload()
    automatico = bool(config.ha_twilio or config.ha_callmebot)
    return {
        "available": True,
        "can_send": _can("messaggi.scrivi") or _can("admin.configura"),
        "channel": {
            "automatico": automatico,
            "label": "Invio automatico attivo" if automatico else "Invio manuale WhatsApp disponibile",
            "detail": "I messaggi possono partire dal gestionale." if automatico else "Il gestionale prepara il messaggio e apre WhatsApp per l'invio.",
        },
        "clienti": clienti_con_numero[:300],
        "clienti_totali": len(clienti),
        "clienti_con_numero": len(clienti_con_numero),
        "appuntamenti_domani": appuntamenti,
        "appuntamenti_inviabili": sum(1 for item in appuntamenti if item.get("inviabile")),
        "registro": registro,
        "registro_totale": len(_leggi_log()),
        "quick_texts": [
            "Le ricordiamo l'appuntamento fissato con lo studio.",
            "La documentazione richiesta e' disponibile per la consultazione.",
            "Lo studio resta a disposizione per eventuali chiarimenti.",
        ],
    }


def _resolve_cliente(payload: dict[str, Any]) -> tuple[Any | None, str]:
    id_cliente = _text(payload.get("id_cliente"))
    numero = _text(payload.get("numero"))
    cliente = _clienti().get(id_cliente) if id_cliente else None
    if cliente:
        numero = _text(getattr(getattr(cliente, "recapiti", None), "cellulare", "")) or numero
    return cliente, numero


def _build_message(cliente: Any | None, testo: str) -> str:
    from pct.notifiche_wa import msg_libero

    nome = _text(getattr(cliente, "nome_completo", ""), "Cliente")
    return msg_libero(nome, testo, _studio_nome())


def prepare_notifica_link(payload: dict[str, Any]) -> dict[str, Any]:
    if not (_can("messaggi.scrivi") or _can("admin.configura")):
        return {"ok": False, "message": "Permesso richiesto per preparare il messaggio."}
    from pct.notifiche_wa import wa_link

    data = payload or {}
    testo = _text(data.get("testo"))
    cliente, numero = _resolve_cliente(data)
    if not numero or not testo:
        return {"ok": False, "message": "Seleziona un cliente con numero WhatsApp e scrivi il messaggio."}
    return {
        "ok": True,
        "link": wa_link(numero, _build_message(cliente, testo)),
        "message": "Link WhatsApp pronto.",
    }


def send_notifica(payload: dict[str, Any]) -> dict[str, Any]:
    if not (_can("messaggi.scrivi") or _can("admin.configura")):
        return {"ok": False, "message": "Permesso richiesto per inviare notifiche."}
    from pct.notifiche_wa import invia_messaggio

    data = payload or {}
    testo = _text(data.get("testo"))
    cliente, numero = _resolve_cliente(data)
    if not cliente or not numero or not testo:
        return {"ok": False, "message": "Seleziona un cliente con numero WhatsApp e scrivi il messaggio."}
    messaggio = _build_message(cliente, testo)
    esito = invia_messaggio(numero, messaggio, _config_wa())
    _scrivi_log(
        {
            "ts": datetime.now().isoformat(),
            "tipo": "messaggio_cliente",
            "cliente": _text(getattr(cliente, "nome_completo", "")),
            "numero": numero,
            "esito": esito,
            "utente": _text(getattr(g.get("utente_corrente"), "username", "")),
        }
    )
    ok = esito.get("ok")
    if ok is True:
        message = "Messaggio inviato."
    elif ok is None:
        message = "Link WhatsApp pronto per l'invio manuale."
    else:
        message = "Invio non completato. Controlla il canale WhatsApp."
    return {"ok": ok is not False, "message": message, "link": esito.get("wa_link", ""), "payload": build_notifiche_payload()}


def send_promemoria_domani() -> dict[str, Any]:
    if not (_can("messaggi.scrivi") or _can("admin.configura")):
        return {"ok": False, "message": "Permesso richiesto per inviare promemoria."}
    from pct.notifiche_wa import promemoria_appuntamenti_di_domani

    risultati = promemoria_appuntamenti_di_domani(
        agenda=_agenda(),
        get_cliente_fn=_clienti().get,
        config=_config_wa(),
        studio_nome=_studio_nome(),
    )
    for item in risultati:
        _scrivi_log(
            {
                "ts": datetime.now().isoformat(),
                "tipo": "promemoria_appuntamento",
                "cliente": _text(item.get("cliente")),
                "numero": _text(item.get("numero")),
                "esito": item.get("esito") if isinstance(item.get("esito"), dict) else {},
                "utente": _text(getattr(g.get("utente_corrente"), "username", "system"), "system"),
            }
        )
    automatici = sum(1 for item in risultati if (item.get("esito") or {}).get("ok") is True)
    if not risultati:
        message = "Nessun appuntamento di domani ha un numero WhatsApp utilizzabile."
    elif automatici == len(risultati):
        message = f"Promemoria inviati: {automatici}."
    else:
        message = f"Promemoria preparati: {len(risultati)}. Controlla il registro per completare gli invii manuali."
    return {"ok": True, "message": message, "results": risultati, "payload": build_notifiche_payload()}
