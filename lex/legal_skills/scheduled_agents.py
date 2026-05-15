"""Agenti schedulati read-only per Legal Skills."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from .models import (
    LegalSkillCitation,
    LegalSkillReviewerNote,
    ScheduledAgentDefinition,
    ScheduledAgentRunResult,
    utc_now_iso,
)


DEFAULT_AGENTS: tuple[ScheduledAgentDefinition, ...] = (
    ScheduledAgentDefinition(
        agent_id="regulatory_monitor",
        name="Monitor normativo",
        description="Raccoglie un promemoria read-only sulle fonti da verificare per le aree dello studio.",
        skill_ref="regulatory_legal/regulatory_monitor",
        enabled=False,
    ),
    ScheduledAgentDefinition(
        agent_id="renewal_watcher",
        name="Scadenze contrattuali",
        description="Prepara una lista di rinnovi da controllare sui documenti collegati.",
        skill_ref="commercial_legal/renewal_watch",
        enabled=False,
    ),
    ScheduledAgentDefinition(
        agent_id="docket_watcher",
        name="Agenda fascicolo",
        description="Controlla eventi e scadenze senza modificare agenda o fascicoli.",
        skill_ref="litigation_legal/hearing_prep",
        enabled=False,
    ),
    ScheduledAgentDefinition(
        agent_id="diligence_grid",
        name="Griglia diligence",
        description="Prepara una griglia di controllo privacy o contrattuale.",
        skill_ref="privacy_legal/dpa_review",
        enabled=False,
    ),
    ScheduledAgentDefinition(
        agent_id="launch_radar",
        name="Radar novita",
        description="Evidenzia temi da portare all'attenzione dello studio.",
        skill_ref="regulatory_legal/policy_gap_check",
        enabled=False,
    ),
)


class ScheduledLegalAgentsService:
    def __init__(self, storage_path: str | Path) -> None:
        self.storage_path = Path(storage_path)

    def list_agents(self, *, enabled: bool = False) -> list[ScheduledAgentDefinition]:
        return [
            ScheduledAgentDefinition(
                agent_id=agent.agent_id,
                name=agent.name,
                description=agent.description,
                skill_ref=agent.skill_ref,
                enabled=enabled and agent.agent_id == "regulatory_monitor",
                read_only=True,
                required_permission=agent.required_permission,
            )
            for agent in DEFAULT_AGENTS
        ]

    def run_now(self, agent_id: str, *, enabled: bool) -> ScheduledAgentRunResult:
        agents = {agent.agent_id: agent for agent in self.list_agents(enabled=enabled)}
        if agent_id not in agents:
            raise KeyError(agent_id)
        agent = agents[agent_id]
        if not agent.enabled:
            return ScheduledAgentRunResult(
                agent_id=agent.agent_id,
                run_id=hashlib.sha256(f"{utc_now_iso()}:{agent_id}".encode("utf-8")).hexdigest()[:24],
                status="disabled",
                summary="Agente schedulato non attivo per questo studio.",
                reviewer_note=LegalSkillReviewerNote(
                    text="Agente non eseguito: attiva il controllo schedulato solo dopo configurazione e permessi.",
                    needs_review=True,
                    blocks_export=True,
                ),
            )
        citations = [
            LegalSkillCitation(
                label="Normattiva",
                source_type="official",
                reference="Fonte normativa primaria da verificare",
                reliability="high",
                url="https://www.normattiva.it",
            ),
            LegalSkillCitation(
                label="Gazzetta Ufficiale",
                source_type="official",
                reference="Pubblicazioni ufficiali da verificare",
                reliability="high",
                url="https://www.gazzettaufficiale.it",
            ),
        ]
        return ScheduledAgentRunResult(
            agent_id=agent.agent_id,
            run_id=hashlib.sha256(f"{utc_now_iso()}:{agent_id}".encode("utf-8")).hexdigest()[:24],
            status="completed",
            summary="Promemoria read-only generato. Verificare le fonti ufficiali prima di aggiornare fascicoli o policy.",
            reviewer_note=LegalSkillReviewerNote(
                text="Bozza per revisione: nessuna modifica automatica e nessuna scadenza creata.",
                needs_review=True,
                blocks_export=False,
            ),
            citations=citations,
        )


__all__ = ["DEFAULT_AGENTS", "ScheduledLegalAgentsService"]
