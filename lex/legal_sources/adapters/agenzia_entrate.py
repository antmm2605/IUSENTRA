from __future__ import annotations

from ..source_base import BaseLegalSourceAdapter, citation_policy, source_manuscript, source_metadata, source_scorecard


class AgenziaEntrateAdapter(BaseLegalSourceAdapter):
    def __init__(self) -> None:
        metadata = source_metadata(
            source_id="agenzia_entrate",
            display_name="Agenzia delle Entrate",
            category="tax_practice",
            jurisdiction="IT",
            base_url="https://www.agenziaentrate.gov.it/",
            official=True,
            priority=74,
            supports_open_data=False,
            supports_search=True,
            supports_fetch_by_id=True,
            supports_versions=False,
            requires_auth=False,
        )
        super().__init__(
            metadata=metadata,
            manuscript=source_manuscript(
                metadata=metadata,
                access_modes=["portale istituzionale", "documenti ufficiali pubblici", "PDF o schede"],
                identifiers_supported=["numero provvedimento", "numero interpello", "circolare", "risoluzione", "data"],
                versioning_supported=False,
                ingestion_strategy=["fase futura: lookup puntuale documenti di prassi citabili"],
                limitations=["prassi e guide non sono normativa primaria", "marcare sempre come prassi/guida di autorita"],
            ),
            scorecard=source_scorecard(
                source_id=metadata.source_id,
                official=True,
                citation_quality=0.55,
                identifier_stability=0.55,
                legal_risk=0.55,
            ),
            citation_policy=citation_policy(
                document_types=["interpello", "circolare", "risoluzione", "provvedimento", "guida"],
                identifiers=["numero", "data", "tipologia documento"],
                notes=["Risposte e guide vanno distinte dalla normativa vincolante."],
            ),
        )
