"""Pianificazione strutturata della bozza atto."""

from __future__ import annotations

from typing import Any

from .models import AttoDraftPlan, AttoDraftSection
from .validators import clean_text, validate_plan


DEFAULT_SECTION_BLUEPRINT = (
    ("intestazione", "Intestazione e parti", "Dati del fascicolo, ufficio, parti e difensore."),
    ("premesse", "Premesse in fatto", "Ricostruzione dei fatti solo da fascicolo e fonti indicate."),
    ("diritto", "Motivi in diritto", "Argomentazione giuridica prudente e verificabile."),
    ("conclusioni", "Conclusioni", "Domande, richieste o istanze da sottoporre al giudice o alla controparte."),
    ("allegati", "Documenti prodotti e allegati", "Elenco dei documenti richiamati e dati da completare."),
    ("firma", "Luogo, data e firma", "Chiusura dell'atto secondo prassi dello studio."),
)


def _source_refs(documents: list[dict[str, Any]], document_ids: list[str]) -> list[str]:
    selected = {clean_text(item) for item in document_ids if clean_text(item)}
    refs: list[str] = []
    for doc in documents:
        doc_id = clean_text(doc.get("document_id") or doc.get("id"))
        if selected and doc_id not in selected:
            continue
        if clean_text(doc.get("status")) and clean_text(doc.get("status")) != "ready":
            continue
        refs.append(doc_id)
    return [ref for ref in refs if ref]


def build_draft_plan(
    *,
    tipo_atto: str,
    template: dict[str, Any],
    context: dict[str, Any],
    document_ids: list[str] | None = None,
) -> AttoDraftPlan:
    title = clean_text(template.get("titolo") or template.get("name") or tipo_atto) or "Bozza atto"
    template_id = clean_text(template.get("id") or template.get("codice"))
    facts = context.get("facts") if isinstance(context, dict) else {}
    facts = facts if isinstance(facts, dict) else {}
    documents = list(context.get("documents") or []) if isinstance(context, dict) else []
    sources = _source_refs(documents, list(document_ids or []))

    required_fields = [
        "cliente",
        "oggetto",
        "tipo_atto",
        "ufficio",
        "numero_rg",
    ]
    missing_fields = [
        label
        for key, label in (
            ("cliente", "Cliente"),
            ("oggetto", "Oggetto del fascicolo"),
            ("ufficio", "Ufficio giudiziario"),
            ("numero_rg", "Numero RG"),
        )
        if not clean_text(facts.get(key))
    ]
    missing_fields.extend(clean_text(item) for item in context.get("missing_fields", []) if clean_text(item))

    sections: list[AttoDraftSection] = []
    for index, (section_id, heading, purpose) in enumerate(DEFAULT_SECTION_BLUEPRINT, start=1):
        refs = sources if section_id in {"premesse", "diritto", "allegati"} else []
        sections.append(
            AttoDraftSection(
                id=f"sec-{index}-{section_id}",
                heading=heading,
                level=1,
                purpose=purpose,
                source_refs=list(refs),
                required=section_id != "allegati" or bool(sources),
            )
        )

    warnings = list(context.get("warnings") or []) if isinstance(context, dict) else []
    if not sources:
        warnings.append("Nessun documento indicizzato selezionato: la bozza usa solo dati strutturati del fascicolo.")
    if missing_fields:
        warnings.append("Sono presenti dati da completare prima del deposito o invio.")

    plan = AttoDraftPlan(
        title=title,
        tipo_atto=clean_text(tipo_atto) or title,
        template_id=template_id,
        sections=sections,
        required_fields=required_fields,
        missing_fields=sorted(set(missing_fields), key=str.casefold),
        sources_to_use=sources,
        warnings=sorted(set(clean_text(item) for item in warnings if clean_text(item)), key=str.casefold),
    )
    validate_plan(plan)
    return plan
