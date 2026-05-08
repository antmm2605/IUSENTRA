from __future__ import annotations

from pathlib import Path

from datetime import date

from pct.fascicoli import StatoFascicolo, TipoAttivita, TipoDocumento, TipoFascicolo
from pct.scadenziario import TipoTermine
from tests.test_applicazioni import _crea_operatore, _login
from tests.test_react_shell import _app
from web.helpers import get_fascicoli, get_scadenziario


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
        response = client.get("/api/v1/ui/fascicoli?page=1&page_size=25", headers={"X-API-Key": "react-test-key"})

    payload = response.get_json()
    assert response.status_code == 200
    assert len(payload["items"]) == 25
    assert payload["pagination"] == {"page": 1, "pageSize": 25, "total": 31, "pages": 2}
    assert payload["contracts"]["mock_fallback"] is False


def test_fascicoli_api_filtri_q_tipo_stato_e_tribunale(tmp_path):
    app = _app(tmp_path)
    _seed_fascicoli(app, 18)

    with app.test_client() as client:
        by_query = client.get("/api/v1/ui/fascicoli?q=paginata%2007&page_size=25", headers={"X-API-Key": "react-test-key"}).get_json()
        by_type = client.get("/api/v1/ui/fascicoli?type=penale&page_size=25", headers={"X-API-Key": "react-test-key"}).get_json()
        by_status = client.get("/api/v1/ui/fascicoli?status=da_archiviare&page_size=25", headers={"X-API-Key": "react-test-key"}).get_json()
        by_court = client.get("/api/v1/ui/fascicoli?court=TAR&page_size=25", headers={"X-API-Key": "react-test-key"}).get_json()

    assert [item["title"] for item in by_query["items"]] == ["Pratica paginata 07"]
    assert by_type["pagination"]["total"] == 6
    assert all(item["type"] == "penale" for item in by_type["items"])
    assert by_status["pagination"]["total"] == 4
    assert all(item["status"] == "da_archiviare" for item in by_status["items"])
    assert all("TAR" in item["court"] for item in by_court["items"])


def test_fascicoli_api_sort_stabile_e_summary_coerente(tmp_path):
    app = _app(tmp_path)
    _seed_fascicoli(app, 12)

    with app.test_client() as client:
        payload = client.get("/api/v1/ui/fascicoli?sort=rg&page_size=10", headers={"X-API-Key": "react-test-key"}).get_json()

    rg_values = [item["rg"] for item in payload["items"]]
    assert rg_values == sorted(rg_values)
    assert payload["summary"]["total"] == payload["pagination"]["total"]
    assert payload["pagination"]["pageSize"] == 10


def test_fascicoli_frontend_contratto_query_params_e_lazy_tab():
    data_source = Path("frontend/src/fascicoliData.ts").read_text(encoding="utf-8")
    page_source = Path("frontend/src/components/FascicoliPage.tsx").read_text(encoding="utf-8")

    assert "query.set('page_size', String(params.pageSize))" in data_source
    assert "query.set('alerts_only', '1')" in data_source
    assert "getFascicoloDetailSection" in data_source
    assert "loadLazySection('regia')" in page_source
    assert "getFascicoloDetail(id).then" in page_source
    assert "getFascicoloDetail(id, { include: 'all' })" in page_source


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

    assert len(main["documents"]) == 1
    assert any(item["title"] == "Udienza filtro lazy" for item in main["activities"])
    assert len(main["deadlines"]) == 1
    assert len(main["deposits"]) == 1
    assert main["regia"]["page_state"] == "lazy_non_caricata"
    assert main["quickCounts"]["documenti"] == 1
    assert main["quickCounts"]["attivita"] >= 1
    assert main["quickCounts"]["udienze_scadenze"] >= 1
    assert main["quickCounts"]["comunicazioni"] == 1
    assert len(documenti["documents"]) == 1
    assert any(item["title"] == "Udienza filtro lazy" for item in attivita["activities"])
    assert len(scadenze["deadlines"]) == 1
    assert len(depositi["deposits"]) == 1
    assert regia["mock_fallback"] is False
