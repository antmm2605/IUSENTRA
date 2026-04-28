"""Registro fonti ufficiali controllate dal motore giornaliero."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class LegalSource:
    id: str
    name: str
    url: str
    category: str
    enabled: bool = True
    official: bool = True
    apply_mode: str = "manual"
    impact_areas: tuple[str, ...] = field(default_factory=tuple)
    user_agent_note: str = "controllo giornaliero fonti ufficiali IUSENTRA"

    def to_record(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "url": self.url,
            "category": self.category,
            "enabled": int(self.enabled),
            "official": int(self.official),
            "apply_mode": self.apply_mode,
            "impact_areas": list(self.impact_areas),
            "user_agent_note": self.user_agent_note,
        }


DEFAULT_LEGAL_SOURCES: tuple[LegalSource, ...] = (
    LegalSource(
        id="normattiva_opendata",
        name="Normattiva Open Data",
        url="https://api.normattiva.it/t/normattiva.api/bff-opendata/v1/api/v1/collections/collection-predefinite",
        category="normativa",
        apply_mode="manual",
        impact_areas=("template_atti", "compliance", "ai_knowledge_base"),
    ),
    LegalSource(
        id="gazzetta_ufficiale_serie_generale",
        name="Gazzetta Ufficiale - Serie Generale",
        url="https://www.gazzettaufficiale.it/30giorni/serie_generale",
        category="novita_normative",
        apply_mode="manual",
        impact_areas=("template_atti", "scadenze", "tariffario", "ai_knowledge_base"),
    ),
    LegalSource(
        id="pst_software_house",
        name="PST Ministero Giustizia - Software house",
        url="https://pst.giustizia.it/PST/it/pst_26.wp",
        category="pct",
        apply_mode="auto",
        impact_areas=("PCT", "compliance", "deposito_telematico"),
    ),
    LegalSource(
        id="pst_comunicazioni_software_house",
        name="PST - Comunicazioni software house",
        url="https://pst.giustizia.it/PST/it/pst_28.wp",
        category="pct",
        apply_mode="auto",
        impact_areas=("PCT", "template_atti", "compliance"),
    ),
    LegalSource(
        id="pat_siga",
        name="Giustizia Amministrativa - PAT/SIGA",
        url="https://www.giustizia-amministrativa.it/portale/pages/istituzionale/servizi-online",
        category="pat",
        apply_mode="manual",
        impact_areas=("PAT", "template_atti", "compliance"),
    ),
    LegalSource(
        id="ptt_sigit",
        name="Giustizia Tributaria - PTT/SIGIT",
        url="https://www.giustiziatributaria.gov.it/gt/web/guest/processo-tributario-telematico",
        category="ptt",
        apply_mode="manual",
        impact_areas=("PTT", "template_atti", "compliance", "scadenze"),
    ),
    LegalSource(
        id="documentazione_tributaria",
        name="Documentazione tributaria",
        url="https://def.finanze.it/DocTribFrontend/RS2_HomePage.jsp",
        category="tributario",
        apply_mode="manual",
        impact_areas=("PTT", "tariffario", "ai_knowledge_base"),
    ),
    LegalSource(
        id="pdp_penale",
        name="Portale Depositi Penali",
        url="https://pst.giustizia.it/PST/it/pst_38.wp",
        category="pdp",
        apply_mode="manual",
        impact_areas=("PDP", "template_atti", "compliance"),
    ),
)


def enabled_sources(source_ids: list[str] | None = None) -> list[LegalSource]:
    wanted = {item for item in (source_ids or []) if item}
    return [source for source in DEFAULT_LEGAL_SOURCES if source.enabled and (not wanted or source.id in wanted)]
