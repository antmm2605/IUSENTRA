from __future__ import annotations

from ..source_base import BaseLegalSourceAdapter, citation_policy, source_manuscript, source_metadata, source_scorecard


class NormattivaAdapter(BaseLegalSourceAdapter):
    def __init__(self) -> None:
        metadata = source_metadata(
            source_id="normattiva",
            display_name="Normattiva",
            category="primary_legislation",
            jurisdiction="IT",
            base_url="https://www.normattiva.it/",
            official=True,
            priority=100,
            supports_open_data=True,
            supports_search=True,
            supports_fetch_by_id=True,
            supports_versions=True,
            requires_auth=False,
        )
        super().__init__(
            metadata=metadata,
            manuscript=source_manuscript(
                metadata=metadata,
                access_modes=["open data ufficiale", "ricerca per identificativo", "URL stabile pubblico"],
                identifiers_supported=["URN:NIR", "numero atto", "data atto", "ELI dove disponibile"],
                versioning_supported=True,
                ingestion_strategy=[
                    "fase futura: ingestione campione di un solo atto tramite canale ufficiale documentato",
                    "conservare checksum e versione giuridica",
                    "reindicizzare solo documenti cambiati",
                ],
                limitations=["nessun download massivo in questa fase", "test unitari solo fixture"],
            ),
            scorecard=source_scorecard(
                source_id=metadata.source_id,
                official=True,
                citation_quality=0.65,
                identifier_stability=0.7,
                versioning=0.75,
                updateability=0.4,
            ),
            citation_policy=citation_policy(
                document_types=["legge", "decreto", "codice", "testo unico", "regolamento"],
                identifiers=["URN:NIR", "ELI", "numero atto", "data atto"],
                notes=["Per diritto vigente richiedere data di versione o vigenza dichiarata."],
            ),
        )
