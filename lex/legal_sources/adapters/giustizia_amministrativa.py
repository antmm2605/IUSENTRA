from __future__ import annotations

from ..source_base import BaseLegalSourceAdapter, citation_policy, source_manuscript, source_metadata, source_scorecard


class GiustiziaAmministrativaAdapter(BaseLegalSourceAdapter):
    def __init__(self) -> None:
        metadata = source_metadata(
            source_id="giustizia_amministrativa",
            display_name="Giustizia Amministrativa",
            category="administrative_case_law",
            jurisdiction="IT",
            base_url="https://www.giustizia-amministrativa.it/",
            official=True,
            priority=88,
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
                access_modes=["portale ufficiale", "OpenGA ove applicabile", "ricerca per estremi"],
                identifiers_supported=["TAR", "Consiglio di Stato", "CGA", "numero", "anno", "data"],
                versioning_supported=False,
                ingestion_strategy=["fase futura: lookup per autorita, numero e anno con fixture"],
                limitations=["distinguere TAR, Consiglio di Stato e CGA", "nessun uso di portali riservati"],
            ),
            scorecard=source_scorecard(
                source_id=metadata.source_id,
                official=True,
                citation_quality=0.6,
                identifier_stability=0.6,
                retrieval_reliability=0.2,
            ),
            citation_policy=citation_policy(
                document_types=["sentenza", "ordinanza", "decreto", "parere"],
                identifiers=["autorita", "numero", "anno", "data"],
                notes=["Citare sempre autorita giudicante: TAR, Consiglio di Stato o CGA."],
            ),
        )
