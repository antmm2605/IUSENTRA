from __future__ import annotations

from ..source_base import BaseLegalSourceAdapter, citation_policy, source_manuscript, source_metadata, source_scorecard


class SenatoAdapter(BaseLegalSourceAdapter):
    def __init__(self) -> None:
        metadata = source_metadata(
            source_id="senato",
            display_name="Senato della Repubblica",
            category="parliamentary_materials",
            jurisdiction="IT",
            base_url="https://dati.senato.it/",
            official=True,
            priority=60,
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
                access_modes=["open data ufficiale", "atti parlamentari", "download documentati"],
                identifiers_supported=["atto Senato", "numero ddl", "legislatura", "seduta"],
                versioning_supported=True,
                ingestion_strategy=["fase futura: lookup puntuale atto parlamentare e iter"],
                limitations=["materiali preparatori non sono diritto vigente", "citare come fonte parlamentare"],
            ),
            scorecard=source_scorecard(
                source_id=metadata.source_id,
                official=True,
                citation_quality=0.45,
                identifier_stability=0.55,
                versioning=0.4,
                legal_risk=0.6,
            ),
            citation_policy=citation_policy(
                document_types=["disegno di legge", "resoconto", "atto parlamentare", "dossier"],
                identifiers=["legislatura", "numero atto", "seduta", "data"],
                notes=["Usare per lavori preparatori, non come testo normativo vigente."],
            ),
        )
