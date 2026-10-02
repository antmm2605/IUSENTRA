"""Filtri di retrieval per il modulo Lex."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

WORKFLOW_GIURIDICI = {"normativa", "giurisprudenza", "prassi", "research", "fonti"}
# Unici tipi di evidenza ammessi per una domanda giuridica: testi di norma, sentenze, prassi,
# fonti ufficiali lette. Catalogo fonti, template, impostazioni, PEC, dati clienti restano fuori.
TIPI_EVIDENZA_GIURIDICA = {
    "normativa",
    "normativa_normattiva",
    "normativa_gazzetta",
    "giurisprudenza",
    "prassi",
    "web_ufficiale",
    "legal_updates",
    "lex_memory",
}


def e_domanda_giuridica(request, workflow: str) -> bool:
    """Vero per i workflow di ricerca giuridica o per una domanda giuridica senza fascicolo."""

    if workflow in WORKFLOW_GIURIDICI:
        return True
    if workflow == "question_answering" and not getattr(request, "fascicolo_id", None):
        try:
            from lex.ricerca_giuridica.classificatore import classifica_domanda

            return classifica_domanda(str(getattr(request, "query", "") or "")).giuridica
        except Exception:
            return False
    return False


def _tipo(item) -> str:
    valore = item.get("source_type") if isinstance(item, dict) else getattr(item, "source_type", "")
    return str(valore or "").strip().lower()


class RetrievalFilters:
    def apply(self, items, request, context, workflow: str):
        rows = [item for item in list(items or []) if item]
        if not e_domanda_giuridica(request, workflow):
            return rows
        kept = [item for item in rows if _tipo(item) in TIPI_EVIDENZA_GIURIDICA]
        scartate = len(rows) - len(kept)
        if scartate:
            logger.info("Domanda giuridica (%s): escluse %d evidenze non giuridiche.", workflow, scartate)
        return kept
