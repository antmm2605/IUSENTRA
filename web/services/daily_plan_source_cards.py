"""Fonti puntuali per le attività del piano del giorno: PEC, scadenze, agenda.

Ogni funzione riusa la risoluzione fonte GIÀ governata dalle superfici
Agenda, Scadenziario e PEC (``pec_source_links`` e i bridge React), così
«Apri» dal piano del giorno apre esattamente lo stesso documento utile che
l'avvocato vedrebbe da quelle pagine, nel lettore interno unico.

Base normativa del presidio: art. 16 D.L. 179/2012 e D.M. 44/2011
(comunicazioni di cancelleria via PEC), art. 127-ter c.p.c. per le
decorrenze dalla comunicazione; nessun contenuto viene inventato: se la fonte non esiste la
risposta lo dichiara.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from urllib.parse import quote

from pct.formatting import format_date_it, format_datetime_it

VIEWABLE_KINDS = {"documento", "pec"}


def fonte(
    *,
    tipo: str,
    etichetta: str,
    href: str = "",
    apri_href: str = "",
    verificata: bool = False,
    rilevata_il: str = "",
    dettagli: list[dict[str, str]] | None = None,
    nota: str = "",
) -> dict[str, Any]:
    return {
        "tipo": tipo,
        "etichetta": " ".join(str(etichetta or "").split())[:160],
        "href": href,
        "apri_href": apri_href,
        "verificata": bool(verificata),
        "rilevata_il": rilevata_il,
        "dettagli": [d for d in (dettagli or []) if str(d.get("valore") or "").strip()],
        "nota": nota,
    }


def _dettaglio(etichetta: str, valore: Any) -> dict[str, str]:
    return {"etichetta": etichetta, "valore": " ".join(str(valore or "").split())[:600]}


def _date_label(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    if len(raw) > 10:
        return format_datetime_it(raw) or format_date_it(raw[:10]) or ""
    return format_date_it(raw) or ""


def _pec_audit_db(paths: Any) -> str:
    from pathlib import Path

    from web.services.daily_plan_runtime import _path_from_mapping

    email_db = Path(_path_from_mapping(paths, "EMAIL_CASELLA_DB", "./email/casella.json"))
    return str(paths.get("PEC_AUDIT_DB") or email_db.parent / "pec_audit.sqlite")


def _tenant_candidates(tenant_label: str) -> list[str]:
    return list(dict.fromkeys([str(tenant_label or "default"), "default"]))


def pec_profiles_for(items: list[Any], *, paths: Any, tenant_label: str) -> dict[str, dict[str, Any]]:
    from web.services.pec_source_links import latest_pec_profiles

    db = _pec_audit_db(paths)
    for tenant in _tenant_candidates(tenant_label):
        profiles = latest_pec_profiles(items, pec_audit_db=db, tenant_id=tenant)
        if profiles:
            return profiles
    return {}


def pec_message_source(
    message_id: str, *, paths: Any, tenant_label: str, rilevata_il: str = ""
) -> dict[str, Any] | None:
    """PEC dell'audit: apre l'allegato utile già indicizzato, altrimenti la PEC."""
    from web.services.pec_source_links import (
        normalize_pec_audit_message_id,
        pec_original_label,
        pec_profile_source_name,
        pec_source_href,
    )

    mid = normalize_pec_audit_message_id(str(message_id or "").split(":link")[0])
    if not mid:
        return None
    marker = SimpleNamespace(note=f"PEC_AUDIT:{mid}")
    profile = pec_profiles_for([marker], paths=paths, tenant_label=tenant_label).get(mid)
    source_name = pec_profile_source_name(profile)
    return fonte(
        tipo="pec",
        etichetta=pec_original_label(source_name),
        href=pec_source_href(mid, source_name),
        apri_href=f"/email/?audit_id={quote(mid, safe='')}",
        verificata=True,
        rilevata_il=rilevata_il,
    )


def scadenza_sources(scadenza_id: str, *, paths: Any, tenant_label: str) -> list[dict[str, Any]]:
    from web.services.daily_plan_runtime import _scadenziario_store
    from web.services.pec_source_links import control_tower_source_key, latest_control_tower_sources
    from web.services.react_scadenziario_bridge import (
        _legal_scadenza_detail_description,
        _pec_audit_message_id,
        _source_evidence,
    )

    scadenza = _scadenziario_store(paths).get(scadenza_id) if scadenza_id else None
    if scadenza is None:
        return []
    fascicolo_id = str(getattr(scadenza, "id_fascicolo", "") or "")
    profiles = pec_profiles_for([scadenza], paths=paths, tenant_label=tenant_label)
    tower: dict[str, dict[str, Any]] = {}
    for tenant in _tenant_candidates(tenant_label):
        tower = latest_control_tower_sources(
            [scadenza], pec_audit_db=_pec_audit_db(paths), tenant_id=tenant
        )
        if tower:
            break
    origin = _source_evidence(
        scadenza,
        fascicolo_id=fascicolo_id,
        control_tower_source=tower.get(control_tower_source_key(scadenza)),
        pec_profile=profiles.get(_pec_audit_message_id(scadenza)),
    )
    out: list[dict[str, Any]] = []
    kind = str(origin.get("sourceKind") or "")
    if origin.get("sourceHref") and kind in VIEWABLE_KINDS:
        out.append(
            fonte(
                tipo=kind,
                etichetta=str(origin.get("sourceLabel") or ""),
                href=str(origin.get("sourceHref") or ""),
                verificata=bool(origin.get("sourceVerified")),
            )
        )
    perentorio = bool(getattr(scadenza, "perentorio", False))
    out.append(
        fonte(
            tipo="scadenza",
            etichetta=str(getattr(scadenza, "titolo", "") or "Scadenza"),
            apri_href=f"/scadenziario?scadenza={quote(scadenza_id, safe='')}",
            verificata=True,
            dettagli=[
                _dettaglio("Termine", _date_label(getattr(scadenza, "data_scadenza", ""))),
                _dettaglio("Natura del termine", "Perentorio" if perentorio else "Non perentorio"),
                _dettaglio("Descrizione", _legal_scadenza_detail_description(scadenza)),
            ],
            nota=(
                ""
                if out
                else "La scadenza non ha un documento o una PEC di origine collegati: verifica nello scadenziario."
            ),
        )
    )
    return out


def agenda_sources(appuntamento_id: str, *, paths: Any, tenant_label: str) -> list[dict[str, Any]]:
    from web.services.daily_plan_runtime import _agenda_store
    from web.services.pec_source_links import pec_profile_source_name
    from web.services.react_agenda_bridge import _source_evidence

    evento = _agenda_store(paths).get(appuntamento_id) if appuntamento_id else None
    if evento is None:
        return []
    notes = "\n".join(
        part
        for part in (
            str(getattr(evento, "descrizione", "") or "").strip(),
            str(getattr(evento, "note", "") or "").strip(),
        )
        if part
    )
    profiles = pec_profiles_for([evento], paths=paths, tenant_label=tenant_label)
    profile = next(iter(profiles.values()), None)
    origin = _source_evidence(
        notes,
        matter_id=str(getattr(evento, "id_fascicolo", "") or ""),
        external_source_url=str(getattr(evento, "external_source_url", "") or ""),
        external_uid=str(getattr(evento, "external_uid", "") or ""),
        source_name=str(getattr(evento, "remote_hearing_source", "") or ""),
        indexed_source_name=pec_profile_source_name(profile),
    )
    out: list[dict[str, Any]] = []
    kind = str(origin.get("sourceKind") or "")
    if origin.get("sourceHref") and kind in VIEWABLE_KINDS:
        out.append(
            fonte(
                tipo=kind,
                etichetta=str(origin.get("sourceLabel") or ""),
                href=str(origin.get("sourceHref") or ""),
                verificata=bool(origin.get("sourceVerified")),
            )
        )
    out.append(
        fonte(
            tipo="agenda",
            etichetta=str(getattr(evento, "titolo", "") or "Impegno in agenda"),
            apri_href=f"/agenda?appuntamento={quote(appuntamento_id, safe='')}",
            verificata=True,
            dettagli=[
                _dettaglio("Data e ora", _date_label(getattr(evento, "data_ora", ""))),
                _dettaglio("Luogo", getattr(evento, "luogo", "")),
                _dettaglio("Procedimento", getattr(evento, "procedimento", "")),
                _dettaglio("Avvocato", getattr(evento, "avvocato", "")),
            ],
        )
    )
    return out


__all__ = [
    "VIEWABLE_KINDS",
    "agenda_sources",
    "fonte",
    "pec_message_source",
    "pec_profiles_for",
    "scadenza_sources",
]
