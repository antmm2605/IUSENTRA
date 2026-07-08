from __future__ import annotations

from pathlib import Path

from datetime import date

from pct.agenda import TipoAppuntamento
from pct.fascicoli import StatoFascicolo, TipoAttivita, TipoDocumento, TipoFascicolo
from pct.scadenziario import TipoTermine
from tests.test_applicazioni import _crea_operatore, _login
from tests.test_react_shell import _app
from web.blueprints import api_v1_react
from web.helpers import get_agenda, get_fascicoli, get_fatturazione, get_scadenziario
from web.services import react_fascicoli_bridge


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


def test_fascicoli_api_cache_ttl_riusa_payload_identico(tmp_path, monkeypatch):
    app = _app(tmp_path)
    _seed_fascicoli(app, 61)
    api_v1_react._clear_fascicoli_list_payload_cache()
    calls = {"count": 0}
    original = api_v1_react.build_react_fascicoli_payload

    def counted_payload(**kwargs):
        calls["count"] += 1
        return original(**kwargs)

    monkeypatch.setattr(api_v1_react, "build_react_fascicoli_payload", counted_payload)

    with app.test_client() as client:
        first = client.get("/api/v1/ui/fascicoli?page=2&page_size=25&sort=rg&view=economica", headers={"X-API-Key": "react-test-key"})
        second = client.get("/api/v1/ui/fascicoli?page=2&pageSize=25&sort=rg&vista=economica", headers={"X-API-Key": "react-test-key"})
        other_page = client.get("/api/v1/ui/fascicoli?page=3&page_size=25&sort=rg&view=economica", headers={"X-API-Key": "react-test-key"})

    assert first.status_code == 200
    assert second.status_code == 200
    assert other_page.status_code == 200
    assert calls["count"] == 2
    assert first.get_data() == second.get_data()
    assert first.get_json()["pagination"]["page"] == 2
    assert other_page.get_json()["pagination"]["page"] == 3
    api_v1_react._clear_fascicoli_list_payload_cache()


def test_fascicoli_api_cache_base_riusa_lista_tra_pagine(tmp_path, monkeypatch):
    app = _app(tmp_path)
    _seed_fascicoli(app, 61)
    api_v1_react._clear_fascicoli_list_payload_cache()
    calls = {"count": 0}
    original = react_fascicoli_bridge._item_light

    def counted_item(*args, **kwargs):
        calls["count"] += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(react_fascicoli_bridge, "_item_light", counted_item)

    with app.test_client() as client:
        first = client.get("/api/v1/ui/fascicoli?page=1&page_size=25&sort=rg&view=economica", headers={"X-API-Key": "react-test-key"})
        second = client.get("/api/v1/ui/fascicoli?page=2&page_size=25&sort=rg&view=economica", headers={"X-API-Key": "react-test-key"})

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.get_json()["pagination"]["page"] == 1
    assert second.get_json()["pagination"]["page"] == 2
    assert calls["count"] == 61
    api_v1_react._clear_fascicoli_list_payload_cache()


def test_fascicoli_vista_economica_legge_dato_consolidato_senza_presidio_massivo(tmp_path, monkeypatch):
    app = _app(tmp_path)
    _seed_fascicoli(app, 31)
    api_v1_react._clear_fascicoli_list_payload_cache()

    def fail_automatic_scan(*args, **kwargs):
        raise AssertionError("La lista fascicoli non deve avviare la lettura documentale massiva.")

    monkeypatch.setattr(react_fascicoli_bridge, "_automatic_payment_sources_for_fascicolo", fail_automatic_scan)

    with app.test_client() as client:
        response = client.get(
            "/api/v1/ui/fascicoli?page=1&page_size=25&sort=rg&view=economica",
            headers={"X-API-Key": "react-test-key"},
        )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["pagination"] == {"page": 1, "pageSize": 25, "total": 31, "pages": 2}
    assert payload["items"][0]["paymentSummary"]["analysis"]["status"] in {"da_analizzare", "aggiornato", "da_rianalizzare"}


