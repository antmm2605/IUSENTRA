"""Schede della Ricerca legale per la shell React: news, fonte ufficiale, variazione.

Sostituiscono le viste storiche `/ricerca-legale/news/<slug>`,
`/ricerca-legale/fonte/<id>` e `/ricerca-legale/daily/update/<id>/diff`.
I dati sono gli stessi: la news pubblicata dal motore degli aggiornamenti
legali, la scheda della fonte del motore giornaliero (storico degli snapshot con
impronta SHA-256, variazioni rilevate) e il diff dell'aggiornamento.
"""

from __future__ import annotations

from typing import Any, Callable, Iterable
from urllib.parse import urlparse


def _t(value: Any, limite: int = 0) -> str:
    testo = "" if value is None else str(value).strip()
    return testo[:limite] if limite else testo


def _url_esterno(value: Any) -> str:
    testo = _t(value)
    return testo if testo.startswith(("https://", "http://")) else ""


def scheda_news(news: dict[str, Any] | None) -> tuple[dict[str, Any], int]:
    if not news:
        return {"ok": False, "message": "News non trovata o non ancora pubblicata."}, 404
    return {
        "ok": True,
        "item": {
            "slug": _t(news.get("slug")),
            "title": _t(news.get("title")),
            "type": _t(news.get("news_type")).replace("_", " "),
            "matter": _t(news.get("matter_name")),
            "submatter": _t(news.get("submatter_name")),
            "summary": _t(news.get("short_summary")),
            "content": _t(news.get("content")),
            "publishedAt": _t(news.get("published_at") or news.get("created_at")),
            "origin": "Generata dal motore AI" if news.get("is_auto_generated") else "Inserimento manuale",
            "sourceName": _t(news.get("source_name")),
            "sourceOfficial": bool(news.get("source_is_official")),
            "sourceHref": _url_esterno(news.get("source_url")),
        },
    }, 200


def _variazione(update: dict[str, Any]) -> dict[str, Any]:
    ident = _t(update.get("id"))
    return {
        "id": ident,
        "title": _t(update.get("title")),
        "summary": _t(update.get("summary")),
        "detectedAt": _t(update.get("detected_at")),
        "status": _t(update.get("status")),
        "statusLabel": _t(update.get("status")).replace("_", " "),
        "severity": _t(update.get("severity")),
        "applyMode": _t(update.get("apply_mode")),
        "detailHref": f"/ricerca-legale/daily/update/{ident}/diff" if ident else "",
        "approveAction": f"/api/v1/ui/ricerca-legale/aggiornamenti/{ident}/approva" if update.get("status") == "pending_review" else "",
    }


_SUFFISSI_DI_SECONDO_LIVELLO = {"gov.it", "edu.it"}


def _host(url: Any) -> str:
    """Il dominio registrato del sito ufficiale (api.normattiva.it e www.normattiva.it sono lo stesso sito)."""
    parti = [p for p in (urlparse(_t(url)).hostname or "").lower().split(".") if p]
    if len(parti) < 2:
        return ".".join(parti)
    quante = 3 if ".".join(parti[-2:]) in _SUFFISSI_DI_SECONDO_LIVELLO and len(parti) >= 3 else 2
    return ".".join(parti[-quante:])


def _fonte_da_motore(source_id: str, fonti_giornaliere: Iterable[Any]) -> dict[str, Any] | None:
    fonte = next((f for f in fonti_giornaliere if _t(getattr(f, "id", "")) == source_id), None)
    if fonte is None:
        return None
    return {
        "id": source_id,
        "nome": _t(getattr(fonte, "name", "")),
        "area": _t(getattr(fonte, "category", "")),
        "connector_kind": "controllo giornaliero",
        "cadence": "giornaliera",
        "official_url": _t(getattr(fonte, "url", "")),
        "monitor_url": _t(getattr(fonte, "url", "")),
    }


