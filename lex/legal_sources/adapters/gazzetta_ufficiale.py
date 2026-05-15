from __future__ import annotations

from ..source_base import BaseLegalSourceAdapter, citation_policy, source_manuscript, source_metadata, source_scorecard


class GazzettaUfficialeAdapter(BaseLegalSourceAdapter):
    def __init__(self) -> None:
        metadata = source_metadata(
            source_id="gazzetta_ufficiale",
            display_name="Gazzetta Ufficiale",
            category="official_publication",
            jurisdiction="IT",
            base_url="https://www.gazzettaufficiale.it/",
            official=True,
            priority=95,
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
                access_modes=["RSS o feed ufficiale", "URL di pubblicazione", "PDF ufficiale"],
                identifiers_supported=["serie", "numero", "data", "ELI/URN se disponibili"],
                versioning_supported=False,
                ingestion_strategy=[
                    "fase futura: acquisizione di un solo fascicolo o atto tramite endpoint documentato",
                    "tracciare data pubblicazione, numero e serie",
                ],
                limitations=["la pubblicazione non sostituisce il testo consolidato vigente", "nessun crawling degli archivi"],
            ),
            scorecard=source_scorecard(
                source_id=metadata.source_id,
                official=True,
                citation_quality=0.7,
                identifier_stability=0.65,
                updateability=0.35,
            ),
            citation_policy=citation_policy(
                document_types=["pubblicazione ufficiale", "legge pubblicata", "decreto pubblicato", "avviso"],
                identifiers=["serie", "numero gazzetta", "data pubblicazione", "ELI", "URN"],
                notes=["Citare sempre serie, numero e data di pubblicazione quando disponibili."],
            ),
        )
