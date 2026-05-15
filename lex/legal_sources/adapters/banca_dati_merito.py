from __future__ import annotations

from ..source_base import BaseLegalSourceAdapter, citation_policy, source_manuscript, source_metadata, source_scorecard


class BancaDatiMeritoAdapter(BaseLegalSourceAdapter):
    def __init__(self) -> None:
        metadata = source_metadata(
            source_id="banca_dati_merito",
            display_name="Banca Dati di Merito",
            category="trial_court_case_law",
            jurisdiction="IT",
            base_url="https://bdp.giustizia.it/",
            official=True,
            priority=76,
            supports_open_data=False,
            supports_search=True,
            supports_fetch_by_id=True,
            supports_versions=False,
            requires_auth=True,
        )
        super().__init__(
            metadata=metadata,
            manuscript=source_manuscript(
                metadata=metadata,
                access_modes=["portale ufficiale regolamentato", "accesso autenticato ove previsto"],
                identifiers_supported=["tribunale", "corte d'appello", "numero", "data", "tipo provvedimento"],
                versioning_supported=False,
                ingestion_strategy=["fase futura solo con canale autorizzato, audit e credenziali configurate esplicitamente"],
                limitations=["fonte non abilitabile senza verifica licenza/accesso", "nessun crawling o scraping del portale"],
            ),
            scorecard=source_scorecard(
                source_id=metadata.source_id,
                official=True,
                citation_quality=0.45,
                identifier_stability=0.45,
                retrieval_reliability=0.05,
                legal_risk=0.75,
            ),
            citation_policy=citation_policy(
                document_types=["sentenza", "ordinanza", "decreto"],
                identifiers=["ufficio", "numero", "data", "tipo provvedimento"],
                notes=["Trattare come fonte ufficiale solo nel perimetro di accesso autorizzato."],
            ),
        )
