from __future__ import annotations

from ..source_base import BaseLegalSourceAdapter, citation_policy, source_manuscript, source_metadata, source_scorecard


class LeggiRegionaliAdapter(BaseLegalSourceAdapter):
    def __init__(self) -> None:
        metadata = source_metadata(
            source_id="leggi_regionali",
            display_name="Banche dati regionali di normativa",
            category="regional_legislation",
            jurisdiction="IT-regional",
            base_url="",
            official=True,
            priority=64,
            supports_open_data=False,
            supports_search=True,
            supports_fetch_by_id=True,
            supports_versions=True,
            requires_auth=False,
        )
        super().__init__(
            metadata=metadata,
            manuscript=source_manuscript(
                metadata=metadata,
                access_modes=["registro fonte da configurare per singola Regione", "bollettini regionali", "banche dati ufficiali regionali"],
                identifiers_supported=["Regione", "numero legge regionale", "data", "BUR", "ELI dove disponibile"],
                versioning_supported=True,
                ingestion_strategy=["fase futura: registry per Regione con policy, licenza e rate limit dedicati"],
                limitations=["non esiste un unico endpoint nazionale garantito per tutte le Regioni", "ogni Regione richiede verifica separata"],
                notes=["Il base_url resta vuoto finche non viene selezionata una fonte regionale specifica e ufficiale."],
            ),
            scorecard=source_scorecard(
                source_id=metadata.source_id,
                official=True,
                citation_quality=0.35,
                identifier_stability=0.35,
                versioning=0.25,
                legal_risk=0.65,
            ),
            citation_policy=citation_policy(
                document_types=["legge regionale", "regolamento regionale", "bollettino ufficiale regionale"],
                identifiers=["Regione", "numero", "data", "BUR", "ELI"],
                notes=["Abilitare solo dopo configurazione della fonte regionale ufficiale puntuale."],
            ),
        )
