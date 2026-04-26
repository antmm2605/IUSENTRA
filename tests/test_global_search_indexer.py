from pct.global_search.adapters import ClientiSearchAdapter, FascicoliSearchAdapter
from pct.global_search.indexer import GlobalSearchIndexer
from pct.global_search.repository import GlobalSearchRepository


class FakeManager:
    def __init__(self, items):
        self._items = items

    def tutti(self, **kwargs):
        return list(self._items)


def test_ranking_preferisce_match_esatto_rg(tmp_path):
    repo = GlobalSearchRepository(tmp_path / "search.db")
    try:
        context = {
            "tenant_id": "studio",
            "fascicoli": FakeManager([
                {"id": "F1", "numero_rg": "466/2023", "titolo": "Sinistro stradale"},
                {"id": "F2", "numero_rg": "999/2023", "titolo": "Note su RG 466/2023 citato in memoria"},
            ]),
        }
        GlobalSearchIndexer(repo, adapters=[FascicoliSearchAdapter()]).reindex_all(context)
        results = repo.search(tenant_id="studio", query="466/2023", limit=5)
        assert [r.entity_id for r in results][:2] == ["F1", "F2"]
    finally:
        repo.close()


def test_filtro_entity_type(tmp_path):
    repo = GlobalSearchRepository(tmp_path / "search.db")
    try:
        context = {
            "tenant_id": "studio",
            "fascicoli": FakeManager([{"id": "F1", "numero_rg": "12/2026", "titolo": "Mario Rossi"}]),
            "clienti": FakeManager([{"id": "C1", "nome": "Mario", "cognome": "Rossi"}]),
        }
        GlobalSearchIndexer(repo, adapters=[FascicoliSearchAdapter(), ClientiSearchAdapter()]).reindex_all(context)
        results = repo.search(tenant_id="studio", query="Mario Rossi", entity_types=["cliente"], limit=10)
        assert len(results) == 1
        assert results[0].entity_type == "cliente"
    finally:
        repo.close()


def test_ricerca_su_mille_record_sintetici(tmp_path):
    repo = GlobalSearchRepository(tmp_path / "search.db")
    try:
        records = [
            {"id": f"F{i}", "numero_rg": f"{i}/2026", "titolo": f"Fascicolo sintetico {i}"}
            for i in range(1000)
        ]
        records.append({"id": "TARGET", "numero_rg": "466/2023", "titolo": "Fascicolo Alessi contro Zurich"})
        context = {"tenant_id": "studio", "fascicoli": FakeManager(records)}
        report = GlobalSearchIndexer(repo, adapters=[FascicoliSearchAdapter()]).reindex_all(context)
        assert report.indexed == 1001
        results = repo.search(tenant_id="studio", query="Alessi Zurich", limit=3)
        assert results
        assert results[0].entity_id == "TARGET"
    finally:
        repo.close()
