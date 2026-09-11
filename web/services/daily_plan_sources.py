"""Risoluzione on-demand delle fonti di un'attività del piano del giorno.

Quando l'avvocato clicca «Apri» su un'attività, IUSENTRA deve mostrare la
FONTE che la prova (il decreto nel fascicolo, la PEC con l'allegato utile,
la scadenza o l'impegno), sopra la pagina Oggi, nel lettore interno unico:
non l'intero fascicolo.

Regole:
- tenant e percorsi dati sono risolti lato server (mai dal client);
- nessun OCR e nessuna estrazione: si leggono solo dati già materializzati;
- si riusano le risoluzioni fonte già governate da Agenda, Scadenziario, PEC
  e presidio fascicolo (nessuna seconda logica concorrente);
- se una fonte documentale non esiste, la risposta lo dichiara con una nota,
  senza proporre un documento «probabile».
"""

from __future__ import annotations

from datetime import date
from typing import Any
from urllib.parse import quote

from pct.daily_plan.models import DailyWorkItem, SignalEvidence
from web.services.daily_plan_source_cards import (
    agenda_sources,
    fonte,
    pec_message_source,
    scadenza_sources,
)

_SECTION_LABELS = {
    "pec": "Comunicazioni / Cancelleria",
    "documenti": "Documenti",
    "relata": "Relata e prova notifica",
    "economico": "Economia",
    "doppioni": "Controllo doppioni",
}


def _text(value: Any) -> str:
    return " ".join(str(value or "").split())


def _is_viewer_href(href: str) -> bool:
    raw = _text(href)
    return (
        (raw.startswith("/fascicoli/") and "/documenti/" in raw and raw.split("?")[0].endswith("/visualizza"))
        or raw.startswith("/api/v1/ui/email/source/")
        or raw.startswith("/email/?audit_id=")
    )


def _document_href(fascicolo_id: str, document_id: str) -> str:
    return f"/fascicoli/{quote(fascicolo_id, safe='')}/documenti/{quote(document_id, safe='')}/visualizza"


_DOCUMENT_NAME_ATTRS = (
    "nome_portale",
    "nome",
    "nome_originale",
    "filename",
    "safe_filename",
    "original_filename",
)


def _document_name(doc: Any) -> str:
    """Stesso ordine di ``_document_display_name`` della scheda fascicolo."""
    for attr in _DOCUMENT_NAME_ATTRS:
        value = _text(getattr(doc, attr, ""))
        if value:
            return value
    return ""


def _document_by_name(fascicolo: Any, name: str) -> Any | None:
    """Solo corrispondenza esatta del nome file: mai documenti «simili»."""
    wanted = _text(name).casefold()
    if not wanted:
        return None
    for doc in list(getattr(fascicolo, "documenti", []) or []):
        names = {
            _text(getattr(doc, attr, "")).casefold()
            for attr in _DOCUMENT_NAME_ATTRS
        }
        if wanted in names:
            return doc
    return None


def _document_by_id(fascicolo: Any, document_id: str) -> Any | None:
    for doc in list(getattr(fascicolo, "documenti", []) or []):
        if _text(getattr(doc, "id", "")) == document_id:
            return doc
    return None


