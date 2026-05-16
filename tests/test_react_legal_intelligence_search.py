from types import SimpleNamespace

from web.services import react_legal_intelligence_bridge as bridge


class _Rows:
    def tutti(self, *args, **kwargs):
        return []

    def tutte(self):
        return []


class _Manager:
    def build_dashboard_snapshot(self, **kwargs):
        return {"headline": {}, "source_rows": []}

    def mediazione_registry_snapshot(self, **kwargs):
        return {"rows": [], "total_rows": 0, "filtered_rows": 0, "mediazione_registry": {}}


class _Repository:
    def __init__(self, *, news=None, search_rows=None):
        self.news = list(news or [])
        self.search_rows = list(search_rows or [])
        self.search_queries = []

    def list_news(self, **kwargs):
        return self.news

    def list_matters(self):
        return []

    def search_lex_sources(self, query, *, limit=12):
        self.search_queries.append((query, limit))
        return self.search_rows


class _Pipeline:
    def __init__(self, repository):
        self.repository = repository

    def dashboard_snapshot(self):
        return {"headline": {}, "sources": []}


def _payload(repository, *, page="ricerca-legale", query=None):
    pipeline = _Pipeline(repository)
    return bridge.build_react_legal_intelligence_payload(
        get_legal_intelligence=lambda: _Manager(),
        get_legal_update_pipeline=lambda: pipeline,
        get_fascicoli=lambda: _Rows(),
        get_clienti=lambda: _Rows(),
        get_agenda=lambda: _Rows(),
        get_scadenziario=lambda: _Rows(),
        page=page,
        query=query or {},
    )


def test_ricerca_legale_interroga_repository_e_mantiene_estratti(monkeypatch):
    def _unexpected_public_search(*args, **kwargs):
        raise AssertionError("la ricerca web non serve quando l'archivio interno ha fonti ufficiali sufficienti")

    monkeypatch.setattr(bridge, "_run_public_legal_research", _unexpected_public_search)
    long_excerpt = (
        "Estratto ufficiale completo sul credito di imposta per investimenti produttivi, "
        "con pubblicazione, fonte primaria e contenuto sufficiente per mostrare il contesto."
    )
    repository = _Repository(
        search_rows=[
            {
                "type": "normativa",
                "id": "normativa:1",
                "title": "Decreto credito imposta investimenti",
                "excerpt": long_excerpt,
                "authority": "Gazzetta Ufficiale",
                "official_url": "https://www.gazzettaufficiale.it/eli/id/2026/03/27/26G00038/sg",
                "published_at": "2026-03-27",
                "verified_reference": True,
            },
            {
                "type": "prassi",
                "id": "prassi:1",
                "title": "Circolare credito imposta investimenti",
                "excerpt": long_excerpt,
                "authority": "Agenzia delle Entrate",
                "official_url": "https://www.agenziaentrate.gov.it/portale/",
                "published_at": "2026-03-28",
                "verified_reference": True,
            },
        ]
    )

    payload = _payload(repository, query={"q": "credito imposta investimenti"})

    assert repository.search_queries == [("credito imposta investimenti", 12)]
    assert payload["contracts"]["external_fetch"] is False
    assert [record["title"] for record in payload["records"][:2]] == [
        "Decreto credito imposta investimenti",
        "Circolare credito imposta investimenti",
    ]
    assert all(record["subtitle"] for record in payload["records"][:2])
    assert all(record["sourceExcerpt"] for record in payload["records"][:2])
    assert all(record["sourceContext"] for record in payload["records"][:2])
    assert all(record["practicalUse"] for record in payload["records"][:2])
    assert all(record["reliabilityNote"] for record in payload["records"][:2])


def test_ricerca_legale_attiva_fonti_ufficiali_quando_archivio_non_basta(monkeypatch):
    monkeypatch.setattr(
        bridge,
        "_rewrite_query_for_legal_research",
        lambda query: SimpleNamespace(
            original_query=query,
            public_research_query=query,
            can_use_ldr=True,
            local_deep_research_query=query,
        ),
    )

    def _public_search(rewritten, **kwargs):
        assert rewritten.can_use_ldr is False
        return SimpleNamespace(
            warnings=[],
            sources=[
                SimpleNamespace(
                    id="pst-mediazione",
                    title="Registro organismi di mediazione",
                    source_name="Portale Servizi Telematici",
                    source_type="web_ufficiale",
                    official=True,
                    url="https://pst.giustizia.it/PST/it/servizi.page",
                    date="2026-05-11",
                    excerpt=(
                        "Fonte ufficiale PST sul registro degli organismi di mediazione, "
                        "con contenuto utile alla verifica del ripristino dei servizi."
                    ),
                )
            ],
        )

    monkeypatch.setattr(bridge, "_run_public_legal_research", _public_search)
    repository = _Repository()

    payload = _payload(repository, query={"q": "usura bancaria tasso soglia"})

    assert repository.search_queries == [("usura bancaria tasso soglia", 12)]
    assert payload["contracts"]["external_fetch"] is True
    assert any(record["title"] == "Registro organismi di mediazione" for record in payload["records"])
    assert any(record["sourceKind"] == "fonte ufficiale" for record in payload["records"])


def test_news_pst_mediazione_ripristinata_presente_in_news_e_ricerca():
    repository = _Repository()

    news_payload = _payload(repository, page="news")
    search_payload = _payload(repository, page="ricerca-legale")

    for payload in (news_payload, search_payload):
        pst_record = next(
            record for record in payload["records"]
            if record["id"] == "pst-nws4865-ripristino-mediazione"
        )
        assert pst_record["date"] == "2026-05-11"
        assert pst_record["registryNumber"] == "NWS4865"
        assert "22/04/2026" in pst_record["subtitle"]
        assert pst_record["sourceHref"] == bridge._PST_MEDIAZIONE_RECOVERY_URL


def test_mediazione_espone_accessi_ufficiali_ripristinati():
    repository = _Repository()

    mediazione_payload = _payload(repository, page="mediazione")
    search_payload = _payload(repository, page="ricerca-legale", query={"q": "elenco formatori mediazione"})

    records_by_id = {record["id"]: record for record in mediazione_payload["records"]}
    expected_links = {
        "mediazione-registro-organismi": "https://mediazione.giustizia.it/ROM/ALBOORGANISMIMEDIAZIONE.ASPX",
        "mediazione-elenco-enti": "https://mediazione.giustizia.it/ROM/AlboEntiFormazione.aspx",
        "mediazione-elenco-formatori": "https://mediazione.giustizia.it/ROM/AlboFormatori.aspx",
    }
    for record_id, official_url in expected_links.items():
        record = records_by_id[record_id]
        assert record["sourceKind"] == "fonte ufficiale"
        assert record["sourceHref"] == official_url
        assert record["date"] == "22/04/2026"
        assert record["approvalLabel"] == "ripristinato"
        assert record["evidenceType"] == "accesso ufficiale"
        assert record["sourceContext"]
        assert "mediazione" in record["practicalUse"].lower()

    assert any(
        record["id"] == "mediazione-elenco-formatori"
        for record in search_payload["records"]
    )
