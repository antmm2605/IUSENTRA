from __future__ import annotations

from ..source_base import BaseLegalSourceAdapter, citation_policy, source_manuscript, source_metadata, source_scorecard


class AnacAdapter(BaseLegalSourceAdapter):
    def __init__(self) -> None:
        metadata = source_metadata(
            source_id="anac",
            display_name="ANAC",
            category="public_procurement_anticorruption",
            jurisdiction="IT",
            base_url="https://www.anticorruzione.it/",
            official=True,
            priority=70,
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
                access_modes=["portale istituzionale", "open data dove disponibile", "delibere e pareri pubblici"],
                identifiers_supported=["numero delibera", "data", "linea guida", "parere"],
                versioning_supported=False,
                ingestion_strategy=["fase futura: lookup puntuale delibere/linee guida con canale ufficiale"],
                limitations=["distinguere soft law, prassi e atti vincolanti", "non usare dataset appalti come norma"],
            ),
            scorecard=source_scorecard(
                source_id=metadata.source_id,
                official=True,
                citation_quality=0.55,
                identifier_stability=0.55,
                legal_risk=0.55,
            ),
            citation_policy=citation_policy(
                document_types=["delibera", "linea guida", "parere", "comunicato"],
                identifiers=["numero", "data", "tipologia"],
                notes=["Marcare sempre la natura del documento ANAC."],
            ),
        )
