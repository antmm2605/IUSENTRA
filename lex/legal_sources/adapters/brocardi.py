from __future__ import annotations

from ..source_base import BaseLegalSourceAdapter, citation_policy, source_manuscript, source_metadata, source_scorecard


class BrocardiAdapter(BaseLegalSourceAdapter):
    """Adapter per Brocardi — portale italiano di consultazione normativa (tier 2).

    Brocardi è un portale semi-ufficiale che fornisce accesso ai codici italiani
    principali (Civile, Penale, Procedure civili e penali, Costituzione) con
    commento dottrinale e giurisprudenza associata.

    Caratteristiche:
    - Non è fonte ufficiale (secondaria), ma autorevole
    - URL stabili per articolo (articolo, comma, sezione)
    - Non mantiene versioni storiche
    - Accesso libero senza autenticazione
    - Supporta ricerca per numero articolo
    """

    def __init__(self) -> None:
        metadata = source_metadata(
            source_id="brocardi",
            display_name="Brocardi",
            category="secondary_legislation",
            jurisdiction="IT",
            base_url="https://www.brocardi.it/",
            official=False,
            priority=45,
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
                access_modes=[
                    "ricerca web per articolo",
                    "URL stabile per articolo/comma",
                    "navigazione gerarchica sezione/titolo/capo",
                ],
                identifiers_supported=[
                    "articolo (numero)",
                    "comma (numero)",
                    "codice (civile, penale, procedura civile, procedura penale, costituzione)",
                    "sezione/titolo/capo (gerarchico)",
                ],
                versioning_supported=False,
                ingestion_strategy=[
                    "ingestione campione articoli dai 6 codici principali",
                    "preservare gerarchia libro/titolo/capo",
                    "estrarre numero articolo e comma per identificazione univoca",
                    "memorizzare URL stabile per ogni articolo",
                    "incluire testo normativo e note commentate da Brocardi",
                ],
                limitations=[
                    "nessun versioning storico",
                    "no download massivo in questa fase",
                    "Brocardi è tier 2 (secondaria), non fonte ufficiale",
                    "test unitari solo su fixture pre-scaricate",
                ],
            ),
            scorecard=source_scorecard(
                source_id=metadata.source_id,
                official=False,
                citation_quality=0.65,
                identifier_stability=0.8,
                versioning=0.0,
                updateability=0.3,
            ),
            citation_policy=citation_policy(
                document_types=[
                    "articolo",
                    "codice",
                    "comma",
                    "sezione",
                    "titolo",
                    "capo",
                ],
                identifiers=[
                    "articolo + numero",
                    "comma + numero",
                    "codice + sezione",
                    "URL stabile",
                ],
                notes=[
                    "Brocardi è fonte secondaria di commento e consultazione.",
                    "Per citazione ufficiale preferire Normattiva o Gazzetta Ufficiale.",
                    "Brocardi non mantiene versioni storiche (sempre testo vigente).",
                    "Gerarchia: Codice → Libro → Titolo → Capo → Articolo → Comma",
                ],
            ),
        )
