"""Adapter compliance per il retrieval applicativo Lex."""

from __future__ import annotations

from lex.contracts import EvidenceItem


def _clean(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _structured_context(context):
    payload = dict(context or {})
    structured = payload.get("structured_context")
    return dict(structured or {}) if isinstance(structured, dict) else payload


class ComplianceSource:
    source_name = "compliance"

    def search(self, queries, request, context):
        structured = _structured_context(context)
        compliance = dict(structured.get("conformita_fascicolo") or {})
        if compliance:
            general = dict(compliance.get("general") or {})
            rows = [
                EvidenceItem(
                    source_type="compliance",
                    source_id="fascicolo:compliance",
                    title=_clean(compliance.get("readiness_label")) or "Responsabile di conformita'",
                    content=(
                        _clean(compliance.get("summary"))
                        or (
                            f"Stato {_clean(general.get('label')) or 'Da verificare'}; "
                            f"blocchi {int(general.get('blocking_count') or 0)}; "
                            f"avvisi {int(general.get('warning_count') or 0)}."
                        )
                    ),
                    score=0.96,
                    metadata={
                        "authority": "responsabile_conformita",
                        "overall_state": _clean(compliance.get("overall_state")),
                    },
                )
            ]
            for issue in list(compliance.get("blocking_issues") or [])[:3]:
                rows.append(
                    EvidenceItem(
                        source_type="compliance",
                        source_id=_clean(issue.get("code")) or "compliance:block",
                        title=_clean(issue.get("title")) or "Blocco di conformita'",
                        content=_clean(issue.get("detail")) or _clean(issue.get("suggested_action")),
                        score=0.9,
                        metadata={"authority": "responsabile_conformita", "level": _clean(issue.get("level"))},
                    )
                )
            if len(rows) == 1:
                for issue in list(compliance.get("warning_issues") or [])[:2]:
                    rows.append(
                        EvidenceItem(
                            source_type="compliance",
                            source_id=_clean(issue.get("code")) or "compliance:warning",
                            title=_clean(issue.get("title")) or "Verifica aperta",
                            content=_clean(issue.get("detail")) or _clean(issue.get("suggested_action")),
                            score=0.78,
                            metadata={"authority": "responsabile_conformita", "level": _clean(issue.get("level"))},
                        )
                    )
            for row in list(compliance.get("missing_documents") or [])[:2]:
                label = _clean(row.get("label") or row.get("key") or "Documento richiesto")
                rows.append(
                    EvidenceItem(
                        source_type="compliance",
                        source_id=f"missing-doc:{_clean(row.get('key')) or label.lower().replace(' ', '-')}",
                        title=label,
                        content=_clean(row.get("reason")) or "Documento richiesto non ancora rilevato nel fascicolo.",
                        score=0.84,
                        metadata={"authority": "responsabile_conformita", "state": _clean(row.get("state"))},
                    )
                )
            return rows[:6]

        query = queries[0] if queries else request.query
        return [
            EvidenceItem(
                source_type="compliance",
                source_id="guard-rail-telematico",
                title="Regole di conformita operative",
                content=f"Applicare guard rail di conformita e verifica ufficiale su: {query}",
                score=0.7,
                metadata={"authority": "compliance_engine"},
            )
        ]
