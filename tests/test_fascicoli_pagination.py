from __future__ import annotations

from pathlib import Path

from datetime import date

from pct.agenda import TipoAppuntamento
from pct.fascicoli import StatoFascicolo, TipoAttivita, TipoDocumento, TipoFascicolo
from pct.scadenziario import TipoTermine
from tests.test_applicazioni import _crea_operatore, _login
from tests.test_react_shell import _app
from web.helpers import get_agenda, get_fascicoli, get_scadenziario


def _seed_fascicoli(app, total: int = 31):
    created = []
    with app.app_context():
        fascicoli = get_fascicoli()
        for index in range(total):
            tipo = TipoFascicolo.PENALE if index % 3 == 0 else TipoFascicolo.CIVILE
            fascicolo = fascicoli.nuovo(
                f"Pratica paginata {index:02d}",
                tipo,
                nome_cliente=f"Cliente {index:02d}",
                tribunale="Tribunale di Milano" if index % 2 == 0 else "TAR Lombardia",
                numero_rg=f"{1000 + index}",
                anno_rg=2026,
            )
            if index % 5 == 0:
                fascicoli.cambia_stato(fascicolo.id, StatoFascicolo.DEFINITO, avvocato="Tester")
            created.append(fascicolo)
    return created


def test_fascicoli_api_pagina_server_side_massimo_page_size(tmp_path):
    app = _app(tmp_path)
    _seed_fascicoli(app, 31)

    with app.test_client() as client:
        default_response = client.get("/api/v1/ui/fascicoli?page=1", headers={"X-API-Key": "react-test-key"})
        response = client.get("/api/v1/ui/fascicoli?page=1&page_size=25", headers={"X-API-Key": "react-test-key"})

    default_payload = default_response.get_json()
    payload = response.get_json()
    assert default_response.status_code == 200
    assert len(default_payload["items"]) == 5
    assert default_payload["pagination"] == {"page": 1, "pageSize": 5, "total": 31, "pages": 7}
    assert response.status_code == 200
    assert len(payload["items"]) == 25
    assert payload["pagination"] == {"page": 1, "pageSize": 25, "total": 31, "pages": 2}
    assert payload["contracts"]["mock_fallback"] is False


def test_fascicoli_api_filtri_q_tipo_stato_e_tribunale(tmp_path):
    app = _app(tmp_path)
    _seed_fascicoli(app, 18)

    with app.test_client() as client:
        by_query = client.get("/api/v1/ui/fascicoli?q=paginata%2007&page_size=25", headers={"X-API-Key": "react-test-key"}).get_json()
        by_query_client = client.get("/api/v1/ui/fascicoli?q=Cliente%2007&page_size=25", headers={"X-API-Key": "react-test-key"}).get_json()
        by_query_rg = client.get("/api/v1/ui/fascicoli?q=1017&page_size=25", headers={"X-API-Key": "react-test-key"}).get_json()
        by_client = client.get("/api/v1/ui/fascicoli?client=Cliente%2007&page_size=25", headers={"X-API-Key": "react-test-key"}).get_json()
        by_rg = client.get("/api/v1/ui/fascicoli?rg=1017&page_size=25", headers={"X-API-Key": "react-test-key"}).get_json()
        by_type = client.get("/api/v1/ui/fascicoli?type=penale&page_size=25", headers={"X-API-Key": "react-test-key"}).get_json()
        by_status = client.get("/api/v1/ui/fascicoli?status=da_archiviare&page_size=25", headers={"X-API-Key": "react-test-key"}).get_json()
        by_court = client.get("/api/v1/ui/fascicoli?court=TAR&page_size=25", headers={"X-API-Key": "react-test-key"}).get_json()
        combined = client.get("/api/v1/ui/fascicoli?client=Cliente%2012&rg=1012&type=penale&status=aperto&court=Milano&page_size=25", headers={"X-API-Key": "react-test-key"}).get_json()

    assert [item["title"] for item in by_query["items"]] == ["Pratica paginata 07"]
    assert [item["client"] for item in by_query_client["items"]] == ["Cliente 07"]
    assert [item["rg"] for item in by_query_rg["items"]] == ["RG 1017/2026"]
    assert [item["client"] for item in by_client["items"]] == ["Cliente 07"]
    assert [item["rg"] for item in by_rg["items"]] == ["RG 1017/2026"]
    assert by_type["pagination"]["total"] == 6
    assert all(item["type"] == "penale" for item in by_type["items"])
    assert by_status["pagination"]["total"] == 4
    assert all(item["status"] == "da_archiviare" for item in by_status["items"])
    assert all("TAR" in item["court"] for item in by_court["items"])
    assert [item["title"] for item in combined["items"]] == ["Pratica paginata 12"]


