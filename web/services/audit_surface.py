"""Helper UI per rendere il registro audit piu' leggibile e spiegabile."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from flask import current_app, url_for

from pct.fascicoli import GestioneFascicoli
from web.services.storage_runtime import get_request_studio_db


_DOCUMENT_NAME_RE = re.compile(
    r"(?:file:\s*|doc\s+[A-Z0-9]+\s+[-\u2014]\s*)([^\\/:*?\"<>|\r\n]+\.[A-Za-z0-9]{2,5}(?:\.p7m)?)$",
    re.IGNORECASE,
)


def _label_fascicolo(fascicolo) -> str:
    numero = str(getattr(fascicolo, "numero", "") or "").strip()
    titolo = str(getattr(fascicolo, "titolo", "") or "").strip()
    rg = str(getattr(fascicolo, "numero_rg", "") or "").strip()
    anno_rg = str(getattr(fascicolo, "anno_rg", "") or "").strip()

    parti: list[str] = []
    if numero:
        parti.append(numero)
    if titolo:
        parti.append(titolo)
    elif rg and anno_rg:
        parti.append(f"RG {rg}/{anno_rg}")
    elif rg:
        parti.append(f"RG {rg}")

    return " - ".join(parti) if parti else str(getattr(fascicolo, "id", "") or "").strip()


def _extract_document_name(dettagli: str) -> str:
    testo = str(dettagli or "").strip()
    if not testo:
        return ""
    match = _DOCUMENT_NAME_RE.search(testo)
    if match:
        return match.group(1).strip()
    return Path(testo).name if "." in testo else ""


def _build_document_index(fascicoli: list) -> dict[str, list]:
    indice: dict[str, list] = {}
    for fascicolo in fascicoli:
        visti: set[str] = set()
        for documento in getattr(fascicolo, "documenti", []) or []:
            for nome in (
                str(getattr(documento, "nome", "") or "").strip(),
                Path(str(getattr(documento, "percorso", "") or "")).name.strip(),
            ):
                chiave = nome.lower()
                if not chiave or chiave in visti:
                    continue
                indice.setdefault(chiave, []).append(fascicolo)
                visti.add(chiave)
    return indice


def _load_fascicoli_manager() -> GestioneFascicoli:
    anchor_path = str(current_app.config.get("FASCICOLI_DB", ""))
    return GestioneFascicoli(
        db_path=anchor_path,
        documents_dir=str(current_app.config.get("FASCICOLI_DOCS", "")),
        archive_dir=str(current_app.config.get("FASCICOLI_ARCH", "")),
        studio_db=get_request_studio_db(anchor_path),
    )


def build_audit_view(eventi: list) -> dict[str, Any]:
    """Arricchisce gli eventi audit con il contesto fascicolo corrente quando possibile."""
    try:
        fascicoli_manager = _load_fascicoli_manager()
        fascicoli = list(fascicoli_manager.tutti())
    except Exception:
        return {"eventi": [evento.to_dict() for evento in eventi], "summary": {}}

    per_id = {
        str(getattr(fascicolo, "id", "") or "").strip(): fascicolo
        for fascicolo in fascicoli
    }
    per_documento = _build_document_index(fascicoli)

    alias_storici: dict[str, Any] = {}
    for evento in eventi:
        if str(getattr(evento, "risorsa_tipo", "") or "").strip().lower() != "fascicolo":
            continue
        storico_id = str(getattr(evento, "risorsa_id", "") or "").strip()
        if not storico_id or storico_id in per_id or storico_id in alias_storici:
            continue
        nome_documento = _extract_document_name(getattr(evento, "dettagli", ""))
        if not nome_documento:
            continue
        candidati = {
            str(getattr(fascicolo, "id", "") or "").strip(): fascicolo
            for fascicolo in per_documento.get(nome_documento.lower(), [])
        }
        if len(candidati) == 1:
            alias_storici[storico_id] = next(iter(candidati.values()))

    arricchiti: list[dict[str, Any]] = []
    summary = {"attivi": 0, "riconciliati": 0, "storici": 0}

    for evento in eventi:
        row = evento.to_dict()
        row["resource_state"] = ""
        row["resource_label"] = ""
        row["resource_note"] = ""
        row["resource_url"] = ""
        row["resource_badge_class"] = "bg-secondary-subtle text-secondary-emphasis"
        row["resource_badge_label"] = "Storico"

        if str(getattr(evento, "risorsa_tipo", "") or "").strip().lower() == "fascicolo":
            storico_id = str(getattr(evento, "risorsa_id", "") or "").strip()
            fascicolo = per_id.get(storico_id)
            if fascicolo is not None:
                stato = str(
                    getattr(getattr(fascicolo, "stato", ""), "value", getattr(fascicolo, "stato", "")) or ""
                ).upper()
                row["resource_state"] = "attivo"
                row["resource_label"] = _label_fascicolo(fascicolo)
                row["resource_note"] = "Fascicolo attualmente presente nel database dello studio."
                row["resource_url"] = url_for("dettaglio_fascicolo", id_fasc=fascicolo.id)
                if stato == "ARCHIVIATO":
                    row["resource_badge_label"] = "Archiviato"
                    row["resource_badge_class"] = "bg-warning-subtle text-warning-emphasis"
                else:
                    row["resource_badge_label"] = "Attivo"
                    row["resource_badge_class"] = "bg-success-subtle text-success-emphasis"
                summary["attivi"] += 1
            else:
                riconciliato = alias_storici.get(storico_id)
                if riconciliato is not None:
                    row["resource_state"] = "riconciliato"
                    row["resource_label"] = _label_fascicolo(riconciliato)
                    row["resource_note"] = (
                        f"Evento storico registrato con ID {storico_id}; oggi il contenuto risulta nel fascicolo {riconciliato.id}."
                    )
                    row["resource_url"] = url_for("dettaglio_fascicolo", id_fasc=riconciliato.id)
                    row["resource_badge_label"] = "Riconciliato"
                    row["resource_badge_class"] = "bg-info-subtle text-info-emphasis"
                    summary["riconciliati"] += 1
                else:
                    row["resource_state"] = "storico"
                    row["resource_note"] = (
                        "Fascicolo storico non piu' presente con questo ID nel database corrente: "
                        "puo' essere stato rimosso, migrato o ricreato con un nuovo ID."
                    )
                    summary["storici"] += 1

        arricchiti.append(row)

    return {"eventi": arricchiti, "summary": summary}
