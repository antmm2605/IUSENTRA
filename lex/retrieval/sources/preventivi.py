"""Adapter preventivi per il retrieval applicativo Lex."""

from __future__ import annotations

from web.helpers import get_preventivi

from . import row_to_evidence


def _structured_context(context):
    payload = dict(context or {})
    structured = payload.get("structured_context")
    return dict(structured or {}) if isinstance(structured, dict) else payload


class PreventiviSource:
    source_name = "preventivi"

    def search(self, queries, request, context):
        question = queries[0] if queries else request.query
        structured = _structured_context(context)
        economico = dict(structured.get("economico") or {})
        gestore = get_preventivi()
        best_runtime = dict(gestore.select_best_preventivi_runtime(question, limit=3) or {})
        best_practice = dict(gestore.select_best_pratiche_preventivo(question, limit=3) or {})
        rows = []

        summary = dict(economico.get("summary") or {})
        if summary:
            scope = str(economico.get("scope") or "studio").strip() or "studio"
            fascicolo = dict(economico.get("fascicolo") or {})
            labels = []
            if scope == "fascicolo" and str(fascicolo.get("numero") or "").strip():
                labels.append(f"fascicolo {fascicolo.get('numero')}")
            labels.append(f"preventivi {int(summary.get('preventivi_count') or 0)}")
            labels.append(f"conferimenti {int(summary.get('conferimenti_count') or 0)}")
            labels.append(f"parcelle {int(summary.get('parcelle_count') or 0)}")
            labels.append(f"saldo aperto {summary.get('saldo_aperto') or 0}")
            rows.append(
                row_to_evidence(
                    {
                        "type": "economico",
                        "id": f"economico-{scope}",
                        "title": "Presidio economico fascicolo" if scope == "fascicolo" else "Presidio economico studio",
                        "excerpt": "; ".join(str(item) for item in labels if str(item).strip()) + ".",
                        "score": 0.9 if scope == "fascicolo" else 0.78,
                        "authority": "economico_runtime",
                        "source_level": 3,
                        "trust_class": "B",
                    },
                    "economico",
                )
            )

        for preventivo_row in list(economico.get("preventivi") or [])[:2]:
            rows.append(
                row_to_evidence(
                    {
                        "type": "preventivo",
                        "id": preventivo_row.get("id") or "",
                        "title": preventivo_row.get("oggetto") or preventivo_row.get("numero") or "Preventivo",
                        "excerpt": (
                            f"Stato {preventivo_row.get('stato') or 'n.d.'}; "
                            f"totale {preventivo_row.get('totale') or 0}; "
                            f"workflow {preventivo_row.get('workflow_channel') or 'n.d.'}."
                        ),
                        "score": 0.92,
                        "authority": "economico_runtime",
                        "source_level": 3,
                        "trust_class": "B",
                    },
                    "preventivo",
                )
            )

        for parcella_row in list(economico.get("parcelle") or [])[:2]:
            rows.append(
                row_to_evidence(
                    {
                        "type": "fatturazione",
                        "id": parcella_row.get("id") or "",
                        "title": parcella_row.get("numero") or "Parcella",
                        "excerpt": (
                            f"Stato {parcella_row.get('stato') or 'n.d.'}; "
                            f"totale {parcella_row.get('totale') or 0}; "
                            f"scadenza {parcella_row.get('data_scadenza') or 'n.d.'}."
                        ),
                        "score": 0.84,
                        "authority": "economico_runtime",
                        "source_level": 3,
                        "trust_class": "B",
                    },
                    "fatturazione",
                )
            )

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