def scheda_fonte(
    source_id: str,
    righe_fonti: Iterable[dict[str, Any]],
    carica_scheda: Callable[[str], dict[str, Any] | None],
    fonti_giornaliere: Iterable[Any] = (),
) -> tuple[dict[str, Any], int]:
    """La scheda di una fonte del registro o di una fonte del controllo giornaliero.

    I due elenchi hanno identificativi diversi («normattiva» e
    «normattiva_opendata»): lo storico e le variazioni si prendono dalle fonti
    giornaliere che controllano lo stesso sito ufficiale.
    """
    fonti_giornaliere = list(fonti_giornaliere)
    fonte = next((riga for riga in righe_fonti if _t(riga.get("id")) == source_id), None) or _fonte_da_motore(source_id, fonti_giornaliere)
    if not fonte:
        return {"ok": False, "message": "Fonte non trovata nel registro della Ricerca legale."}, 404
    host_fonte = {_host(fonte.get("official_url")), _host(fonte.get("monitor_url"))} - {""}
    collegate = [f for f in fonti_giornaliere if _t(getattr(f, "id", "")) == source_id or _host(getattr(f, "url", "")) in host_fonte]
    schede: list[dict[str, Any]] = []
    for ident in dict.fromkeys([source_id, *(_t(getattr(f, "id", "")) for f in collegate)]):
        try:
            scheda = carica_scheda(ident)
        except Exception:
            scheda = None
        if scheda:
            schede.append(scheda)
    ultimo = next((s.get("latest_snapshot") for s in schede if s.get("latest_snapshot")), {}) or {}
    descrittore = next((s.get("descriptor") for s in schede if s.get("descriptor")), {}) or {}
    storico = sorted((snap for s in schede for snap in (s.get("history") or [])), key=lambda snap: _t(snap.get("fetched_at")), reverse=True)[:10]
    variazioni = sorted((u for s in schede for u in (s.get("updates") or [])), key=lambda u: _t(u.get("detected_at")), reverse=True)[:10]
    errore = next((_t((s.get("source") or {}).get("last_error")) for s in schede if (s.get("source") or {}).get("last_error")), "")
    return {
        "ok": True,
        "item": {
            "id": source_id,
            "name": _t(fonte.get("nome")),
            "area": _t(fonte.get("area")),
            "channel": _t(fonte.get("connector_kind")),
            "cadence": _t(fonte.get("cadence")),
            "warning": _t(fonte.get("warning")),
            "freshness": _t(fonte.get("freshness")),
            "officialHref": _url_esterno(fonte.get("official_url")),
            "monitorHref": _url_esterno(fonte.get("monitor_url")),
            "formats": [_t(f) for f in (fonte.get("formats") or []) if _t(f)],
            "fetcherNote": _t(descrittore.get("user_agent_note")),
            "impactAreas": [_t(a) for a in (descrittore.get("impact_areas") or []) if _t(a)],
            "dailySources": [
                {"id": _t(getattr(f, "id", "")), "name": _t(getattr(f, "name", "")), "href": f"/ricerca-legale/fonte/{_t(getattr(f, 'id', ''))}"}
                for f in collegate if _t(getattr(f, "id", "")) != source_id
            ],
            "monitor": {
                "lastCheck": _t(fonte.get("last_check")),
                "status": _t(fonte.get("status")).replace("_", " "),
                "httpStatus": _t(fonte.get("status_code")),
                "changed": bool(fonte.get("changed")),
                "version": _t(fonte.get("detected_version")),
                "reference": _t(fonte.get("detected_reference")),
                "package": _t(fonte.get("detected_package")),
                "packageStatus": _t(fonte.get("detected_status")),
            },
            "latest": {
                "fetchedAt": _t(ultimo.get("fetched_at")),
                "href": _url_esterno(ultimo.get("url")),
                "sha256": _t(ultimo.get("content_sha256")),
                "etag": _t(ultimo.get("etag")),
                "lastModified": _t(ultimo.get("last_modified")),
            } if ultimo else None,
            "downloadHref": f"/ricerca-legale/fonte/{_t(ultimo.get('source_id')) or source_id}/scarica" if ultimo else "",
            "history": [
                {
                    "fetchedAt": _t(snap.get("fetched_at")),
                    "httpStatus": _t(snap.get("status_code")),
                    "sha256": _t(snap.get("content_sha256")),
                    "bytes": int(snap.get("text_bytes") or 0),
                    "etag": _t(snap.get("etag"), 24),
                    "lastModified": _t(snap.get("last_modified")),
                }
                for snap in storico
            ],
            "updates": [_variazione(u) for u in variazioni],
            "lastError": errore,
        },
    }, 200