def test_presidio_economico_consolida_cu_poi_lista_legge_solo_db(tmp_path, monkeypatch):
    app = _app(tmp_path)
    api_v1_react._clear_fascicoli_list_payload_cache()
    with app.app_context():
        fascicoli = get_fascicoli()
        fascicolo = fascicoli.nuovo(
            "Alfano Giuseppe c. MIM",
            TipoFascicolo.CIVILE,
            nome_cliente="Alfano Giuseppe",
            tribunale="Tribunale di Palmi",
            numero_rg="1100",
            anno_rg=2026,
            oggetto="222050 - Retribuzione",
        )
        fascicoli.aggiungi_documento(
            fascicolo.id,
            "rt_33E000GLVE6L4BIFLARMYPA0VKIRL7DIRYT.xml",
            TipoDocumento.ATTO_GIUDIZIARIO,
            b"<xml/>",
            note="Pagamento contributo unificato PagoPA",
        )
        fascicoli.aggiorna(
            fascicolo.id,
            pagamenti={
                "contributo_unificato": {
                    "status": "da_registrare",
                    "importo": 0,
                    "documento_fonte": "Import pratiche",
                    "updated_at": "2026-07-05",
                }
            },
        )

    calls = {"count": 0}

    def fake_auto(fascicolo_arg, payments, **kwargs):
        calls["count"] += 1
        assert kwargs.get("allow_full_document_scan") is False
        return {
            "contributo_unificato": {
                "kind": "contributo_unificato",
                "label": "Contributo unificato",
                "status": "pagato",
                "previsto": True,
                "pagato": True,
                "importo": 49.0,
                "valuta": "EUR",
                "data_pagamento": "2026-05-31",
                "documento_fonte": "rt_33E000GLVE6L4BIFLARMYPA0VKIRL7DIRYT.xml",
                "origine": "Document AI / fascicolo",
                "updated_by": "IUSENTRA automatico",
                "note": "Compilato automaticamente dalla ricevuta contributo unificato presente nel fascicolo.",
            }
        }

    monkeypatch.setattr(react_fascicoli_bridge, "_automatic_payment_sources_for_fascicolo", fake_auto)
    with app.app_context():
        repo = get_fascicoli()
        original_save = repo._salva
        save_calls = {"count": 0}

        def counted_save():
            save_calls["count"] += 1
            return original_save()

        def forbidden_single_update(*args, **kwargs):
            raise AssertionError("Il presidio automatico deve salvare in batch, non con aggiorna() per ogni fascicolo.")

        monkeypatch.setattr(repo, "_salva", counted_save)
        monkeypatch.setattr(repo, "aggiorna", forbidden_single_update)
        result = react_fascicoli_bridge.run_react_fascicoli_economic_presidio(
            get_fascicoli=lambda: repo,
            get_fatturazione=get_fatturazione,
            actor="Test automatico",
            limit=1000,
        )
        saved = get_fascicoli().get(fascicolo.id)
        marker = saved.pagamenti["_presidio_documentale"]

    assert result["contributiUpdatedCount"] == 1
    assert result["documentAnalysisUpdatedCount"] == 1
    assert saved.pagamenti["contributo_unificato"]["status"] == "pagato"
    assert saved.pagamenti["contributo_unificato"]["importo"] == 49.0
    assert marker["status"] == "aggiornato"
    assert marker["fingerprint"] == react_fascicoli_bridge._document_analysis_fingerprint(saved)

    with app.app_context():
        repeat = react_fascicoli_bridge.run_react_fascicoli_economic_presidio(
            get_fascicoli=get_fascicoli,
            get_fatturazione=get_fatturazione,
            actor="Test automatico",
            limit=1000,
        )
    assert repeat["contributiUpdatedCount"] == 0
    assert repeat["documentAnalysisUpdatedCount"] == 0
    assert calls["count"] == 1

    def fail_automatic_scan(*args, **kwargs):
        raise AssertionError("La lista economica deve leggere il contributo dal DB, non dal parser.")

    monkeypatch.setattr(react_fascicoli_bridge, "_automatic_payment_sources_for_fascicolo", fail_automatic_scan)
    api_v1_react._clear_fascicoli_list_payload_cache()
    with app.test_client() as client:
        response = client.get(
            "/api/v1/ui/fascicoli?page=1&page_size=25&sort=rg&view=economica",
            headers={"X-API-Key": "react-test-key"},
        )
    payload = response.get_json()
    item = next(row for row in payload["items"] if row["id"] == fascicolo.id)
    contributo = item["paymentSummary"]["items"]["contributo_unificato"]

    assert response.status_code == 200
    assert contributo["status"] == "pagato"
    assert contributo["importo"] == 49.0
    assert contributo["importoLabel"] == "€ 49,00"
    assert item["paymentSummary"]["analysis"]["status"] == "aggiornato"

    monkeypatch.setattr(react_fascicoli_bridge, "_automatic_payment_sources_for_fascicolo", fake_auto)
    with app.app_context():
        get_fascicoli().aggiungi_documento(
            fascicolo.id,
            "Pagamento integrativo cu.xml",
            TipoDocumento.ATTO_GIUDIZIARIO,
            b"<xml/>",
            note="Nuova ricevuta contributo unificato",
        )
        changed = react_fascicoli_bridge.run_react_fascicoli_economic_presidio(
            get_fascicoli=get_fascicoli,
            get_fatturazione=get_fatturazione,
            actor="Test automatico",
            limit=1000,
        )

    assert changed["contributiUpdatedCount"] == 0
    assert changed["documentAnalysisUpdatedCount"] == 1
    assert calls["count"] == 2


