from __future__ import annotations

from ..source_base import BaseLegalSourceAdapter, citation_policy, source_manuscript, source_metadata, source_scorecard


class CassazioneAdapter(BaseLegalSourceAdapter):
    def __init__(self) -> None:
        metadata = source_metadata(
            source_id="cassazione",
            display_name="Corte di Cassazione",
            category="case_law",
            jurisdiction="IT",
            base_url="https://www.cortedicassazione.it/",
            official=True,
            priority=90,
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
                access_modes=["ricerca pubblica ufficiale", "URL ufficiale", "PDF o scheda quando disponibili"],
                identifiers_supported=["numero sentenza", "numero ordinanza", "sezione", "data", "ECLI se disponibile"],
                versioning_supported=False,
                ingestion_strategy=["fase futura: lookup esatto per numero/data/sezione senza scraping ampio"],
                limitations=["copertura e disponibilita del testo integrale possono variare", "mai inventare estremi di pronuncia"],
            ),
            scorecard=source_scorecard(
                source_id=metadata.source_id,
                official=True,
                citation_quality=0.6,
                identifier_stability=0.65,
                retrieval_reliability=0.15,
            ),
            citation_policy=citation_policy(
                document_types=["sentenza", "ordinanza", "decreto"],
                identifiers=["numero", "sezione", "data", "ECLI"],
                notes=["Per ricerca esatta richiedere corrispondenza di numero e data o ECLI."],
            ),
        )