def controllo_giornaliero(cruscotto: dict[str, Any], *, puo_eseguire: bool, in_corso: bool) -> dict[str, Any]:
    """Il cruscotto del controllo giornaliero delle fonti ufficiali (motore con impronta e diff)."""
    ultimo = cruscotto.get("last_run") or {}
    conteggi = cruscotto.get("counts") or {}
    return {
        "ok": True,
        "running": in_corso,
        "canRun": puo_eseguire,
        "runAction": "/api/v1/ui/ricerca-legale/controllo-giornaliero/esegui" if puo_eseguire else "",
        # Operazioni della pagina storica /ricerca-legale, ora avviate da qui.
        "operations": [
            {"key": "monitoraggio", "label": "Monitora le fonti", "detail": "Controlla disponibilità e aggiornamento delle fonti ufficiali registrate.", "action": "/api/v1/ui/ricerca-legale/monitoraggio/esegui"},
            {"key": "tabelle-normative", "label": "Allinea le tabelle normative", "detail": "Aggiorna tariffe, scaglioni e tabelle dalle fonti ufficiali; le voci incerte restano da verificare.", "action": "/api/v1/ui/ricerca-legale/tabelle-normative/sincronizza"},
            {"key": "registro-mediazione", "label": "Aggiorna il registro della mediazione", "detail": "Legge il registro ministeriale degli organismi di mediazione (D.Lgs. 28/2010).", "action": "/api/v1/ui/ricerca-legale/mediazione/sincronizza"},
        ] if puo_eseguire else [],
        "importAction": "/api/v1/ui/ricerca-legale/mediazione/importa" if puo_eseguire else "",
        "lastRun": {"startedAt": _t(ultimo.get("started_at")), "finishedAt": _t(ultimo.get("finished_at")), "status": _t(ultimo.get("status"))} if ultimo else None,
        "counts": {k: int(conteggi.get(k) or 0) for k in ("sources", "updates", "pending", "applied", "errors")},
        "sources": [
            {
                "id": _t(riga.get("id")),
                "name": _t(riga.get("name")),
                "category": _t(riga.get("category")),
                "lastCheck": _t(riga.get("last_checked_at")),
                "status": _t(riga.get("last_status")),
                "error": _t(riga.get("last_error"), 240),
                "href": f"/ricerca-legale/fonte/{_t(riga.get('id'))}",
            }
            for riga in (cruscotto.get("sources") or [])
        ],
        "updates": [
            {**_variazione(u), "approveAction": _variazione(u)["approveAction"] if puo_eseguire else ""}
            for u in (cruscotto.get("updates") or [])
        ],
    }


def scheda_variazione(update: dict[str, Any] | None) -> tuple[dict[str, Any], int]:
    if not update:
        return {"ok": False, "message": "Aggiornamento non trovato."}, 404
    voce = _variazione(update)
    voce.update(
        {
            "oldSha256": _t(update.get("old_sha256")),
            "newSha256": _t(update.get("new_sha256")),
            "diff": _t(update.get("diff_text")),
        }
    )
    return {"ok": True, "item": voce}, 200


__all__ = ["controllo_giornaliero", "scheda_fonte", "scheda_news", "scheda_variazione"]