def test_presidio_economico_automatico_non_scansiona_tutti_i_documenti(tmp_path, monkeypatch):
    app = _app(tmp_path)
    api_v1_react._clear_fascicoli_list_payload_cache()
    with app.app_context():
        fascicoli = get_fascicoli()
        fascicolo = fascicoli.nuovo(
            "Controllo performance presidio",
            TipoFascicolo.CIVILE,
            nome_cliente="Cliente Performance",
            tribunale="Tribunale di Palmi",
            numero_rg="1222",
            anno_rg=2026,
        )
        for index in range(8):
            fascicoli.aggiungi_documento(
                fascicolo.id,
                f"Documento generico {index}.pdf",
                TipoDocumento.ATTO_GIUDIZIARIO,
                b"contenuto generico",
                note="Documento non economico",
            )
        fascicoli.aggiorna(
            fascicolo.id,
            pagamenti={
                "contributo_unificato": {
                    "status": "da_registrare",
                    "importo": 0,
                    "documento_fonte": "Import pratiche",
                }
            },
        )

    fallback_flags: list[bool] = []

    def guarded_candidates(*args, **kwargs):
        fallback_flags.append(bool(kwargs.get("fallback_all")))
        assert kwargs.get("fallback_all") is False
        return []

    monkeypatch.setattr(react_fascicoli_bridge, "_document_candidates_for_hints", guarded_candidates)

    with app.app_context():
        repo = get_fascicoli()
        original_save = repo._salva
        save_calls = {"count": 0}

        def counted_save():
            save_calls["count"] += 1
            return original_save()

        def forbidden_single_update(*args, **kwargs):
            raise AssertionError("Il presidio automatico deve salvare in batch, non con aggiorna() per ogni fascicolo.")

        monkeypatch.setattr(repo, "_salva", counted_save)
        monkeypatch.setattr(repo, "aggiorna", forbidden_single_update)
        result = react_fascicoli_bridge.run_react_fascicoli_economic_presidio(
            get_fascicoli=lambda: repo,
            get_fatturazione=get_fatturazione,
            actor="Test automatico",
            limit=1000,
        )

    assert result["contributiCheckedCount"] == 1
    assert result["documentAnalysisUpdatedCount"] == 1
    assert fallback_flags
    assert set(fallback_flags) == {False}
    assert save_calls["count"] == 1


