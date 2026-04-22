"""Adapter preventivi per il retrieval applicativo Lex."""

from __future__ import annotations

from web.helpers import get_preventivi

from . import row_to_evidence


class PreventiviSource:
    source_name = "preventivi"

    def search(self, queries, request, context):
        question = queries[0] if queries else request.query
        gestore = get_preventivi()
        best_runtime = dict(gestore.select_best_preventivi_runtime(question, limit=3) or {})
        best_practice = dict(gestore.select_best_pratiche_preventivo(question, limit=3) or {})
        rows = []

        preventivo = dict(best_runtime.get("best_preventivo") or {})
        if preventivo:
            lines = [
                f"Stato {preventivo.get('stato') or 'n.d.'}",
                f"canale {preventivo.get('workflow_channel_label') or 'Studio'}",
            ]
            if str(preventivo.get("wizard_step_label") or "").strip():
                lines.append(f"step {preventivo.get('wizard_step_label')}")
            missing_fields = list(preventivo.get("campi_mancanti") or [])
            if missing_fields:
                lines.append("campi mancanti: " + ", ".join(str(item) for item in missing_fields[:4]))
            rows.append(
                row_to_evidence(
                    {
                        "type": "preventivo",
                        "id": preventivo.get("preventivo_id") or preventivo.get("id") or "",
                        "title": preventivo.get("oggetto") or preventivo.get("numero") or "Preventivo guidato",
                        "excerpt": "; ".join(line for line in lines if line) + ".",
                        "score": 0.88,
                        "authority": "studio_context",
                        "source_level": 3,
                        "trust_class": "B",
                    },
                    "preventivo",
                )
            )

        practice = dict(best_practice.get("best_practice") or {})
        if practice:
            rows.append(
                row_to_evidence(
                    {
                        "type": "tariffario",
                        "id": practice.get("practice_id") or practice.get("id") or "",
                        "title": practice.get("label") or practice.get("title") or "Pratica preventivo",
                        "excerpt": (
                            f"Motore {practice.get('motore_label') or practice.get('motore') or 'preventivo guidato'}; "
                            f"area {practice.get('area_label') or practice.get('area') or 'economico'}; "
                            f"workflow {practice.get('workflow_label') or practice.get('workflow') or 'n.d.'}."
                        ),
                        "score": 0.84,
                        "authority": "studio_context",
                        "source_level": 3,
                        "trust_class": "B",
                    },
                    "tariffario",
                )
            )

        return rows[:4]
