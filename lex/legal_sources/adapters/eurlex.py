from __future__ import annotations

from ..source_base import BaseLegalSourceAdapter, citation_policy, source_manuscript, source_metadata, source_scorecard


class EurLexAdapter(BaseLegalSourceAdapter):
    def __init__(self) -> None:
        metadata = source_metadata(
            source_id="eurlex",
            display_name="EUR-Lex",
            category="eu_law",
            jurisdiction="EU",
            base_url="https://eur-lex.europa.eu/",
            official=True,
            priority=86,
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
                access_modes=["portale ufficiale", "download per identificativo", "open data/API dove documentati"],
                identifiers_supported=["CELEX", "ELI", "OJ number", "data pubblicazione"],
                versioning_supported=True,
                ingestion_strategy=["fase futura: lookup CELEX/ELI con un solo documento campione"],
                limitations=["alcuni servizi possono richiedere registrazione", "distinguere diritto UE, giurisprudenza UE e atti preparatori"],
            ),
            scorecard=source_scorecard(
                source_id=metadata.source_id,
                official=True,
                citation_quality=0.7,
                identifier_stability=0.8,
                versioning=0.55,
                updateability=0.4,
            ),
            citation_policy=citation_policy(
                document_types=["regolamento", "direttiva", "decisione", "sentenza UE", "atto preparatorio"],
                identifiers=["CELEX", "ELI", "OJ", "data"],
                notes=["CELEX e ELI sono identificativi privilegiati quando disponibili."],
            ),
        )
