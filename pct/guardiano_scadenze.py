"""Valutazione preventiva dei rischi nello scadenziario.

Il Guardiano non calcola termini di legge e non chiude attività: legge soltanto
le scadenze già persistite, espone i fattori di rischio e porta l'avvocato alla
correzione concreta (fonte, responsabile, fascicolo o data operativa).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Iterable

try:  # ZoneInfo è disponibile nella standard library Python 3.9+.
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover - compatibilità runtime datati
    ZoneInfo = None  # type: ignore[assignment,misc]


def _today_rome() -> date:
    if ZoneInfo is not None:
        return datetime.now(ZoneInfo("Europe/Rome")).date()
    return date.today()


def _text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _enum_value(value: Any) -> str:
    return _text(getattr(value, "value", value)).upper()


def _as_date(value: Any) -> date | None:
    raw = _text(value)
    if not raw:
        return None
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        return None


def _confidence(value: Any) -> float:
    try:
        return max(0.0, min(float(value or 0.0), 1.0))
    except (TypeError, ValueError):
        return 0.0


def _risk_band(score: int) -> tuple[str, str, str]:
    if score >= 80:
        return "critico", "Rischio critico", "danger"
    if score >= 55:
        return "alto", "Rischio alto", "warning"
    if score >= 30:
        return "medio", "Da presidiare", "info"
    return "basso", "Presidio ordinario", "neutral"


def _is_open(item: Any) -> bool:
    return _enum_value(getattr(item, "stato", "")) == "APERTO"


def _is_notification_presidio(item: Any) -> bool:
    return _text(getattr(item, "source_event_type", "")) == "legal_notification_presidio"


def _reason(code: str, label: str, weight: int, action: str) -> dict[str, Any]:
    return {"code": code, "label": label, "weight": weight, "action": action}


def _risk_for_deadline(item: Any, today: date) -> dict[str, Any] | None:
    if not _is_open(item) or _is_notification_presidio(item):
        return None

    reasons: list[dict[str, Any]] = []
    due_date = _as_date(getattr(item, "data_scadenza", "")) or _as_date(getattr(item, "legal_due_at", ""))
    operational_due = _as_date(getattr(item, "operational_due_at", ""))
    days = (due_date - today).days if due_date else None
    peremptory = bool(getattr(item, "perentorio", False))
    owner = _text(getattr(item, "id_utente_responsabile", ""))
    fascicolo_id = _text(getattr(item, "id_fascicolo", ""))
    source_type = _text(getattr(item, "source_event_type", ""))
    source_document = _text(getattr(item, "source_document_name", ""))
    source_message = _text(getattr(item, "source_message_id", ""))
    source_snippet = _text(getattr(item, "source_snippet", ""))
    confidence = _confidence(getattr(item, "source_confidence", 0.0))

    if days is None:
        reasons.append(_reason("data_mancante", "Data della scadenza da verificare", 35, "Apri e completa la scadenza."))
    elif days < 0:
        reasons.append(_reason("termine_superato", "Termine aperto oltre la data prevista", 100, "Apri subito la scadenza e registra la decisione professionale."))
    elif days == 0:
        reasons.append(_reason("scadenza_oggi", "Scadenza prevista oggi", 50, "Completa o rivaluta l’attività prima della chiusura della giornata."))
    elif days <= 2:
        reasons.append(_reason("scadenza_imminente", "Scadenza entro due giorni", 38, "Predisponi oggi documenti, firma e controlli necessari."))
    elif days <= 7:
        reasons.append(_reason("scadenza_vicina", "Scadenza entro sette giorni", 22, "Pianifica la preparazione e verifica il fascicolo."))

    if peremptory and (days is None or days <= 7):
        reasons.append(_reason("perentorio", "Termine perentorio nell’orizzonte operativo", 30, "Verifica subito decorrenza, fonte e attività necessaria."))
    if not owner:
        reasons.append(_reason("responsabile_mancante", "Nessun responsabile assegnato", 24, "Assegna un responsabile prima della prossima azione."))
    if operational_due and operational_due < today and (due_date is None or due_date >= today):
        reasons.append(_reason("anticipo_superato", "Finestra interna di preparazione già superata", 28, "Apri la scadenza e riallinea la preparazione dello studio."))
    if not fascicolo_id:
        reasons.append(_reason("fascicolo_mancante", "Scadenza non collegata a un fascicolo", 16, "Collega il fascicolo per conservare documenti e prova dell’attività."))

    derived_from_source = bool(source_type or source_document or source_message or source_snippet)
    if derived_from_source and confidence and confidence < 0.75:
        reasons.append(_reason("fonte_da_confermare", "Affidabilità della fonte da confermare", 22, "Apri la fonte e conferma la data prima di agire."))
    if source_type and not (source_document or source_message or source_snippet):
        reasons.append(_reason("prova_fonte_incompleta", "Manca il collegamento alla fonte dell’evento", 20, "Collega o verifica il documento o la comunicazione di origine."))
    if bool(getattr(item, "remote_hearing_detected", False)) and not bool(getattr(item, "remote_hearing_verified", False)):
        reasons.append(_reason("udienza_remota_da_verificare", "Link o modalità dell’udienza da verificare", 18, "Apri il documento fonte e verifica il collegamento di udienza."))

    if not reasons:
        return None
    score = min(100, sum(int(reason["weight"]) for reason in reasons))
    band, label, tone = _risk_band(score)
    primary = max(reasons, key=lambda reason: int(reason["weight"]))
    item_id = _text(getattr(item, "id", ""))
    action_href = f"/scadenziario/{item_id}/modifica" if item_id else "/scadenziario"
    if primary["code"] in {"fonte_da_confermare", "prova_fonte_incompleta", "udienza_remota_da_verificare"}:
        action_href = f"/scadenziario/{item_id}" if item_id else "/scadenziario"
    return {
        "id": item_id,
        "title": _text(getattr(item, "titolo", "")) or "Scadenza senza titolo",
        "date": due_date.isoformat() if due_date else "",
        "days": days,
        "peremptory": peremptory,
        "fascicoloId": fascicolo_id,
        "ownerAssigned": bool(owner),
        "score": score,
        "band": band,
        "label": label,
        "tone": tone,
        "primaryReason": primary["label"],
        "nextAction": primary["action"],
        "reasons": reasons,
        "href": action_href,
    }


def build_guardiano_scadenze_payload(items: Iterable[Any], *, today: date | None = None) -> dict[str, Any]:
    """Restituisce la coda rischio derivata da scadenze già persistite."""

    reference_day = today or _today_rome()
    risks = [risk for item in items if (risk := _risk_for_deadline(item, reference_day)) is not None]
    rank = {"critico": 0, "alto": 1, "medio": 2, "basso": 3}
    risks.sort(key=lambda item: (rank[item["band"]], item["days"] is None, item["days"] if item["days"] is not None else 10_000, item["title"]))
    return {
        "referenceDate": reference_day.isoformat(),
        "summary": {
            "total": len(risks),
            "critical": sum(1 for item in risks if item["band"] == "critico"),
            "high": sum(1 for item in risks if item["band"] == "alto"),
            "medium": sum(1 for item in risks if item["band"] == "medio"),
            "unassigned": sum(1 for item in risks if not item["ownerAssigned"]),
            "sourceReview": sum(1 for item in risks if any(reason["code"] in {"fonte_da_confermare", "prova_fonte_incompleta"} for reason in item["reasons"])),
        },
        "items": risks[:12],
        "message": (
            "Nessun rischio aperto nel perimetro delle scadenze attive."
            if not risks
            else "Il Guardiano evidenzia solo dati già presenti nello scadenziario: ogni termine resta soggetto alla verifica professionale."
        ),
    }


__all__ = ["build_guardiano_scadenze_payload"]
