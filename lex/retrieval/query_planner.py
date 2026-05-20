"""Pianificazione query per il retrieval Lex."""

from __future__ import annotations


class QueryPlanner:
    def plan(self, request, context, workflow: str) -> list[str]:
        query = request.query.strip()
        queries = [query] if query else []

        if request.fascicolo_id:
            queries.append(f"fascicolo {request.fascicolo_id} {query}".strip())

        if workflow == "telematico":
            queries.append(f"errore telematico {query}".strip())

        if workflow == "udienza":
            queries.append(f"preparazione udienza {query}".strip())

        if workflow == "atto_da_template":
            metadata = dict(getattr(request, "metadata", {}) or {})
            active = metadata.get("active_context") if isinstance(metadata.get("active_context"), dict) else {}
            model_code = str(active.get("model_code") or active.get("modelCode") or metadata.get("model_code") or "").strip()
            queries.append(f"template atto {query}".strip())
            queries.append(f"catalogo atti {query}".strip())
            if model_code:
                queries.append(f"{model_code} {query}".strip())
            case_id = str(
                getattr(request, "fascicolo_id", "")
                or active.get("case_id")
                or active.get("caseId")
                or active.get("linked_case_id")
                or active.get("linkedCaseId")
                or ""
            ).strip()
            if case_id:
                queries.append(f"fascicolo {case_id} {query}".strip())

        return [item for item in queries if item]
