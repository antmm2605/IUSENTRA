from __future__ import annotations

from ..source_base import BaseLegalSourceAdapter, citation_policy, source_manuscript, source_metadata, source_scorecard


class GarantePrivacyAdapter(BaseLegalSourceAdapter):
    def __init__(self) -> None:
        metadata = source_metadata(
            source_id="garante_privacy",
            display_name="Garante per la protezione dei dati personali",
            category="privacy_authority",
            jurisdiction="IT",
            base_url="https://www.garanteprivacy.it/",
            official=True,
            priority=72,
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
                access_modes=["portale istituzionale", "provvedimenti pubblici", "linee guida e pareri"],
                identifiers_supported=["numero provvedimento", "data", "registro provvedimenti"],
                versioning_supported=False,
                ingestion_strategy=["fase futura: lookup puntuale provvedimento o linea guida"],
                limitations=["distinguere provvedimenti, linee guida, FAQ e comunicati", "non confondere con il testo GDPR su EUR-Lex"],
            ),
            scorecard=source_scorecard(
                source_id=metadata.source_id,
                official=True,
                citation_quality=0.55,
                identifier_stability=0.55,
                legal_risk=0.5,
            ),
            citation_policy=citation_policy(
                document_types=["provvedimento", "linea guida", "parere", "FAQ"],
                identifiers=["numero", "data", "registro"],
                notes=["Marcare come autorita amministrativa, non come normativa primaria."],
            ),
        )
