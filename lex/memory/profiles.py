"""Profili sintetici di tenant, utente e fascicolo per Lex."""

from __future__ import annotations


class ProfileStore:
    def __init__(self) -> None:
        self._profiles: dict[str, dict] = {}

    def remember(self, request, context) -> None:
        tenant_id = str(getattr(request, "tenant_id", "") or "")
        session_id = str(getattr(request, "session_id", "") or "")
        fascicolo_id = str(getattr(request, "fascicolo_id", "") or "")
        studio = dict(context.get("studio") or {})
        fascicolo = dict(context.get("fascicolo") or {})
        if tenant_id:
            self._profiles[f"tenant:{tenant_id}"] = {
                "tenant_id": tenant_id,
                "workflow_hint": str(getattr(request, "workflow_hint", "") or ""),
                "engine_ids": list(studio.get("engine_ids") or []),
                "legal_route_scope": str(studio.get("legal_route_scope") or ""),
            }
        if session_id:
            self._profiles[f"session:{session_id}"] = {
                "session_id": session_id,
                "user_id": str(getattr(request, "user_id", "") or ""),
                "query": str(getattr(request, "query", "") or ""),
            }
        if fascicolo_id or fascicolo.get("id"):
            case_id = fascicolo_id or str(fascicolo.get("id") or "")
            self._profiles[f"case:{case_id}"] = {
                "fascicolo_id": case_id,
                "stato": fascicolo.get("stato"),
                "fase": fascicolo.get("fase"),
                "ufficio": fascicolo.get("ufficio") or fascicolo.get("tribunale"),
            }

    def snapshot(self, request) -> dict:
        tenant_id = str(getattr(request, "tenant_id", "") or "")
        session_id = str(getattr(request, "session_id", "") or "")
        fascicolo_id = str(getattr(request, "fascicolo_id", "") or "")
        payload = {}
        if tenant_id:
            payload["tenant"] = dict(self._profiles.get(f"tenant:{tenant_id}") or {})
        if session_id:
            payload["session"] = dict(self._profiles.get(f"session:{session_id}") or {})
        if fascicolo_id:
            payload["case"] = dict(self._profiles.get(f"case:{fascicolo_id}") or {})
        return payload