def test_presidio_economico_rianalizza_marker_corrente_incompleto_senza_unresolved(tmp_path, monkeypatch):
    app = _app(tmp_path)
    api_v1_react._clear_fascicoli_list_payload_cache()
    with app.app_context():
        fascicoli = get_fascicoli()
        fascicolo = fascicoli.nuovo(
            "Moscato Marco c. MIM",
            TipoFascicolo.CIVILE,
            nome_cliente="Moscato Marco",
            tribunale="Tribunale di Palmi",
            numero_rg="12",
            anno_rg=2026,
        )
        fascicoli.aggiungi_documento(
            fascicolo.id,
            "Contributo unificato Moscato.PDF",
            TipoDocumento.ATTO_GIUDIZIARIO,
            b"pdf",
            note="Contributo unificato",
        )
        saved = fascicoli.get(fascicolo.id)
        marker = react_fascicoli_bridge._build_presidio_documentale_marker(
            saved,
            actor="Import precedente",
            automatic_sources={},
        )
        fascicoli.aggiorna(
            fascicolo.id,
            pagamenti={
                "contributo_unificato": {"status": "da_registrare", "importo": 0},
                "_presidio_documentale": marker,
            },
        )

    calls = {"count": 0}

    def fake_auto(*args, **kwargs):
        calls["count"] += 1
        return {
            "contributo_unificato": {
                "kind": "contributo_unificato",
                "status": "pagato",
                "importo": 21.5,
                "data_pagamento": "2026-03-17",
                "documento_fonte": "Contributo unificato Moscato.PDF",
            }
        }

    monkeypatch.setattr(react_fascicoli_bridge, "_automatic_payment_sources_for_fascicolo", fake_auto)
    with app.app_context():
        result = react_fascicoli_bridge.run_react_fascicoli_economic_presidio(
            get_fascicoli=get_fascicoli,
            get_fatturazione=get_fatturazione,
            actor="Test automatico",
            limit=1000,
        )
        saved = get_fascicoli().get(fascicolo.id)

    assert calls["count"] == 1
    assert result["contributiUpdatedCount"] == 1
    assert saved.pagamenti["contributo_unificato"]["status"] == "pagato"
    assert saved.pagamenti["contributo_unificato"]["importo"] == 21.5


def test_presidio_economico_non_rilegge_marker_corrente_con_unresolved(tmp_path, monkeypatch):
    app = _app(tmp_path)
    with app.app_context():
        fascicoli = get_fascicoli()
        fascicolo = fascicoli.nuovo(
            "Nessuna ricevuta c. MIM",
            TipoFascicolo.CIVILE,
            nome_cliente="Cliente senza ricevuta",
            tribunale="Tribunale di Palmi",
            numero_rg="1300",
            anno_rg=2026,
        )
        saved = fascicoli.get(fascicolo.id)
        marker = react_fascicoli_bridge._build_presidio_documentale_marker(
            saved,
            actor="Test automatico",
            automatic_sources={},
        )
        marker["unresolvedKinds"] = ["contributo_unificato"]
        fascicoli.aggiorna(
            fascicolo.id,
            pagamenti={
                "contributo_unificato": {"status": "da_registrare", "importo": 0},
                "_presidio_documentale": marker,
            },
        )

    def fail_auto(*args, **kwargs):
        raise AssertionError("Un marker corrente con unresolvedKinds non deve rilanciare il presidio.")

    monkeypatch.setattr(react_fascicoli_bridge, "_automatic_payment_sources_for_fascicolo", fail_auto)
    with app.app_context():
        result = react_fascicoli_bridge.run_react_fascicoli_economic_presidio(
            get_fascicoli=get_fascicoli,
            get_fatturazione=get_fatturazione,
            actor="Test automatico",
            limit=1000,
        )

    assert result["contributiUpdatedCount"] == 0
    assert result["documentAnalysisUpdatedCount"] == 0
    with app.app_context():
        summary = react_fascicoli_bridge.payment_summary_for_fascicolo_fast(get_fascicoli().get(fascicolo.id))
    assert summary["analysis"]["status"] == "aggiornato_con_rilievi"
    assert summary["analysis"]["unresolvedKinds"] == ["contributo_unificato"]
    assert summary["items"]["contributo_unificato"]["importoLabel"] == "Non trovato"
    assert "ricevuta" in summary["items"]["contributo_unificato"]["note"]


def test_presidio_economico_definisce_fascicolo_con_liquidazione_pagata_e_parcella_da_emettere(tmp_path, monkeypatch):
    app = _app(tmp_path)
    with app.app_context():
        fascicoli = get_fascicoli()
        fascicolo = fascicoli.nuovo(
            "Sentenza economica c. MIM",
            TipoFascicolo.CIVILE,
            nome_cliente="Cliente definito",
            tribunale="Tribunale di Palmi",
            numero_rg="1400",
            anno_rg=2026,
        )
        fascicoli.cambia_stato(fascicolo.id, StatoFascicolo.IN_CORSO, avvocato="Tester")
        fascicoli.aggiorna(
            fascicolo.id,
            pagamenti={
                "contributo_unificato": {"status": "non_previsto", "previsto": False},
                "liquidazione_giudice": {"status": "pagato", "importo": 258.0, "data_pagamento": "2026-06-15"},
                "parcella": {"status": "da_emettere", "importo": 376.46},
            },
        )

    monkeypatch.setattr(react_fascicoli_bridge, "_automatic_payment_sources_for_fascicolo", lambda *args, **kwargs: {})
    with app.app_context():
        result = react_fascicoli_bridge.run_react_fascicoli_economic_presidio(
            get_fascicoli=get_fascicoli,
            get_fatturazione=get_fatturazione,
            actor="Test automatico",
            limit=1000,
        )
        saved = get_fascicoli().get(fascicolo.id)

    assert result["statusDefinedUpdatedCount"] == 1
    assert saved.stato == StatoFascicolo.DEFINITO
    assert saved.data_chiusura


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