def test_fascicoli_api_sort_rg_decrescente_per_anno_e_numero(tmp_path):
    app = _app(tmp_path)
    with app.app_context():
        fascicoli = get_fascicoli()
        fascicoli.nuovo("RG basso anno nuovo", TipoFascicolo.CIVILE, numero_rg="1", anno_rg=2026)
        fascicoli.nuovo("RG alto anno nuovo", TipoFascicolo.CIVILE, numero_rg="20", anno_rg=2026)
        fascicoli.nuovo("RG anno precedente", TipoFascicolo.CIVILE, numero_rg="99", anno_rg=2025)
        fascicoli.nuovo("RG storico", TipoFascicolo.CIVILE, numero_rg="450", anno_rg=2024)

    with app.test_client() as client:
        payload = client.get("/api/v1/ui/fascicoli?page_size=10", headers={"X-API-Key": "react-test-key"}).get_json()
        explicit = client.get("/api/v1/ui/fascicoli?sort=rg&page_size=10", headers={"X-API-Key": "react-test-key"}).get_json()

    rg_values = [item["rg"] for item in payload["items"]]
    assert rg_values == ["RG 20/2026", "RG 1/2026", "RG 99/2025", "RG 450/2024"]
    assert [item["rg"] for item in explicit["items"]] == rg_values
    assert [(item["rgYear"], item["rgNumber"]) for item in payload["items"]] == [(2026, 20), (2026, 1), (2025, 99), (2024, 450)]
    assert payload["summary"]["total"] == payload["pagination"]["total"]
    assert payload["pagination"]["pageSize"] == 10


def test_fascicoli_frontend_contratto_query_params_e_lazy_tab():
    data_source = Path("frontend/src/fascicoliData.ts").read_text(encoding="utf-8")
    page_source = Path("frontend/src/components/FascicoliPage.tsx").read_text(encoding="utf-8")
    css_source = Path("frontend/src/components/FascicoliPage.css").read_text(encoding="utf-8")

    assert "query.set('page_size', String(params.pageSize))" in data_source
    assert "query.set('client', params.client.trim())" in data_source
    assert "query.set('rg', params.rg.trim())" in data_source
    assert "query.set('alerts_only', '1')" in data_source
    assert "Contesto filtri" not in page_source
    assert "client={clientFilter}" not in page_source
    assert "rg={rgFilter}" not in page_source
    assert "setClientFilter" not in page_source
    assert "setRgFilter" not in page_source
    assert "Nome cliente" not in page_source
    assert "Numero o anno" not in page_source
    assert "Cerca numero, anno, RG, cliente, titolo..." in page_source
    assert "Elimina selezionati" in page_source
    assert "fascicoli filtrati" in page_source
    assert "filtered={filtersActive}" in page_source
    assert "getFascicoloDetailSection" in data_source
    assert "loadLazySection('regia')" in page_source
    assert "loadLazySection('relata')" in page_source
    assert "loadLazySection('audit')" in page_source
    assert "loadLazySection('lex')" in page_source
    assert "getFascicoloDetail(id).then" in page_source
    assert "getFascicoloDetail(id, { include: 'all' })" in page_source
    assert "fascicoliListCacheKey" in page_source
    assert "pageCacheRef" in page_source
    assert "pageRequestsRef" in page_source
    assert "onPagePrefetch" in page_source
    assert "Caricamento pagina {pendingPage}..." in page_source
    assert ".iu-fas-page-loading" in css_source


def test_fascicoli_route_archivio_e_dettaglio_restano_raggiungibili(tmp_path):
    app = _app(tmp_path)
    _crea_operatore(app)
    fascicolo = _seed_fascicoli(app, 1)[0]

    with app.test_client() as client:
        _login(client)
        archive = client.get("/fascicoli/archivio")
        detail = client.get(f"/fascicoli/{fascicolo.id}")

    assert archive.status_code == 200
    assert detail.status_code == 200


