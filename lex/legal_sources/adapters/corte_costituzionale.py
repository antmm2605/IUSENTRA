from __future__ import annotations

from ..source_base import BaseLegalSourceAdapter, citation_policy, source_manuscript, source_metadata, source_scorecard


class CorteCostituzionaleAdapter(BaseLegalSourceAdapter):
    def __init__(self) -> None:
        metadata = source_metadata(
            source_id="corte_costituzionale",
            display_name="Corte Costituzionale",
            category="constitutional_case_law",
            jurisdiction="IT",
            base_url="https://www.cortecostituzionale.it/",
            official=True,
            priority=92,
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
                access_modes=["open data ufficiale", "ricerca pronunce", "URL pronuncia"],
                identifiers_supported=["numero sentenza", "numero ordinanza", "anno", "ECLI dove disponibile"],
                versioning_supported=False,
                ingestion_strategy=["fase futura: lookup esatto pronuncia con fixture e citazione strutturata"],
                limitations=["nessun download massivo", "distinguere sentenze, ordinanze e comunicati"],
            ),
            scorecard=source_scorecard(
                source_id=metadata.source_id,
                official=True,
                citation_quality=0.65,
                identifier_stability=0.65,
                retrieval_reliability=0.2,
            ),
            citation_policy=citation_policy(
                document_types=["sentenza", "ordinanza", "decisione"],
                identifiers=["numero", "anno", "ECLI"],
                notes=["Citare tipo pronuncia, numero, anno, data e link ufficiale."],
            ),
        )
