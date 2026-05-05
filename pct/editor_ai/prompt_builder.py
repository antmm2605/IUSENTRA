"""Prompt originali IUSENTRA per generazione atti nell'editor."""

from __future__ import annotations

import json
from typing import Any

from .models import AttoAIDraftRequest, AttoDraftPlan
from .validators import clean_text


EDITOR_AI_SYSTEM_PROMPT = """
Sei Lex AI dentro IUSENTRA, gestionale per studi legali italiani.
Devi redigere bozze di atti in italiano, prudenti e verificabili.
Rispondi sempre e solo in lingua italiana. Non usare inglese per titoli,
intestazioni, formule introduttive, riassunti o conclusioni. Puoi mantenere in
lingua originale solo citazioni letterali presenti nei documenti.
Non inventare RG, uffici, date, importi, parti, prove, norme o fonti.
Se un dato manca, inserisci un segnaposto professionale e segnala il dato da
completare. Usa solo documenti del fascicolo e dati strutturati forniti nel
prompt, salvo esplicita richiesta di fonte esterna.
Il risultato deve essere contenuto HTML compatibile con l'editor IUSENTRA:
h1/h2/h3, p, ol/li, ul/li, blockquote e table. Non inserire script, stili o link
esterni.
""".strip()


def _compact_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)


def build_generation_prompt(
    *,
    request: AttoAIDraftRequest,
    template: dict[str, Any],
    context: dict[str, Any],
    plan: AttoDraftPlan,
) -> str:
    selected_docs = [
        doc
        for doc in context.get("documents", [])
        if not request.document_ids or clean_text(doc.get("document_id") or doc.get("id")) in set(request.document_ids)
    ]
    payload = {
        "richiesta": request.to_dict(),
        "template": {
            "id": clean_text(template.get("id") or template.get("codice")),
            "titolo": clean_text(template.get("titolo") or template.get("name")),
            "area": clean_text(template.get("area") or template.get("materia")),
            "canale_telematico": clean_text(template.get("canale_telematico") or template.get("canale_deposito")),
            "controlli_conformita": list(template.get("controlli_conformita") or template.get("checklist_conformita") or [])[:12],
            "campi_guidati": list(template.get("campi_guidati") or template.get("campi_precompila") or [])[:24],
        },
        "piano": plan.to_dict(),
        "contesto_fascicolo": {
            "facts": context.get("facts") or {},
            "documents": selected_docs,
            "activities": context.get("activities") or [],
            "deadlines": context.get("deadlines") or [],
            "communications": context.get("communications") or [],
            "missing_fields": context.get("missing_fields") or [],
            "warnings": context.get("warnings") or [],
        },
    }
    return (
        "Genera il contenuto HTML della bozza atto seguendo il piano strutturato.\n"
        "Regole obbligatorie:\n"
        "- usa solo italiano;\n"
        "- non inventare dati mancanti;\n"
        "- se manca un dato, usa [DATO DA COMPLETARE: ...];\n"
        "- cita i documenti con marker brevi tra parentesi quadre, ad esempio [Doc: nome file, p. 1];\n"
        "- non rispondere con spiegazioni fuori dall'HTML dell'atto.\n\n"
        f"Payload governato:\n{_compact_json(payload)}"
    )


def build_edit_prompt(*, instructions: str, current_snapshot: dict[str, Any]) -> str:
    return (
        "Proponi modifiche puntuali all'atto corrente. Non rigenerare l'intero documento. "
        "Restituisci solo proposte compatibili con replace, insert_after, insert_before, delete, rewrite_section o add_section.\n"
        f"Istruzioni utente: {clean_text(instructions)}\n"
        f"Documento corrente:\n{_compact_json(current_snapshot)}"
    )