def test_fascicoli_api_filtra_rg_mancanti_da_card(tmp_path):
    app = _app(tmp_path)
    with app.app_context():
        fascicoli = get_fascicoli()
        fascicoli.nuovo("Senza RG c. MIM", TipoFascicolo.CIVILE, nome_cliente="Cliente Senza RG")
        fascicoli.nuovo("Completo c. MIM", TipoFascicolo.CIVILE, nome_cliente="Cliente Completo", numero_rg="778", anno_rg=2026)

    with app.test_client() as client:
        missing_response = client.get("/api/v1/ui/fascicoli?missing_rg_only=1&page_size=25", headers={"X-API-Key": "react-test-key"})
        duplicate_response = client.get("/api/v1/ui/fascicoli?duplicates_only=1&page_size=25", headers={"X-API-Key": "react-test-key"})
        missing = missing_response.get_json()
        duplicates = duplicate_response.get_json()

    assert missing_response.status_code == 200
    assert duplicate_response.status_code == 200
    assert missing["pagination"]["total"] == 1
    assert missing["summary"]["missingRg"] == 1
    assert [item["client"] for item in missing["items"]] == ["Cliente Senza RG"]
    assert "duplicatePracticeRows" in duplicates["summary"]


def test_fascicoli_parcelle_card_filtra_solo_lavoro_reale():
    base_item = {
        "title": "Fascicolo",
        "client": "Cliente",
        "ref": "RG 1/2026",
        "rg": "RG 1/2026",
        "type": "civile",
        "status": "in_corso",
        "court": "Tribunale",
        "alerts": 0,
        "unreadCommunications": 0,
        "rgMissing": False,
        "duplicateCount": 0,
    }

    generic_da_emettere = {
        **base_item,
        "paymentSummary": {
            "parcelleDaEmettere": 0,
            "proformaPresidio": {"existingDraftCount": 0},
            "items": {"parcella": {"status": "da_emettere"}},
        },
    }
    amount_to_issue = {
        **base_item,
        "paymentSummary": {
            "parcelleDaEmettere": 1,
            "proformaPresidio": {"existingDraftCount": 0},
            "items": {"parcella": {"status": "da_emettere"}},
        },
    }
    draft_to_review = {
        **base_item,
        "paymentSummary": {
            "parcelleDaEmettere": 0,
            "proformaPresidio": {"existingDraftCount": 1},
            "items": {"parcella": {"status": "da_emettere"}},
        },
    }

    filters = {"parcella": "da_emettere"}
    assert not react_fascicoli_bridge._matches_list_filters(generic_da_emettere, payment_filters=filters)
    assert react_fascicoli_bridge._matches_list_filters(amount_to_issue, payment_filters=filters)
    assert react_fascicoli_bridge._matches_list_filters(draft_to_review, payment_filters=filters)


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
    assert "query.set('missing_rg_only', '1')" in data_source
    assert "query.set('duplicates_only', '1')" in data_source
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
    assert "warmEconomicFirstPages" in page_source
    assert "[2, 3].forEach" in page_source
    assert "applyStatContext({ missingRgOnly: true })" in page_source
    assert "applyStatContext({ duplicatesOnly: true })" in page_source
    assert "syncListContextInUrl(next)" in page_source
    assert "economicPresidioRunRef.current === presidioKey" in page_source
    assert "data.summary.economicAnalysisDue" in page_source
    assert "const presidioDue = Number(data.summary.economicAnalysisDue || 0)" in page_source
    assert "data.summary.invoicesToIssue || 0) + Number(data.summary.economicAnalysisDue" not in page_source
    assert "data.generatedAt, data.summary.economicAnalysisDue" not in page_source
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
