"""Adapter operativo per il retrieval applicativo di Lex."""

from __future__ import annotations

from lex.contracts import EvidenceItem


def _clean(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _structured_context(context):
    payload = dict(context or {})
    structured = payload.get("structured_context")
    return dict(structured or {}) if isinstance(structured, dict) else payload


class OperationalSource:
    source_name = "operativo"

    def search(self, queries, request, context):
        structured = _structured_context(context)
        studio = dict(structured.get("studio_operativo") or {})
        fascicolo = dict(structured.get("fascicolo_intelligence") or {})
        economico = dict(structured.get("economico") or {})
        rows: list[EvidenceItem] = []

        summary = dict(studio.get("summary") or {})
        if summary:
            rows.append(
                EvidenceItem(
                    source_type="operativo",
                    source_id="studio:overview",
                    title="Cabina operativa studio",
                    content=(
                        f"Scadenze urgenti {int(summary.get('scadenze_urgenti') or 0)}; "
                        f"appuntamenti in orizzonte {int(summary.get('appuntamenti_orizzonte') or 0)}; "
                        f"fascicoli attenzionati {int(summary.get('fascicoli_attenzionati') or 0)}."
                    ),
                    score=0.86,
                    metadata={"authority": "workspace_intelligente"},
                )
            )

        first_action = next((row for row in list(studio.get("actions") or []) if isinstance(row, dict)), None)
        if first_action:
            rows.append(
                EvidenceItem(
                    source_type="operativo",
                    source_id=f"studio:action:{_clean(first_action.get('title')).lower().replace(' ', '-')}",
                    title=_clean(first_action.get("title")) or "Azione operativa",
                    content=_clean(first_action.get("description")) or "Azione operativa disponibile.",
                    score=0.82,
                    metadata={"authority": "workspace_intelligente", "tone": _clean(first_action.get("tone"))},
                )
            )

        hot_case = next((row for row in list(studio.get("fascicoli_hot") or []) if isinstance(row, dict)), None)
        if hot_case:
            rows.append(
                EvidenceItem(
                    source_type="operativo",
                    source_id=f"studio:fascicolo-hot:{_clean(hot_case.get('id'))}",
                    title=_clean(hot_case.get("titolo")) or _clean(hot_case.get("numero")) or "Fascicolo attenzionato",
                    content=(
                        f"Tribunale {_clean(hot_case.get('tribunale')) or 'n.d.'}; "
                        f"score {int(hot_case.get('score') or 0)}; "
                        f"azioni: {'; '.join(str(item) for item in list(hot_case.get('azioni') or [])[:2]) or 'nessuna'}."
                    ),
                    score=0.78,
                    metadata={"authority": "workspace_intelligente"},
                )
            )

        next_action = next((str(item).strip() for item in list(fascicolo.get("next_actions") or []) if str(item).strip()), "")
        if next_action:
            rows.append(
                EvidenceItem(
                    source_type="operativo",
                    source_id="fascicolo:intelligence",
                    title="Quadro intelligente fascicolo",
                    content=next_action,
                    score=0.88,
                    metadata={"authority": "workspace_intelligente"},
                )
            )

        economic_summary = dict(economico.get("summary") or {})
        if economic_summary:
            rows.append(
                EvidenceItem(
                    source_type="economico",
                    source_id=f"economico:{_clean(economico.get('scope')) or 'studio'}",
                    title="Presidio economico",
                    content=(
                        f"Preventivi {int(economic_summary.get('preventivi_count') or 0)}, "
                        f"conferimenti {int(economic_summary.get('conferimenti_count') or 0)}, "
                        f"parcelle {int(economic_summary.get('parcelle_count') or 0)}, "
                        f"saldo aperto {economic_summary.get('saldo_aperto') or 0}."
                    ),
                    score=0.72,
                    metadata={"authority": "economico_runtime"},
                )
            )

        return rows[:6]
