from __future__ import annotations

from lex.contracts import LexRequest
from lex.retrieval.source_router import SourceRouter
from lex.retrieval.sources.studio_database import StudioDatabaseSource
from pct.global_search.adapters import (
    ComunicazioniSearchAdapter,
    EmailRicevuteSearchAdapter,
    default_adapters,
)
from pct.global_search.indexer import GlobalSearchIndexer
from pct.global_search.models import GlobalSearchDocument
from pct.global_search.repository import GlobalSearchRepository


class FakeManager:
    def __init__(self, items):
        self._items = items

    def tutti(self, **kwargs):
        return list(self._items)

    def tutte(self, **kwargs):
        return list(self._items)


def test_router_aggancia_studio_database_senza_web_libero():
    request = LexRequest(
        tenant_id="tenant-a",
        user_id="u1",
        session_id="s1",
        query="Qual e' l'ultima PEC ricevuta?",
    )

    names = [source.__class__.__name__ for source in SourceRouter().resolve(request, {}, "chat")]

    assert names[0] == "StudioDatabaseSource"

    free_request = LexRequest(
        tenant_id="tenant-a",
        user_id="u1",
        session_id="s1",
        query="cerca liberamente questo tema",
        metadata={"source_mode": "web_libero", "free_web_enabled": True},
    )
    free_names = [source.__class__.__name__ for source in SourceRouter().resolve(free_request, {}, "chat")]

    assert free_names == ["OfficialWebSource"]


def test_default_adapters_includono_email_pec_e_ordinaria():
    adapter_names = [adapter.__class__.__name__ for adapter in default_adapters()]

    assert "EmailRicevuteSearchAdapter" in adapter_names


def test_reindex_indicizza_comunicazioni_pec_email_e_allegati(tmp_path):
    repo = GlobalSearchRepository(tmp_path / "global_search.db")
    try:
        context = {
            "tenant_id": "tenant-a",
            "messaggi": FakeManager(
                [
                    {
                        "id": "MSG-PEC-1",
                        "tipo": "PEC",
                        "oggetto": "Deposito memoria",
                        "mittente": "cancelleria@example.it",
                        "destinatari": "studio@example.it",
                        "corpo": "Comunicazione di cancelleria",
                        "allegati_salvati": [{"nome": "ricevuta-accettazione.eml"}],
                    }
                ]
            ),
            "email_pec": FakeManager(
                [
                    {
                        "id": "PEC-1",
                        "oggetto": "Ultima PEC ricevuta",
                        "mittente": "tribunale@example.it",
                        "destinatari": "studio@example.it",
                        "corpo_testo": "Notifica con allegato",
                        "allegati": [{"nome": "procura.pdf"}],
                        "data": "2026-05-19T09:15:00",
                    }
                ]
            ),
            "email_ordinaria": FakeManager(
                [
                    {
                        "id": "MAIL-1",
                        "oggetto": "Email ordinaria cliente",
                        "mittente": "cliente@example.it",
                        "corpo_testo": "Promemoria operativo",
                        "allegati": [{"nome": "documento-cliente.pdf"}],
                    }
                ]
            ),
        }
        report = GlobalSearchIndexer(
            repo,
            adapters=[ComunicazioniSearchAdapter(), EmailRicevuteSearchAdapter()],
        ).reindex_all(context)

        assert report.indexed == 3
        pec_results = repo.search(tenant_id="tenant-a", query="procura", limit=5)
        mail_results = repo.search(tenant_id="tenant-a", query="documento cliente", limit=5)
        message_results = repo.search(tenant_id="tenant-a", query="ricevuta accettazione", limit=5)

        assert pec_results[0].entity_type == "pec"
        assert pec_results[0].source_url == "/email/messaggio/PEC-1"
        assert pec_results[0].metadata["allegati"] == ["procura.pdf"]
        assert mail_results[0].entity_type == "email"
        assert mail_results[0].source_url == "/email-ordinaria/messaggio/MAIL-1"
        assert message_results[0].entity_type == "pec"
        assert message_results[0].metadata["allegati"] == ["ricevuta-accettazione.eml"]
    finally:
        repo.close()


def test_studio_database_source_filtra_fonti_legali_e_mantiene_identita(tmp_path):
    db_path = tmp_path / "global_search.db"
    repo = GlobalSearchRepository(db_path)
    try:
        repo.upsert_document(
            GlobalSearchDocument(
                tenant_id="tenant-a",
                entity_type="cliente",
                entity_id="C1",
                title="Mario Rossi",
                body="Codice fiscale RSSMRA80A01H501U",
                source_module="clienti",
                source_url="/clienti/C1",
            )
        )
        repo.upsert_document(
            GlobalSearchDocument(
                tenant_id="tenant-a",
                entity_type="legal_intelligence",
                entity_id="L1",
                title="Mario Rossi Cassazione",
                body="Fonte legale gia' trattata dagli adapter dedicati",
                source_module="legal_intelligence",
                source_url="/ricerca-legale",
            )
        )
    finally:
        repo.close()

    request = LexRequest(
        tenant_id="tenant-a",
        user_id="u1",
        session_id="s1",
        query="Mario Rossi",
    )
    items = StudioDatabaseSource().search(
        ["Mario Rossi"],
        request=request,
        context={"tenant_id": "tenant-a", "global_search_db_path": str(db_path)},
    )

    assert len(items) == 1
    assert items[0].source_type == "studio_db:cliente"
    assert items[0].source_id == "C1"
    assert items[0].metadata["source_url"] == "/clienti/C1"
    assert items[0].verified_reference is True
