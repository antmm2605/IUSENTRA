from __future__ import annotations

from ..source_base import BaseLegalSourceAdapter, citation_policy, source_manuscript, source_metadata, source_scorecard


class AgcmAdapter(BaseLegalSourceAdapter):
    def __init__(self) -> None:
        metadata = source_metadata(
            source_id="agcm",
            display_name="AGCM",
            category="competition_consumer_authority",
            jurisdiction="IT",
            base_url="https://www.agcm.it/",
            official=True,
            priority=68,
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
                access_modes=["portale istituzionale", "provvedimenti pubblici"],
                identifiers_supported=["numero provvedimento", "numero bollettino", "data", "procedimento"],
                versioning_supported=False,
                ingestion_strategy=["fase futura: lookup puntuale provvedimento o bollettino"],
                limitations=["distinguere provvedimenti, bollettini e comunicati", "non trattare commenti come diritto vincolante"],
            ),
            scorecard=source_scorecard(
                source_id=metadata.source_id,
                official=True,
                citation_quality=0.5,
                identifier_stability=0.5,
                legal_risk=0.55,
            ),
            citation_policy=citation_policy(
                document_types=["provvedimento", "bollettino", "comunicato"],
                identifiers=["numero", "data", "procedimento"],
                notes=["Citare numero provvedimento o bollettino quando disponibile."],
            ),
        )