def test_fascicolo_dettaglio_principale_include_quadro_operativo_e_tab_lazy(tmp_path):
    app = _app(tmp_path)
    with app.app_context():
        fascicoli = get_fascicoli()
        fascicolo = fascicoli.nuovo("Dettaglio lazy", TipoFascicolo.CIVILE, numero_rg="42", anno_rg=2026)
        fascicoli.aggiungi_documento(fascicolo.id, "atto.txt", TipoDocumento.ATTO_GIUDIZIARIO, b"atto")
        fascicoli.aggiungi_attivita(fascicolo.id, TipoAttivita.UDIENZA, date.today().isoformat(), "Udienza filtro lazy")
        fascicoli.aggiungi_esito_deposito(fascicolo.id, "Comparsa", "tribunale@example.pec.it", stato="ACCETTATO_PEC")
        get_scadenziario().nuova(
            "Termine lazy",
            TipoTermine.DEPOSITO_MEMORIA,
            date.today().isoformat(),
            id_fascicolo=fascicolo.id,
        )
    headers = {"X-API-Key": "react-test-key"}

    with app.test_client() as client:
        main = client.get(f"/api/v1/ui/fascicoli/{fascicolo.id}", headers=headers).get_json()
        documenti = client.get(f"/api/v1/ui/fascicoli/{fascicolo.id}/documenti", headers=headers).get_json()
        attivita = client.get(f"/api/v1/ui/fascicoli/{fascicolo.id}/attivita", headers=headers).get_json()
        scadenze = client.get(f"/api/v1/ui/fascicoli/{fascicolo.id}/scadenze", headers=headers).get_json()
        depositi = client.get(f"/api/v1/ui/fascicoli/{fascicolo.id}/depositi", headers=headers).get_json()
        regia = client.get(f"/api/v1/ui/fascicoli/{fascicolo.id}/regia", headers=headers).get_json()
        relata = client.get(f"/api/v1/ui/fascicoli/{fascicolo.id}/relata", headers=headers).get_json()
        audit = client.get(f"/api/v1/ui/fascicoli/{fascicolo.id}/audit", headers=headers).get_json()
        lex = client.get(f"/api/v1/ui/fascicoli/{fascicolo.id}/lex", headers=headers).get_json()

    assert main["documents"] == []
    assert main["activities"] == []
    assert main["deadlines"] == []
    assert main["deposits"] == []
    assert main["regia"]["page_state"] == "lazy_non_caricata"
    assert main["auditTrail"]["status"] == "lazy_non_caricato"
    assert main["quickCounts"]["documenti"] == 1
    assert main["quickCounts"]["attivita"] >= 1
    assert main["quickCounts"]["udienze_scadenze"] >= 1
    assert main["quickCounts"]["comunicazioni"] == 1
    assert len(documenti["documents"]) == 1
    assert any(item["title"] == "Udienza filtro lazy" for item in attivita["activities"])
    assert len(scadenze["deadlines"]) == 1
    assert len(depositi["deposits"]) == 1
    assert regia["mock_fallback"] is False
    assert "notificationRelata" in relata
    assert audit["auditTrail"]["status"] != "lazy_non_caricato"
    assert lex["lex_indexing"]["total_documents"] == 1


def test_fascicolo_dettaglio_collega_agenda_importata_da_source_external_id(tmp_path):
    app = _app(tmp_path)
    with app.app_context():
        fascicoli = get_fascicoli()
        fascicolo = fascicoli.nuovo("Import QuickOrganizer", TipoFascicolo.CIVILE, numero_rg="", anno_rg=0)
        fascicolo = fascicoli.aggiorna(
            fascicolo.id,
            source="IMPORT_PRATICHE",
            source_external_id="quickorganizer:101",
            source_snapshot={
                "portale": "Import pratiche",
                "external_id": "quickorganizer:101",
                "counts": {"documenti": 2, "eventi": 1, "udienze": 1},
            },
            events_sync_enabled=True,
        )
        get_agenda().aggiungi(
            "Udienza importata Studio Telematico",
            TipoAppuntamento.UDIENZA,
            "2026-09-10T09:30:00",
            luogo="Tribunale di Milano",
            allow_overlap=True,
            cliente="Rossi Mario",
            procedimento="quickorganizer:101",
            external_provider="import_pratiche",
            external_source_url="quickorganizer:101",
            external_profile_id=f"fascicolo:{fascicolo.id}",
            external_uid="quickorganizer:agenda:99",
        )

    headers = {"X-API-Key": "react-test-key"}
    with app.test_client() as client:
        main = client.get(f"/api/v1/ui/fascicoli/{fascicolo.id}", headers=headers).get_json()
        scadenze = client.get(f"/api/v1/ui/fascicoli/{fascicolo.id}/scadenze", headers=headers).get_json()

    assert main["quickCounts"]["udienze_scadenze"] == 1
    assert main["fascicolo"]["sourceExternalId"] == "quickorganizer:101"
    assert [item["title"] for item in scadenze["appointments"]] == ["Udienza importata Studio Telematico"]
    assert scadenze["appointments"][0]["type"] == "UDIENZA"