def _case_presidio_sources(
    ev: SignalEvidence, item: DailyWorkItem, *, paths: Any, today: date
) -> list[dict[str, Any]]:
    from web.services.daily_plan_runtime import _fascicoli_store, operational_presidio_actions

    fascicolo_id, _, action_id = _text(ev.source_id).partition(":")
    fascicolo_id = fascicolo_id or item.fascicolo_id
    fascicolo = _fascicoli_store(paths).get(fascicolo_id) if fascicolo_id else None
    label = _text(ev.label)

    if _is_viewer_href(ev.href) and "/documenti/" in ev.href:
        doc_id = _text(ev.href).split("/documenti/", 1)[1].split("/", 1)[0]
        doc = _document_by_id(fascicolo, doc_id) if fascicolo is not None else None
        return [
            fonte(
                tipo="documento",
                etichetta=(_document_name(doc) if doc is not None else "") or label or "Documento del fascicolo",
                href=ev.href,
                verificata=True,
            )
        ]
    if fascicolo is None:
        return []

    action: dict[str, Any] = {}
    try:
        action = next(
            (a for a in operational_presidio_actions(fascicolo, today=today) if a.get("id") == action_id),
            {},
        )
    except Exception:
        action = {}

    source_href = _text(action.get("sourceHref"))
    source_name = _text(action.get("source"))
    if source_href:
        doc = _document_by_id(fascicolo, _text(action.get("documentId")))
        return [
            fonte(
                tipo="documento",
                etichetta=(_document_name(doc) if doc is not None else "") or source_name or "Documento del fascicolo",
                href=source_href,
                verificata=True,
            )
        ]
    doc = _document_by_name(fascicolo, source_name)
    if doc is not None and _text(getattr(doc, "id", "")):
        return [
            fonte(
                tipo="documento",
                etichetta=_document_name(doc),
                href=_document_href(fascicolo_id, _text(getattr(doc, "id", ""))),
                verificata=True,
            )
        ]
    sector = _text(action.get("sector")) or action_id.split("-", 1)[0]
    section = _SECTION_LABELS.get(sector, "Fascicolo")
    return [
        fonte(
            tipo="fascicolo",
            etichetta=f"Sezione «{section}» del fascicolo",
            apri_href=_text(action.get("href")) or item.href,
            dettagli=[
                {"etichetta": "Controllo", "valore": source_name},
                {"etichetta": "Base di riferimento", "valore": _text(action.get("legalBasis"))},
            ],
            nota=(
                "L'attività nasce da un controllo della sezione, non da un singolo documento: "
                "apri la sezione del fascicolo per completarla."
            ),
        )
    ]


def _evidence_sources(
    ev: SignalEvidence, item: DailyWorkItem, *, paths: Any, tenant_label: str, today: date
) -> list[dict[str, Any]]:
    if ev.source_type == "pec":
        found = pec_message_source(
            ev.source_id, paths=paths, tenant_label=tenant_label, rilevata_il=ev.timestamp
        )
        return [found] if found else []
    if ev.source_type == "scadenziario":
        return scadenza_sources(_text(ev.source_id), paths=paths, tenant_label=tenant_label)
    if ev.source_type == "agenda":
        ids = [part for part in _text(ev.source_id).split("+") if part]
        return [s for part in ids for s in agenda_sources(part, paths=paths, tenant_label=tenant_label)]
    if ev.source_type == "case_presidio":
        return _case_presidio_sources(ev, item, paths=paths, today=today)
    if item.href:
        return [
            fonte(
                tipo="economico" if ev.source_type == "economic" else "scheda",
                etichetta=_text(ev.label) or item.title,
                apri_href=item.href,
                verificata=True,
                nota=(
                    "Apri la scheda collegata per consultare il documento economico."
                    if ev.source_type == "economic"
                    else "Apri la scheda collegata per consultare l'origine dell'attività."
                ),
            )
        ]
    return []


def resolve_item_sources(
    item: DailyWorkItem, *, paths: Any, tenant_label: str, today: date
) -> dict[str, Any]:
    """Fonti consultabili per l'attività, documenti e PEC per primi."""
    fonti: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for ev in item.evidence:
        try:
            resolved = _evidence_sources(ev, item, paths=paths, tenant_label=tenant_label, today=today)
        except Exception:
            resolved = []
        for entry in resolved:
            key = (entry["tipo"], entry["href"] or entry["apri_href"], entry["etichetta"])
            if key in seen:
                continue
            seen.add(key)
            fonti.append(entry)
    fonti.sort(key=lambda entry: 0 if entry["href"] else 1)
    return {
        "ok": True,
        "attivita_id": item.id,
        "fonti": fonti,
        "fascicolo_href": f"/fascicoli/{quote(item.fascicolo_id, safe='')}" if item.fascicolo_id else "",
        "messaggio": (
            ""
            if fonti
            else "Per questa attività non risulta ancora una fonte consultabile: apri il dettaglio o il fascicolo."
        ),
    }


__all__ = ["resolve_item_sources"]
