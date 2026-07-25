"""Esecuzione governata dei prompt LegalSkills Italia con il motore Lex.

Trasforma un prompt del catalogo (eventualmente precompilato dal
fascicolo) in una skill sintetica read-only e nella relativa richiesta,
così che l'esecuzione passi per l'intera pipeline governata del Legal
Skills Engine: profilo studio obbligatorio, fonti di policy, guardrail,
nota di revisione e salvataggio nella coda di approvazione.
"""

from __future__ import annotations

from typing import Any, Mapping

from ..models import LegalSkill, SkillRunRequest

PROMPT_PACK_ID = "prompt_library"
_MAX_NOTA = 2000


def prepara_esecuzione_prompt(
    dettaglio: Mapping[str, Any],
    *,
    nota: str = "",
    documents: list[dict[str, Any]] | None = None,
    source_mode: str = "",
) -> tuple[LegalSkill, SkillRunRequest]:
    """Costruisce la skill sintetica e la richiesta di esecuzione dal prompt."""
    prompt_id = str(dettaglio.get("prompt_id") or "").strip()
    testo = str(dettaglio.get("testo") or "").strip()
    skill = LegalSkill(
        pack_id=PROMPT_PACK_ID,
        skill_id=prompt_id,
        name=str(dettaglio.get("titolo") or prompt_id),
        description=str(dettaglio.get("descrizione") or ""),
        area=str(dettaglio.get("area_id") or "default"),
        references=list(dettaglio.get("riferimenti") or []),
        source_mode="balanced",
        builtin=True,
        read_only=True,
    )
    question = testo
    nota_pulita = " ".join(str(nota or "").split())[:_MAX_NOTA]
    if nota_pulita:
        question = f"{testo}\n\nNota dell'avvocato: {nota_pulita}"
    contesto_fascicolo = dettaglio.get("contesto_fascicolo") or {}
    request = SkillRunRequest(
        pack_id=PROMPT_PACK_ID,
        skill_id=prompt_id,
        question=question,
        documents=[doc for doc in (documents or []) if isinstance(doc, Mapping)][:20],
        requested_source_mode=str(source_mode or "").strip(),
        context={
            "prompt_id": prompt_id,
            "forma": str(dettaglio.get("forma") or ""),
            "fascicolo_id": str(contesto_fascicolo.get("fascicolo_id") or ""),
        },
    )
    return skill, request


__all__ = ["PROMPT_PACK_ID", "prepara_esecuzione_prompt"]
