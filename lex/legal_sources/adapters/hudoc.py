from __future__ import annotations

from ..source_base import BaseLegalSourceAdapter, citation_policy, source_manuscript, source_metadata, source_scorecard


class HudocAdapter(BaseLegalSourceAdapter):
    def __init__(self) -> None:
        metadata = source_metadata(
            source_id="hudoc",
            display_name="HUDOC / Corte Europea dei Diritti dell'Uomo",
            category="echr_case_law",
            jurisdiction="ECHR",
            base_url="https://hudoc.echr.coe.int/",
            official=True,
            priority=84,
            supports_open_data=True,
            supports_search=True,
            supports_fetch_by_id=True,
            supports_versions=False,
            requires_auth=False,
        )
        super().__init__(
            metadata=metadata,
            manuscript=source_manuscript(
                metadata=metadata,
                access_modes=["portale HUDOC ufficiale", "identificativo HUDOC", "filtri pubblici"],
                identifiers_supported=["HUDOC ID", "numero ricorso", "ECLI dove disponibile", "data decisione"],
                versioning_supported=False,
                ingestion_strategy=["fase futura: lookup HUDOC ID con fixture e citazione controllata"],
                limitations=["distinguere sentenze, decisioni e comunicati", "traduzioni non sempre ufficiali"],
            ),
            scorecard=source_scorecard(
                source_id=metadata.source_id,
                official=True,
                citation_quality=0.65,
                identifier_stability=0.7,
                retrieval_reliability=0.2,
            ),
            citation_policy=citation_policy(
                document_types=["judgment", "decision", "communicated case"],
                identifiers=["HUDOC ID", "application number", "ECLI"],
                notes=["Citare HUDOC ID o numero ricorso e data della decisione."],
            ),
        )
