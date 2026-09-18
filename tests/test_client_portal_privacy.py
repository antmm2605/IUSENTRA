"""Il cliente legge l'informativa prima di accettarla, e la prova lo dimostra.

Il pannello mostrava la sola chiave del consenso e un pulsante «Accetta»: un
consenso prestato senza poter leggere non è informato. L'art. 7 § 1 GDPR
chiede al titolare di dimostrare che il consenso è stato prestato, e gli
artt. 13-14 impongono che l'informativa sia resa prima.
"""

from __future__ import annotations

import json
from pathlib import Path

from tests.test_applicazioni import _crea_operatore, _login
from tests.test_client_portal_api import _app, _create_invite, _seed_cliente_fascicolo
from web.services.client_portal_privacy_testi import (
    CHIAVE_INFORMATIVA,
    VERSIONE_INFORMATIVA,
    informativa_payload,
)
from web.services.client_portal_privacy_testi import testo_informativa as informativa_in_testo


def test_l_informativa_dichiara_titolare_finalita_basi_e_diritti():
    payload = informativa_payload()
    intestazioni = [sezione["heading"] for sezione in payload["sections"]]
    testo = informativa_in_testo()

    assert payload["key"] == CHIAVE_INFORMATIVA
    assert payload["version"] == VERSIONE_INFORMATIVA
    # Le sezioni che l'art. 13 GDPR impone di rendere all'interessato.
    assert "Chi tratta i suoi dati" in intestazioni
    assert "Quali dati e perché" in intestazioni
    assert "Su quale base giuridica" in intestazioni
    assert "Chi può vederli" in intestazioni
    assert "Dove restano e per quanto" in intestazioni
    assert "Che cosa può chiedere" in intestazioni
    # Il rifiuto non può pregiudicare l'incarico, e va detto.
    assert "Che cosa succede se non acconsente" in intestazioni
    assert "Garante" in testo
    assert "revocarlo" in testo or "revocare" in testo
    assert VERSIONE_INFORMATIVA in testo


def test_il_portale_manda_al_cliente_il_testo_da_leggere(tmp_path: Path):
    app = _app(tmp_path)
    _crea_operatore(app)
    cliente, fascicolo = _seed_cliente_fascicolo(app)
    with app.test_client() as client:
        _login(client)
        token, _ = _create_invite(client, cliente.id, fascicolo.id)
        client.post(f"/api/v1/ui/client-portal/public/invites/{token}/accept", json={})
        dashboard = client.get(
            "/api/v1/ui/client-portal/public/dashboard",
            headers={"X-Client-Portal-Token": token},
        ).get_json()

    informativa = dashboard["privacyNotice"]
    assert informativa["key"] == CHIAVE_INFORMATIVA
    assert len(informativa["sections"]) >= 7
    assert informativa["declaration"]
    # Il consenso da accettare esiste e usa la stessa chiave dell'informativa.
    assert any(voce["consent_key"] == CHIAVE_INFORMATIVA for voce in dashboard["consents"])


def test_l_accettazione_conserva_testo_e_versione_del_server(tmp_path: Path):
    """La prova registra ciò che l'interessato aveva davanti, non ciò che dice il browser."""
    app = _app(tmp_path)
    _crea_operatore(app)
    cliente, fascicolo = _seed_cliente_fascicolo(app)
    with app.test_client() as client:
        _login(client)
        token, _ = _create_invite(client, cliente.id, fascicolo.id)
        client.post(f"/api/v1/ui/client-portal/public/invites/{token}/accept", json={})
        risposta = client.post(
            "/api/v1/ui/client-portal/public/consents",
            json={"key": CHIAVE_INFORMATIVA, "accepted": True, "version": "versione-inventata-dal-client"},
            headers={"X-Client-Portal-Token": token},
        ).get_json()

    voce = risposta["item"]
    prova = voce.get("payload") or json.loads(voce.get("payload_json") or "{}")

    assert voce["accepted"] == 1
    assert voce["accepted_at"]
    # La versione è quella del server: il client non può riscriverla.
    assert voce["version"] == VERSIONE_INFORMATIVA
    assert prova["versione_informativa"] == VERSIONE_INFORMATIVA
    assert prova["testo_informativa"] == informativa_in_testo()
    assert prova["dichiarazione"]
