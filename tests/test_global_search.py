from pct.global_search.adapters import (
    ClientiSearchAdapter,
    DocumentiSearchAdapter,
    FascicoliSearchAdapter,
    ScadenzeSearchAdapter,
)
from pct.global_search.indexer import GlobalSearchIndexer
from pct.global_search.repository import GlobalSearchRepository


class FakeManager:
    def __init__(self, items):
        self._items = items

    def tutti(self, **kwargs):
        return list(self._items)

    def tutte(self, **kwargs):
        return list(self._items)


def _repo(tmp_path):
    return GlobalSearchRepository(tmp_path / "global_search.db")


def test_indicizza_e_cerca_fascicolo_cliente_documento_scadenza(tmp_path):
    repo = _repo(tmp_path)
    try:
        context = {
            "tenant_id": "tenant-a",
            "fascicoli": FakeManager([
                {
                    "id": "F1",
                    "numero_rg": "466/2023",
                    "titolo": "Risarcimento danno stradale",
                    "nome_cliente": "Alessi Robertino",
                    "controparte": "Zurich Ass.ni",
                    "documenti": [
                        {
                            "id": "D1",
                            "nome": "SentenzaDefinitiva_33581101.pdf",
                            "tipo_atto": "SentenzaDefinitiva",
                            "note": "Rigetto parziale e compensazione spese",
                            "firmato": True,
                        }
                    ],
                }
            ]),
            "clienti": FakeManager([
                {
                    "id": "C1",
                    "nome": "Robertino",
                    "cognome": "Alessi",
                    "codice_fiscale": "LSSRRT64L01L063H",
                    "email": "alessi@example.it",
                }
            ]),
            "scadenziario": FakeManager([
                {"id": "S1", "titolo": "Termine deposito note", "data_scadenza": "2026-05-10", "priorita": "alta"}
            ]),
        }
        indexer = GlobalSearchIndexer(
            repo,
            adapters=[
                FascicoliSearchAdapter(),
                ClientiSearchAdapter(),
                DocumentiSearchAdapter(),
                ScadenzeSearchAdapter(),
            ],
        )
        report = indexer.reindex_all(context)
        assert report.indexed == 4
        assert repo.search(tenant_id="tenant-a", query="466/2023", limit=5)[0].entity_type == "fascicolo"
        assert repo.search(tenant_id="tenant-a", query="LSSRRT64L01L063H", limit=5)[0].entity_type == "cliente"
        assert repo.search(tenant_id="tenant-a", query="Zurich", limit=5)[0].entity_type == "fascicolo"
        assert repo.search(tenant_id="tenant-a", query="SentenzaDefinitiva", entity_types=["documento"], limit=5)
        assert repo.search(tenant_id="tenant-a", query="deposito note", entity_types=["scadenza"], limit=5)
    finally:
        repo.close()


def test_isolamento_tenant_nessun_leakage(tmp_path):
    repo = _repo(tmp_path)
    try:
        for tenant, title in (("tenant-a", "Fascicolo Rossi"), ("tenant-b", "Fascicolo Bianchi")):
            GlobalSearchIndexer(repo, adapters=[FascicoliSearchAdapter()]).reindex_all(
                {
                    "tenant_id": tenant,
                    "fascicoli": FakeManager([{"id": tenant, "numero_rg": "100/2026", "titolo": title}]),
                }
            )
        results_a = repo.search(tenant_id="tenant-a", query="Bianchi", limit=10)
        results_b = repo.search(tenant_id="tenant-b", query="Bianchi", limit=10)
        assert results_a == []
        assert len(results_b) == 1
    finally:
        repo.close()
