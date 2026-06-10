from __future__ import annotations

from pct.fascicoli import StatoFascicolo, TipoFascicolo
from tests.test_react_shell import _app
from web.helpers import get_fascicoli


def _seed(app, count: int = 3):
    created = []
    with app.app_context():
        fascicoli = get_fascicoli()
        for index in range(count):
            fascicolo = fascicoli.nuovo(
                f"Pratica stato {index:02d}",
                TipoFascicolo.CIVILE,
                nome_cliente=f"Cliente stato {index:02d}",
                tribunale="Tribunale di Milano",
                numero_rg=f"{2000 + index}",
                anno_rg=2026,
            )
            created.append(fascicolo)
    return created


def test_cambio_stato_inline_da_elenco(tmp_path):
    app = _app(tmp_path)
    fascicolo = _seed(app, 1)[0]

    with app.test_client() as client:
        response = client.post(
            f"/api/v1/ui/fascicoli/{fascicolo.id}/stato",
            json={"stato": "in_corso"},
            headers={"X-API-Key": "react-test-key"},
        )
        assert response.status_code == 200
        payload = response.get_json()
        assert payload["ok"] is True
        assert payload["fascicolo"]["status"] == "in_corso"
        assert payload["fascicolo"]["tone"]

        response = client.post(
            f"/api/v1/ui/fascicoli/{fascicolo.id}/stato",
            json={"stato": "definito"},
            headers={"X-API-Key": "react-test-key"},
        )
        assert response.status_code == 200
        assert response.get_json()["fascicolo"]["status"] in {"definito", "da_archiviare"}

    with app.app_context():
        aggiornato = get_fascicoli().get(fascicolo.id)
        assert aggiornato.stato == StatoFascicolo.DEFINITO
        # il cambio stato deve restare tracciato nell'avanzamento pratica
        assert any("DEFINITO" in (av.stato_nuovo or "") for av in aggiornato.avanzamento)


def test_cambio_stato_rifiuta_valori_non_validi(tmp_path):
    app = _app(tmp_path)
    fascicolo = _seed(app, 1)[0]

    with app.test_client() as client:
        response = client.post(
            f"/api/v1/ui/fascicoli/{fascicolo.id}/stato",
            json={"stato": "da_archiviare"},
            headers={"X-API-Key": "react-test-key"},
        )
        assert response.status_code == 400

        response = client.post(
            f"/api/v1/ui/fascicoli/{fascicolo.id}/stato",
            json={"stato": "inesistente"},
            headers={"X-API-Key": "react-test-key"},
        )
        assert response.status_code == 400

        response = client.post(
            "/api/v1/ui/fascicoli/id-che-non-esiste/stato",
            json={"stato": "aperto"},
            headers={"X-API-Key": "react-test-key"},
        )
        assert response.status_code == 404


def test_filtri_per_voce_economica(tmp_path):
    app = _app(tmp_path)
    fascicoli = _seed(app, 3)

    with app.test_client() as client:
        # primo fascicolo: contributo unificato pagato
        response = client.post(
            f"/api/v1/ui/fascicoli/{fascicoli[0].id}/pagamenti/contributo_unificato",
            json={"status": "pagato", "importo": "259", "dataPagamento": "2026-06-01"},
            headers={"X-API-Key": "react-test-key"},
        )
        assert response.status_code == 200
        # secondo fascicolo: parcella pagata (lo stato di default per parcella
        # e' "da_emettere" su tutti i fascicoli, quindi serve uno stato distintivo)
        response = client.post(
            f"/api/v1/ui/fascicoli/{fascicoli[1].id}/pagamenti/parcella",
            json={"status": "pagato", "importo": "1450", "dataPagamento": "2026-06-05"},
            headers={"X-API-Key": "react-test-key"},
        )
        assert response.status_code == 200

        # filtro cu=pagato: deve restituire solo il primo
        response = client.get(
            "/api/v1/ui/fascicoli?cu=pagato",
            headers={"X-API-Key": "react-test-key"},
        )
        assert response.status_code == 200
        items = response.get_json()["items"]
        assert [item["id"] for item in items] == [fascicoli[0].id]

        # filtro parcella=pagato: deve restituire solo il secondo
        response = client.get(
            "/api/v1/ui/fascicoli?parcella=pagato",
            headers={"X-API-Key": "react-test-key"},
        )
        items = response.get_json()["items"]
        assert [item["id"] for item in items] == [fascicoli[1].id]

        # parcella=da_emettere e' il default di dominio: include i fascicoli senza
        # registrazione parcella ed esclude quello con parcella pagata
        response = client.get(
            "/api/v1/ui/fascicoli?parcella=da_emettere",
            headers={"X-API-Key": "react-test-key"},
        )
        ids = {item["id"] for item in response.get_json()["items"]}
        assert fascicoli[1].id not in ids
        assert {fascicoli[0].id, fascicoli[2].id} <= ids

        # filtro combinato senza riscontri: cu pagato E parcella pagata su fascicoli diversi
        response = client.get(
            "/api/v1/ui/fascicoli?cu=pagato&parcella=pagato",
            headers={"X-API-Key": "react-test-key"},
        )
        assert response.get_json()["items"] == []

        # valore "tutti" o vuoto: nessun filtro applicato
        response = client.get(
            "/api/v1/ui/fascicoli?cu=tutti&fondo_spese=",
            headers={"X-API-Key": "react-test-key"},
        )
        assert len(response.get_json()["items"]) == 3
